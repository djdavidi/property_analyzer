"""PWD existing-site screens over frozen physical GIS; never acquires or reroutes.

A screen_pass describes reviewed prerequisites, not a grant, award or legal opinion.
The separate area ledger below implements Manual 4.3.5; it never adds independently
calculated savings or applies a further seven percent to already uplifted credits.
"""

from copy import deepcopy
from datetime import date, timedelta
from decimal import Decimal
from hashlib import sha256
from urllib.parse import urlparse
import json
from shapely.geometry import shape
from shapely.errors import ShapelyError
from drainage_core.geometry import case_area_sqft, effective_features
from drainage_core.evidence import validate_references
from .billing import (
    monthly_bill,
    default_tariff,
    cents,
    decimal,
    bill_terms,
    billable_ia,
    recorded_credits,
    npdes_alone_credits,
    BaselineError,
    IAR_SPLIT_BLOCK,
    undeveloped_unknown,
    merge_status_alternatives,
    minimum_discontinuity,
    STATUS_ALTERNATIVES,
    billed_area_check,
)
from .rules import screen, open_space_factor, factor, load_rule_config, MANUAL_URL, TARIFF_URL
from .existing_systems import existing_system_leads
from .prerequisites import case_vetoes

_CONFIG = load_rule_config()
VERSION = _CONFIG["existing_site_rule_version"]
LABELS = {
    "green_roof": "Existing green roofs",
    "permeable_pavement": "Existing permeable pavement",
    "direct_discharge": "Direct surface-water discharge",
    "industrial_npdes": "Industrial NPDES",
    # Fix 3: a mapped system on the parcel is a management-credit lead (manual 4.3.2.2).
    "existing_system_management": "Existing mapped system (management lead)",
}
# One source for the verified rule period: config/rules-pwd-2026-09.json (the
# assessment uses the tariff verification window; docs/ASSESSMENT-RULES.md).
RULES = {
    "version": VERSION,
    "verified_on": _CONFIG["verified_on"],
    "effective_from": _CONFIG["tariff_effective_from"],
    "verified_through": _CONFIG["tariff_verified_through"],
    "config_source": "config/rules-pwd-2026-09.json",
    "manual": MANUAL_URL,
    "tariff": TARIFF_URL,
    "gis_area_numerical_precision_sqft": "0.000000001",
    "manual_sections": [
        "4.3.2.1",
        "4.3.2.2",
        "4.3.3.1",
        "4.3.3.2",
        "4.3.4",
        "4.3.5",
        "4.4.1",
        "4.5.1",
        "4.5.5",
    ],
    "source_snapshots": [
        {
            "url": "https://water.phila.gov/wp-content/uploads/files/stormwater-credits-appeals-manual.pdf",
            "retrieved_at": "2026-11-15T06:51:38.544003+00:00",
            "sha256": "5c7b6e87ae442731625b91e278ccdd160a21e960b3460886e8349aa42f8ffb49",
            "bytes": 665543,
        },
        {
            "url": "https://water.phila.gov/wp-content/uploads/files/rates-and-charges-2026-09-01.pdf",
            "retrieved_at": "2026-11-15T06:51:38.781280+00:00",
            "sha256": "880779871b2e47c11c619d33f499752afc9b3791dda5c326793165800f4ad9e6",
            "bytes": 855667,
        },
    ],
    "claim": "Technical screening; PWD approval and actual billed reductions are not established.",
}
COMMON = (
    "existing_installation",
    "account_current",
    "physical_area_confirmed",
    "parcel_allocation_confirmed",
)
SMP = (
    "routing_confirmed",
    "approved_record_drawings",
    "current_condition_confirmed",
    "maintenance_documented",
    "professional_reviewed",
)
PAVEMENT = (
    "material_confirmed",
    "construction_documented",
    "storage_documented",
    "infiltration_or_underdrain_documented",
)
DIRECT = (
    "catchment_confirmed",
    "route_confirmed",
    "outfall_confirmed",
    "destination_confirmed",
    "no_city_infrastructure",
    "ownership_confirmed",
    "no_erosion_or_detriment",
    "site_plan_documented",
    "photographs_current",
    "private_connections_resolved",
)
# Manual Table 1 and 4.3.2.1: "Rooftop Disconnection via Green Roof" is an impervious
# area reduction (IAR), "a direct reduction of the billable IA" (tariff 4.5(c)(1)(i)(A),
# rooftop disconnection). Manual 4.5.1 (Impervious Area Reductions): "submit a site plan
# delineating the requested areas to be credited as well as recent photographs".
GREEN_ROOF_IAR = ("site_plan_documented", "photographs_current")
GREEN_ROOF_PATHS = (None, "impervious_area_reduction", "iar")
NPDES = (
    "site_match",
    "operator_match",
    "industrial_stormwater",
    "active",
    "compliance_previous_12_months",
    "permit_documented",
    "discharge_monitoring_reports_previous_12_months",
)


def _area_decimal(value):
    # Remove sub-nanosquare-foot float conversion noise before 500 sqft ceilings.
    # This is numerical stabilization of GIS output, not billable-area rounding.
    return decimal(value).quantize(Decimal(".000000001"))


def _day(value):
    return date.fromisoformat(value) if isinstance(value, str) else value


def _prior_year(day):
    try:
        return day.replace(year=day.year - 1)
    except ValueError:
        return day.replace(year=day.year - 1, day=28)


def _source_url(value):
    if not isinstance(value, str):
        return False
    try:
        parsed = urlparse(value)
        return parsed.scheme in ("https", "http") and bool(parsed.hostname)
    except ValueError:
        return False


def _validate_assessment_inputs(assessment):
    if not isinstance(assessment, dict):
        raise ValueError("Assessment must be an object")
    for field in ("records", "existing_credit_allocations"):
        entries = assessment.get(field, [])
        if not isinstance(entries, list):
            raise ValueError(field + " must be a list")
        identifiers = set()
        for record in entries:
            if not isinstance(record, dict):
                raise ValueError(field + " entries must be objects")
            identifier = record.get("id")
            if not isinstance(identifier, str) or not identifier.strip():
                raise ValueError(field + " entries need a nonempty string ID")
            if identifier in identifiers:
                raise ValueError("Duplicate " + field + " ID: " + identifier)
            identifiers.add(identifier)
            if not isinstance(record.get("facts", {}), dict):
                raise ValueError("Facts must be an object")
            if field == "records":
                if record.get("category") not in LABELS:
                    raise ValueError("Unsupported assessment category")
                if record.get("decision", "candidate") not in (
                    "candidate",
                    "confirmed",
                    "rejected",
                ):
                    raise ValueError("Invalid candidate decision")
                if record.get("basis", "manual") not in (
                    "public_candidate",
                    "manual",
                    "documented",
                    "modeled",
                ):
                    raise ValueError("Invalid evidence basis")
            refs = record.get("evidence_refs", [])
            if not isinstance(refs, list) or any(not isinstance(ref, dict) for ref in refs):
                raise ValueError("Evidence references must be a list of objects")


def _months_before(day, months):
    year, month = divmod(day.year * 12 + day.month - 1 - months, 12)
    month += 1
    for d in (day.day, 30, 29, 28):
        try:
            return day.replace(year=year, month=month, day=d)
        except ValueError:
            continue
    raise ValueError("Invalid date")


def _lagging_dmr_period(facts, through, as_of, output, missing):
    """Manual 4.3.4 / 4.5.5: compliance "during the preceding twelve months", shown by
    the required PADEP DMRs "from the previous 12 months". The evidence must cover the
    whole window before the assessment date (``compliance_from`` at or before as_of
    minus twelve months, checked by the caller). Only the tail after the latest DMR
    period may be unevidenced, and only when (a) no DMR has fallen due since that
    period ended (a sourced ``next_dmr_due`` after the assessment date) and (b) the
    period ended recently: within ``npdes_max_compliance_lag_months`` (a project
    screening threshold in the rule config, not a PWD or DEP rule) so most of the
    twelve months is evidenced. Otherwise the record needs an update: stale evidence
    is missing, never a failed permit.
    """
    output.setdefault("date_notes", [])
    due = facts.get("next_dmr_due")
    lag = int(_CONFIG.get("npdes_max_compliance_lag_months", 6))
    recent = through >= _months_before(as_of, lag)
    if recent and due:
        try:
            if _day(due) > as_of:
                output["date_notes"].append(
                    "Latest DMR period ends "
                    + through.isoformat()
                    + "; next required DMR is due "
                    + _day(due).isoformat()
                    + ", so no DMR has fallen due since and the reporting cycle is current"
                )
                return True
        except (ValueError, TypeError):
            return False
    output.setdefault("needs_update", []).append("compliance_through")
    if not recent:
        missing.append("compliance_through_current")
        output["date_notes"].append(
            "Compliance evidence ends "
            + through.isoformat()
            + ", more than "
            + str(lag)
            + " months before the assessment date, so it does not show compliance during most of "
            "the preceding twelve months (manual 4.3.4); supply later DMRs (needs update, not a "
            "failed requirement)"
        )
        return None
    missing.append("compliance_through_current" if due else "next_dmr_due")
    output["date_notes"].append(
        "Compliance evidence ends "
        + through.isoformat()
        + " before the assessment date and a DMR may have fallen due since; supply the reporting "
        "schedule or later DMRs (needs update, not a failed requirement)"
    )
    return None


