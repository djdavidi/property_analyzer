"""PWD Appendix A worksheet over frozen mapped areas. No routing or awards."""

from copy import deepcopy
import re
from decimal import Decimal
from hashlib import sha256
from math import isfinite
from shapely.geometry import shape, mapping
from drainage_core.geometry import effective_features, union, reproject, case_area_sqft
from drainage_core.sources import canonical, now
from .rules import MANUAL_URL, open_space_factor
from .soil_sources import boundary_hash
from .physical_reuse import normalize_numbers

VERSION = "pwd-open-space-cn-2026-09-v1"
# Table A-1, September 2026; columns A, B, C, D, Ub. No soil default.
TABLE = {
    "lawn": {
        "poor": [68, 79, 86, 89, 79],
        "fair": [49, 69, 79, 84, 69],
        "good": [39, 61, 74, 80, 61],
    },
    "meadow": {"na": [30, 58, 71, 78, 58]},
    "athletic_field": {"na": [68, 79, 86, 89, 79]},
    "porous_turf": {"na": [70, 70, 79, 84, 69]},
    "brush": {
        "poor": [57, 73, 82, 86, 73],
        "fair": [43, 65, 76, 82, 65],
        "good": [32, 58, 72, 79, 58],
    },
    "woods_grass": {
        "poor": [57, 73, 82, 86, 73],
        "fair": [43, 65, 76, 82, 65],
        "good": [32, 58, 72, 79, 58],
    },
    "woods": {
        "poor": [45, 66, 77, 83, 66],
        "fair": [36, 60, 73, 79, 60],
        "good": [30, 55, 70, 77, 55],
    },
    "gravel": {"na": [76, 85, 89, 91, 89]},
    "dirt": {"na": [72, 82, 87, 89, 87]},
    "water": {"na": [100, 100, 100, 100, 100]},
}
GROUPS = ["A", "B", "C", "D", "UB"]
EMPTY = {"type": "GeometryCollection", "geometries": []}


def soil_groups(properties):
    """All components must account for 100% and agree for an exact mapped HSG.

    Components are not spatially located inside their map unit. Do not assign
    dominant-component percentages to invented sub-parcel polygons.
    """
    parts = properties.get("components", [])
    groups = set()
    total = 0.0
    reasons = []
    if not parts:
        return None, [], ["Soil component information missing"]
    for p in parts:
        try:
            pct = float(p["comppct_r"])
            if isinstance(p["comppct_r"], bool) or not isfinite(pct) or not 0 < pct <= 100:
                raise ValueError()
        except (KeyError, TypeError, ValueError):
            reasons.append("Soil component percentage missing or invalid")
            continue
        total += pct
        group = str(p.get("hydgrp") or "").strip().upper()
        if group in GROUPS:
            groups.add(group)
        elif group in ("A/D", "B/D", "C/D"):
            groups.update(group.split("/"))
            reasons.append("Dual soil group needs drainage evidence")
        else:
            reasons.append("Soil hydrologic group missing or unsupported")
    if abs(total - 100) > 0.01:
        reasons.append("Soil component percentages do not total 100%")
    if len(groups) > 1:
        reasons.append("Soil components do not establish a unique site group")
    # Incomplete groups cannot yield even a reliable candidate range.
    possible = (
        sorted(groups, key=GROUPS.index)
        if not any("missing" in r or "percent" in r for r in reasons)
        else []
    )
    return (
        (possible[0] if len(possible) == 1 and not reasons else None),
        possible,
        list(dict.fromkeys(reasons)),
    )


def review_scope(case):
    # Reviews are conditional on the mapped features and original image lineage.
    # A changed surface/model/boundary must not inherit a previous interpretation.
    return sha256(
        canonical(
            normalize_numbers(
                {
                    k: case.get(k)
                    for k in ("crs", "parcel", "features", "corrections", "imagery_age_policy")
                }
            )
        )
    ).hexdigest()


