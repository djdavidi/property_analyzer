"""Deterministic PWD nonresidential stormwater scenarios with an explicit ledger.

All area inputs are unrounded square feet. Decimal arithmetic avoids float-cent
artifacts. Unsupported account treatment or unreconciled overlap blocks scenarios.
Rates, the minimum, the collection charge and the small-parcel statutory IA rule
are read from ``config/rules-pwd-2026-09.json``.

Minimum charge (one rule for baseline and every scenario): each account's SWMS
share is ``max(parcel SWMS x allocation, minimum)``. Sources: tariff 2026-09-01
section 4.3(a)(6) (minimum), 4.3(a)(8) (equal division among accounts, each also
billed the Billing & Collection charge), 4.5(b) (minimum applies after credits);
manual section 4.3.5 step 5 ("each account will be subject to the Non-residential
minimum monthly charge"); PWD stormwater billing FAQ, water.phila.gov/stormwater/
billing/, retrieved 2026-11-16 ("each water/sewer account will be assigned 25% of
the total monthly SWMS charge. If that value is less than the Minimum Charge, then
the minimum will apply."). A credit therefore can never raise a bill.
"""

from copy import deepcopy
from decimal import Decimal, ROUND_CEILING, ROUND_HALF_UP
from .rules import screen, RULE_VERSION, MANUAL_URL, TARIFF_URL, load_rule_config
from .prerequisites import baseline_vetoes

D = Decimal
MINIMUM_RULE = (
    "per_account: each account SWMS = max(allocated share, minimum); tariff 4.3(a)(6), 4.3(a)(8), "
    "4.5(b); manual 4.3.5 step 5; PWD billing FAQ"
)
UNDEVELOPED_UNKNOWN = (
    "Undeveloped status is unknown for a parcel under 5,000 sq ft GA; tariff 1.0(p) and "
    "4.3(a)(2)(i) set statutory IA at 25% (undeveloped) or 85% of GA. Both alternatives are shown; "
    "the baseline is unverified."
)
STATUS_ALTERNATIVES = (("developed", False), ("undeveloped", True))


def decimal(value, name="value"):
    if value is None or isinstance(value, bool):
        raise ValueError(f"{name} is required and must be numeric")
    try:
        result = D(str(value))
    except Exception:
        raise ValueError(f"{name} must be numeric") from None
    if not result.is_finite() or result < 0:
        raise ValueError(f"{name} must be finite and nonnegative")
    return result


def cents(value):
    return value.quantize(D(".01"), rounding=ROUND_HALF_UP)


def default_tariff(config_path=None):
    """Tariff 2026-09-01 sections 4.3(a)(2)-(6), from the versioned rule config."""
    c = load_rule_config(config_path)
    return {
        "version": c["tariff_version"],
        "effective_from": c["tariff_effective_from"],
        "verified_on": c["verified_on"],
        "verified_through": c["tariff_verified_through"],
        "ga_rate": c["ga_rate_per_500_sqft"],
        "ia_rate": c["ia_rate_per_500_sqft"],
        "unit_sqft": str(c["billing_area_increment_sqft"]),
        "minimum_swms": c["minimum_swms_monthly"],
        "collection_charge": c["collection_per_account_monthly"],
        "statutory_ia_threshold_sqft": str(c["statutory_ia_ga_threshold_sqft"]),
        "statutory_ia_fraction_developed": c["statutory_ia_fraction_developed"],
        "statutory_ia_fraction_undeveloped": c["statutory_ia_fraction_undeveloped"],
        "minimum_rule": c["minimum_charge_rule"],
        "tariff_source": TARIFF_URL,
        "manual_source": MANUAL_URL,
        "config_source": "config/rules-pwd-2026-09.json",
        "money_rounding": "ROUND_HALF_UP each component and allocated account charge",
    }


def _tariff_value(t, key):
    if key in t:
        return t[key]
    return default_tariff()[key]