def _administratively_continued(facts, expires, output, missing, failed):
    """25 Pa. Code 92a.7(b)-(c): an expiring NPDES permit is automatically continued
    when the permittee submitted a timely reissuance application (92a.75(a): at least
    180 days before expiry unless DEP permitted a later date) and DEP has not acted.
    ``administratively_continued`` is the reviewed fact; an expired permit without it
    lacks evidence rather than failing.
    """
    continued = facts.get("administratively_continued")
    output.setdefault("date_notes", [])
    if continued is None:
        missing.append("administratively_continued")
        output["date_notes"].append(
            "Permit expiry "
            + expires.isoformat()
            + " precedes the assessment date; continuation under 25 Pa. Code 92a.7 is not established"
        )
        return None
    if continued is not True:
        return False
    submitted = facts.get("renewal_application_submitted_on")
    if submitted:
        try:
            limit = expires - timedelta(days=180)
            if _day(submitted) > limit and facts.get("later_renewal_date_permitted") is not True:
                failed.append("renewal_application_submitted_on")
                return None
        except (ValueError, TypeError):
            failed.append("renewal_application_submitted_on")
            return None
    output["date_notes"].append(
        "Expired permit treated as administratively continued under 25 Pa. Code 92a.7(b)-(c) (reviewed fact)"
    )
    return True


def _managed_surfaces(record, category, geom, case, gis):
    """Manual 4.3.2.2 / 4.3.3.2: IA credit is for IA Managed, with equivalent GA
    underneath. A real SMP or surface-discharge drainage area may also contain open
    space. That open space is credited only as the manual allows (4.3.3.1 notes):
    direct discharge to surface water -> 90% GA (97% with NPDES, 4.3.5.4) regardless
    of cover or soil; an approved SMP sized for it with PWD design pre-approval ->
    80% GA (87% with NPDES). Unresolved surfaces are reported, never credited.
    """
    geometries = gis["measurement"]["geometries"]
    empty = {"type": "GeometryCollection", "geometries": []}
    ia_part = geom.intersection(shape(geometries["physical_ia"]))
    open_part = geom.intersection(shape(geometries.get("pervious") or empty))
    ia_area = case_area_sqft(ia_part, case) if not ia_part.is_empty else 0.0
    open_area = case_area_sqft(open_part, case) if not open_part.is_empty else 0.0
    total = case_area_sqft(geom, case)
    out = {
        "managed_ia_sqft": ia_area,
        "managed_open_space_sqft": open_area,
        "managed_unresolved_sqft": max(0.0, total - ia_area - open_area),
    }
    facts = record.get("facts") or {}
    if open_area < 0.000001:
        out["open_space_credit"] = {"status": "not_applicable"}
    elif category == "direct_discharge":
        out["open_space_credit"] = {
            "status": "screen_pass",
            "basis": "manual 4.3.3.1 note: open space discharging directly to surface water, 90% regardless of cover or soil",
        }
    else:
        needed = ("open_space_smp_sizing_confirmed", "open_space_design_preapproval")
        absent = [k for k in needed if facts.get(k) is None]
        bad = [k for k in needed if facts.get(k) is not None and facts.get(k) is not True]
        out["open_space_credit"] = {
            "status": (
                "requirements_failed" if bad else "missing_evidence" if absent else "screen_pass"
            ),
            "missing": absent,
            "failed": bad,
            "basis": "manual 4.3.3.1 note: open space managed by an approved SMP sized for it, with PWD design-phase pre-approval, may receive 80%",
        }
    return out


def _green_roof_iar(footprint, case, gis):
    """Manual 4.3.2.1: green-roof IAR area = the roof footprint on mapped physical IA."""
    part = footprint.intersection(shape(gis["measurement"]["geometries"]["physical_ia"]))
    return case_area_sqft(part, case) if not part.is_empty else 0.0


def _evidence(record, case):
    refs = record.get("evidence_refs") or []
    attachments = {a["id"] for a in case.get("assessment", {}).get("attachments", []) if "id" in a}
    return any(
        isinstance(r, dict)
        and (_source_url(r.get("source_url")) or r.get("attachment_id") in attachments)
        for r in refs
    )


def _support_review(record):
    """A URL is a citation, not proof. Require an explicit human support review.

    This records an assertion by the reviewer; it never claims automatic source
    authentication or independent agency confirmation.
    """
    review = record.get("evidence_review") or {}
    keys = {k for k, v in record.get("facts", {}).items() if v is not None}
    return (
        isinstance(review, dict)
        and all(
            review.get(k) is True for k in ("support_reviewed", "property_match", "period_match")
        )
        and isinstance(review.get("note"), str)
        and bool(review["note"].strip())
        and isinstance(review.get("fact_keys"), list)
        and all(isinstance(k, str) for k in review["fact_keys"])
        and keys <= set(review["fact_keys"])
        and any(r.get("page") or r.get("locator") for r in record.get("evidence_refs", []))
    )