def _cover(properties, override):
    cover = override.get("cover", properties.get("cn_cover"))
    condition = override.get("condition", properties.get("cn_condition"))
    if cover == "lawn" and not condition:
        pct = properties.get("grass_cover_percent")
        if (
            isinstance(pct, (int, float))
            and not isinstance(pct, bool)
            and isfinite(pct)
            and 0 <= pct <= 100
        ):
            condition = "poor" if pct < 50 else "fair" if pct <= 75 else "good"
    if cover in TABLE and set(TABLE[cover]) == {"na"}:
        condition = "na"
    return cover, condition


def worksheet(case, gis):
    measurement = gis["measurement"]
    parcel = shape(case["parcel"])
    area = lambda g: case_area_sqft(g, case)
    physical = shape(measurement["geometries"]["pervious"])
    unknown = shape(measurement["geometries"]["unknown"])
    a = case.get("assessment", {})
    snapshot = a.get("soil_snapshot") or {}
    issues = []
    usable = snapshot.get("status") in ("retrieved", "cached_after_failure")
    if snapshot.get("boundary_sha256") != boundary_hash(case):
        usable = False
        issues.append("Soil snapshot missing or does not match current parcel boundary")
    if (
        snapshot.get("snapshot_sha256")
        and snapshot["snapshot_sha256"]
        != sha256(
            canonical({k: v for k, v in snapshot.items() if k != "snapshot_sha256"})
        ).hexdigest()
    ):
        usable = False
        issues.append("Soil snapshot content hash mismatch")
    soils = []
    if usable:
        for f in snapshot.get("features", []):
            g = reproject(shape(f["geometry"]), snapshot["crs"], case["crs"]).intersection(parcel)
            if not g.is_empty and g.area > 0:
                soils.append((f, g))
    else:
        issues.append(
            snapshot.get("error") or "Public soil data have not been acquired successfully"
        )
    soil_conflicts = union(
        [g.intersection(h) for i, (_, g) in enumerate(soils) for _, h in soils[i + 1 :]]
    )
    soil_conflicts = _area_only(soil_conflicts)
    soil_union = union([g for _, g in soils])
    patches = []
    for f in effective_features(case):
        p = f.get("properties", {})
        if p.get("layer") == "surface" and p.get("class") == "pervious":
            g = _area_only(shape(f["geometry"]).intersection(physical))
            if not g.is_empty:
                patches.append((str(f["id"]), g, p, "mapped_open_space"))
    # Conservative observations take precedence over modeled grass/soil candidates.
    ai = gis.get("modeled_integration", {}).get("ai", {})
    if ai.get("status") == "modeled":
        for cls in ("grass_shrub", "bare_soil"):
            g = _area_only(shape(ai.get("geometries", {}).get(cls, EMPTY)).intersection(unknown))
            if not g.is_empty:
                patches.append(("image-" + cls, g, {"image_class": cls}, "image_candidate"))
    patch_conflicts = _area_only(
        union(
            [
                g.intersection(h)
                for i, (_, g, _, _) in enumerate(patches)
                for _, h, _, _ in patches[i + 1 :]
            ]
        )
    )
    rows = []
    soil_reviews = (
        a.get("soil_group_reviews", {}) if isinstance(a.get("soil_group_reviews"), dict) else {}
    )

    def add(fid, g, p, basis, soil=None, extra=None):
        if g.is_empty or area(g) < 0.001:
            return
        saved_override = a.get("open_space_inputs", {}).get(fid, {})
        stale = bool(saved_override and saved_override.get("scope_sha256") != review_scope(case))
        override = {} if stale else saved_override
        cover, condition = _cover(p, override)
        missing = list(extra or [])
        if stale:
            missing.append("Previous cover review is stale after mapped-input change")
        group = None
        possible = []
        soil_basis = None
        soil_review = None
        ub_eligible = False
        ub_note = None
        if soil:
            group, possible, reasons = soil_groups(soil["properties"])
            if group:
                soil_basis = "mapped SSURGO components"
            else:
                # B8: UB is a reviewer choice for urban-soil components, never inferred.
                ub_eligible, ub_note = ub_eligibility(soil["properties"])
                review = soil_reviews.get(str(soil["properties"].get("mukey")))
                if isinstance(review, dict) and review.get("group") == "UB":
                    soil_review = {**deepcopy(review), "status": "applied"}
                    if review.get("components_sha256") != components_digest(soil["properties"]):
                        soil_review["status"] = "stale"
                        reasons = reasons + [
                            "Previous soil review is stale after soil record change"
                        ]
                    elif not ub_eligible:
                        soil_review["status"] = "not_applicable"
                        reasons = reasons + ["Reviewed UB choice no longer applies: " + ub_note]
                    else:
                        group, possible, reasons, soil_basis = (
                            "UB",
                            ["UB"],
                            [],
                            "reviewer choice (UB, evidence-tagged)",
                        )
            missing += reasons
        else:
            missing.append("Soil group unknown")
        if cover not in TABLE:
            missing.append("PWD cover type unknown")
        elif condition not in TABLE[cover]:
            missing.append("Cover condition unknown")
        values = []
        ub_values = []
        covers = (
            [cover]
            if cover in TABLE
            else (
                ["lawn", "brush"]
                if p.get("image_class") == "grass_shrub"
                else ["dirt"] if p.get("image_class") == "bare_soil" else []
            )
        )
        for c in covers:
            conditions = [condition] if condition in TABLE[c] else list(TABLE[c])
            for cond in conditions:
                values.extend(TABLE[c][cond][GROUPS.index(s)] for s in possible)
                ub_values.append(TABLE[c][cond][GROUPS.index("UB")])
        exact = (
            TABLE[cover][condition][GROUPS.index(group)]
            if group and cover in TABLE and condition in TABLE[cover] and not extra
            else None
        )
        candidate_ub = group is None and ub_eligible and not extra
        ub_exact = (
            TABLE[cover][condition][GROUPS.index("UB")]
            if candidate_ub and cover in TABLE and condition in TABLE[cover]
            else None
        )
        sqft = area(g)
        rows.append(
            {
                "feature_id": fid,
                "basis": basis,
                "input_basis": "manual review" if override else "mapped attributes",
                "cover_reviewed": bool(override) or p.get("reviewed") is True,
                "area_sqft": sqft,
                "geometry": mapping(g),
                "cover": cover,
                "condition": condition,
                "image_class": p.get("image_class"),
                "soil_group": group,
                "possible_soil_groups": possible,
                "soil_basis": soil_basis,
                "soil_review": soil_review,
                "mapunit_key": soil["properties"].get("mukey") if soil else None,
                "mapunit_name": soil["properties"].get("mapunit_name") if soil else None,
                "soil_polygon_id": soil.get("id") if soil else None,
                "soil_components": (
                    deepcopy(soil["properties"].get("components", [])) if soil else []
                ),
                "curve_number": exact,
                "area_times_cn": sqft * exact if exact is not None else None,
                "candidate_cn_min": min(values) if values and not extra else None,
                "candidate_cn_max": max(values) if values and not extra else None,
                "ub_choice_available": bool(ub_eligible and group is None),
                "ub_candidate_cn": ub_exact,
                "ub_candidate_cn_min": min(ub_values) if candidate_ub and ub_values else None,
                "ub_candidate_cn_max": max(ub_values) if candidate_ub and ub_values else None,
                "status": "calculated_conditional" if exact is not None else "unknown_inputs",
                "missing": list(dict.fromkeys(missing)),
                "cover_source": {
                    k: deepcopy(p[k])
                    for k in (
                        "source_family",
                        "source_url",
                        "source_sha256",
                        "model_sha256",
                        "acquisition_date",
                        "source_vintage",
                    )
                    if k in p
                },
                "review": deepcopy(saved_override),
                "review_stale": stale,
            }
        )

    for fid, g, p, basis in patches:
        conflict = g.intersection(patch_conflicts)
        clean = g.difference(patch_conflicts)
        # Emit each conflicting area once; no arbitrary first-feature preference.
        if not conflict.is_empty:
            patches_conflict_seen = union(
                [shape(r["geometry"]) for r in rows if r["feature_id"] == "conflicting-open-space"]
            )
            add(
                "conflicting-open-space",
                conflict.difference(patches_conflict_seen),
                {},
                basis,
                extra=["Overlapping open-space cover inputs"],
            )
        add(
            fid,
            clean.intersection(soil_conflicts),
            p,
            basis,
            extra=["Overlapping soil polygons; unique soil assignment unknown"],
        )
        clean = clean.difference(soil_conflicts)
        for soil, sg in soils:
            add(fid, clean.intersection(sg), p, basis, soil)
        add(fid, clean.difference(soil_union), p, basis, extra=["Soil polygon coverage missing"])
    # Frozen pervious geometry may be supplied without detailed feature records.
    mapped_union = union([g for _, g, _, basis in patches if basis == "mapped_open_space"])
    add(
        "unattributed-open-space",
        physical.difference(mapped_union),
        {},
        "mapped_open_space",
        extra=["Mapped open space has no cover feature"],
    )
    mapped = [r for r in rows if r["basis"] == "mapped_open_space"]
    candidates = [r for r in rows if r["basis"] == "image_candidate"]
    # Appendix A steps 3-5: sum(area x CN) / sum(area). Summed in Decimal so a
    # uniform CN61 split into strips averages to exactly 61 (review B4).
    d_total = sum((_dec(r["area_sqft"]) for r in mapped), Decimal(0))
    d_known = sum(
        (_dec(r["area_sqft"]) for r in mapped if r["curve_number"] is not None), Decimal(0)
    )
    d_product = sum(
        (
            _dec(r["area_sqft"]) * Decimal(r["curve_number"])
            for r in mapped
            if r["curve_number"] is not None
        ),
        Decimal(0),
    )
    total = float(d_total)
    known = float(d_known)
    product = float(d_product)
    complete = total > 0.000001 and total - known < 0.001
    d_average = d_product / d_total if complete else None
    average = float(d_average) if d_average is not None else None
    unresolved = area(unknown)
    # A complete mapped subset still cannot establish all open space on an
    # incompletely mapped parcel. Keep that average separate from property CN.
    property_cn = average if average is not None and unresolved < 0.001 else None
    d_property_cn = d_average if property_cn is not None else None
    if unresolved >= 0.001:
        issues.append(
            "Unresolved ground may contain additional open space; property-wide CN unknown"
        )
    if not total:
        issues.append("No confirmed mapped open-space area; absence is not established")
    if total - known >= 0.001:
        issues.append("Open-space rows have unresolved cover, condition or soil inputs")
    output = {
        "version": VERSION,
        "status": "calculated_conditional" if property_cn is not None else "incomplete",
        "average_cn": property_cn,
        "mapped_open_space_average_cn": average,
        "known_portion_average_cn": float(d_product / d_known) if d_known else None,
        "mapped_open_space_sqft": total if total else None,
        "known_cn_area_sqft": known if total else None,
        "unknown_cn_area_sqft": float(d_total - d_known) if total else None,
        "image_candidate_area_sqft": (
            sum(r["area_sqft"] for r in candidates) if ai.get("status") == "modeled" else None
        ),
        "unresolved_ground_sqft": unresolved,
        "total_area_times_cn": product if complete else None,
        "credit_factor": open_space_factor(d_property_cn) if d_property_cn is not None else None,
        "rows": rows,
        "issues": list(dict.fromkeys(issues)),
        "area_tolerance_sqft": 0.001,
        "formula": "Average CN = sum(area × CN) / total open-space area; impervious areas excluded",
        "lookup_sha256": sha256(canonical(TABLE)).hexdigest(),
        "rule_source": {
            "url": MANUAL_URL,
            "sha256": "5c7b6e87ae442731625b91e278ccdd160a21e960b3460886e8349aa42f8ffb49",
            "version": "September 2026",
            "sections": "Appendix A Tables A-1 and A-2",
            "verified_from": "2026-09-01",
            "verified_through": "2027-08-31",
        },
        "soil_status": snapshot.get("status", "not_acquired"),
        "soil_snapshot_sha256": snapshot.get("snapshot_sha256"),
        "soil_sources": deepcopy(snapshot.get("sources", [])),
        "gis_analysis_sha256": gis.get("analysis_sha256"),
        "gis_input_sha256": gis.get("input_sha256"),
        "claim": "Conditional mapped-soil estimate, not verified site soil, permeability, eligibility or an award. Image candidates are separate. No benefits or manual CN facts are changed.",
        "rounding": "Average summed in Decimal; credit counts whole CN steps below 75 (manual 4.3.3.1), so a fractional average uses the next whole CN upward. PWD has not confirmed fractional handling. No automatic bill savings allocation.",
    }
    output["ub_candidate"] = _ub_candidate(mapped, unresolved)
    output["worksheet_sha256"] = sha256(canonical(output)).hexdigest()
    return output