def rounded_area(value, tariff=None):
    t = tariff or default_tariff()
    u = decimal(t["unit_sqft"])
    return (decimal(value) / u).to_integral_value(rounding=ROUND_CEILING) * u


def statutory_threshold(tariff=None):
    return decimal(_tariff_value(tariff or default_tariff(), "statutory_ia_threshold_sqft"))


def monthly_bill(
    ga_sqft,
    ia_sqft,
    accounts=None,
    tariff=None,
    ga_credit_sqft=0,
    ia_credit_sqft=0,
    iar_sqft=0,
    npdes_fraction=0,
    property_type="NonRes",
    undeveloped=None,
    bill_date=None,
):
    t = tariff or default_tariff()
    if property_type not in ["NonRes", "Condo", "Non-residential", "Condominium"]:
        raise ValueError("Only nonresidential and condominium billing is implemented")
    if bill_date and not (t["effective_from"] <= bill_date <= t["verified_through"]):
        raise ValueError(
            "Billing date is outside the verified tariff period; supply a verified tariff"
        )
    ga, ia = decimal(ga_sqft, "ga_sqft"), decimal(ia_sqft, "ia_sqft")
    if ia > ga:
        raise ValueError("Physical IA cannot exceed GA")
    if undeveloped is not None and not isinstance(undeveloped, bool):
        raise ValueError("undeveloped must be true, false or unknown (null)")
    if ga < statutory_threshold(t):
        # Tariff 4.3(a)(2)(i): below 5,000 sq ft GA the IA is a percentage of GA.
        if undeveloped is None:
            raise ValueError(UNDEVELOPED_UNKNOWN)
        fraction = decimal(
            _tariff_value(
                t,
                (
                    "statutory_ia_fraction_undeveloped"
                    if undeveloped
                    else "statutory_ia_fraction_developed"
                ),
            )
        )
        statutory_ia = ga * fraction
    else:
        statutory_ia = ia
    cg, ci, ir = [decimal(x) for x in [ga_credit_sqft, ia_credit_sqft, iar_sqft]]
    if cg > ga or ci + ir > statutory_ia:
        raise ValueError("Credits exceed the applicable billing area")
    npdes = decimal(npdes_fraction, "npdes_fraction")
    if npdes not in [D(0), D(".07")]:
        raise ValueError("Only 0% and 7% existing NPDES are supported")
    final_ga, final_ia = ga - cg, statutory_ia - ir - ci
    billed_ga, billed_ia = rounded_area(final_ga, t), rounded_area(final_ia, t)
    u = decimal(t["unit_sqft"])
    gross_charge = cents(billed_ga / u * decimal(t["ga_rate"]))
    impervious_charge = cents(billed_ia / u * decimal(t["ia_rate"]))
    area_charge = cents((gross_charge + impervious_charge) * (1 - npdes))
    minimum = decimal(t["minimum_swms"])
    accounts = accounts if accounts is not None else [{"allocation": 1, "discount_factor": 1}]
    if not accounts:
        raise ValueError("At least one account is required")
    allocations = [decimal(a.get("allocation"), "allocation") for a in accounts]
    if abs(sum(allocations) - 1) > D(".000000001"):
        raise ValueError("Account allocations must sum to one")
    # Normalize only tiny representation error in thirds/twelfths.
    allocations = [x / sum(allocations) for x in allocations]
    lines = []
    for i, (a, allocation) in enumerate(zip(accounts, allocations)):
        discount = decimal(a.get("discount_factor", 1), "discount_factor")
        if discount not in [D("1"), D(".75")]:
            raise ValueError("Only standard and verified 75% special rates are supported")
        if discount == D(".75") and a.get("discount_verified") is not True:
            raise ValueError("Special discount requires verified account evidence")
        share = cents(area_charge * allocation)
        allocated = max(share, minimum)
        account_total = cents((allocated + decimal(t["collection_charge"])) * discount)
        lines.append(
            {
                "account_index": i,
                "allocation": float(allocation),
                "allocated_share": float(share),
                "swms": float(allocated),
                "minimum_applied": share < minimum,
                "collection_charge": float(decimal(t["collection_charge"])),
                "discount_factor": float(discount),
                "total": float(account_total),
            }
        )
    total = sum(decimal(x["total"]) for x in lines)
    return {
        "status": "calculated",
        "monthly_total": float(total),
        "annualized_total": float(total * 12),
        "physical_ga_sqft": float(ga),
        "physical_ia_sqft": float(ia),
        "statutory_ia_sqft": float(statutory_ia),
        "final_ga_sqft": float(final_ga),
        "final_ia_sqft": float(final_ia),
        "billed_ga_sqft": float(billed_ga),
        "billed_ia_sqft": float(billed_ia),
        "ga_charge": float(gross_charge),
        "ia_charge": float(impervious_charge),
        "parcel_swms_charge": float(area_charge),
        "minimum_applied": any(x["minimum_applied"] for x in lines),
        "minimum_mode": "per_account",
        "minimum_rule": MINIMUM_RULE,
        "npdes_fraction": float(npdes),
        "accounts": lines,
        "undeveloped": undeveloped,
        "tariff_version": t["version"],
        "warning": "Annualized current-rate illustration; not a historical invoice.",
    }