def screen_record(record, case, gis, as_of):
    category = record["category"]
    facts = record.get("facts") or {}
    missing = []
    failed = []
    output = {
        key: deepcopy(record.get(key))
        for key in ("id", "category", "decision", "basis", "evidence_refs", "source")
    }
    output.update(
        label=LABELS[category],
        missing=missing,
        failed=failed,
        managed_area_sqft=None,
        managed_ia_sqft=None,
        managed_open_space_sqft=None,
        managed_unresolved_sqft=None,
        footprint_area_sqft=None,
        rule_version=VERSION,
    )

    def require(name):
        if facts.get(name) is None:
            missing.append(name)
        elif facts[name] is not True:
            failed.append(name)

    def number(name, minimum=0):
        if facts.get(name) is None:
            missing.append(name)
            return
        try:
            if decimal(facts[name], name) < Decimal(str(minimum)):
                failed.append(name)
        except ValueError:
            failed.append(name)

    for key in ("account_current",) if category == "industrial_npdes" else COMMON:
        require(key)
    if not _evidence(record, case):
        missing.append("supporting_document_or_source_reference")
    if not _support_review(record):
        missing.append("property_period_fact_support_review")
    output["evidence_verification"] = (
        "Human assertions linked to cited evidence; source content not automatically authenticated"
    )
    if record.get("source_update", {}).get("status") == "pending_review":
        missing.append("source_update_review")
    if category == "industrial_npdes":
        for key in NPDES:
            require(key)
        if not facts.get("permit_id"):
            missing.append("permit_id")
        if facts.get("permit_type") in ("construction", "municipal", "no_exposure", "terminated"):
            failed.append("permit_type")
        for key in ("effective_from", "expires_on", "compliance_from", "compliance_through"):
            if not facts.get(key):
                missing.append(key)
                continue
            if key == "compliance_through" and facts.get("compliance_from"):
                try:
                    if _day(facts["compliance_from"]) > _day(facts[key]):
                        failed.append("compliance_period_order")
                        continue
                except (ValueError, TypeError):
                    pass
            try:
                day = _day(facts[key])
                if key == "effective_from":
                    valid = day <= as_of
                elif key == "compliance_from":
                    valid = day <= _prior_year(as_of)
                elif key == "compliance_through":
                    valid = day >= as_of or _lagging_dmr_period(facts, day, as_of, output, missing)
                else:
                    valid = day >= as_of or _administratively_continued(
                        facts, day, output, missing, failed
                    )
                if valid is False:
                    failed.append(key)
            except (ValueError, TypeError):
                failed.append(key)
        if facts.get("terminated_on"):
            try:
                if _day(facts["terminated_on"]) <= as_of:
                    failed.append("terminated_on")
            except (ValueError, TypeError):
                failed.append("terminated_on")
    else:
        geom = None
        if not record.get("geometry"):
            if category != "green_roof":
                missing.append("managed_area_geometry")
        else:
            try:
                geom = shape(record["geometry"])
                if (
                    not geom.is_valid
                    or geom.is_empty
                    or geom.geom_type not in ("Polygon", "MultiPolygon")
                ):
                    raise ValueError()
                area = case_area_sqft(geom, case)
                output["managed_area_sqft"] = area
                parcel = shape(case["parcel"])
                if geom.difference(parcel).area > 1e-8:
                    failed.append("managed_geometry_inside_parcel")
                output.update(_managed_surfaces(record, category, geom, case, gis))
                if (
                    category != "green_roof"
                    and output["managed_ia_sqft"] < 0.000001
                    and output["managed_open_space_sqft"] < 0.000001
                ):
                    # Only unresolved ground: neither managed IA nor open space is established.
                    missing.append("managed_area_surface_classification")
                if record.get("managed_area_sqft") is not None and abs(
                    float(decimal(record["managed_area_sqft"])) - area
                ) > max(0.1, area * 0.001):
                    failed.append("managed_area_matches_geometry")
            except (ValueError, TypeError, KeyError, IndexError, AttributeError, ShapelyError):
                failed.append("managed_area_geometry")
        if record.get("footprint_geometry"):
            try:
                footprint = shape(record["footprint_geometry"])
                if (
                    footprint.is_empty
                    or not footprint.is_valid
                    or footprint.geom_type not in ("Polygon", "MultiPolygon")
                ):
                    raise ValueError()
                output["footprint_area_sqft"] = case_area_sqft(footprint, case)
                if footprint.difference(shape(case["parcel"])).area > 1e-8:
                    failed.append("footprint_inside_parcel")
                if category == "green_roof":
                    # The IAR is the vegetated roof itself: footprint within mapped IA.
                    output["iar_area_sqft"] = _green_roof_iar(footprint, case, gis)
                    if output["iar_area_sqft"] < 0.000001:
                        missing.append("green_roof_on_mapped_impervious_roof")
            except (ValueError, TypeError, KeyError, IndexError, AttributeError, ShapelyError):
                failed.append("footprint_geometry")
        elif category in ("green_roof", "permeable_pavement"):
            missing.append("physical_footprint_geometry")
        if category == "green_roof":
            # Manual Table 1 / 4.3.2.1: an IAR, not SMP management; 4.5.1 documents.
            output["credit_path"] = "impervious_area_reduction"
            for key in GREEN_ROOF_IAR:
                require(key)
            if facts.get("credit_path") not in GREEN_ROOF_PATHS:
                failed.append("unsupported_credit_path")
        elif category == "permeable_pavement":
            for key in SMP:
                require(key)
            number(
                "treatment_depth_inches",
                1 if facts.get("old_standard_renewal_verified") is True else 1.5,
            )
            for key in PAVEMENT:
                require(key)
            if facts.get("credit_path") not in (None, "management"):
                failed.append("unsupported_credit_path")
        elif category == "existing_system_management":
            # Manual 4.3.2.2 / 4.5.1: an existing SMP managing IA; the PCSMP/as-built
            # drainage area is the managed geometry, never the mapped footprint.
            for key in SMP:
                require(key)
            number(
                "treatment_depth_inches",
                1 if facts.get("old_standard_renewal_verified") is True else 1.5,
            )
            if facts.get("credit_path") not in (None, "management"):
                failed.append("unsupported_credit_path")
        else:
            for key in DIRECT:
                require(key)
            if not facts.get("waterway_name"):
                missing.append("waterway_name")
            if not facts.get("outfall_id"):
                missing.append("outfall_id")
            if facts.get("upstream_smp_present") is None:
                missing.append("upstream_smp_present")
            elif not isinstance(facts["upstream_smp_present"], bool):
                failed.append("upstream_smp_present")
            elif facts["upstream_smp_present"] is True:
                require("upstream_smp_compliant")
                require("upstream_smp_functional")
    decision = record.get("decision", "candidate")
    from drainage_core.installation import installation_issues

    if category != "industrial_npdes":
        failed.extend(installation_issues(facts, as_of))
    applicable = RULES["effective_from"] <= as_of.isoformat() <= RULES["verified_through"]
    output["rule_applicability"] = "applicable" if applicable else "outside_verified_period"
    if not applicable:
        missing.append("applicable_rule_version")
    output["basis"] = record.get("basis", "manual")
    output["status"] = (
        "rejected"
        if decision == "rejected"
        else (
            "candidate"
            if decision != "confirmed"
            else (
                "requirements_failed"
                if failed
                else "missing_evidence" if missing else "screen_pass"
            )
        )
    )
    output["conclusion"] = (
        "Prerequisites reviewed; eligibility/approval not established"
        if output["status"] == "screen_pass"
        else "No supported eligibility conclusion"
    )
    return output


def _blocked(reasons):
    return {
        "status": "blocked",
        "reasons": list(dict.fromkeys(reasons)),
        "gross_monthly_reduction": None,
        "gross_annual_reduction": None,
        "bill": None,
        "ledger": None,
    }


# Report table rows (historical names) -> the single assessment ledger scenario.
BILLING_VIEW = (
    ("appeal_only", "measurement_only"),
    ("credit_only", "modeled"),
    ("combined", "modeled_combined"),
    ("documented_credit_only", "documented"),
    ("documented_combined", "documented_combined"),
)


def ledger_billing_view(economics):
    """The report's billing table read from ``_economics`` (decision D7).

    There is one savings path: these rows are relabelled ledger scenarios, never
    a second calculation. Blocked scenarios carry no totals or savings.
    """
    base = economics.get("baseline")
    if not isinstance(base, dict):
        reasons = list(
            dict.fromkeys(
                (economics.get("documented") or {}).get("reasons")
                or ["Billing baseline unavailable"]
            )
        )
        return {
            "status": "blocked",
            "reason": "; ".join(reasons),
            "reasons": reasons,
            "source": "assessment_economics",
        }
    view = {
        "source": "assessment_economics",
        "baseline": deepcopy(base),
        "claim": "Rows are the assessment ledger scenarios; alternatives, never additive.",
    }
    for key in ("billed_area_check", "undeveloped_status", "allocation_sensitive"):
        if key in economics:
            view[key] = deepcopy(economics[key])
    for legacy, key in BILLING_VIEW:
        s = economics.get(key) or _blocked(["Scenario unavailable"])
        calculated = s.get("status") == "calculated"
        row = {
            **(deepcopy(s.get("bill")) if calculated and s.get("bill") else {}),
            "status": s.get("status"),
            "basis": s.get("basis"),
            "reasons": list(s.get("reasons", [])),
            "monthly_savings": s.get("gross_monthly_reduction"),
            "annual_savings": s.get("gross_annual_reduction"),
            "ledger": deepcopy(s.get("ledger")),
            "assumptions": list(s.get("assumptions", [])),
            "ledger_scenario": key,
        }
        if not calculated:
            row["monthly_total"] = None
        if "alternatives" in s:
            row["alternatives"] = deepcopy(s["alternatives"])
        view[legacy] = row
    return view


def _legacy_benefits(case, gis):
    """Normalize the existing benefits into the same geometric ledger."""
    result = []
    benefits = [b for b in case.get("benefits", []) if not b.get("geometry")]
    benefits.extend(
        {**f["properties"]["benefit"], "geometry": f["geometry"]}
        for f in effective_features(case)
        if f["properties"].get("layer") == "benefit"
    )
    for b in benefits:
        r = deepcopy(b)
        facts = r.setdefault("evidence", {})
        if r.get("geometry"):
            r["area_sqft"] = case_area_sqft(shape(r["geometry"]), case)
            target = (
                "pervious"
                if r["category"] in ("open_space", "open-space")
                else (
                    "canopy_ground_ia"
                    if r["category"] in ("canopy", "tree_canopy")
                    else "physical_ia"
                )
            )
            if (
                shape(r["geometry"])
                .difference(shape(gis["measurement"]["geometries"][target]))
                .area
                > 1e-8
            ):
                facts["physical_area_confirmed"] = False
        else:
            facts["physical_area_confirmed"] = None
        s = screen(r["category"], r["area_sqft"], facts)
        if s["status"] == "screen_pass":
            result.append((r, s))
    return result


IA_MANAGED_CATEGORIES = (
    "management",
    "direct_discharge",
    "permeable_pavement",
    "existing_system_management",
)
OPEN_CATEGORIES = ("open_space", "open_space_direct_discharge")
# Manual Table 1 IARs; a green roof is "Rooftop Disconnection via Green Roof".
IAR_CATEGORIES = ("canopy", "roof_disconnection", "pavement_disconnection", "green_roof")
ECONOMIC_KEYS = (
    "documented",
    "modeled",
    "measurement_only",
    "documented_combined",
    "modeled_combined",
)


def _factors(direct, npdes):
    """Manual 4.3.5.1-4.3.5.4 maximum credit factors (config-loaded)."""
    if direct:
        return (
            factor("surface_discharge_npdes_factor" if npdes else "surface_discharge_factor"),
            factor(
                "surface_discharge_open_space_npdes_factor"
                if npdes
                else "surface_discharge_open_space_factor"
            ),
        )
    return (
        factor("non_surface_management_npdes_factor" if npdes else "non_surface_management_factor"),
        factor("managed_open_space_npdes_factor" if npdes else "managed_open_space_factor"),
    )