def _ub_candidate(mapped, unresolved):
    """B8: the property CN *if* a reviewer chose UB for every eligible urban-soil row.

    A candidate only: it never fills ``average_cn`` or the credit factor, and it is
    shown only when UB is the single missing input on every incomplete row.
    """
    eligible = [r for r in mapped if r["curve_number"] is None and r["ub_choice_available"]]
    if not eligible:
        return None
    base = {
        "status": "candidate_requires_reviewer_ub_choice",
        "average_cn": None,
        "credit_factor": None,
        "eligible_rows": sorted({r["feature_id"] for r in eligible}),
        "eligible_mapunits": sorted({str(r["mapunit_key"]) for r in eligible}),
        "eligible_area_sqft": sum(r["area_sqft"] for r in eligible),
        "claim": "Shown only to help review: the PWD Table A-1 UB (urban soil) column applies only after a reviewer "
        "records an evidence-tagged UB choice for these Urban land/Udorthents map units. Not an automatic soil group.",
    }
    if any(r["curve_number"] is None and r["ub_candidate_cn"] is None for r in mapped):
        return {
            **base,
            "status": "incomplete",
            "reason": "Other open-space rows lack cover, condition or soil inputs",
        }
    if unresolved >= 0.001:
        return {
            **base,
            "status": "incomplete",
            "reason": "Unresolved ground may contain additional open space",
        }
    d_total = sum((_dec(r["area_sqft"]) for r in mapped), Decimal(0))
    d_product = sum(
        (
            _dec(r["area_sqft"])
            * Decimal(r["curve_number"] if r["curve_number"] is not None else r["ub_candidate_cn"])
            for r in mapped
        ),
        Decimal(0),
    )
    if d_total <= 0:
        return {**base, "status": "incomplete", "reason": "No mapped open-space area"}
    d_average = d_product / d_total
    return {**base, "average_cn": float(d_average), "credit_factor": open_space_factor(d_average)}