def account_terms(baseline):
    """Accounts with explicit allocation status; unknown shares are never silent.

    Tariff 4.3(a)(8) and manual 2.2.6: PWD divides the parcel SWMS equally among
    accounts unless an approved Form A-1 reallocation exists. When every share is
    unknown, that tariff default is used as an explicit, labelled alternative and
    the baseline stays unverified. A partly known allocation is not completed.
    """
    raw = baseline.get("accounts")
    if raw is None:
        return None, None
    accounts = deepcopy(raw)
    unknown = [a for a in accounts if a.get("allocation") is None]
    if not unknown:
        return accounts, None
    if len(unknown) != len(accounts):
        raise ValueError(
            "Some account allocations are unknown; a partial Form A-1 allocation cannot be completed by assumption"
        )
    share = D(1) / D(len(accounts))
    for a in accounts:
        a["allocation"] = str(share)
    return accounts, {
        "status": "unknown",
        "basis": "tariff_4.3(a)(8)_equal_default",
        "note": "Account allocation unknown; the tariff 4.3(a)(8) equal-division default is shown as an unverified "
        "alternative. An approved Form A-1 reallocation (manual 2.2.6) would change per-account minimums.",
    }


def bill_terms(baseline, tariff):
    """Common monthly_bill keywords plus the allocation note for one baseline."""
    accounts, allocation = account_terms(baseline)
    common = {
        k: baseline[k] for k in ("property_type", "undeveloped", "bill_date") if k in baseline
    }
    if accounts is not None:
        common["accounts"] = accounts
    common["tariff"] = tariff
    return common, allocation


def undeveloped_unknown(baseline, *gross_areas, tariff=None):
    """True when unknown undeveloped status can change a charge (GA under 5,000)."""
    if baseline.get("undeveloped") is not None:
        return False
    threshold = statutory_threshold(tariff)
    for value in gross_areas:
        try:
            if value is not None and decimal(value) < threshold:
                return True
        except ValueError:
            continue
    return False