def _open_space_credit(area, curve_number, npdes):
    """Table A-2 open-space GA credit, read literally (the NPDES column gives 0.00 at
    CN >= 75 and 4.35% at CN 74). A credited open space is a GA credit, so with NPDES
    the property then receives the 7% residual only on uncredited IA (manual
    4.3.5.2); a resulting drop below the NPDES-alone credit is reported, not hidden."""
    rate = Decimal(str(open_space_factor(curve_number, npdes)))
    return area * rate, rate > 0


def _allocation_surfaces(geometry, case, gis):
    geometries = gis["measurement"]["geometries"]
    empty = {"type": "GeometryCollection", "geometries": []}
    ia_part = geometry.intersection(shape(geometries["physical_ia"]))
    open_part = geometry.intersection(shape(geometries.get("pervious") or empty))
    ia = _area_decimal(case_area_sqft(ia_part, case)) if not ia_part.is_empty else Decimal(0)
    open_area = (
        _area_decimal(case_area_sqft(open_part, case)) if not open_part.is_empty else Decimal(0)
    )
    return ia, open_area, _area_decimal(case_area_sqft(geometry, case)) - ia - open_area


def _existing_allocations(case, gis, baseline):
    """An approved itemized ledger must reconcile every recorded existing credit.

    Management/direct-discharge drainage areas may include open space (manual
    4.3.2.2, 4.3.3.1 notes): IA credit = factor x IA Managed; GA credit is the
    same amount, plus the open-space factor on the open part when that part was
    credited. ``open_space_direct_discharge`` is the GA-only 90% open-space
    surface-discharge credit of manual 4.3.3.1.
    """
    items = case.get("assessment", {}).get("existing_credit_allocations", [])
    if not items:
        return [], ["Detailed existing credit allocation ledger missing"]
    errors = []
    allocations = []
    totals = {key: Decimal(0) for key in ("ga_credit_sqft", "ia_credit_sqft", "iar_sqft")}
    tolerance = Decimal(".000001")
    for item in items:
        try:
            if item.get("facts", {}).get("approved_ledger_confirmed") is not True or not _evidence(
                item, case
            ):
                raise ValueError("Approved existing allocation evidence missing")
            geometry = shape(item["geometry"])
            area = _area_decimal(case_area_sqft(geometry, case))
            cat = item["category"]
            if (
                geometry.is_empty
                or not geometry.is_valid
                or geometry.geom_type not in ("Polygon", "MultiPolygon")
            ):
                raise ValueError("Invalid existing allocation geometry")
            extra = {}
            observed = {key: decimal(item.get(key, 0)) for key in totals}
            if cat in ("management", "direct_discharge"):
                ia_part, open_part, unresolved = _allocation_surfaces(geometry, case, gis)
                if unresolved > tolerance:
                    raise ValueError("Existing allocation includes unresolved surfaces")
                rate, open_rate = _factors(cat == "direct_discharge", False)
                ia_credit = ia_part * rate
                credited_open = (
                    open_part
                    if open_part > 0
                    and abs(observed["ga_credit_sqft"] - ia_credit - open_part * open_rate)
                    <= tolerance
                    else Decimal(0)
                )
                expected = {
                    "ga_credit_sqft": ia_credit + credited_open * open_rate,
                    "ia_credit_sqft": ia_credit,
                    "iar_sqft": Decimal(0),
                }
                extra = {
                    "area_sqft": float(ia_part),
                    "open_space_area_sqft": float(credited_open),
                    "drainage_area_sqft": float(area),
                }
            else:
                target = (
                    "pervious"
                    if cat in OPEN_CATEGORIES
                    else "canopy_ground_ia" if cat == "canopy" else "physical_ia"
                )
                if geometry.difference(shape(gis["measurement"]["geometries"][target])).area > 1e-8:
                    raise ValueError("Existing allocation is outside its physical area")
                if cat == "open_space":
                    expected = {
                        "ga_credit_sqft": area
                        * Decimal(str(open_space_factor(item["facts"]["curve_number"]))),
                        "ia_credit_sqft": Decimal(0),
                        "iar_sqft": Decimal(0),
                    }
                elif cat == "open_space_direct_discharge":
                    expected = {
                        "ga_credit_sqft": area * factor("surface_discharge_open_space_factor"),
                        "ia_credit_sqft": Decimal(0),
                        "iar_sqft": Decimal(0),
                    }
                elif cat in IAR_CATEGORIES:
                    expected = {
                        "ga_credit_sqft": Decimal(0),
                        "ia_credit_sqft": Decimal(0),
                        "iar_sqft": area
                        * (
                            factor("canopy_ground_ia_overlap_iar_factor")
                            if cat == "canopy"
                            else Decimal(1)
                        ),
                    }
                else:
                    raise ValueError("Unsupported existing allocation category")
            for key, value in expected.items():
                if abs(value - observed[key]) > tolerance:
                    raise ValueError("Existing allocation amount does not match supported rule")
                totals[key] += observed[key]
            allocations.append(
                {**deepcopy(item), "area_sqft": float(area), **extra, "existing": True}
            )
        except (ValueError, TypeError, KeyError, IndexError, AttributeError, ShapelyError) as exc:
            errors.append(str(exc))
    for key, total in totals.items():
        recorded = baseline.get("existing_" + key, 0)
        if recorded is None:
            errors.append(
                IAR_SPLIT_BLOCK if key == "iar_sqft" else "Recorded existing " + key + " unknown"
            )
            continue
        try:
            recorded = decimal(recorded)
        except ValueError:
            errors.append("Recorded existing " + key + " is not a valid number")
            continue
        if abs(total - recorded) > tolerance:
            errors.append("Existing allocation totals do not reconcile " + key)
    return allocations, errors


def _hypothetical_benefits(benefits):
    """Adapter alternatives (``system_pricing.price_benefit``) as ledger benefits.

    Each keeps its whole possible geometry for overlap checks while crediting its
    stated area (a weighted fraction may be smaller than the geometry). Saved case
    benefits are not credited alongside: each priced system is one alternative.
    """
    out = []
    errors = []
    for b in benefits:
        r = deepcopy(b)
        r.setdefault("basis", "modeled")
        r.setdefault("existing_overlap_reconciled", True)
        try:
            s = screen(r["category"], r["area_sqft"], r.get("evidence"))
        except (ValueError, KeyError) as exc:
            errors.append(str(exc))
            continue
        if s["status"] != "screen_pass":
            errors.append(
                "Alternative "
                + str(r.get("id"))
                + " prerequisites: "
                + ", ".join(s["failed"] + s["missing"])
            )
            continue
        out.append((r, s))
    return out, errors


UNDEVELOPED_INFERENCE = (
    "Inference, not a recorded classification: {failed} status infeasible given recorded "
    "credits ({reason}), so only the {chosen} alternative of tariff 4.3(a)(2)(i) can be billed. "
    "Confirm the BRT/OPA classification (tariff 1.0(p))."
)


def _economics(case, gis, records, as_of, tariff, hypothetical=None):
    """One ledger for every savings figure. Unknown undeveloped status on a parcel
    under 5,000 sq ft GA yields explicit developed/undeveloped alternatives (D6).
    When only one alternative can be billed (for example recorded credits exceed the
    25% undeveloped statutory IA), that one is used and labelled as an inference.

    ``hypothetical`` (list of benefits) replaces saved case benefits with adapter
    alternatives priced by this same ledger (D7); see ``_hypothetical_benefits``."""
    if case.get("assessment", {}).get("baseline_refresh", {}).get("status") == "pending_review":
        blocked = _blocked(
            ["New public billing/credit facts differ from the retained baseline; review required"]
        )
        return {"baseline": None, **{k: deepcopy(blocked) for k in ECONOMIC_KEYS}}
    baseline = case.get("baseline")
    if not baseline:
        return {
            "baseline": None,
            **{k: _blocked(["Billing baseline missing"]) for k in ECONOMIC_KEYS},
        }
    t = tariff or default_tariff()
    measured_ga = (gis.get("measurement") or {}).get("ga_sqft")
    if undeveloped_unknown(baseline, baseline.get("ga_sqft"), measured_ga, tariff=t):
        outputs = {
            name: _economics_once(
                case, {**baseline, "undeveloped": flag}, gis, records, as_of, t, hypothetical
            )
            for name, flag in STATUS_ALTERNATIVES
        }
        billed = [name for name, _ in STATUS_ALTERNATIVES if outputs[name].get("baseline")]
        if len(billed) == 1:
            chosen = billed[0]
            failed = next(name for name, _ in STATUS_ALTERNATIVES if name != chosen)
            reason = "; ".join((outputs[failed].get("documented") or {}).get("reasons") or [])
            out = outputs[chosen]
            note = UNDEVELOPED_INFERENCE.format(failed=failed, chosen=chosen, reason=reason)
            label = {
                "status": "inferred",
                "basis": "inference",
                "inferred": chosen,
                "infeasible": failed,
                "note": note,
            }
            out["undeveloped_status"] = label
            out["baseline"]["undeveloped_status"] = deepcopy(label)
            out["baseline"]["undeveloped_basis"] = "inference"
            for key in ECONOMIC_KEYS:
                if isinstance(out.get(key), dict) and out[key].get("status") == "calculated":
                    out[key]["assumptions"] = list(out[key].get("assumptions", [])) + [note]
            return out
        if not billed:
            return outputs[STATUS_ALTERNATIVES[0][0]]
        return merge_status_alternatives(outputs, ECONOMIC_KEYS, _blocked)
    return _economics_once(case, baseline, gis, records, as_of, t, hypothetical)