# ---- B8: evidence-tagged reviewer UB choice for urban-soil map units --------------
URBAN_COMPONENT = re.compile(r"^\s*(urban land|udorthents)\b", re.IGNORECASE)
SOIL_EVIDENCE = (
    "site_soil_test",
    "geotechnical_report",
    "field_observation",
    "record_drawing",
    "pwd_correspondence",
    "other_documented",
)


def components_digest(properties):
    """Hash of a map unit's SSURGO components; a changed record makes a soil review stale."""
    parts = sorted(
        (
            normalize_numbers(deepcopy(p))
            for p in properties.get("components", [])
            if isinstance(p, dict)
        ),
        key=lambda p: canonical(p),
    )
    return sha256(
        canonical({"mukey": str(properties.get("mukey")), "components": parts})
    ).hexdigest()


def ub_eligibility(properties):
    """(eligible, note): may a reviewer choose PWD's UB column for this map unit?

    Eligible only when at least one Urban land/Udorthents component lacks a
    hydrologic group, every other group-less component is also urban soil, and
    component percentages total 100%. Natural components with their own group
    are noted: the UB choice then covers the whole mapped polygon.
    """
    parts = properties.get("components", [])
    total = 0.0
    urban = []
    natural = []
    other = []
    if not parts:
        return False, "Soil component information missing"
    for p in parts:
        try:
            pct = float(p["comppct_r"])
            if isinstance(p["comppct_r"], bool) or not isfinite(pct) or not 0 < pct <= 100:
                raise ValueError()
        except (KeyError, TypeError, ValueError):
            return False, "Soil component percentage missing or invalid"
        total += pct
        group = str(p.get("hydgrp") or "").strip().upper()
        name = str(p.get("compname") or "").strip()
        if group in ("A", "B", "C", "D", "A/D", "B/D", "C/D"):
            natural.append(f'{name or "unnamed"} ({group})')
        elif URBAN_COMPONENT.match(name):
            urban.append(name)
        else:
            other.append(name or "unnamed component")
    if abs(total - 100) > 0.01:
        return False, "Soil component percentages do not total 100%"
    if not urban:
        return False, "No Urban land/Udorthents component without a hydrologic group"
    if other:
        return False, "Components without a group are not urban soils: " + ", ".join(other)
    note = "Urban land/Udorthents components without a mapped hydrologic group: " + ", ".join(urban)
    if natural:
        note += (
            "; the map unit also lists "
            + ", ".join(natural)
            + " and a UB choice would cover the whole mapped polygon"
        )
    return True, note


