"""Deterministic PWD nonresidential stormwater scenarios with an explicit ledger.

All area inputs are unrounded square feet. Decimal arithmetic avoids float-cent
artifacts. Unsupported account treatment or unreconciled overlap blocks scenarios.
Rates, the minimum, the collection charge and the small-parcel statutory IA rule
are read from ``config/rules-pwd-2026-09.json``.

Minimum charge (one rule for baseline and every scenario; final LIVE-SAVINGS fix 9):
manual section 4.3.5 step 5 read literally -- "If, after the application of all
applicable credits, a parcel's monthly total SWMS charge ... is less than the
non-residential minimum monthly charge, then each account will be subject to the
Non-residential minimum monthly charge" -- with tariff 2026-09-01 section 4.3(a)(6)
(minimum), 4.3(a)(8) (division among accounts, each billed Billing & Collection) and
4.5(b) (minimum after credits). The test is the PARCEL's SWMS; an account share below
$20.89 on a parcel at or above it is billed as is. PWD's published calculation follows
this reading on all 7 multi-account snapshot parcels that distinguish it from the
former per-account reading (2026-11-16 snapshot, 2,590 parcels; docs/RULES.md). A
credit that pushes a multi-account parcel below the minimum can therefore raise the
bill; that scenario carries a ``manual_rule_discontinuity`` note (``minimum_discontinuity``).
An account with an explicit 0 allocation (approved Form A-1 reallocation) is billed no
SWMS share and no Billing & Collection charge, as all 60 such accounts are in the snapshot.

Money rounding (fix 10): PWD rounds each money step in binary floating point, scaled
by 100 and rounded half to even (the .NET ``Math.Round(double, 2)`` default):
``pwd_cents``. It reproduces every current-year GrossCharge, ImpervCharge,
AccountSubtotal and DistributedAccountSubtotal of the 5,983 nonresidential/condominium
accounts in the snapshot; exact-decimal half-up did not (it missed 119 GA charges).

NPDES (one representation): manual section 4.3.5.2 applies the NPDES credit as area
credits ("a 7% credit towards both the IA and GA square footage"); tariff 4.5(e)
delegates the application of credits to the manual. ``monthly_bill`` therefore has
no charge-percentage discount; a recorded NPDES baseline is converted to area
credits by ``recorded_credits``, the same function the assessment ledger and the
billed-area reconciliation use.
"""

from copy import deepcopy
from decimal import Decimal, ROUND_CEILING, ROUND_HALF_UP
from .rules import MANUAL_URL, TARIFF_URL, factor, load_rule_config