def billed_area_check(baseline, bill):
    """G1: compare PWD's billed areas (FinalGross/FinalImperv) with computed areas.

    A recorded value matching either the computed final (post-credit) area or the
    500 sq ft billed area is consistent. A mismatch is a visible validation flag,
    never an automatic correction.
    """
    if not bill or bill.get("monthly_total") is None:
        return {"status": "not_calculated", "rows": []}
    rows = []
    for key, final, label in (
        ("billed_ga_sqft", "final_ga_sqft", "FinalGross"),
        ("billed_ia_sqft", "final_ia_sqft", "FinalImperv"),
    ):
        recorded = baseline.get(key)
        if recorded is None:
            rows.append({"field": key, "source_field": label, "status": "not_available"})
            continue
        try:
            recorded = decimal(recorded)
        except ValueError:
            rows.append({"field": key, "source_field": label, "status": "invalid"})
            continue
        computed_billed, computed_final = decimal(bill[key]), decimal(bill[final])
        status = (
            "matches_billed_area"
            if abs(recorded - computed_billed) <= D(".5")
            else "matches_final_area" if abs(recorded - computed_final) <= D(".5") else "mismatch"
        )
        rows.append(
            {
                "field": key,
                "source_field": label,
                "status": status,
                "recorded_sqft": float(recorded),
                "computed_billed_sqft": float(computed_billed),
                "computed_final_sqft": float(computed_final),
            }
        )
    statuses = {r["status"] for r in rows}
    status = (
        "mismatch"
        if "mismatch" in statuses or "invalid" in statuses
        else "not_available" if statuses == {"not_available"} else "consistent"
    )
    out = {"status": status, "rows": rows}
    if status == "mismatch":
        out["warning"] = (
            "PWD billed area differs from the computed billed area; reconcile recorded credits, credit "
            "order, statutory IA and rounding before relying on any scenario."
        )
    return out


def _money_signature(value):
    if not isinstance(value, dict):
        return value
    bill = value.get("bill") if isinstance(value.get("bill"), dict) else {}
    return (
        value.get("status"),
        value.get("monthly_total", bill.get("monthly_total")),
        value.get("monthly_savings", value.get("gross_monthly_reduction")),
    )


def merge_status_alternatives(outputs, scenario_keys, blocked):
    """Join developed/undeveloped outputs; equal money means status is immaterial."""
    first = outputs[STATUS_ALTERNATIVES[0][0]]
    names = [name for name, _ in STATUS_ALTERNATIVES]
    keys = ("baseline",) + tuple(scenario_keys)
    if all(len({repr(_money_signature(outputs[n].get(k))) for n in names}) == 1 for k in keys):
        merged = deepcopy(first)
        merged["undeveloped_status"] = {
            "status": "unknown_immaterial",
            "note": "Undeveloped status is unknown, but both tariff 4.3(a)(2)(i) alternatives give identical charges.",
            "statutory_ia_sqft": {
                n: (outputs[n].get("baseline") or {}).get("statutory_ia_sqft") for n in names
            },
        }
        if isinstance(merged.get("baseline"), dict):
            merged["baseline"]["undeveloped"] = None
        return merged
    merged = {k: deepcopy(v) for k, v in first.items() if k not in keys}
    merged["undeveloped_status"] = {"status": "unknown_alternatives", "note": UNDEVELOPED_UNKNOWN}
    merged["baseline"] = {
        "status": "unverified_alternatives",
        "monthly_total": None,
        "annualized_total": None,
        "reasons": [UNDEVELOPED_UNKNOWN],
        "alternatives": {n: deepcopy(outputs[n].get("baseline")) for n in names},
    }
    for key in scenario_keys:
        merged[key] = {
            **blocked([UNDEVELOPED_UNKNOWN]),
            "alternatives": {n: deepcopy(outputs[n].get(key)) for n in names},
        }
    if "billed_area_check" in first:
        merged["billed_area_check"] = {
            "status": "alternatives",
            "alternatives": {n: deepcopy(outputs[n].get("billed_area_check")) for n in names},
        }
    if isinstance(merged.get("warnings"), list):
        merged["warnings"] = list(dict.fromkeys(merged["warnings"] + [UNDEVELOPED_UNKNOWN]))
    return merged


SCENARIO_KEYS = (
    "appeal_only",
    "credit_only",
    "combined",
    "documented_credit_only",
    "documented_combined",
)


def _blocked_scenario(reasons):
    return {
        "status": "blocked",
        "reasons": list(dict.fromkeys(reasons)),
        "monthly_savings": None,
        "annual_savings": None,
    }