def review_soil_group(case, mukey, group, evidence_basis, reason, evidence_refs=None):
    """Record (or withdraw, ``group=None``) a reviewer's UB choice for one map unit.

    Never automatic. Requires an evidence basis from ``SOIL_EVIDENCE`` and a reason.
    The choice is scoped to the map unit's current SSURGO components and becomes
    stale if they change. History is append-only. Mapped A-D groups are not
    overridden here.
    """
    if not isinstance(reason, str) or not reason.strip():
        raise ValueError("A review reason is required")
    if group not in ("UB", None, ""):
        raise ValueError("Only the PWD urban-soil (UB) column can be chosen by review")
    mukey = str(mukey or "")
    snapshot = (case.get("assessment") or {}).get("soil_snapshot") or {}
    units = [
        f["properties"]
        for f in snapshot.get("features", [])
        if str(f.get("properties", {}).get("mukey")) == mukey
    ]
    if group == "UB":
        if evidence_basis not in SOIL_EVIDENCE:
            raise ValueError("Choose an evidence basis: " + ", ".join(SOIL_EVIDENCE))
        if not units:
            raise ValueError("Choose a map unit from the current soil snapshot")
        digests = {components_digest(u) for u in units}
        if len(digests) != 1:
            raise ValueError(
                "Map unit components differ between soil polygons; review is ambiguous"
            )
        eligible, note = ub_eligibility(units[0])
        if not eligible:
            raise ValueError("UB is not available for this map unit: " + note)
        refs = evidence_refs or []
        if not isinstance(refs, list) or not all(isinstance(x, str) and x for x in refs):
            raise ValueError("Evidence references must be a list of IDs")
    result = deepcopy(case)
    a = result.setdefault("assessment", {})
    reviews = a.setdefault("soil_group_reviews", {})
    before = deepcopy(reviews.get(mukey))
    if group == "UB":
        entry = {
            "group": "UB",
            "mukey": mukey,
            "mapunit_name": units[0].get("mapunit_name"),
            "evidence_basis": evidence_basis,
            "evidence_refs": list(refs),
            "reason": reason.strip(),
            "at": now(),
            "basis": "manual",
            "components_sha256": digests.pop(),
            "eligibility_note": note,
            "claim": "Reviewer choice of the PWD Table A-1 UB (urban soil) column; not a mapped SSURGO group or an automatic default.",
        }
        reviews[mukey] = entry
    else:
        if before is None:
            raise ValueError("No soil review to withdraw for this map unit")
        entry = None
        reviews.pop(mukey, None)
    a.setdefault("soil_group_review_history", []).append(
        {
            "mukey": mukey,
            "at": now(),
            "reason": reason.strip(),
            "before": before,
            "after": deepcopy(entry),
            "before_sha256": sha256(canonical(before)).hexdigest(),
            "after_sha256": sha256(canonical(entry)).hexdigest(),
        }
    )
    return result


