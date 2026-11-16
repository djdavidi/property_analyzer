"""Plain-language owner summary built from an already-safe analysis view.

It restates findings computed elsewhere; it never computes eligibility or money of
its own. Missing evidence stays missing: supported savings are $0 unless a
documented scenario passed, and every conditional figure is labelled "not
supported yet" with the single biggest assumption behind the highest one.
Withheld (outdated) figures stay withheld. New categories and fields (for
example ``existing_system_management`` or ``systems_without_recorded_credit``)
are read generically when present.
"""

from html import escape
import math

VERSION = 1
CLAIM = (
    "Plain-language summary of the evidence in this report. It is not an application, "
    "an approval, an award or a refund."
)
# Conditional money rows by where they sit in the assessment; order breaks ties.
FAMILIES = (
    ("surface", ("area_alternatives",)),
    ("mapped_system", ("catchment_scenarios", "research_drainage_scenarios")),
    ("existing_system", ("existing_system_management",)),
    ("permit", ("permit_scenarios",)),
    ("canopy", ("canopy_scenarios",)),
    ("open_space", ("open_space_curve_number",)),
    ("modeled", ("modeled", "modeled_combined", "measurement_only", "combined")),
)
DOCUMENTED = ("documented", "documented_combined")


def _number(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def usd(value, cents=True):
    if not _number(value):
        return "unknown"
    sign = "-" if value < 0 else ""
    return sign + ("${:,.2f}" if cents else "${:,.0f}").format(abs(value))


def sqft(value):
    return "unknown" if not _number(value) else f"{value:,.0f} sq ft"


def _family(path):
    for name, markers in FAMILIES:
        if any(m in path for m in markers):
            return name
    return "other"


def conditional_rows(assessment):
    """Calculated conditional annual figures outside the documented ledger."""
    rows = []

    def walk(value, path):
        if isinstance(value, dict):
            figure = next(
                (
                    value[k]
                    for k in ("gross_annual_reduction", "annual_savings")
                    if _number(value.get(k))
                ),
                None,
            )
            if figure is not None and value.get("status") == "calculated":
                rows.append({"annual": float(figure), "path": path, "row": value})
            for key, item in value.items():
                if key in ("bill", "ledger", "accounts", "baseline", "increment") or (
                    path == "economics" and key in DOCUMENTED
                ):
                    continue
                walk(item, (path + "." if path else "") + key)
        elif isinstance(value, list):
            for i, item in enumerate(value):
                # Name category entries so their rows can be told apart generically.
                tag = item.get("category") if isinstance(item, dict) else None
                walk(item, path + "." + str(i) + (f"[{tag}]" if tag else ""))

    walk(assessment or {}, "")
    for row in rows:
        row["family"] = _family(row["path"])
    return rows


def _sid(value):
    """System ID text; leading zeros of an all-digit ID dropped ('062571' is 62571)."""
    text = str(value if value is not None else "").strip()
    return str(int(text)) if text.isdigit() else text


def mapped_systems(case, assessment):
    """Public stormwater systems mapped on the parcel (PWD footprints), by system id."""
    from shapely.geometry import shape

    try:
        parcel = shape(case["parcel"])
    except (KeyError, TypeError, ValueError, AttributeError):
        parcel = None
    systems = {}
    for f in (case.get("features") or {}).get("features", []):
        p = f.get("properties") or {}
        if p.get("kind") != "system_footprint" and not p.get("gsi_system_id"):
            continue
        try:
            if parcel is not None and not shape(f["geometry"]).intersects(parcel):
                continue
        except (KeyError, TypeError, ValueError, AttributeError):
            continue
        key = _sid(p.get("gsi_system_id") or f.get("id"))
        systems.setdefault(
            key,
            {
                "id": key,
                "type": p.get("gsi_system_type") or p.get("system_type") or "stormwater system",
                "project": p.get("project_number"),
                "project_type": p.get("project_type"),
                "installed": p.get("year_installed"),
            },
        )
    management = (assessment or {}).get("existing_system_management")
    for info in (management or {}).get("systems", []) if isinstance(management, dict) else []:
        # Policy-side management leads (one per on-parcel system), when present.
        if not isinstance(info, dict):
            continue
        key = _sid(info.get("system_id") or info.get("gsi_system_id") or "")
        if not key:
            continue
        row = systems.setdefault(
            key,
            {
                "id": key,
                "type": info.get("system_type") or "stormwater system",
                "project": info.get("project_number"),
                "project_type": info.get("project_type"),
                "installed": info.get("year_installed"),
            },
        )
        for field, value in (
            ("type", info.get("system_type")),
            ("project", info.get("project_number")),
            ("installed", info.get("year_installed")),
        ):
            if value not in (None, "") and row.get(field) in (None, "", "stormwater system"):
                row[field] = value
        if info.get("lead_label"):
            row["lead"] = info["lead_label"]
    for item in _find(assessment, "systems_without_recorded_credit"):
        for entry in item if isinstance(item, list) else []:
            info = entry if isinstance(entry, dict) else {"id": entry}
            key = _sid(info.get("gsi_system_id") or info.get("system_id") or info.get("id") or "")
            if not key:
                continue
            row = systems.setdefault(
                key,
                {
                    "id": key,
                    "type": info.get("gsi_system_type")
                    or info.get("system_type")
                    or info.get("type")
                    or "stormwater system",
                    "project": info.get("project_number") or info.get("project"),
                    "project_type": info.get("project_type"),
                    "installed": info.get("year_installed") or info.get("installed"),
                },
            )
            row["no_recorded_credit"] = True
    return list(systems.values())


def _find(value, key):
    found = []
    if isinstance(value, dict):
        for k, v in value.items():
            if k == key:
                found.append(v)
            else:
                found.extend(_find(v, key))
    elif isinstance(value, list):
        for v in value:
            found.extend(_find(v, key))
    return found


def _system_name(s):
    words = [str(s["type"]), str(s["id"])]
    extra = []
    if s.get("project"):
        extra.append("project " + str(s["project"]))
    if s.get("installed"):
        extra.append("installed " + str(s["installed"]))
    return " ".join(words) + (" (" + ", ".join(extra) + ")" if extra else "")


def _assumption(row, unknown_area):
    family, data = row["family"], row["row"]
    name = str(data.get("name") or "")
    receiver = data.get("receiver_id")
    if family == "surface":
        if "pervious" in name and "impervious" not in name:
            return (
                f"all {sqft(unknown_area)} of ground the imagery could not classify is "
                "unpaved (grass or soil), so PWD would bill less impervious area"
            )
        return "PWD accepts a re-measured parcel area"
    if family == "mapped_system":
        if receiver and not str(receiver).startswith("all"):
            return (
                f"mapped stormwater system {receiver} treats the runoff from its modeled "
                "drainage area and PWD approves a credit for it"
            )
        return (
            "the mapped stormwater systems treat the runoff from their modeled drainage "
            "areas and PWD approves credits for them"
        )
    if family == "existing_system":
        return "the existing mapped systems work as built and PWD grants a credit not now on record"
    if family == "permit":
        permit = data.get("permit_id") or "the matched permit"
        return (
            f"industrial stormwater permit {permit} covers this site and operator and was "
            "complied with for the past 12 months"
        )
    if family == "canopy":
        return "trees overhang paved ground and PWD credits that canopy"
    if family == "open_space":
        return "the open space qualifies for the open-space credit at the worksheet curve number"
    return "reviewed modeled evidence or a complete re-measurement is accepted by PWD"


def owner_summary(case, analysis):
    """Five plain-language findings for an owner; reads only the safe view given."""
    analysis = analysis or {}
    assessment = analysis.get("assessment") or {}
    economics = assessment.get("economics") or {}
    baseline = case.get("baseline") or {}
    outdated = (analysis.get("quality_review") or {}).get("status") == "outdated"
    computed = economics.get("baseline") or (analysis.get("billing") or {}).get("baseline") or {}
    measurement = analysis.get("measurement") or {}
    unknown_area = measurement.get("unknown_sqft")

    # (i) Current bill.
    published = baseline.get("published_monthly_total")
    total = computed.get("monthly_total") if computed.get("status") == "calculated" else None
    if _number(published) and _number(total):
        difference = round(total - published, 2)
        check = "matches" if abs(difference) < 0.005 else "differs"
    else:
        difference, check = None, "not_checked"
    if not _number(published):
        bill_text = "PWD's published monthly charge for this parcel was not available."
    else:
        bill_text = (
            f"PWD publishes a stormwater charge of {usd(published)} per month for this parcel."
        )
    if check == "matches":
        bill_text += " Our check from the billed areas and current rates gives the same amount."
    elif check == "differs":
        bill_text += (
            f" Our check from the billed areas and current rates gives {usd(total)}, "
            f"{usd(abs(difference))} {'more' if difference > 0 else 'less'}; ask PWD which areas it bills."
        )
    else:
        reasons = "; ".join(str(r) for r in (computed.get("reasons") or [])[:2])
        bill_text += " We could not recompute it" + (f" ({reasons})." if reasons else ".")
    notes = [str(n) for n in (computed.get("billing_notes") or []) if n]
    if notes:
        bill_text += " Note: " + " ".join(notes[:2])

    # (ii) Supported savings (documented evidence only).
    supported = None
    for key in DOCUMENTED:
        row = economics.get(key) or {}
        if row.get("status") == "calculated" and _number(row.get("gross_annual_reduction")):
            if supported is None or row["gross_annual_reduction"] > supported["annual"]:
                supported = {
                    "annual": float(row["gross_annual_reduction"]),
                    "monthly": row.get("gross_monthly_reduction"),
                }
    if outdated:
        supported_block = {
            "status": "withheld",
            "annual": None,
            "text": "Saved savings figures are withheld because the calculation rules changed; "
            "recompute from the saved inputs to see current figures.",
        }
    elif supported and supported["annual"] > 0:
        supported_block = {
            "status": "supported",
            "annual": supported["annual"],
            "text": f"Documents on file support a reduction of {usd(supported['monthly'])} per month "
            f"({usd(supported['annual'])} per year), subject to PWD approval.",
        }
    else:
        supported_block = {
            "status": "none",
            "annual": 0.0,
            "text": "$0. No savings are supported yet: no documented evidence on file has passed "
            "the credit or appeal requirements.",
        }

    # (iii) Hypothetical range (conditional, not supported yet).
    rows = [] if outdated else conditional_rows(assessment)
    if rows:
        low = min(rows, key=lambda r: r["annual"])
        high = max(rows, key=lambda r: (r["annual"], -FAMILY_ORDER.get(r["family"], 99)))
        biggest = _assumption(high, unknown_area)

        def money(value):
            return (
                f"a {usd(abs(value), False)} per year increase"
                if value < 0
                else f"{usd(value, False)} per year"
            )

        hypothetical = {
            "label": "Not supported yet",
            "low": low["annual"],
            "high": high["annual"],
            "count": len(rows),
            "biggest_assumption": biggest,
            "text": f"Not supported yet: between {money(low['annual'])} and "
            f"{money(high['annual'])} if unproven conditions hold. The highest figure "
            f"assumes {biggest}.",
        }
    else:
        hypothetical = {
            "label": "Not supported yet",
            "low": None,
            "high": None,
            "count": 0,
            "biggest_assumption": None,
            "text": (
                "Withheld until the saved result is recomputed."
                if outdated
                else "No conditional figure could be calculated from the available evidence."
            ),
        }

    # (v) Mapped systems and recorded credit.
    systems = mapped_systems(case, assessment)
    credits = [
        baseline.get(k)
        for k in ("existing_ga_credit_sqft", "existing_ia_credit_sqft", "existing_iar_sqft")
    ]
    flags = assessment.get("public_credit_observations") or []
    credit_flag = next(
        (f.get("credits_flag") for f in flags if f.get("credits_flag") is not None), None
    )
    expired_flag = next(
        (f.get("expired_flag") for f in flags if f.get("expired_flag") is not None), None
    )
    status = (
        (assessment.get("existing_system_management") or {})
        if isinstance(assessment.get("existing_system_management"), dict)
        else {}
    ).get("recorded_credit_status")
    if status == "recorded_credits_unattributed" and not any(_number(c) and c > 0 for c in credits):
        credit_text = "PWD's billing record shows a credit or permit reduction, but not which system it is for."
        recorded = True
    elif any(_number(c) and c > 0 for c in credits):
        credit_text = (
            "PWD's billing record shows existing credits ("
            + ", ".join(
                f"{label} {sqft(v)}"
                for label, v in zip(
                    ("gross area", "impervious area", "impervious reduction"), credits
                )
                if _number(v) and v > 0
            )
            + ")."
        )
        recorded = True
    elif all(_number(c) for c in credits) or credit_flag == 0 or status == "no_recorded_credit":
        credit_text = "PWD's billing record shows no stormwater credit on this parcel."
        recorded = False
    else:
        credit_text = "Whether PWD records any credit for this parcel is unknown."
        recorded = None
    if expired_flag == 1:
        credit_text += (
            " Its public record carries an 'Expired' credit flag; what it refers to is unknown."
        )
    unrecorded = [s for s in systems if s.get("no_recorded_credit")]
    if systems:
        shown = systems[:5]
        systems_text = (
            f"{len(systems)} stormwater system{'s are' if len(systems) != 1 else ' is'} mapped on "
            "this parcel: "
            + "; ".join(_system_name(s) for s in shown)
            + (f"; and {len(systems) - len(shown)} more" if len(systems) > len(shown) else "")
            + ". "
            + credit_text
        )
        if unrecorded:
            systems_text += (
                f" {len(unrecorded)} of these {'have' if len(unrecorded) != 1 else 'has'} no "
                "recorded credit."
            )
        elif recorded is False:
            systems_text += (
                " None of them is credited on the bill today."
                if len(systems) > 1
                else " It is not credited on the bill today."
            )
    else:
        systems_text = "No public stormwater system is mapped on this parcel. " + credit_text

    # (iv) Next evidence, ranked by the largest conditional figure each would unlock.
    candidates = []
    best = {}
    for row in rows:
        family = row["family"]
        key = (family, _sid(row["row"].get("receiver_id") or row["row"].get("permit_id") or ""))
        best[key] = max(best.get(key, 0.0), row["annual"])
        best[(family, "")] = max(best.get((family, ""), 0.0), row["annual"])
    if check == "differs":
        candidates.append(
            (
                float("inf"),
                0,
                f"Ask PWD for the gross and impervious areas behind the {usd(published)} monthly "
                f"charge; our recomputed charge differs by {usd(abs(difference))}.",
            )
        )
    projects = {}
    for system in systems:
        projects.setdefault(system.get("project") or "system " + system["id"], []).append(system)
    for project, group in projects.items():
        value = max(
            [best.get(("mapped_system", s["id"]), 0.0) for s in group]
            + [
                best.get(("mapped_system", "all_unassigned_gsi"), 0.0),
                best.get(("existing_system", ""), 0.0),
            ]
        )
        names = ", ".join(f"{s['type']} {s['id']}" for s in group[:4]) + (
            f" and {len(group) - 4} more" if len(group) > 4 else ""
        )
        installed = sorted({str(s["installed"]) for s in group if s.get("installed")})
        if group[0].get("project"):
            text = (
                "Ask PWD for the approved post-construction stormwater management plan (PCSMP) "
                f"for project {project} ({names}"
                + (f", installed {', '.join(installed)}" if installed else "")
                + ") and whether a credit was ever awarded for it."
            )
        else:
            text = (
                f"Ask PWD for the approved design and maintenance records for mapped "
                f"{names} and whether it was ever credited."
            )
        candidates.append((value, 1, text))
    if best.get(("surface", ""), 0.0) > 0 or (_number(unknown_area) and unknown_area > 0):
        candidates.append(
            (
                best.get(("surface", ""), 0.0),
                2,
                f"Get a current site plan or survey showing which of the {sqft(unknown_area)} of "
                "ground the imagery could not classify is paved and which is grass or soil.",
            )
        )
    for (family, ident), value in best.items():
        if family == "permit" and ident:
            candidates.append(
                (
                    value,
                    3,
                    f"Confirm whether industrial stormwater permit {ident} covers this site and "
                    "operator, and collect the last 12 months of discharge monitoring reports.",
                )
            )
    if best.get(("canopy", ""), 0.0) > 0:
        candidates.append(
            (
                best[("canopy", "")],
                4,
                "Have a site visit confirm where tree canopy overhangs paved ground.",
            )
        )
    for category in assessment.get("categories") or []:
        if category.get("category") == "existing_system_management":
            for item in (category.get("missing") or [])[:2]:
                candidates.append(
                    (
                        best.get(("existing_system", ""), 0.0),
                        1,
                        "For the existing systems: " + str(item),
                    )
                )
    if expired_flag == 1:
        candidates.append(
            (
                0.0,
                5,
                "Ask PWD what the 'Expired' credit flag on this parcel's record refers to "
                "(award letter, credited area and dates).",
            )
        )
    seen, ranked = set(), []
    for value, order, text in sorted(candidates, key=lambda c: (-c[0], c[1])):
        if text not in seen:
            seen.add(text)
            ranked.append(
                {
                    "text": text,
                    "unlocks_up_to_annual": None if math.isinf(value) or not value else value,
                }
            )
    return {
        "version": VERSION,
        "claim": CLAIM,
        "current_bill": {
            "published_monthly": published if _number(published) else None,
            "computed_monthly": total,
            "check": check,
            "difference": difference,
            "text": bill_text,
        },
        "supported": supported_block,
        "hypothetical": hypothetical,
        "next_evidence": ranked[:3],
        "systems": {
            "count": len(systems),
            "items": systems[:20],
            "recorded_credit": recorded,
            "text": systems_text,
        },
    }


FAMILY_ORDER = {name: i for i, (name, _) in enumerate(FAMILIES)}


def summary_html(summary):
    """The summary as the first section of the HTML report (all text escaped)."""
    e = lambda v: escape(str(v))
    s = summary
    steps = "".join("<li>" + e(item["text"]) + "</li>" for item in s["next_evidence"]) or (
        "<li>No further evidence request was identified from the available records.</li>"
    )
    return (
        '<section class="owner-summary"><h2>Summary for the owner</h2>'
        "<dl>"
        "<dt>1. Current bill</dt><dd>" + e(s["current_bill"]["text"]) + "</dd>"
        "<dt>2. Savings supported today</dt><dd><strong>"
        + e(s["supported"]["text"])
        + "</strong></dd>"
        "<dt>3. Possible savings — not supported yet</dt><dd>"
        + e(s["hypothetical"]["text"])
        + "</dd>"
        "<dt>4. What to get next</dt><dd><ol>" + steps + "</ol></dd>"
        "<dt>5. Stormwater systems on the parcel</dt><dd>" + e(s["systems"]["text"]) + "</dd>"
        '</dl><p class="note">' + e(s["claim"]) + "</p></section>"
    )