ALLOCATION_SENSITIVE = (
    "The parcel minimum binds and each account is billed it under the assumed equal allocation; "
    "the unknown actual allocation (Form A-1, manual 2.2.6; a 0% account is billed nothing) can "
    "change the total."
)
BASELINE_AREAS = {
    "ga_sqft": "recorded gross area (GrossArea)",
    "ia_sqft": "recorded impervious area (ImpervArea)",
}


def _baseline_area(baseline, key):
    value = baseline.get(key)
    if value is None:
        raise BaselineError(
            "The billing baseline does not state the "
            + BASELINE_AREAS[key]
            + "; the bill cannot be computed (missing evidence is not zero)."
        )
    try:
        return decimal(value, key)
    except ValueError:
        raise BaselineError(
            "The " + BASELINE_AREAS[key] + " is not a valid nonnegative number."
        ) from None


def _baseline_reason(exc):
    """A readable baseline failure; never a bare validator message."""
    text = str(exc)
    if isinstance(exc, BaselineError):
        return text
    if isinstance(exc, KeyError):
        return "Billing baseline cannot be computed: missing field " + text
    return "Billing baseline cannot be computed: " + text


def _economics_once(case, baseline, gis, records, as_of, t, hypothetical=None):
    try:
        common, allocation = bill_terms(baseline, t)
        if not RULES["effective_from"] <= as_of.isoformat() <= RULES["verified_through"]:
            raise BaselineError("Assessment date outside verified rule period")
        if not t["effective_from"] <= as_of.isoformat() <= t["verified_through"]:
            raise BaselineError("Assessment date outside verified tariff period")
        ga = _baseline_area(baseline, "ga_sqft")
        ia = _baseline_area(baseline, "ia_sqft")
        terms = recorded_credits(baseline, ga, ia, baseline.get("undeveloped"), t)
        cg = terms["recorded_ga_credit_sqft"]
        ci = terms["recorded_ia_credit_sqft"]
        ir = terms["recorded_iar_sqft"]
        recorded_npdes = terms["npdes"]
        base = monthly_bill(
            ga,
            ia,
            ga_credit_sqft=terms["ga_credit_sqft"],
            ia_credit_sqft=terms["ia_credit_sqft"],
            iar_sqft=terms["iar_sqft"],
            **common,
        )
    except (ValueError, KeyError) as exc:
        blocked = _blocked([_baseline_reason(exc)])
        return {"baseline": None, **{k: deepcopy(blocked) for k in ECONOMIC_KEYS}}
    if allocation:
        base["allocation_status"] = allocation
    base["iar_split"] = terms["iar_split"]
    if terms["assumptions"]:
        base["assumptions"] = list(terms["assumptions"])
    if recorded_npdes:
        base["npdes_credit"] = {
            "basis": "recorded NPDES credit",
            "representation": "area credits (manual 4.3.5.2)",
            "ga_credit_sqft": float(terms["npdes_ga_credit_sqft"]),
            "ia_credit_sqft": float(terms["npdes_ia_credit_sqft"]),
        }
    for field, target in (
        ("published_monthly_total", "published_difference"),
        ("actual_bill_total", "actual_bill_difference"),
    ):
        if baseline.get(field) is not None:
            try:
                base[target] = float(
                    cents(decimal(base["monthly_total"]) - decimal(baseline[field]))
                )
            except ValueError:
                pass
    vetoes = case_vetoes(case)
    residual_rate = factor("npdes_unmanaged_area_factor")
    minimum_credit_ga = factor("credit_minimum_gross_area_sqft")
    if hypothetical is None:
        legacy, hypothetical_errors = _legacy_benefits(case, gis), []
    else:
        legacy, hypothetical_errors = _hypothetical_benefits(hypothetical)

    def scenario(documented, use_measure=False, use_benefits=True):
        total_ga, total_ia = ga, ia
        active = [
            r
            for r in records
            if use_benefits
            and r["status"] == "screen_pass"
            and (not documented or r["basis"] == "documented")
        ]
        originals = {r["id"]: r for r in case.get("assessment", {}).get("records", [])}
        legacy_active = [
            (b, s)
            for b, s in legacy
            if use_benefits and (not documented or b.get("basis") == "documented")
        ]
        if not use_measure and not active and not legacy_active:
            return _blocked(
                (hypothetical_errors if use_benefits and not documented else [])
                + [
                    "No passing "
                    + ("documented" if documented else "reviewed")
                    + " existing-site or baseline benefits"
                ]
            )
        errors = []
        regions = []
        ledger = []
        notes = []
        new_ga = Decimal(0)
        new_ia = Decimal(0)
        new_iar = Decimal(0)
        if use_benefits and not documented:
            errors.extend(hypothetical_errors)
        if active or legacy_active:
            errors.extend(vetoes)
        # One NPDES representation (manual 4.3.5.2 area credits): a recorded NPDES
        # baseline and a passing NPDES record are the same credit.
        npdes = recorded_npdes or any(r["category"] == "industrial_npdes" for r in active)
        if use_measure:
            measurement = gis.get("measurement", {})
            if measurement.get("complete") is not True:
                errors.append("Complete physical IA/GA measurements are missing")
            else:
                total_ga = _area_decimal(measurement.get("ga_sqft"))
                total_ia = _area_decimal(measurement.get("ia_sqft"))
        existing = bool(cg or ci or ir)
        if terms["iar_split"] == "unknown" and (existing or npdes):
            errors.append(IAR_SPLIT_BLOCK)
        if (active or legacy_active) and total_ga < minimum_credit_ga:
            errors.append("Minimum parcel gross area for credit is 500 square feet")
        if existing and baseline.get("existing_credits_spatially_reconciled") is not True:
            errors.append("Existing aggregate credits require spatial reconciliation")
        supplied_allocations = bool(case.get("assessment", {}).get("existing_credit_allocations"))
        existing_allocations, allocation_errors = (
            _existing_allocations(case, gis, baseline)
            if existing or supplied_allocations
            else ([], [])
        )
        if allocation_errors and (supplied_allocations or existing):
            errors.extend(allocation_errors)
        uplift = bool(npdes)
        if existing_allocations and not allocation_errors:
            regions.extend((item["id"], shape(item["geometry"])) for item in existing_allocations)
            if uplift:
                # Manual 4.3.5.2/4.3.5.4: NPDES replaces 80/90% with 87/97%; the
                # recorded amounts are removed and recomputed, never added twice.
                new_ga = -cg
                new_ia = -ci
                new_iar = -ir
                for item in existing_allocations:
                    area = _area_decimal(item["area_sqft"])
                    cat = item["category"]
                    j = Decimal(0)
                    open_area = Decimal(0)
                    applied = True
                    if cat in ("management", "direct_discharge"):
                        rate, open_rate = _factors(cat == "direct_discharge", True)
                        open_area = _area_decimal(item.get("open_space_area_sqft", 0))
                        i = area * rate
                        g = i + open_area * open_rate
                    elif cat == "open_space":
                        g, applied = _open_space_credit(area, item["facts"]["curve_number"], True)
                        i = Decimal(0)
                    elif cat == "open_space_direct_discharge":
                        g = area * factor("surface_discharge_open_space_npdes_factor")
                        i = Decimal(0)
                    else:
                        g = i = Decimal(0)
                        j = decimal(item.get("iar_sqft", 0))
                    new_ga += g
                    new_ia += i
                    new_iar += j
                    ledger.append(
                        {
                            "id": item["id"],
                            "category": cat,
                            "area_sqft": float(area),
                            "open_space_area_sqft": float(open_area),
                            "credit_applied": applied,
                            "ga_credit_sqft": float(g),
                            "ia_credit_sqft": float(i),
                            "iar_sqft": float(j),
                            "existing": True,
                        }
                    )
        for r in active:
            if r["category"] == "industrial_npdes":
                continue
            source = originals[r["id"]]
            if existing and source.get("facts", {}).get("existing_overlap_reconciled") is not True:
                errors.append("New benefit overlap with existing credits is unreconciled")
            if r["category"] == "green_roof":
                # Manual Table 1 / 4.3.2.1: rooftop disconnection via green roof is an
                # IAR, a direct reduction of billable IA by the vegetated roof area.
                try:
                    roof = shape(source["footprint_geometry"])
                    if roof.is_empty or not roof.is_valid:
                        raise ValueError()
                except (ValueError, TypeError, KeyError, AttributeError, ShapelyError):
                    errors.append(
                        "Green roof "
                        + str(r["id"])
                        + " needs its documented roof footprint (manual 4.5.1 site plan)"
                    )
                    continue
                regions.append((r["id"], roof))
                j = _area_decimal(_green_roof_iar(roof, case, gis))
                new_iar += j
                ledger.append(
                    {
                        "id": r["id"],
                        "category": "green_roof",
                        "credit_path": "impervious_area_reduction",
                        "area_sqft": float(j),
                        "ga_credit_sqft": 0.0,
                        "ia_credit_sqft": 0.0,
                        "iar_sqft": float(j),
                        "rule": "manual Table 1 / 4.3.2.1: rooftop disconnection via green roof (IAR)",
                    }
                )
                continue
            region = shape(source["geometry"])
            regions.append((r["id"], region))
            managed_ia = r.get("managed_ia_sqft")
            a = _area_decimal(managed_ia if managed_ia is not None else r["managed_area_sqft"])
            rate, open_rate = _factors(r["category"] == "direct_discharge", npdes)
            open_area = (
                _area_decimal(r.get("managed_open_space_sqft") or 0)
                if (r.get("open_space_credit") or {}).get("status") == "screen_pass"
                else Decimal(0)
            )
            g = a * rate + open_area * open_rate
            i = a * rate
            new_ga += g
            new_ia += i
            ledger.append(
                {
                    "id": r["id"],
                    "category": r["category"],
                    "area_sqft": float(a),
                    "open_space_area_sqft": float(open_area),
                    "factor": float(rate),
                    "open_space_factor": float(open_rate) if open_area else None,
                    "ga_credit_sqft": float(g),
                    "ia_credit_sqft": float(i),
                    "iar_sqft": 0,
                }
            )
        for b, s in legacy_active:
            # An unlocated adapter unit sensitivity has no geometry; it cannot be
            # reconciled against recorded existing credits.
            if not b.get("geometry") and (existing or supplied_allocations):
                errors.append(
                    "Unlocated area cannot be reconciled against existing credit allocations"
                )
            region = shape(b.get("geometry") or {"type": "GeometryCollection", "geometries": []})
            regions.append((b["id"], region))
            a = _area_decimal(s["area_sqft"])
            cat = s["category"]
            applied = True
            if existing and b.get("existing_overlap_reconciled") is not True:
                errors.append("Baseline benefit overlap with existing credits is unreconciled")
            if cat == "management":
                g = i = a * _factors(False, npdes)[0]
                j = Decimal(0)
            elif cat == "open_space":
                g, applied = _open_space_credit(a, b["evidence"]["curve_number"], npdes)
                i = j = Decimal(0)
            else:
                g = i = Decimal(0)
                j = decimal(s["iar_sqft"])
            new_ga += g
            new_ia += i
            new_iar += j
            ledger.append(
                {
                    "id": b["id"],
                    "category": cat,
                    "area_sqft": float(a),
                    "credit_applied": applied,
                    "ga_credit_sqft": float(g),
                    "ia_credit_sqft": float(i),
                    "iar_sqft": float(j),
                }
            )
        for index, (identifier, region) in enumerate(regions):
            if any(region.intersection(other).area > 1e-8 for _, other in regions[:index]):
                errors.append("Overlapping physical allocations: " + str(identifier))

        def total(rows, cats, key="area_sqft", only_applied=False):
            return sum(
                (
                    _area_decimal(x.get(key) or 0)
                    for x in rows
                    if x["category"] in cats and (not only_applied or x.get("credit_applied", True))
                ),
                Decimal(0),
            )

        # Existing areas remain occupied even when their recorded credit amount
        # is preserved rather than recomputed. Percentage credits are not physical
        # area: an 800 sqft credit can reserve a full 1000 sqft management region.
        preserved = existing_allocations if not allocation_errors and not uplift else []
        rows = ledger + preserved
        managed = total(rows, IA_MANAGED_CATEGORIES)
        iar_area = total(rows, IAR_CATEGORIES)
        open_area = total(rows, OPEN_CATEGORIES) + total(
            rows, IA_MANAGED_CATEGORIES, "open_space_area_sqft"
        )
        reserved_aggregate_iar = ir if allocation_errors else Decimal(0)
        if managed + iar_area > total_ia - reserved_aggregate_iar:
            errors.append("Allocations exceed available physical impervious area")
        if open_area > total_ga - total_ia:
            errors.append("Open-space allocations exceed available physical open space")
        literal = None
        if npdes:
            # Manual 4.3.5.2, read literally (PWD confirmation pending): "Any remaining
            # uncredited IA area will receive 7% credit toward both the IA and GA square
            # footage"; only "if the property is not eligible for any GA or IA credits"
            # does it receive 7% of all IA and GA. Table A-2's NPDES column (0.00 at
            # CN >= 75, 4.35 at CN 74) agrees: uncredited open space keeps no 7%.
            other_ga, other_ia, other_iar = cg + new_ga, ci + new_ia, ir + new_iar
            has_other = other_ga > 0 or other_ia > 0 or other_iar > 0
            try:
                bia = billable_ia(total_ga, total_ia, baseline.get("undeveloped"), t)
            except ValueError as exc:
                errors.append(str(exc))
                bia = total_ia
            if has_other:
                uncredited = bia - other_iar - managed
                if uncredited < 0:
                    errors.append("NPDES residual area is negative")
                uncredited = max(Decimal(0), uncredited)
                residual_ia = residual_ga = uncredited * residual_rate
                rule = "manual 4.3.5.2: 7% of remaining uncredited IA, toward both IA and GA"
            else:
                uncredited = bia
                residual_ga, residual_ia = npdes_alone_credits(total_ga, bia)
                rule = "manual 4.3.5.2: no other GA or IA credit, 7% of IA and of GA"
            new_ia += residual_ia
            new_ga += residual_ga
            ledger.append(
                {
                    "id": "npdes-residual",
                    "category": "industrial_npdes",
                    "ga_credit_sqft": float(residual_ga),
                    "ia_credit_sqft": float(residual_ia),
                    "iar_sqft": 0,
                    "area_sqft": float(uncredited),
                    "rule": rule,
                }
            )
            if has_other and not existing and not supplied_allocations:
                literal = (
                    npdes_alone_credits(total_ga, bia),
                    other_ga + residual_ga,
                    other_ia + other_iar + residual_ia,
                )
        if ci + new_ia + ir + new_iar > total_ia:
            errors.append("Credits exceed remaining IA")
        if cg + new_ga > total_ga:
            errors.append("Credits exceed GA")
        if errors:
            return _blocked(errors)
        try:
            bill = monthly_bill(
                total_ga,
                total_ia,
                ga_credit_sqft=cg + new_ga,
                ia_credit_sqft=ci + new_ia,
                iar_sqft=ir + new_iar,
                **common,
            )
        except ValueError as exc:
            return _blocked([str(exc)])
        if literal is not None:
            note = _discontinuity_note(total_ga, total_ia, literal, bill, common)
            if note:
                notes.append(note)
        # Fix 9: a credit that pushes a multi-account parcel below the minimum.
        note = minimum_discontinuity(base, bill)
        if note:
            notes.append(note)
        saving = cents(decimal(base["monthly_total"]) - decimal(bill["monthly_total"]))
        basis = (
            "documented"
            if documented and baseline.get("actual_bill_verified") is True and not use_measure
            else "conditional"
        )
        assumptions = (
            ["Complete GIS measurements used; independent empirical validation still required"]
            if use_measure
            else []
        )
        assumptions += (
            []
            if baseline.get("actual_bill_verified")
            else ["Actual account bill, payer and special-rate enrollment are unverified"]
        )
        assumptions += list(terms["assumptions"])
        assumptions += [allocation["note"]] if allocation else []
        assumptions += [n["note"] for n in notes]
        assumptions += [
            "Gross current-rate illustration; no approval, award or realized savings asserted"
        ]
        out = {
            "status": "calculated",
            "basis": basis,
            "gross_monthly_reduction": float(saving),
            "gross_annual_reduction": float(saving * 12),
            "bill": bill,
            "ledger": {
                "existing_ga_credit_sqft": float(cg),
                "existing_ia_credit_sqft": float(ci),
                "existing_iar_sqft": float(ir),
                "allocations": ledger,
                "new_ga_credit_sqft": float(new_ga),
                "new_ia_credit_sqft": float(new_ia),
                "new_iar_sqft": float(new_iar),
            },
            "assumptions": assumptions,
        }
        if notes:
            out["manual_rule_discontinuity"] = notes[0]
            if len(notes) > 1:
                out["manual_rule_discontinuities"] = notes
        return out

    output = {
        "baseline": base,
        "documented": scenario(True),
        "modeled": scenario(False),
        "measurement_only": scenario(True, True, False),
        "documented_combined": scenario(True, True),
        "modeled_combined": scenario(False, True),
        "tariff": t,
        "billed_area_check": billed_area_check(baseline, base),
        "claim": "One baseline minus one reconciled final bill; annual reduction is twelve times monthly. No refund included.",
    }
    # Tariff 4.3(a)(8) equal default under an unknown allocation: when a per-account
    # minimum binds, the actual (unknown) Form A-1 allocation can change the total.
    if (
        allocation
        and len(base["accounts"]) > 1
        and (
            base.get("minimum_applied")
            or any(
                ((output.get(k) or {}).get("bill") or {}).get("minimum_applied")
                for k in ECONOMIC_KEYS
            )
        )
    ):
        output["allocation_sensitive"] = True
        base["allocation_sensitive"] = True
        base["assumptions"] = list(base.get("assumptions", [])) + [ALLOCATION_SENSITIVE]
    return output