# ---- A5: worksheet CN to open-space finance, as a labelled conditional scenario -----
SCENARIO_ID = "cn-worksheet-open-space-scenario"
SCENARIO_ASSUMPTIONS = (
    "physical_area_confirmed",
    "parcel_allocation_confirmed",
    "account_current",
    "cover_confirmed",
    "soil_confirmed",
    "runoff_characteristics_confirmed",
    "non_impervious_confirmed",
)


def _manual_cn_facts(case):
    """Entered open-space CN facts (benefits, existing allocations); these stay authoritative."""
    found = []
    benefits = [b for b in case.get("benefits", []) if isinstance(b, dict)]
    benefits += [
        f.get("properties", {}).get("benefit") or {}
        for f in case.get("features", {}).get("features", [])
        if f.get("properties", {}).get("layer") == "benefit"
    ]
    for b in benefits:
        if (
            b.get("category") in ("open_space", "open-space")
            and (b.get("evidence") or {}).get("curve_number") is not None
        ):
            found.append(
                {
                    "id": b.get("id"),
                    "source": "benefit",
                    "curve_number": b["evidence"]["curve_number"],
                }
            )
    for item in (case.get("assessment") or {}).get("existing_credit_allocations", []):
        if (
            item.get("category") == "open_space"
            and (item.get("facts") or {}).get("curve_number") is not None
        ):
            found.append(
                {
                    "id": item.get("id"),
                    "source": "existing_credit_allocation",
                    "curve_number": item["facts"]["curve_number"],
                }
            )
    return found