D = Decimal
MINIMUM_RULE = (
    "parcel_then_each_account: when the parcel SWMS after credits is below the minimum, each "
    "account is billed the minimum SWMS; otherwise each account pays its allocated share, even "
    "below the minimum. Manual 4.3.5 step 5 (literal); tariff 4.3(a)(6), 4.3(a)(8), 4.5(b); "
    "followed by PWD's published totals on all 7 distinguishing snapshot parcels"
)
MONEY_ROUNDING = (
    "PWD binary floating point: each GA/IA charge, the parcel SWMS, each allocated share and each "
    "account total = round_half_even(double x 100) / 100 (reproduces the 2026-11-16 snapshot)"
)
MINIMUM_EACH_ACCOUNT_UNVERIFIED = (
    "The parcel SWMS is below the minimum and the parcel has several accounts: each account is "
    "billed the minimum (manual 4.3.5 step 5, literal). Tariff 4.3(a)(6) says the minimum is "
    "'billed to the Property'; the 2026-11-16 snapshot has no multi-account parcel below the "
    "minimum, so PWD's handling of this case is unverified."
)
ZERO_ALLOCATION_NOTE = (
    "An account with a 0% allocation (approved Form A-1 reallocation, manual 2.2.6) is billed no SWMS "
    "share and no Billing & Collection charge, as PWD's published calculation does for all 60 such "
    "accounts in the 2026-11-16 snapshot."
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


def pwd_cents(value):
    """Round one money step as PWD's published calculation does (fix 10).

    ``value`` is evaluated in binary floating point (pass the product/sum of
    ``float`` operands, as PWD computes it); the double is scaled by 100 and
    rounded half to even on its exact binary value (.NET ``Math.Round(double, 2)``).
    Returns an exact two-place Decimal.
    """
    return D(round(float(value) * 100.0)) / D(100)


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
        "money_rounding": MONEY_ROUNDING,
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


def billable_ia(ga_sqft, ia_sqft, undeveloped=None, tariff=None):
    """Tariff 4.3(a)(2)(i): below 5,000 sq ft GA the billed IA is a percentage of GA."""
    t = tariff or default_tariff()
    ga, ia = decimal(ga_sqft, "ga_sqft"), decimal(ia_sqft, "ia_sqft")
    if ga >= statutory_threshold(t):
        return ia
    if undeveloped is None:
        raise ValueError(UNDEVELOPED_UNKNOWN)
    key = "statutory_ia_fraction_undeveloped" if undeveloped else "statutory_ia_fraction_developed"
    return ga * decimal(_tariff_value(t, key))


class BaselineError(ValueError):
    """A recorded billing baseline that cannot be billed; the text is user-facing."""


NPDES_ALONE_NOTE = (
    "Recorded NPDES credit applied as manual 4.3.5.2 area credits: with no other GA or IA credit "
    "the property receives 7% of its IA and GA square footage (one area-based representation; "
    "no charge-percentage discount)."
)
IAR_SPLIT_UNKNOWN = (
    "IA-side credit split unknown: the public record gives one impervious credit and does not "
    "separate impervious area reductions (IAR, manual 4.3.5 step 1) from IA credit (step 2). It is "
    "treated as IA credit with IAR 0. Both reduce billed IA, so the baseline bill is unaffected; "
    "scenarios that depend on the split stay blocked."
)
IAR_SPLIT_BLOCK = (
    "The recorded impervious credit does not separate IAR from IA credit; scenarios that reconcile "
    "existing credits or compute the NPDES 7% residual (manual 4.3.5.2, uncredited IA after IAR) "
    "need the recorded IAR split."
)
NPDES_WITH_CREDITS_UNKNOWN = (
    "The billing record shows an NPDES credit together with recorded GA/IA credits. Whether those "
    "recorded credits already include the NPDES 7% area credit (manual 4.3.5.2) is unknown, so the "
    "baseline cannot be computed; supply the approved credit ledger or PWD's credit breakdown."
)


def _recorded_area(baseline, key, label):
    if key not in baseline:
        return D(0)
    value = baseline.get(key)
    if value is None:
        raise BaselineError(
            "The billing record does not state the " + label + "; the baseline cannot be computed "
            "without it (missing evidence is not zero)."
        )
    try:
        return decimal(value, key)
    except ValueError:
        raise BaselineError(
            "The recorded " + label + " is not a valid nonnegative number."
        ) from None


def recorded_npdes(baseline):
    """True/False for a recorded NPDES credit; unknown or unsupported values raise."""
    if "npdes_fraction" not in baseline:
        return False
    value = baseline.get("npdes_fraction")
    if value is None:
        raise BaselineError(
            "The billing record does not state whether an NPDES credit applies (NPDESCredit); "
            "the NPDES credit changes billed GA and IA by 7% (manual 4.3.5.2), so the baseline "
            "cannot be computed until it is known."
        )
    try:
        fraction = decimal(value, "npdes_fraction")
    except ValueError:
        raise BaselineError("The recorded NPDES credit value is not numeric.") from None
    if fraction == 0:
        return False
    if fraction == D(".07"):
        return True
    raise BaselineError("Only a 0% or 7% recorded NPDES credit is supported (tariff 4.5(d)(3)).")


def npdes_alone_credits(ga_sqft, billed_ia_sqft):
    """Manual 4.3.5.2: with no other GA/IA credit, 7% of the IA and GA square footage."""
    rate = factor("npdes_unmanaged_area_factor")
    return decimal(ga_sqft) * rate, decimal(billed_ia_sqft) * rate


def recorded_credits(baseline, ga_sqft, ia_sqft, undeveloped=None, tariff=None):
    """Recorded existing credits for a baseline bill, in one area representation.

    Shared by the assessment ledger and the billed-area reconciliation. Returns
    ``ga_credit_sqft``/``ia_credit_sqft``/``iar_sqft`` (Decimal, NPDES area credits
    included), the recorded aggregate credits, ``npdes`` and ``iar_split``
    (``recorded``/``unknown``) with labelled assumptions. Raises ``BaselineError``
    with a readable reason when the bill cannot be computed.
    """
    cg = _recorded_area(baseline, "existing_ga_credit_sqft", "existing gross-area credit")
    ci = _recorded_area(baseline, "existing_ia_credit_sqft", "existing impervious-area credit")
    assumptions = []
    if "existing_iar_sqft" in baseline and baseline.get("existing_iar_sqft") is None:
        ir, split = D(0), "unknown"
        assumptions.append(IAR_SPLIT_UNKNOWN)
    else:
        ir = _recorded_area(baseline, "existing_iar_sqft", "existing impervious area reduction")
        split = "recorded"
    npdes = recorded_npdes(baseline)
    npdes_ga = npdes_ia = D(0)
    if npdes:
        if cg or ci or ir:
            raise BaselineError(NPDES_WITH_CREDITS_UNKNOWN)
        npdes_ga, npdes_ia = npdes_alone_credits(
            ga_sqft, billable_ia(ga_sqft, ia_sqft, undeveloped, tariff)
        )
        assumptions.append(NPDES_ALONE_NOTE)
    return {
        "ga_credit_sqft": cg + npdes_ga,
        "ia_credit_sqft": ci + npdes_ia,
        "iar_sqft": ir,
        "recorded_ga_credit_sqft": cg,
        "recorded_ia_credit_sqft": ci,
        "recorded_iar_sqft": ir,
        "npdes": npdes,
        "npdes_ga_credit_sqft": npdes_ga,
        "npdes_ia_credit_sqft": npdes_ia,
        "iar_split": split,
        "assumptions": assumptions,
    }


def monthly_bill(
    ga_sqft,
    ia_sqft,
    accounts=None,
    tariff=None,
    ga_credit_sqft=0,
    ia_credit_sqft=0,
    iar_sqft=0,
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
    statutory_ia = billable_ia(ga, ia, undeveloped, t)
    cg, ci, ir = [decimal(x) for x in [ga_credit_sqft, ia_credit_sqft, iar_sqft]]
    if cg > ga or ci + ir > statutory_ia:
        raise ValueError("Credits exceed the applicable billing area")
    final_ga, final_ia = ga - cg, statutory_ia - ir - ci
    billed_ga, billed_ia = rounded_area(final_ga, t), rounded_area(final_ia, t)
    u = decimal(t["unit_sqft"])
    # Fix 10: every money step in PWD's double arithmetic and rounding (``pwd_cents``).
    gross_charge = pwd_cents(float(billed_ga / u) * float(decimal(t["ga_rate"])))
    impervious_charge = pwd_cents(float(billed_ia / u) * float(decimal(t["ia_rate"])))
    area_charge = pwd_cents(float(gross_charge) + float(impervious_charge))
    minimum = decimal(t["minimum_swms"])
    collection = decimal(t["collection_charge"])
    accounts = accounts if accounts is not None else [{"allocation": 1, "discount_factor": 1}]
    if not accounts:
        raise ValueError("At least one account is required")
    raw_allocations = [decimal(a.get("allocation"), "allocation") for a in accounts]
    if abs(sum(raw_allocations) - 1) > D(".000000001"):
        raise ValueError("Account allocations must sum to one")
    # Normalize only tiny representation error in thirds/twelfths (reported value);
    # the money product uses the recorded double, as PWD's AccountPercentOfCharge.
    allocations = [x / sum(raw_allocations) for x in raw_allocations]
    # Fix 9: manual 4.3.5 step 5 tests the PARCEL's SWMS against the minimum.
    parcel_minimum = area_charge < minimum
    billed_accounts = sum(1 for x in raw_allocations if x > 0)
    lines = []
    for i, (a, allocation, raw) in enumerate(zip(accounts, allocations, raw_allocations)):
        discount = decimal(a.get("discount_factor", 1), "discount_factor")
        if discount not in [D("1"), D(".75")]:
            raise ValueError("Only standard and verified 75% special rates are supported")
        if discount == D(".75") and a.get("discount_verified") is not True:
            raise ValueError("Special discount requires verified account evidence")
        zero = raw == 0
        share = pwd_cents(float(area_charge) * float(raw))
        allocated = D(0) if zero else (minimum if parcel_minimum else share)
        fee = D(0) if zero else collection
        account_total = pwd_cents((float(allocated) + float(fee)) * float(discount))
        lines.append(
            {
                "account_index": i,
                "allocation": float(allocation),
                "allocated_share": float(share),
                "swms": float(allocated),
                "minimum_applied": parcel_minimum and not zero,
                "below_minimum_share_billed": (not parcel_minimum and not zero and share < minimum),
                "zero_allocation": zero,
                "collection_charge": float(fee),
                "discount_factor": float(discount),
                "total": float(account_total),
            }
        )
    total = sum(decimal(x["total"]) for x in lines)
    notes = []
    if parcel_minimum and billed_accounts > 1:
        notes.append(MINIMUM_EACH_ACCOUNT_UNVERIFIED)
    if any(x["zero_allocation"] for x in lines):
        notes.append(ZERO_ALLOCATION_NOTE)
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
        "minimum_applied": parcel_minimum,
        "minimum_mode": "parcel_then_each_account",
        "minimum_rule": MINIMUM_RULE,
        "money_rounding": MONEY_ROUNDING,
        "billing_notes": notes,
        "accounts": lines,
        "undeveloped": undeveloped,
        "tariff_version": t["version"],
        "warning": "Annualized current-rate illustration; not a historical invoice.",
    }


def minimum_discontinuity(base, bill):
    """Fix 9: manual 4.3.5 step 5 read literally is discontinuous for a multi-account
    parcel. Above the minimum each account pays its share (possibly below $20.89);
    once credits push the parcel SWMS below the minimum, every account is billed the
    minimum, so a credit can raise the bill. Returns a ``manual_rule_discontinuity``
    note when that happens (scenario bill above the baseline), else None."""
    if not isinstance(base, dict) or not isinstance(bill, dict):
        return None
    if not bill.get("minimum_applied") or base.get("minimum_applied"):
        return None
    billed = [a for a in bill.get("accounts", []) if not a.get("zero_allocation")]
    if len(billed) < 2 or bill["monthly_total"] <= base["monthly_total"]:
        return None
    return {
        "kind": "manual_rule_discontinuity",
        "rule": "manual 4.3.5 step 5; tariff 4.3(a)(6)",
        "note": (
            "Manual rule discontinuity (manual 4.3.5 step 5 read literally): this credit lowers the "
            f"parcel SWMS from ${base['parcel_swms_charge']:,.2f} to ${bill['parcel_swms_charge']:,.2f}, "
            f"below the ${bill['accounts'][0]['swms'] if billed else 0:,.2f} minimum, so each of the "
            f"{len(billed)} accounts is billed the minimum and the monthly total rises from "
            f"${base['monthly_total']:,.2f} to ${bill['monthly_total']:,.2f}. PWD confirmation is needed; "
            "the customer may decline the credit or seek a Form A-1 reallocation."
        ),
        "baseline_parcel_swms": base["parcel_swms_charge"],
        "scenario_parcel_swms": bill["parcel_swms_charge"],
        "baseline_monthly_total": base["monthly_total"],
        "scenario_monthly_total": bill["monthly_total"],
        "accounts_billed_minimum": len(billed),
        "bill_higher_than_baseline": True,
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