def calculate_scenarios(baseline, measured=None, benefits=None, tariff=None):
    """Calculate appeal, credits, combined from one baseline; never add savings.

    Benefits must identify disjoint physical ledger_ids if more than one passes.
    Aggregate existing credits require an explicit spatial reconciliation before
    either measurement corrections or new benefits can be combined with them.
    Unknown undeveloped status under 5,000 sq ft GA yields explicit alternatives.
    """
    t = tariff or default_tariff()
    measured = measured or {}
    if undeveloped_unknown(baseline, baseline.get("ga_sqft"), measured.get("ga_sqft"), tariff=t):
        outputs = {
            name: _calculate_scenarios({**baseline, "undeveloped": flag}, measured, benefits, t)
            for name, flag in STATUS_ALTERNATIVES
        }
        return merge_status_alternatives(outputs, SCENARIO_KEYS, _blocked_scenario)
    return _calculate_scenarios(baseline, measured, benefits, t)


def _calculate_scenarios(baseline, measured, benefits, t):
    benefits = benefits or []
    ga = decimal(baseline.get("ga_sqft"), "ga_sqft")
    ia = decimal(baseline.get("ia_sqft"), "ia_sqft")
    cg = decimal(baseline.get("existing_ga_credit_sqft", 0))
    ci = decimal(baseline.get("existing_ia_credit_sqft", 0))
    ir = decimal(baseline.get("existing_iar_sqft", 0))
    npdes = decimal(baseline.get("npdes_fraction", 0))
    common, allocation = bill_terms(baseline, t)
    base = monthly_bill(
        ga, ia, ga_credit_sqft=cg, ia_credit_sqft=ci, iar_sqft=ir, npdes_fraction=npdes, **common
    )
    warnings = []
    if allocation:
        base["allocation_status"] = allocation
        warnings.append(allocation["note"])
    if baseline.get("published_monthly_total") is not None:
        delta = cents(decimal(base["monthly_total"]) - decimal(baseline["published_monthly_total"]))
        base["published_difference"] = float(delta)
        if delta:
            warnings.append(
                "Calculated baseline differs from public snapshot; reconcile account rounding and billing treatment."
            )
    if baseline.get("actual_bill_total") is not None:
        base["actual_bill_difference"] = float(
            cents(decimal(base["monthly_total"]) - decimal(baseline["actual_bill_total"]))
        )
    if not baseline.get("actual_bill_verified"):
        warnings.append("Actual account bill, payer, and special-rate enrollment are unverified.")
    check = billed_area_check(baseline, base)
    if check.get("warning"):
        warnings.append(check["warning"])
    screened = []
    for b in benefits:
        s = screen(b["category"], b["area_sqft"], b.get("evidence"))
        s.update({"id": b.get("id"), "basis": b.get("basis", "modeled")})
        screened.append(s)
    output = {
        "rule_version": RULE_VERSION,
        "tariff": t,
        "baseline": base,
        "screens": screened,
        "warnings": warnings,
        "billed_area_check": check,
    }
    vetoes = baseline_vetoes(baseline)

    def scenario(use_measure, use_benefits, documented_only=False):
        errors = []
        a, g = ia, ga
        if use_measure:
            if (
                measured.get("complete") is not True
                or measured.get("ia_sqft") is None
                or measured.get("ga_sqft") is None
            ):
                errors.append("Complete physical IA/GA measurements are missing.")
            else:
                a, g = decimal(measured["ia_sqft"]), decimal(measured["ga_sqft"])
            if a > g:
                errors.append("Measured IA exceeds measured GA.")
        existing = bool(cg or ci or ir)
        if (
            existing
            and (use_measure or use_benefits)
            and baseline.get("existing_credits_spatially_reconciled") is not True
        ):
            errors.append("Existing aggregate credits need spatial reconciliation before changes.")
        active = (
            [
                (b, s)
                for b, s in zip(benefits, screened)
                if s["status"] == "screen_pass"
                and (not documented_only or s["basis"] == "documented")
            ]
            if use_benefits
            else []
        )
        if active:
            errors.extend(vetoes)
        if active and g < 500:
            errors.append(
                "Credit eligibility requires at least 500 square feet of parcel gross area."
            )
        if any(b.get("evidence", {}).get("npdes") is True for b, _ in active) and not npdes:
            errors.append(
                "Benefit assumes NPDES but the baseline has no verified existing NPDES benefit."
            )
        if npdes and active:
            errors.append(
                "New credits with existing NPDES require a detailed approved area ledger; combination is unresolved."
            )
        if use_benefits and benefits and not active:
            errors.append("No benefit has complete passing prerequisites for this evidence basis.")
        used = set()
        iar_add = D(0)
        ga_add = D(0)
        ia_add = D(0)
        physical_ia_used = D(0)
        physical_open_used = D(0)
        for b, s in active:
            ids = set(map(str, b.get("ledger_ids", [])))
            if len(active) > 1 and not ids:
                errors.append("Multiple benefits require disjoint physical ledger_ids.")
            if used.intersection(ids):
                errors.append(
                    "Benefits overlap the same physical area; resolve sequencing and overlap."
                )
            used.update(ids)
            if existing and b.get("existing_overlap_reconciled") is not True:
                errors.append("New benefit overlap with existing credits is unreconciled.")
            area = decimal(s["area_sqft"])
            if s["category"] == "open_space":
                physical_open_used += area
            else:
                physical_ia_used += area
            iar_add += decimal(s["iar_sqft"])
            ga_add += decimal(s["ga_credit_sqft"])
            ia_add += decimal(s["ia_credit_sqft"])
        if physical_ia_used > a:
            errors.append("Benefit allocations exceed remaining physical IA after correction.")
        if physical_open_used > g - a:
            errors.append("Open-space allocations exceed remaining physical open space.")
        if ci + ir + ia_add + iar_add > a:
            errors.append("IA credits exceed remaining IA; corrected-away area cannot earn credit.")
        if cg + ga_add > g:
            errors.append("GA credits exceed remaining GA.")
        if errors:
            return _blocked_scenario(errors)
        try:
            bill = monthly_bill(
                g,
                a,
                ga_credit_sqft=cg + ga_add,
                ia_credit_sqft=ci + ia_add,
                iar_sqft=ir + iar_add,
                npdes_fraction=npdes,
                **common,
            )
        except ValueError as e:
            return _blocked_scenario([str(e)])
        saving = cents(decimal(base["monthly_total"]) - decimal(bill["monthly_total"]))
        bill.update(
            {
                "monthly_savings": float(saving),
                "annual_savings": float(saving * 12),
                "basis": (
                    "documented"
                    if documented_only
                    else (
                        "modeled"
                        if any(s["basis"] != "documented" for _, s in active) or use_measure
                        else "documented"
                    )
                ),
                "ledger": {
                    "existing_ga_credit_sqft": float(cg),
                    "existing_ia_credit_sqft": float(ci),
                    "existing_iar_sqft": float(ir),
                    "new_ga_credit_sqft": float(ga_add),
                    "new_ia_credit_sqft": float(ia_add),
                    "new_iar_sqft": float(iar_add),
                    "allocated_physical_ia_sqft": float(physical_ia_used),
                    "allocated_open_space_sqft": float(physical_open_used),
                },
            }
        )
        if allocation:
            bill["allocation_status"] = allocation
        return bill

    output["appeal_only"] = scenario(True, False)
    output["credit_only"] = scenario(False, True)
    output["combined"] = scenario(True, True)
    output["documented_credit_only"] = scenario(False, True, True)
    output["documented_combined"] = scenario(True, True, True)
    if (
        allocation
        and len(base["accounts"]) > 1
        and any(
            output[k].get("minimum_applied")
            for k in ("baseline",) + SCENARIO_KEYS
            if isinstance(output.get(k), dict)
        )
    ):
        output["allocation_sensitive"] = True
        warnings.append(
            "A per-account minimum applies under the assumed equal allocation; the unknown actual allocation can change the total."
        )
    return output