def finance_scenario(case, gis, sheet, records, as_of, tariff, economics):
    """Price the worksheet CN as an explicitly conditional open-space credit scenario.

    Runs only when the property-wide worksheet CN and factor exist and every mapped
    open-space row has reviewed cover/condition (a manual review entry or a feature
    marked ``reviewed``). Soil comes from an exact mapped SSURGO group or a
    reviewer UB choice. All open-space prerequisites are *assumed* and listed; the
    result never becomes a screen pass, documented credit or award. Entered manual
    CN facts stay authoritative: the scenario then defers to them.
    """
    out = {
        "version": VERSION,
        "id": SCENARIO_ID,
        "status": "unavailable",
        "reasons": [],
        "label": "Conditional open-space credit scenario from the worksheet CN; not a screen pass, approval or award",
        "curve_number": sheet.get("average_cn"),
        "credit_factor": sheet.get("credit_factor"),
        "open_space_area_sqft": (
            sheet.get("mapped_open_space_sqft") if sheet.get("average_cn") is not None else None
        ),
        "assumed_prerequisites": {k: True for k in SCENARIO_ASSUMPTIONS},
        "gross_monthly_reduction": None,
        "gross_annual_reduction": None,
        "claim": "Only if PWD accepts the reviewed cover, condition and soil and every listed prerequisite holds. "
        "Not included in documented or modeled totals; alternatives are never additive.",
    }
    manual = _manual_cn_facts(case)
    if manual:
        return {
            **out,
            "status": "manual_fact_authoritative",
            "manual_cn_facts": manual,
            "reasons": [
                "Entered open-space CN facts are authoritative; the worksheet CN is shown for comparison only"
            ],
        }
    mapped = [r for r in sheet.get("rows", []) if r["basis"] == "mapped_open_space"]
    if sheet.get("average_cn") is None:
        return {
            **out,
            "reasons": list(sheet.get("issues") or ["Property-wide open-space CN unknown"]),
        }
    if sheet.get("credit_factor") is None:
        return {**out, "reasons": list(sheet.get("issues") or ["Credit factor unavailable"])}
    out["soil_basis"] = {
        "mapped_ssurgo": sorted(
            {r["feature_id"] for r in mapped if r.get("soil_basis") == "mapped SSURGO components"}
        ),
        "reviewer_ub": sorted({r["feature_id"] for r in mapped if r.get("soil_group") == "UB"}),
    }
    unreviewed = sorted({r["feature_id"] for r in mapped if not r.get("cover_reviewed")})
    if unreviewed:
        return {
            **out,
            "status": "requires_review",
            "unreviewed_rows": unreviewed,
            "reasons": [
                "Cover and condition must be reviewed for every mapped open-space row before pricing"
            ],
        }
    factor = Decimal(str(sheet["credit_factor"]))
    area = _dec(sheet["mapped_open_space_sqft"])
    out["ga_credit_sqft"] = float(area * factor)
    if factor <= 0:
        return {
            **out,
            "status": "no_credit_at_this_cn",
            "reasons": ["Worksheet CN gives a zero Table A-2 factor"],
        }
    from .assessment_policy import _economics

    geometry = union([shape(r["geometry"]) for r in mapped])
    working = deepcopy(case)
    working["features"]["features"].append(
        {
            "type": "Feature",
            "id": SCENARIO_ID,
            "geometry": mapping(geometry),
            "properties": {
                "layer": "benefit",
                "benefit": {
                    "id": SCENARIO_ID,
                    "category": "open_space",
                    "area_sqft": case_area_sqft(geometry, case),
                    "basis": "modeled",
                    "evidence": {
                        **{k: True for k in SCENARIO_ASSUMPTIONS},
                        "curve_number": sheet["average_cn"],
                    },
                    "claim": "Counterfactual from the CN worksheet; prerequisites assumed",
                },
            },
        }
    )
    scenario = _economics(working, gis, records, as_of, tariff).get("modeled") or {}
    out["status"] = "conditional" if scenario.get("status") == "calculated" else "blocked"
    out["reasons"] = list(scenario.get("reasons", []))
    if scenario.get("status") == "calculated":
        out.update(
            gross_monthly_reduction=scenario["gross_monthly_reduction"],
            gross_annual_reduction=scenario["gross_annual_reduction"],
            ledger=deepcopy(scenario.get("ledger")),
            bill=deepcopy(scenario.get("bill")),
            assumptions=list(scenario.get("assumptions", [])),
        )
        before = (economics or {}).get("modeled") or {}
        others = [
            x["id"]
            for x in (scenario.get("ledger") or {}).get("allocations", [])
            if x.get("id") != SCENARIO_ID
        ]
        if not others:
            out["increment"] = {
                "status": "calculated",
                "gross_monthly_reduction": scenario["gross_monthly_reduction"],
                "gross_annual_reduction": scenario["gross_annual_reduction"],
                "basis": "only credit in the scenario ledger",
            }
        elif before.get("status") == "calculated":
            monthly = Decimal(str(scenario["gross_monthly_reduction"])) - Decimal(
                str(before["gross_monthly_reduction"])
            )
            out["increment"] = {
                "status": "calculated",
                "gross_monthly_reduction": float(monthly),
                "gross_annual_reduction": float(monthly * 12),
                "basis": "scenario minus the modeled ledger without it",
                "other_credits": others,
            }
        else:
            out["increment"] = {
                "status": "not_isolated",
                "other_credits": others,
                "reason": "Other modeled credits are in the ledger and the ledger without this scenario is not calculated",
            }
    elif "alternatives" in scenario:
        out["alternatives"] = deepcopy(scenario["alternatives"])
    return out