def _discontinuity_note(total_ga, total_ia, literal, bill, common):
    """Manual 4.3.5.2 read literally is discontinuous: the first other GA or IA credit
    replaces 7% of all IA and GA with 7% of the remaining uncredited IA. When that
    lowers a credit total below the NPDES-alone credit, say so with both bills."""
    (alone_ga, alone_ia), ga_total, ia_side = literal
    if ga_total >= alone_ga and ia_side >= alone_ia:
        return None
    try:
        alone_total = monthly_bill(
            total_ga, total_ia, ga_credit_sqft=alone_ga, ia_credit_sqft=alone_ia, **common
        )["monthly_total"]
    except ValueError:
        alone_total = None
    parts = []
    if ga_total < alone_ga:
        parts.append(
            f"the GA credit falls from {float(alone_ga):,.2f} to {float(ga_total):,.2f} sq ft"
        )
    if ia_side < alone_ia:
        parts.append(
            f"the IA-side credit falls from {float(alone_ia):,.2f} to {float(ia_side):,.2f} sq ft"
        )
    text = (
        "Manual rule discontinuity (manual 4.3.5.2 read literally): once any other GA or IA "
        "credit applies, the 7% NPDES credit covers only the remaining uncredited IA (toward "
        "both IA and GA) instead of 7% of all IA and GA, so "
        + " and ".join(parts)
        + ". NPDES alone would bill "
        + (f"${alone_total:,.2f}" if alone_total is not None else "an uncomputed amount")
        + f"/month; this scenario bills ${bill['monthly_total']:,.2f}/month. PWD confirmation is "
        "needed; the customer may decline the other credit."
    )
    return {
        "kind": "manual_rule_discontinuity",
        "rule": "manual 4.3.5.2",
        "note": text,
        "npdes_alone_ga_credit_sqft": float(alone_ga),
        "npdes_alone_ia_credit_sqft": float(alone_ia),
        "scenario_ga_credit_sqft": float(ga_total),
        "scenario_ia_side_credit_sqft": float(ia_side),
        "npdes_alone_monthly_total": alone_total,
        "scenario_monthly_total": bill["monthly_total"],
        "bill_higher_than_npdes_alone": alone_total is not None
        and bill["monthly_total"] > alone_total,
    }


def _research_receiver_vetoes(case, run, gsi_features):
    """{receiver_id: reasons} for research catchments whose receiver is linked to a
    rejected record or one with known-false prerequisites. Uses the one receiver
    resolver (``model_assessment.receiver_links`` / ``record_vetoes``), so research
    never re-prices a receiver that catchment alternatives block (R2)."""
    from .model_assessment import receiver_links

    pseudo = {
        "name": "research",
        "catchments": [
            {"kind": "gsi", "receiver_id": str(c["gsi_id"]), "geometry": c.get("geometry")}
            for c in run.get("catchments", [])
            if c.get("gsi_id") is not None
        ],
    }
    integration = {
        "receiving_features": [
            {"gsi_id": str(f["gsi_id"]), "geometry": f["geometry"]}
            for f in gsi_features
            if f.get("gsi_id") is not None and f.get("geometry")
        ]
    }
    table = receiver_links(case, integration, [pseudo]).get("research", {})
    out = {}
    for receiver, rows in table.items():
        reasons = [reason for row in rows for reason in row["vetoes"]]
        if reasons:
            out[receiver] = list(dict.fromkeys(reasons))
    return out


def research_economics(case, gis, records, as_of, tariff):
    """Counterfactual management value of frozen modeled catchments, never a fact.

    Reuse the existing reconciled ledger/minima/rule blocks. Assumed prerequisites
    live only in a local copy; no confirmed record or evidence is persisted.
    Catchments whose receivers are linked to rejected or vetoed records are removed
    from the priced region and listed; if none remain the scenario is blocked.
    """
    research = gis.get("research_drainage", {})
    if not research.get("primary"):
        return {"status": "unavailable", "scenarios": []}
    from shapely.geometry import mapping
    from drainage_core.geometry import union

    reserved = []
    for r in case.get("assessment", {}).get("existing_credit_allocations", []) + case.get(
        "assessment", {}
    ).get("records", []):
        if r.get("geometry") and r.get("decision") != "rejected":
            try:
                reserved.append(shape(r["geometry"]))
            except (ValueError, TypeError, ShapelyError):
                pass
    for f in effective_features(case):
        if f.get("properties", {}).get("layer") == "benefit":
            reserved.append(shape(f["geometry"]))
    occupied = union(reserved)
    scenarios = []
    # H16: surface GSI receivers' own beds are never contributing IA.
    from drainage_core.research import feature_inputs

    try:
        gsi_features = [f for f in feature_inputs(case)[0] if f.get("role") == "gsi"]
    except (ValueError, TypeError, KeyError, ShapelyError):
        gsi_features = []
    try:
        beds = union(
            [
                shape(f["geometry"])
                for f in gsi_features
                if shape(f["geometry"]).geom_type in ("Polygon", "MultiPolygon")
            ]
        )
    except (ValueError, TypeError, KeyError, ShapelyError):
        beds = union([])
    # Unknown prerequisites are assumed below; known-false ones are not (R1).
    vetoes = case_vetoes(case)
    assumed = {
        key: True
        for key in (
            "physical_area_confirmed",
            "parcel_allocation_confirmed",
            "account_current",
            "routing_confirmed",
            "approved_record_drawings",
            "current_condition_confirmed",
            "maintenance_documented",
            "professional_reviewed",
        )
    }
    assumed["treatment_depth_inches"] = 1.5
    from .system_pricing import catchment_route, combine_routes

    for name, run in [("nominal", research["primary"])] + [
        (r["name"], r) for r in research.get("sensitivity", [])
    ]:
        # R2: receivers linked to rejected/vetoed records are never re-priced here.
        vetoed = _research_receiver_vetoes(case, run, gsi_features)
        kept = [c for c in run.get("catchments", []) if str(c.get("gsi_id")) not in vetoed]
        excluded = [
            {"receiver_id": receiver, "reasons": reasons}
            for receiver, reasons in sorted(vetoed.items())
        ]
        removed = union(
            [
                shape(c["geometry"])
                for c in run.get("catchments", [])
                if str(c.get("gsi_id")) in vetoed and c.get("geometry")
            ]
        )
        # D2: one per-catchment rule (app and pilot). Partial catchments are priced
        # in-window and labelled; untestable extent or a failed invariant blocks.
        route = combine_routes(catchment_route(c, run.get("invariants")) for c in kept)
        known = shape(run["known_ia_union_geometry"])
        unknown = shape(
            run.get("unknown_ground_union_geometry")
            or {"type": "GeometryCollection", "geometries": []}
        )
        if not removed.is_empty:
            known = known.difference(removed)
            unknown = unknown.difference(removed)
        hypotheses = [("known_ground_only", known, False)]
        if not unknown.is_empty:
            hypotheses.append(("unknown_ground_assumed_impervious", known.union(unknown), True))
        for surface_basis, raw_region, assume_unknown in hypotheses:
            region = raw_region.difference(occupied)
            bed_area = case_area_sqft(region.intersection(beds), case) if not beds.is_empty else 0.0
            region = region.difference(beds)
            scenario_assumptions = deepcopy(assumed)
            scenario_assumptions["existing_installation"] = True
            view = gis
            if assume_unknown:
                scenario_assumptions["all_unclassified_catchment_ground_is_impervious"] = True
                # Counterfactual policy view only: original physical measurement
                # and unknown geometry in the frozen GIS artifact stay unchanged.
                geoms = {
                    **gis["measurement"]["geometries"],
                    "physical_ia": mapping(
                        shape(gis["measurement"]["geometries"]["physical_ia"]).union(unknown)
                    ),
                }
                view = {**gis, "measurement": {**gis["measurement"], "geometries": geoms}}
            if vetoes:
                s = _blocked(vetoes)
            elif excluded and not kept:
                s = _blocked(
                    [
                        "Receiver "
                        + item["receiver_id"]
                        + " is not re-priced: "
                        + "; ".join(item["reasons"])
                        for item in excluded
                    ]
                )
            elif route["blocked_reasons"]:
                s = _blocked(route["blocked_reasons"])
            elif region.is_empty or case_area_sqft(region, case) < 0.000001:
                s = _blocked(
                    [
                        "No unallocated known impervious area modeled to GSI; unknown surfaces and missing connections are not zero-area evidence"
                    ]
                )
            else:
                working = deepcopy(case)
                working["features"]["features"].append(
                    {
                        "type": "Feature",
                        "id": "research-management-counterfactual",
                        "geometry": mapping(region),
                        "properties": {
                            "layer": "benefit",
                            "benefit": {
                                "id": "research-management-counterfactual",
                                "category": "management",
                                "area_sqft": case_area_sqft(region, case),
                                "basis": "modeled",
                                "existing_overlap_reconciled": True,
                                "evidence": scenario_assumptions,
                            },
                        },
                    }
                )
                s = _economics(working, view, records, as_of, tariff)["modeled"]
            scenarios.append(
                {
                    **s,
                    "name": name + " / " + surface_basis,
                    "basis": "conditional research scenario",
                    "route_state": route["route_state"],
                    "route_state_reason": route["route_state_reason"],
                    "partial_label": route["partial_label"],
                    "surface_assumption": surface_basis,
                    "modeled_unallocated_area_sqft": case_area_sqft(region, case),
                    "system_bed_ia_excluded_sqft": bed_area,
                    "excluded_receivers": deepcopy(excluded),
                    "assumed_prerequisites": scenario_assumptions,
                    "claim": "Counterfactual: only if the modeled existing system meets all management prerequisites and the stated ground assumption holds. No screen pass, approval or treatment capacity is established.",
                }
            )
    return {
        "status": "conditional",
        "scenarios": scenarios,
        "claim": "Alternatives to the existing assessment, never additional savings to sum; physical/credit evidence is unchanged.",
    }