def _dec(value):
    """Area as Decimal from its shortest float repr (no binary expansion)."""
    return Decimal(str(value))


def _area_only(g):
    if g.geom_type in ("Polygon", "MultiPolygon"):
        return g
    return union([_area_only(p) for p in getattr(g, "geoms", [])])


def review_inputs(case, feature_id, cover, condition, reason):
    if not isinstance(reason, str) or not reason.strip():
        raise ValueError("A review reason is required")
    if cover not in TABLE and cover not in (None, ""):
        raise ValueError("Unsupported PWD cover type")
    if cover in TABLE:
        if set(TABLE[cover]) == {"na"}:
            condition = "na"
        elif condition not in TABLE[cover] and condition not in (None, ""):
            raise ValueError("Unsupported cover condition")
    from drainage_core.geometry import effective_features

    ids = {
        str(f["id"])
        for f in effective_features(case)
        if f.get("properties", {}).get("layer") == "surface"
        and f["properties"].get("class") == "pervious"
    }
    ids.update(("image-grass_shrub", "image-bare_soil"))
    if not isinstance(feature_id, str) or feature_id not in ids:
        raise ValueError("Choose a mapped open-space feature")
    result = deepcopy(case)
    a = result.setdefault("assessment", {})
    inputs = a.setdefault("open_space_inputs", {})
    before = deepcopy(inputs.get(feature_id))
    entry = {
        "cover": cover or None,
        "condition": condition or None,
        "reason": reason.strip(),
        "at": now(),
        "basis": "manual",
        "scope_sha256": review_scope(case),
    }
    inputs[feature_id] = entry
    a.setdefault("open_space_reviews", []).append(
        {
            "feature_id": feature_id,
            "before": before,
            "after": deepcopy(entry),
            "before_sha256": sha256(canonical(before)).hexdigest(),
            "after_sha256": sha256(canonical(entry)).hexdigest(),
        }
    )
    return result