def historical_flags(case, economics):
    """Review flags retain periods and evidence; do not calculate recoveries."""
    baseline = case.get("baseline") or {}
    flags = []
    base = economics.get("baseline") or {}
    for observed_field, label in (
        ("actual_bill_total", "Actual bill"),
        ("published_monthly_total", "Public snapshot"),
    ):
        observed = baseline.get(observed_field)
        if observed is None or base.get("monthly_total") is None:
            continue
        try:
            delta = cents(decimal(base["monthly_total"]) - decimal(observed))
        except ValueError:
            continue
        if delta:
            flags.append(
                {
                    "kind": "billing_discrepancy",
                    "status": "review_only",
                    "affected_from": baseline.get("bill_date"),
                    "affected_through": baseline.get("bill_period_end", baseline.get("bill_date")),
                    "observed_discrepancy": float(delta),
                    "basis": label + " differs from current tariff illustration",
                    "source_basis": deepcopy(baseline.get("source", case.get("sources", []))),
                    "missing": [
                        "Applicable historical tariff",
                        "Actual invoices and account allocations",
                        "Award/effective-period records",
                    ],
                    "refund_entitlement": None,
                    "claim": "Review issue only; no refund or historical debt determined",
                }
            )
    checks = economics.get("billed_area_check") or {}
    alternatives = checks.get("alternatives") if checks.get("status") == "alternatives" else None
    consistent = [
        name
        for name, check in (alternatives or {}).items()
        if (check or {}).get("status") == "consistent"
    ]
    if checks.get("status") == "mismatch" or (
        alternatives
        and not consistent
        and any((c or {}).get("status") == "mismatch" for c in alternatives.values())
    ):
        flags.append(
            {
                "kind": "billed_area_discrepancy",
                "status": "review_only",
                "affected_from": baseline.get("bill_date"),
                "affected_through": baseline.get("bill_period_end", baseline.get("bill_date")),
                "rows": deepcopy(checks.get("rows") if not alternatives else alternatives),
                "basis": "PWD FinalGross/FinalImperv differ from the computed final and billed areas",
                "missing": [
                    "Recorded credit schedule and order",
                    "Undeveloped/statutory IA basis",
                    "Actual invoices",
                ],
                "refund_entitlement": None,
                "claim": "Validation flag only; no correction, refund or historical debt determined",
            }
        )
    elif alternatives and consistent:
        flags.append(
            {
                "kind": "billed_area_status_evidence",
                "status": "review_only",
                "consistent_alternatives": consistent,
                "rows": deepcopy(alternatives),
                "claim": "PWD billed areas are consistent with the listed undeveloped-status alternative(s); confirm the status with the property record before choosing one",
            }
        )
    for record in case.get("assessment", {}).get("historical_issues", []):
        flags.append(
            {
                **deepcopy(record),
                "status": "review_only",
                "refund_entitlement": None,
                "claim": "Manually recorded issue for review; excluded from ongoing savings",
            }
        )
    return flags


def evaluate_assessment(case, gis_result, as_of=None, tariff=None):
    assessment = case.get("assessment", {})
    _validate_assessment_inputs(assessment)
    validate_references(
        {
            **assessment,
            "records": assessment.get("records", [])
            + assessment.get("existing_credit_allocations", []),
        }
    )
    day = _day(as_of) if as_of else date.today()
    records = []
    for record in case.get("assessment", {}).get("records", []):
        if record.get("category") in LABELS:
            records.append(screen_record(record, case, gis_result, day))
    categories = []
    for category, label in LABELS.items():
        selected = [r for r in records if r["category"] == category]
        statuses = {r["status"] for r in selected}
        status = (
            "screen_pass"
            if "screen_pass" in statuses
            else (
                "missing_evidence"
                if not selected
                else (
                    "candidate"
                    if "candidate" in statuses
                    else (
                        "requirements_failed"
                        if "requirements_failed" in statuses
                        else "missing_evidence" if "missing_evidence" in statuses else "rejected"
                    )
                )
            )
        )
        categories.append(
            {
                "category": category,
                "label": label,
                "status": status,
                "records": selected,
                "missing": ["No reviewed evidence records supplied"] if not selected else [],
                "managed_area_sqft": (
                    None
                    if not selected
                    else (
                        sum(
                            r["managed_area_sqft"]
                            for r in selected
                            if r["managed_area_sqft"] is not None
                        )
                        if any(r["managed_area_sqft"] is not None for r in selected)
                        else None
                    )
                ),
            }
        )
    economics = _economics(case, gis_result, records, day, tariff)
    from .model_assessment import integrate as integrate_models

    modeled = integrate_models(case, gis_result, records, day, tariff)
    for info in modeled.get("records", []):
        for record in records:
            if record["id"] == info["record_id"]:
                record["modeled_context"] = info
    for category in categories:
        if category["category"] in modeled.get("category_context", {}):
            category["modeled_context"] = modeled["category_context"][category["category"]]
    result = {
        "rule_version": VERSION,
        "as_of": day.isoformat(),
        "categories": categories,
        "economics": economics,
        "modeled_integration": modeled,
        "research_drainage_scenarios": research_economics(case, gis_result, records, day, tariff),
        # Fix 3: on-parcel mapped systems as leads; a list B2's summary can show.
        "existing_system_management": existing_system_leads(
            case, gis_result, records, day, tariff
        ),
        "historical_flags": historical_flags(case, economics),
        "rules": {
            **deepcopy(RULES),
            "applicability": (
                "applicable"
                if RULES["effective_from"] <= day.isoformat() <= RULES["verified_through"]
                else "outside_verified_period"
            ),
        },
    }
    from .curve_number import worksheet, finance_scenario

    result["systems_without_recorded_credit"] = deepcopy(
        result["existing_system_management"]["systems_without_recorded_credit"]
    )
    sheet = result["open_space_curve_number"] = worksheet(case, gis_result)
    if result["rules"]["applicability"] != "applicable":
        sheet["credit_factor"] = None
        if sheet.get("ub_candidate"):
            sheet["ub_candidate"]["credit_factor"] = None
        sheet["issues"].append("Outside verified PWD policy period; credit factor unavailable")
    # A5: the worksheet CN priced only as a labelled conditional scenario (never a screen pass).
    sheet["finance_scenario"] = finance_scenario(
        case, gis_result, sheet, records, day, tariff, economics
    )
    sheet.pop("worksheet_sha256", None)
    sheet["worksheet_sha256"] = sha256(
        json.dumps(sheet, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
    ).hexdigest()
    from drainage_core.quality import artifact_quality

    if artifact_quality(gis_result)["status"] == "outdated":
        from .quality import safe_analysis

        result = safe_analysis({**gis_result, "assessment": result})["assessment"]
    result["baseline_refresh"] = deepcopy(assessment.get("baseline_refresh"))
    result["assessment_sha256"] = sha256(
        json.dumps(result, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
    ).hexdigest()
    return result
