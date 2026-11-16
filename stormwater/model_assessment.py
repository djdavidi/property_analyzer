"""Per-record policy interpretation of frozen AI/drainage estimates; no rerouting."""

from copy import deepcopy
from math import isfinite
from shapely.geometry import shape, mapping
from shapely.errors import ShapelyError
from drainage_core.geometry import case_area_sqft, union
from drainage_core.model_integration import composition, ia_bounds, EMPTY


def _region(value):
    if not value:
        return None
    try:
        g = shape(value)
        return (
            g
            if g.is_valid and not g.is_empty and g.geom_type in ("Polygon", "MultiPolygon")
            else None
        )
    except (ValueError, TypeError, KeyError, ShapelyError):
        return None


def footprint(record, case):
    if record.get("footprint_geometry"):
        return _region(record["footprint_geometry"])
    if record.get("source", {}).get("crs") == case["crs"] and "footprint" in str(
        record.get("public_geometry_role", "")
    ):
        return _region(record.get("public_geometry"))
    return None


SYSTEM_ID_FIELDS = ("gsi_system_id", "gsi_id", "system_id", "smp_id", "smpid")
ID_CONTAINERS = ("facts", "raw_record", "source", "properties")


def system_identity(value):
    """Canonical system ID text: surrounding space removed, leading zeros of an
    all-digit ID removed ('062571' and '62571' are one system)."""
    text = str(value if value is not None else "").strip()
    return str(int(text)) if text.isdigit() else text


def system_ids(item, generic_id=False):
    """Explicit system identities of a record or feature: the one resolver (H1/H10).

    Reads every system-ID field (``SYSTEM_ID_FIELDS``) on the item and on its
    ``facts``, ``raw_record`` (where discovered PWD GSI records keep
    ``gsi_system_id``), ``source`` and ``properties``. The generic ``id`` is used
    only when ``generic_id`` is set and no system-ID field exists, so an unrelated
    feature whose OBJECTID equals a system number cannot claim that system.
    """
    found = set()
    if not isinstance(item, dict):
        return found
    for container in (item,) + tuple(item.get(k) for k in ID_CONTAINERS):
        if not isinstance(container, dict):
            continue
        for key in SYSTEM_ID_FIELDS:
            value = container.get(key)
            if (
                value is not None
                and not isinstance(value, (dict, list, bool))
                and str(value).strip()
            ):
                found.add(system_identity(value))
    if not found and generic_id and item.get("id") is not None and str(item["id"]).strip():
        found.add(system_identity(item["id"]))
    return found


def match(record, case, integration, run):
    """Identity first; a unique actual receiving-footprint overlap is a candidate."""
    facts = record.get("facts") or {}
    category = record.get("category")
    kind = "outlet" if category == "direct_discharge" else "gsi"
    wanted = (
        {
            str(v).strip()
            for v in [facts.get("outfall_id"), record.get("outfall_id")]
            if v is not None and str(v).strip()
        }
        if kind == "outlet"
        else system_ids(record)
    )
    if len(wanted) > 1:
        return {
            "status": "ambiguous",
            "reason": "Conflicting receiver identifiers",
            "candidate_ids": sorted(wanted),
        }
    if wanted:
        matches = [
            c
            for c in run["catchments"]
            if c["kind"] == kind
            and (system_identity(c["receiver_id"]) if kind == "gsi" else str(c["receiver_id"]))
            in wanted
        ]
        if len(matches) == 1:
            return {
                "status": "linked",
                "basis": "explicit " + kind + " identity",
                "catchment": matches[0],
            }
        return {
            "status": "missing",
            "reason": "Explicit receiver has no modeled catchment",
            "candidate_ids": sorted(wanted),
        }
    if kind == "outlet":
        return {
            "status": "missing",
            "reason": "No explicit outfall identity; proximity does not establish discharge",
        }
    fp = footprint(record, case)
    if fp is None:
        return {"status": "missing", "reason": "No receiver identity or usable system footprint"}
    ids = {
        system_identity(f["gsi_id"])
        for f in integration.get("receiving_features", [])
        if case_area_sqft(fp.intersection(shape(f["geometry"])), case) > 0.000001
    }
    matches = [
        c
        for c in run["catchments"]
        if c["kind"] == "gsi" and system_identity(c["receiver_id"]) in ids
    ]
    if len(ids) == 1 and len(matches) == 1:
        return {
            "status": "linked",
            "basis": "unique receiving-footprint overlap; unverified",
            "catchment": matches[0],
        }
    return {
        "status": "ambiguous" if len(ids) > 1 else "missing",
        "reason": (
            "Multiple overlapping receiving systems"
            if len(ids) > 1
            else "No uniquely linked receiving catchment"
        ),
        "candidate_ids": sorted(ids),
    }


def receiver_links(case, integrated, runs=None):
    """Receiver identity from source records, independent of scenario creation (R2).

    Every non-permit record is matched, whatever its decision, so a rejected record
    or a record with contrary facts keeps its receiver. Returns
    {run name: {receiver_id: [{'record_id','decision','vetoes'}]}}.
    """
    from .assessment_policy import COMMON, SMP, PAVEMENT, DIRECT, GREEN_ROOF_IAR
    from .prerequisites import record_vetoes

    links = {}
    for run in runs if runs is not None else (integrated.get("runs") or []):
        table = links.setdefault(run["name"], {})
        for record in case.get("assessment", {}).get("records", []):
            if record.get("category") == "industrial_npdes":
                continue
            linked = match(record, case, integrated, run)
            if linked["status"] != "linked":
                continue
            category = record.get("category")
            required = COMMON + (
                DIRECT
                if category == "direct_discharge"
                else (
                    GREEN_ROOF_IAR
                    if category == "green_roof"
                    else SMP + (PAVEMENT if category == "permeable_pavement" else ())
                )
            )
            table.setdefault(linked["catchment"]["receiver_id"], []).append(
                {
                    "record_id": record["id"],
                    "category": category,
                    "decision": record.get("decision", "candidate"),
                    "vetoes": record_vetoes(record, required),
                }
            )
    return links


def _conditions(record, case=None, gis=None, as_of=None):
    """Known-false and assumed prerequisites of one record's what-if. ``management``
    is the generic approved-SMP path (mapped GSI); a green roof is an IAR (manual
    Table 1 / 4.3.2.1) needing the 4.5.1 site plan and photographs, not SMP facts."""
    from .assessment_policy import (
        COMMON,
        SMP,
        PAVEMENT,
        DIRECT,
        GREEN_ROOF_IAR,
        GREEN_ROOF_PATHS,
    )

    category = record["category"]
    facts = record.get("facts", {})
    required = COMMON + (
        DIRECT
        if category == "direct_discharge"
        else (
            GREEN_ROOF_IAR
            if category == "green_roof"
            else SMP + (PAVEMENT if category == "permeable_pavement" else ())
        )
    )
    failed = [k for k in required if facts.get(k) is not None and facts.get(k) is not True]
    assumed = [k for k in required if facts.get(k) is not True]
    if facts.get("proposed_only") is True:
        failed.append("Proposed-only system; existing installation not established")
    if facts.get("installed") is False:
        failed.append("Installation recorded false")
    if category == "green_roof":
        if facts.get("credit_path") not in GREEN_ROOF_PATHS:
            failed.append("Unsupported credit path")
    elif category != "direct_discharge":
        value = facts.get("treatment_depth_inches")
        threshold = 1 if facts.get("old_standard_renewal_verified") is True else 1.5
        if value is None:
            assumed.append("treatment_depth_inches >= " + str(threshold))
        else:
            try:
                if not isfinite(float(value)) or float(value) < threshold:
                    failed.append("Insufficient recorded treatment depth")
            except (TypeError, ValueError):
                failed.append("Invalid recorded treatment depth")
        if facts.get("credit_path") not in (None, "management"):
            failed.append("Unsupported credit path")
    else:
        if facts.get("upstream_smp_present") is True:
            for key in ("upstream_smp_compliant", "upstream_smp_functional"):
                if facts.get(key) is False:
                    failed.append(key)
                elif facts.get(key) is not True:
                    assumed.append(key)
        for key in ("waterway_name", "outfall_id", "upstream_smp_present"):
            if facts.get(key) is None:
                assumed.append(key)
    from drainage_core.installation import installation_issues

    failed += installation_issues(facts, as_of)
    if case is not None:
        from .assessment_policy import screen_record

        # Modeled IA may differ from observed IA; all other known contradictory
        # geometry/evidence facts remain failures, not assumed successes.
        evaluated = screen_record(record, case, gis, as_of)
        failed += [k for k in evaluated["failed"] if k != "managed_geometry_matches_physical_ia"]
        if "source_update_review" in evaluated["missing"]:
            failed.append("Unreconciled public source update")
    return list(dict.fromkeys(failed)), assumed


def _counterfactual(case, gis, screened, recipes, as_of, tariff):
    """Reuse one existing ledger. No source facts or verified screens are edited."""
    from .assessment_policy import _economics, _blocked

    if not recipes:
        return _blocked(["No linked, positive modeled area for this scenario"])
    failures = [reason for recipe in recipes for reason in recipe["failed"]]
    if failures:
        return _blocked(failures)
    working = deepcopy(case)
    source_records = {r["id"]: r for r in working.get("assessment", {}).get("records", [])}
    replacements = {}
    assumptions = []
    areas = {}
    all_ia = shape(gis["modeled_integration"]["measurement"]["geometries"]["physical_ia"])
    for recipe in recipes:
        record = source_records[recipe["id"]]
        region = recipe["region"]
        area = case_area_sqft(region, case)
        if area < 0.000001:
            return _blocked(
                [
                    "Modeled area unavailable for "
                    + recipe["id"]
                    + "; missing evidence is not zero savings"
                ]
            )
        record["geometry"] = mapping(region)
        record["managed_area_sqft"] = area
        # Geometric reservations are excluded below; aggregate/account proof still
        # has to pass the existing allocation-reconciliation code.
        record.setdefault("facts", {})["existing_overlap_reconciled"] = True
        replacements[recipe["id"]] = {
            "id": recipe["id"],
            "category": record["category"],
            "basis": "modeled",
            "status": "screen_pass",
            "managed_area_sqft": area,
        }
        all_ia = all_ia.union(region)
        areas[recipe["id"]] = area
        assumptions.extend(recipe["assumed"])
    entries = [replacements.get(r["id"], r) for r in screened]
    m = gis["modeled_integration"]["measurement"]
    view = {
        **gis,
        "measurement": {**m, "geometries": {**m["geometries"], "physical_ia": mapping(all_ia)}},
    }
    economics = _economics(working, view, entries, as_of, tariff)
    s = economics["modeled"]
    return {
        **s,
        "basis": "conditional AI/catchment alternative",
        "record_areas_sqft": areas,
        "financial_scope": "credits only against retained recorded areas; not net of area correction",
        "net_with_area_correction": economics.get("modeled_combined"),
        "assumed_prerequisites": sorted(set(assumptions)),
        "claim": "Alternative under stated source/model/ground and eligibility assumptions; not a verified screen, approval or award. Do not add to other scenarios.",
    }


def _canopy_value(case, gis, screened, region, as_of, tariff, credited_area=None):
    """Canopy alternative priced by the one assessment ledger (D7), not a second engine.

    ``credited_area`` (fix 6) caps the credited canopy area below the region's area;
    the whole region still reserves its geometry for overlap checks."""
    from .assessment_policy import _economics
    from shapely.geometry import mapping as to_geojson

    working = deepcopy(case)
    area = case_area_sqft(region, case)
    if credited_area is not None:
        area = min(area, credited_area)
    evidence = {
        k: True
        for k in (
            "physical_area_confirmed",
            "parcel_allocation_confirmed",
            "account_current",
            "ground_impervious_overlap_confirmed",
        )
    }
    working["features"]["features"].append(
        {
            "type": "Feature",
            "id": "ai-canopy-alternative",
            "geometry": to_geojson(region),
            "properties": {
                "layer": "benefit",
                "benefit": {
                    "id": "ai-canopy-alternative",
                    "category": "canopy",
                    "area_sqft": area,
                    **({"area_cap_sqft": area} if credited_area is not None else {}),
                    "basis": "modeled",
                    "existing_overlap_reconciled": True,
                    "evidence": evidence,
                },
            },
        }
    )
    m = gis["modeled_integration"]["measurement"]
    view = {
        **gis,
        "measurement": {
            **m,
            "geometries": {
                **m["geometries"],
                "canopy_ground_ia": to_geojson(
                    shape(m["geometries"]["canopy_ground_ia"]).union(region)
                ),
            },
        },
    }
    return _economics(working, view, screened, as_of, tariff)["modeled"]


def catchment_alternatives(case, gis, screened, as_of, tariff, occupied, record_infos, links=None):
    """Show existing mapped GSI value even where it is not one of the five record types.

    A receiver linked to a non-rejected source record is priced by that record's own
    path. A receiver linked only to rejected records, or to records with known-false
    prerequisites, is blocked here with those reasons; it is never re-priced as an
    unassigned system (R2). Known-false parcel facts block every row (R1).
    """
    from .assessment_policy import _economics, _blocked
    from .prerequisites import case_vetoes

    integrated = gis["modeled_integration"]
    out = []
    links = receiver_links(case, integrated) if links is None else links
    vetoes = case_vetoes(case)
    facts = {
        k: True
        for k in (
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
    facts["treatment_depth_inches"] = 1.5

    def value(region):
        if case_area_sqft(region, case) < 0.000001:
            return _blocked(["No unallocated modeled IA in this catchment"])
        working = deepcopy(case)
        working["features"]["features"].append(
            {
                "id": "ai-gsi-management-alternative",
                "geometry": mapping(region),
                "properties": {
                    "layer": "benefit",
                    "benefit": {
                        "id": "ai-gsi-management-alternative",
                        "category": "management",
                        "area_sqft": case_area_sqft(region, case),
                        "basis": "modeled",
                        "evidence": facts,
                        "existing_overlap_reconciled": True,
                    },
                },
            }
        )
        m = integrated["measurement"]
        view = {
            **gis,
            "measurement": {
                **m,
                "geometries": {
                    **m["geometries"],
                    "physical_ia": mapping(shape(m["geometries"]["physical_ia"]).union(region)),
                },
            },
        }
        e = _economics(working, view, screened, as_of, tariff)
        return {
            **e["modeled"],
            "financial_scope": "credits only against retained recorded areas; not net of area correction",
            "net_with_area_correction": e.get("modeled_combined"),
        }

    from .system_pricing import catchment_route, combine_routes

    checks = {}
    for run in integrated["runs"]:
        unions = {}
        union_routes = {}
        union_ids = {}
        for c in run["catchments"]:
            linked = links.get(run["name"], {}).get(c["receiver_id"], [])
            if c["kind"] != "gsi" or c["composition"]["region_area_sqft"] < 0.000001:
                continue
            # A lead (fix 3) does not take the receiver over; its vetoes still block.
            if any(
                l["decision"] != "rejected" and l.get("category") != "existing_system_management"
                for l in linked
            ):
                continue
            receiver = next(
                (
                    f
                    for f in integrated.get("receiving_features", [])
                    if str(f["gsi_id"]) == c["receiver_id"]
                ),
                None,
            )
            source = (receiver or {}).get("source", {})
            failed, _ = _conditions(
                {"category": "management", "facts": {**source, **source.get("facts", {})}},
                as_of=as_of,
            )
            failed = vetoes + [reason for l in linked for reason in l["vetoes"]] + failed
            # D2: per-catchment extent test, the same rule as the pilot.
            route = catchment_route(c, run.get("invariants"))
            failed += route["blocked_reasons"]
            if receiver is None:
                failed.append("Receiving feature source is unavailable")
            # H16: the receiver's own bed (surface GSI footprint) is never contributing IA.
            bed = _region((receiver or {}).get("geometry"))
            for bound, region in ia_bounds(case, integrated, shape(c["geometry"])).items():
                region = region.difference(occupied)
                bed_area = (
                    case_area_sqft(region.intersection(bed), case) if bed is not None else 0.0
                )
                if bed is not None:
                    region = region.difference(bed)
                if not failed:
                    unions.setdefault(bound, []).append(region)
                    union_routes.setdefault(bound, []).append(route)
                    union_ids.setdefault(bound, []).append(c["receiver_id"])
                area = case_area_sqft(region, case)
                out.append(
                    {
                        "name": run["name"],
                        "receiver_id": c["receiver_id"],
                        "bound": bound,
                        "area_sqft": area,
                        "on_parcel_contributing_sqft": c["composition"]["region_area_sqft"],
                        "system_bed_ia_excluded_sqft": bed_area,
                        **(_blocked(failed) if failed else value(region)),
                        "basis": "conditional mapped-GSI management alternative",
                        **_route_fields(route),
                        "assumptions": [
                            "Mapped receiver is an existing eligible system and serves this parcel",
                            "All management prerequisites, 1.5-inch treatment and approved allocation are assumed",
                            "AI classes and modeled flow are unvalidated; upper adds unresolved ground as impervious",
                            "No verified inlet, ownership, treatment performance or award is established",
                        ]
                        + _bound_assumptions(bound),
                        # Fix 8: the terrain-visible storage next to the dollar row; the
                        # figure itself is unchanged and still assumes full treatment.
                        "storage_check": _with_volume(
                            storage_check(case, gis, c["receiver_id"], checks), area
                        ),
                    }
                )
        for bound, regions in unions.items():
            if regions:
                out.append(
                    {
                        "name": run["name"],
                        "receiver_id": "all_unassigned_gsi",
                        "bound": bound,
                        "area_sqft": case_area_sqft(union(regions), case),
                        **value(union(regions)),
                        **_route_fields(combine_routes(union_routes[bound])),
                        "basis": "conditional combined mapped-GSI alternative; deduplicated union, not sum of savings",
                        "storage_checks": [
                            {"receiver_id": rid, **checks[rid]}
                            for rid in dict.fromkeys(union_ids.get(bound, []))
                            if rid in checks
                        ],
                    }
                )
    return out


STORAGE_LABEL = "Assumes full 1.5-inch treatment; terrain cannot see engineered storage"
TREATMENT_DEPTH_FT = 1.5 / 12


def _receiver_type(case, receiver_id):
    from drainage_core.geometry import effective_features

    for f in effective_features(case):
        p = f.get("properties") or {}
        if p.get("kind") == "system_footprint" and system_identity(
            p.get("gsi_system_id")
        ) == system_identity(receiver_id):
            return p.get("gsi_system_type")
    return None


def storage_check(case, gis, receiver_id, cache=None):
    """Fix 8: the saved-DEM surface storage of one receiving system
    (``drainage_core.runoff_capacity.estimate_capacity``, the pilot's check), shown
    beside the app's management dollar row; it never replaces that figure."""
    cache = {} if cache is None else cache
    if receiver_id in cache:
        return cache[receiver_id]
    from .management_pilot import surface_storage_system

    kind = _receiver_type(case, receiver_id)
    out = {"label": STORAGE_LABEL, "system_type": kind}
    if not surface_storage_system(kind):
        out.update(
            applies=False,
            status="not_applicable",
            reason=(
                "Not a surface rain garden/bioretention: engineered or subsurface storage is "
                "not visible in terrain"
            ),
            storage_range_cuft=None,
            review_flags=[],
        )
    else:
        from drainage_core.runoff_capacity import estimate_capacity

        try:
            cap = estimate_capacity(case, gis, receiver_id)
        except (ValueError, KeyError, TypeError) as exc:
            cap = {"status": "unavailable", "reason": str(exc), "review_flags": []}
        out.update(
            applies=True,
            status=cap.get("status"),
            reason=cap.get("reason"),
            storage_range_cuft=deepcopy(cap.get("storage_range_cuft")),
            storage_range_scenarios=deepcopy(cap.get("storage_range_scenarios")),
            review_flags=[f.get("code") for f in cap.get("review_flags") or []],
            method_version=cap.get("version"),
            basis=cap.get("basis"),
        )
    cache[receiver_id] = out
    return out


def _with_volume(check, managed_ia_sqft):
    """The row's 1.5-inch treatment volume against the terrain-visible storage range."""
    required = max(0.0, float(managed_ia_sqft or 0)) * TREATMENT_DEPTH_FT
    out = {**deepcopy(check), "required_treatment_volume_cuft": required}
    storage = check.get("storage_range_cuft")
    if check.get("status") == "estimated" and storage and required > 0:
        out["terrain_visible_share_of_required"] = [min(storage) / required, max(storage) / required]
        out["terrain_storage_covers_required"] = min(storage) >= required
        if max(storage) < required:
            out["flag"] = (
                "Terrain-visible storage is below the 1.5-inch volume this figure assumes; the "
                "dollar row holds only if engineered storage (media, underdrain, subsurface) supplies the rest"
            )
    return out


PERMIT_LISTINGS = {
    "priced": "Industrial what-if (best matched active industrial permit)",
    "not_applicable_construction": "Construction stormwater coverage; not the industrial credit",
    "nearby_not_matched": "Nearby, not matched",
    "site_match_unknown": "Site match unknown; not priced",
    "industrial_coverage_unconfirmed": "Industrial stormwater coverage not established; not priced",
    "another_permit_priced": "Matched, but another permit carries the one industrial what-if",
    "blocked": "Matched industrial permit; known-false prerequisite",
}


def _permit_listing(listing, reasons):
    return {
        "status": (
            "not_applicable"
            if listing == "not_applicable_construction"
            else "not_matched" if listing in ("nearby_not_matched", "site_match_unknown") else "not_priced"
        ),
        "listing": listing,
        "listing_label": PERMIT_LISTINGS[listing],
        "reasons": list(dict.fromkeys(reasons)),
        "gross_monthly_reduction": None,
        "gross_annual_reduction": None,
        "bill": None,
        "ledger": None,
    }


def permit_alternatives(case, gis, screened, as_of, tariff):
    """Explicit what-if only; discovery status and source facts stay unchanged.

    Fix 1: every permit row is classified (``permits.permit_classification``) and
    matched to THIS parcel by identity (``permits.permit_site_match``). Construction
    coverage (PAC/PAD/PAI/PAG-02) is not the manual 4.3.4 industrial credit. A
    nearby or unmatched facility is listed, never priced. One industrial what-if is
    priced per property: the best matched industrial permit (reviewed ``active``
    first, then the searched identifier, then permit ID order); the others are listed.
    """
    from .assessment_policy import _economics, _blocked, screen_record
    from .permits import permit_classification, permit_site_match
    from .prerequisites import case_vetoes

    rows = []
    candidates = []
    for r in case.get("assessment", {}).get("records", []):
        if r["category"] != "industrial_npdes" or r.get("decision") == "rejected":
            continue
        facts = r.get("facts", {})
        cls = permit_classification(facts.get("permit_id"), facts)
        site = permit_site_match(r, case)
        row = {
            "record_id": r["id"],
            "permit_id": facts.get("permit_id"),
            "permit_class": cls["class"],
            "permit_class_basis": cls["basis"],
            "site_match": site["status"],
            "site_match_basis": site["basis"],
            "facility_name": facts.get("public_facility_name"),
            "facility_address": facts.get("public_street_address"),
            "basis": "conditional industrial-coverage what-if",
        }
        rows.append(row)
        if cls["class"] == "construction_stormwater":
            row.update(_permit_listing("not_applicable_construction", [cls["basis"]]))
        elif site["status"] == "not_matched":
            row.update(_permit_listing("nearby_not_matched", [site["basis"]]))
        elif site["status"] != "matched":
            row.update(_permit_listing("site_match_unknown", [site["basis"]]))
        elif cls["class"] != "industrial_stormwater":
            row.update(_permit_listing("industrial_coverage_unconfirmed", [cls["basis"]]))
        else:
            rank = (
                facts.get("active") is not True,
                facts.get("identifier_exact_match") is not True,
                str(facts.get("permit_id") or r["id"]),
            )
            candidates.append((rank, r, row))
    priced = False
    for _, r, row in sorted(candidates, key=lambda item: item[0]):
        facts = r.get("facts", {})
        evaluated = screen_record(r, case, gis, as_of)
        failed = case_vetoes(case) + evaluated["failed"]
        if r.get("source_update", {}).get("status") == "pending_review":
            failed.append("Unreconciled public source update")
        row.update(
            assumed_prerequisites=list(evaluated["missing"]),
            date_notes=list(evaluated.get("date_notes", [])),
        )
        if priced:
            row.update(
                _permit_listing(
                    "another_permit_priced",
                    ["One industrial what-if per property; see the priced permit row"],
                )
            )
            continue
        if failed:
            row.update({**_blocked(failed), "listing": "blocked", "listing_label": PERMIT_LISTINGS["blocked"]})
            continue
        hypothetical = [
            {**x, "basis": "modeled", "status": "screen_pass"} if x["id"] == r["id"] else x
            for x in screened
        ]
        s = _economics(case, gis, hypothetical, as_of, tariff)["modeled"]
        row.update(
            {
                **s,
                "listing": "priced",
                "listing_label": PERMIT_LISTINGS["priced"],
                "basis": "conditional industrial-coverage what-if",
                "assumptions": [
                    "Only if this permit is applicable active industrial coverage for this site/operator",
                    "Account and previous-12-month compliance/reporting prerequisites are assumed, not established",
                    "Do not add to canopy/management alternatives; combined benefits require their shared ledger",
                ],
            }
        )
        priced = s.get("status") == "calculated"
    return rows


def _route_fields(route):
    return {k: route[k] for k in ("route_state", "route_state_reason", "partial_label")}


def _bound_assumptions(bound):
    """Labels of the shared class table's extra app bound (D3)."""
    from drainage_core.class_interpretation import APP_LABELLED_BOUNDS, SCENARIOS

    labelled = dict(APP_LABELLED_BOUNDS)
    if bound not in labelled:
        return []
    scenario = SCENARIOS[labelled[bound]]
    return [scenario["label"]] + list(scenario["assumptions"])


def integrate(case, gis, screened, as_of, tariff):
    from .assessment_policy import _blocked, _area_decimal, RULES, is_image_candidate
    from .system_pricing import catchment_route, combine_routes
    from .billing import default_tariff

    integrated = gis.get("modeled_integration")
    if not integrated:
        return {"status": "unavailable", "records": [], "combined": []}
    from drainage_core.quality import artifact_quality

    quality = artifact_quality(gis)
    if quality["status"] == "outdated":
        return {
            "status": "outdated",
            "records": [],
            "combined": [],
            "claim": quality["reason"],
            "reason": quality["reason"],
            "recompute_available": True,
        }
    if case.get("assessment", {}).get("baseline_refresh", {}).get("status") == "pending_review":
        return {
            "status": "blocked",
            "records": [],
            "combined": [],
            "claim": "Public billing baseline changed; reconcile before calculating savings",
        }
    parcel = shape(case["parcel"])
    sources = case.get("assessment", {}).get("records", [])
    items = []
    recipes_by_key = {}
    reserved = []
    for r in case.get("assessment", {}).get("existing_credit_allocations", []):
        if (g := _region(r.get("geometry"))) is not None:
            reserved.append(g)
    # Retain existing legacy benefit allocations too. The ledger checks unsupported
    # overlap/reconciliation even when an item lacks usable geometry.
    from drainage_core.geometry import effective_features

    reserved.extend(
        shape(f["geometry"])
        for f in effective_features(case)
        if f.get("properties", {}).get("layer") == "benefit"
    )
    occupied = union(reserved)
    runs = integrated.get("runs") or [{"name": "no_terrain", "catchments": []}]
    from .prerequisites import case_vetoes

    vetoes = case_vetoes(case)
    links = receiver_links(case, integrated, runs)
    for record in sources:
        rid = record["id"]
        category = record["category"]
        fp = footprint(record, case)
        info = {
            "record_id": rid,
            "basis": "modeled AI/drainage context",
            "runs": [],
            "source_lineage": deepcopy(integrated["ai"]["sources"]),
            "prediction_sha256": integrated["ai"]["prediction_sha256"],
            "input_lineage_sha256": integrated["input_lineage_sha256"],
            "uncertainty": deepcopy(integrated["ai"]["uncertainty"]),
            "footprint_composition": (
                composition(case, integrated["ai"], integrated["measurement"], mapping(fp))
                if fp is not None
                else None
            ),
        }
        if is_image_candidate(record):
            info["record_basis"] = "image_candidate"
            info["record_claim"] = (
                "RGB greenness on a mapped roof: an image candidate, not a public record or a "
                "confirmed green roof; never combined with other records"
            )
        if category == "industrial_npdes":
            info.update(
                status="not_applicable",
                reason="AI/drainage does not establish permit coverage, operator identity or compliance",
            )
            items.append(info)
            continue
        if category == "existing_system_management":
            # Fix 3: a lead is priced only from a documented managed area
            # (``existing_systems``); its modeled catchment stays a catchment alternative.
            info.update(
                status="lead",
                reason=(
                    "Mapped-system lead; priced only from a documented managed area "
                    "(PCSMP/as-built), see existing_system_management"
                ),
            )
            items.append(info)
            continue
        info["linked_receiver_ids"] = {
            name: sorted(r for r, rows in table.items() if any(x["record_id"] == rid for x in rows))
            for name, table in links.items()
        }
        if record.get("decision") == "rejected":
            info.update(
                status="rejected",
                reason="Manual rejection retained; no new modeled allocation; linked receivers are not re-priced as unassigned systems",
            )
            items.append(info)
            continue
        failed, assumed = _conditions(record, case, gis, as_of)
        failed = list(dict.fromkeys(vetoes + failed))
        if record.get("facts", {}).get("existing_overlap_reconciled") is False:
            failed.append("Existing overlap explicitly unreconciled")
        info["status"] = "modeled"
        info["known_failed_prerequisites"] = failed
        info["unverified_prerequisites"] = assumed
        for run in runs:
            linked = match(record, case, integrated, run)
            region = None
            area_basis = None
            declared = _region(record.get("geometry"))
            if linked["status"] == "linked":
                region = shape(linked["catchment"]["geometry"]).intersection(parcel)
                area_basis = "linked research catchment"
            elif linked["status"] != "ambiguous" and declared is not None:
                region = declared.intersection(parcel)
                area_basis = "source-declared managed geometry; research connection unverified"
            elif (
                linked["status"] != "ambiguous"
                and fp is not None
                and category in ("green_roof", "permeable_pavement")
            ):
                region = fp.intersection(parcel)
                area_basis = (
                    "direct rainfall on mapped footprint only; upstream contributing area unknown"
                )
            output = {
                "name": run["name"],
                "catchment_match": {k: v for k, v in linked.items() if k != "catchment"},
                "area_basis": area_basis,
                "managed_geometry": mapping(region) if region is not None else None,
                "scenarios": [],
            }
            if linked.get("catchment"):
                output["receiver_id"] = linked["catchment"]["receiver_id"]
                output["off_parcel_area_sqft"] = linked["catchment"]["off_parcel_area_sqft"]
            if region is not None:
                output["composition"] = composition(
                    case, integrated["ai"], integrated["measurement"], mapping(region)
                )
                bounds = ia_bounds(case, integrated, region)
                # A mapped vegetated roof/permeable surface can be misclassified
                # by the generic model. The upper scenario explicitly assumes
                # unconfirmed ground in this region is qualifying IA.
                observed_pervious = shape(integrated["observed_pervious_geometry"])
                bounds["upper"] = bounds["upper"].union(region.difference(observed_pervious))
                # D2: a linked research catchment carries the per-catchment extent test.
                route = (
                    catchment_route(linked["catchment"], run.get("invariants"))
                    if linked["status"] == "linked"
                    else None
                )
                if route:
                    output.update(_route_fields(route))
                for bound, geom in bounds.items():
                    geom = geom.difference(occupied)
                    assumptions = assumed + [
                        "AI class accuracy and modeled drainage are unverified",
                        area_basis,
                        "Required approval, condition and treatment evidence must cover the modeled area, not only an earlier recorded area",
                    ]
                    if bound == "upper":
                        assumptions += [
                            "All unconfirmed ground in this region assumed impervious; not a confidence bound"
                        ]
                    if bound == "lower":
                        assumptions += [
                            "Observed IA plus eroded AI boundaries; classification error remains unbounded"
                        ]
                    assumptions += _bound_assumptions(bound)
                    route_failed = route["blocked_reasons"] if route else []
                    recipe = {
                        "id": rid,
                        "region": geom,
                        "failed": failed + route_failed,
                        "assumed": assumptions,
                        "route": route,
                    }
                    s = _counterfactual(case, gis, screened, [recipe], as_of, tariff)
                    output["scenarios"].append(
                        {
                            "bound": bound,
                            "area_sqft": case_area_sqft(geom, case),
                            **s,
                            **(_route_fields(route) if route else {}),
                        }
                    )
                    recipes_by_key.setdefault((run["name"], bound), []).append(recipe)
            else:
                output["scenarios"].append(
                    {
                        "bound": "unavailable",
                        **_blocked([linked.get("reason", "Catchment unavailable")]),
                    }
                )
            info["runs"].append(output)
        items.append(info)
    combined = []
    image_ids = {
        r["id"]
        for r in case.get("assessment", {}).get("records", [])
        if is_image_candidate(r)
    }
    for (run, bound), recipes in recipes_by_key.items():
        # Fix 7: an image candidate keeps its own labelled row but never enters (or
        # blocks) a combined row; it is not a public or reviewed record.
        image = [r for r in recipes if r["id"] in image_ids]
        recipes = [r for r in recipes if r["id"] not in image_ids]
        if not recipes:
            continue
        usable = [
            r for r in recipes if not r["failed"] and case_area_sqft(r["region"], case) > 0.000001
        ]
        excluded = [
            {
                "record_id": r["id"],
                "reasons": r["failed"] or ["No positive on-parcel modeled area; not zero savings"],
            }
            for r in recipes
            if r not in usable
        ] + [
            {
                "record_id": r["id"],
                "reasons": [
                    "Image candidate (RGB greenness on a roof); listed separately, never combined"
                ],
            }
            for r in image
        ]
        routes = [r["route"] for r in usable if r.get("route")]
        combined.append(
            {
                "name": run,
                "bound": bound,
                **_counterfactual(case, gis, screened, usable, as_of, tariff),
                **(_route_fields(combine_routes(routes)) if routes else {}),
                "scope": "calculable subset" if excluded else "listed record alternatives",
                "excluded_records": excluded,
                "complete_opportunity": False,
            }
        )
    surface = {}
    t = tariff or default_tariff()
    finance_allowed = (
        RULES["effective_from"] <= as_of.isoformat() <= RULES["verified_through"]
        and t["effective_from"] <= as_of.isoformat() <= t["verified_through"]
    )
    if not finance_allowed:
        surface = {
            "status": "blocked",
            "reason": "Assessment date outside verified rule/tariff period",
        }
    elif case.get("baseline") and integrated["ai"]["status"] == "modeled":
        # Appeal alternatives use the same assessment ledger as every credit (D7).
        from .assessment_policy import _economics, ledger_billing_view

        def appeal(measurement):
            view = ledger_billing_view(
                _economics(case, {**gis, "measurement": measurement}, [], as_of, tariff)
            )
            if view.get("status") == "blocked":
                raise ValueError(view["reason"])
            return view["appeal_only"]

        try:
            measured = {
                **integrated["measurement"],
                **{
                    k: float(_area_decimal(integrated["measurement"][k]))
                    for k in ("ga_sqft", "ia_sqft")
                },
            }
            surface = {
                "status": "conditional",
                "measurement_only": appeal(measured),
                "claim": "AI-based surface correction alternative only; imagery classes and legal/billed areas are unverified. Do not add to credit alternatives.",
            }
            surface["area_alternatives"] = []
            baseline = case["baseline"]
            m = integrated["measurement"]
            # Fix 2: one GA source per row -- the measured parcel polygon, on which the
            # IA and the unknown ground were measured -- and IA clipped to that GA. The
            # two cover ends are a measurement range against the recorded IA, not an
            # appeal; recorded GA is never paired with measured IA.
            mga = float(_area_decimal(m["ga_sqft"]))
            recorded_ia = baseline.get("ia_sqft")
            options = [
                (
                    "gross_area_only",
                    min(float(_area_decimal(recorded_ia)), mga) if recorded_ia is not None else None,
                    "Measured GA with the recorded IA (clipped to the measured GA)",
                ),
                (
                    "ia_unknown_assumed_pervious",
                    min(float(_area_decimal(m["ia_sqft"])), mga),
                    "Low end: unclassified/canopy-hidden ground assumed pervious",
                ),
                (
                    "ia_unknown_assumed_impervious",
                    min(float(_area_decimal(m["ia_sqft"] + m["unknown_sqft"])), mga),
                    "High end: all unclassified/canopy-hidden ground assumed impervious",
                ),
            ]
            for name, ia, assumption in options:
                if ia is None:
                    scenario = _blocked(["Recorded IA unavailable"])
                else:
                    try:
                        scenario = appeal({**m, "ga_sqft": mga, "ia_sqft": ia, "complete": True})
                    except ValueError as exc:
                        scenario = _blocked([str(exc)])
                surface["area_alternatives"].append(
                    {
                        **scenario,
                        "name": name,
                        "ga_sqft": mga,
                        "ia_sqft": ia,
                        "cover_assumption": assumption,
                        "ga_source": "measured parcel polygon (the surface the IA was measured on)",
                        "ia_vs_recorded_sqft": (
                            ia - float(recorded_ia)
                            if ia is not None and recorded_ia is not None
                            else None
                        ),
                        "assumptions": [
                            assumption,
                            "Counterfactual completed cover assumption, not a complete measured survey or a supported appeal",
                        ]
                        + list(scenario.get("assumptions") or []),
                    }
                )

            def end(row):
                calculated = row.get("status") == "calculated"
                return {
                    "assumption": row["cover_assumption"],
                    "ia_sqft": row["ia_sqft"],
                    "ia_vs_recorded_sqft": row["ia_vs_recorded_sqft"],
                    "status": row.get("status"),
                    "monthly_total": row.get("monthly_total") if calculated else None,
                    "monthly_change": row.get("monthly_savings") if calculated else None,
                    "annual_change": row.get("annual_savings") if calculated else None,
                    "unavailable_reason": None
                    if calculated
                    else "; ".join(row.get("reasons") or ["Not calculated"]),
                }

            low, high = surface["area_alternatives"][1], surface["area_alternatives"][2]
            surface["ia_measurement_range"] = {
                "presentation": "Measured-cover range compared with the recorded IA; not an appeal",
                "ga_source": "measured parcel polygon",
                "measured_ga_sqft": mga,
                "recorded_ga_sqft": baseline.get("ga_sqft"),
                "recorded_ia_sqft": recorded_ia,
                "low_end": end(low),
                "high_end": end(high),
                "recorded_ia_within_range": (
                    recorded_ia is not None and low["ia_sqft"] <= float(recorded_ia) <= high["ia_sqft"]
                ),
                "claim": (
                    "Both cover ends from the same measured parcel; positive changes are lower bills "
                    "only if PWD accepted that cover. Imagery classes and legal/billed areas are unverified."
                ),
            }
        except ValueError as exc:
            surface = {"status": "blocked", "reason": str(exc)}
    # Image context is not a permeability or green-roof detector.
    roof_shapes = [
        shape(f["geometry"])
        for f in effective_features(case)
        if f.get("properties", {}).get("class") == "roof"
        and f.get("properties", {}).get("layer") == "surface"
    ]
    roof_shapes.append(shape(integrated["ai"]["roof_supplement_geometry"]))
    vegetation = shape(integrated["ai"]["geometries"]["canopy"]).union(
        shape(integrated["ai"]["geometries"]["grass_shrub"])
    )
    roof_vegetation = vegetation.intersection(union(roof_shapes))
    canopy_scenarios = []
    if case.get("baseline") and integrated["ai"]["status"] == "modeled":
        m = integrated["measurement"]
        canopy = shape(m["geometries"]["canopy"])
        known_overlap = shape(m["geometries"]["canopy_ground_ia"])
        hidden_overlap = canopy.intersection(shape(m["geometries"]["unknown"]))
        for name, region in [
            ("modeled_overlap", known_overlap),
            ("hidden_ground_assumed_impervious", known_overlap.union(hidden_overlap)),
        ]:
            region = region.difference(occupied)
            area = float(_area_decimal(case_area_sqft(region, case)))
            assumptions = [
                "Canopy classification and overlap are modeled; eligibility/actual account bill remain unverified"
            ]
            cap = None
            if name.startswith("hidden"):
                assumptions.append(
                    "All unresolved ground below predicted canopy assumed impervious"
                )
                # Fix 6: canopy-hidden ground counts as IA only up to the recorded IA not
                # already identified (max(0, recorded IA - identified IA)); the implied
                # IA can no longer exceed the recorded IA.
                known_area = float(
                    _area_decimal(case_area_sqft(known_overlap.difference(occupied), case))
                )
                recorded = case["baseline"].get("ia_sqft")
                if recorded is not None:
                    identified = float(_area_decimal(m["ia_sqft"]))
                    room = max(0.0, float(_area_decimal(recorded)) - identified)
                    credited = known_area + min(max(0.0, area - known_area), room)
                    cap = {
                        "label": "Canopy-hidden ground counted as IA only up to recorded IA minus identified IA",
                        "recorded_ia_sqft": float(_area_decimal(recorded)),
                        "identified_ia_sqft": identified,
                        "hidden_ground_cap_sqft": room,
                        "uncapped_area_sqft": area,
                        "credited_area_sqft": credited,
                        "applied": credited < area - 0.000001,
                    }
                    if cap["applied"]:
                        assumptions.append(cap["label"])
            credited_area = cap["credited_area_sqft"] if cap else area
            if not finance_allowed:
                s = _blocked(["Assessment date outside verified rule/tariff period"])
            elif vetoes:
                s = _blocked(vetoes)
            elif credited_area < 0.000001:
                s = _blocked(
                    ["No supported modeled ground-IA overlap; canopy-hidden ground remains unknown"]
                    if area < 0.000001
                    else [
                        "Recorded IA leaves no room for canopy-hidden ground IA beyond the identified IA"
                    ]
                )
            else:
                s = _canopy_value(
                    case, gis, screened, region, as_of, tariff, credited_area if cap else None
                )
            row = {
                **s,
                "name": name,
                "area_sqft": credited_area,
                "basis": "conditional AI canopy alternative",
                "assumptions": assumptions + list(s.get("assumptions", [])),
            }
            if cap:
                row["recorded_ia_cap"] = cap
            canopy_scenarios.append(row)
    available = integrated["ai"]["status"] == "modeled"
    pavement = shape(integrated["ai"]["geometries"]["road"]).union(
        shape(integrated["ai"]["geometries"]["developed_space"])
    )
    categories = {
        "green_roof": {
            "possible_roof_vegetation_sqft": (
                case_area_sqft(roof_vegetation, case) if available else None
            ),
            "claim": "Image vegetation on roof outlines nominates a possible feature; tree overhang and other causes remain possible. No green roof is established.",
        },
        "permeable_pavement": {
            "developed_or_road_appearance_sqft": (
                case_area_sqft(pavement, case) if available else None
            ),
            "permeability": "Unknown",
            "claim": "Developed-space/road appearance is not a pavement measurement or permeability class.",
        },
        "direct_discharge": {
            "explicit_outlet_candidates": [
                {"receiver_id": c["receiver_id"], "composition": c["composition"]}
                for c in (integrated.get("runs") or [{}])[0].get("catchments", [])
                if c["kind"] == "outlet"
            ],
            "claim": "Only supplied outlet connections are traced. Water destination, private ownership and qualifying discharge remain unverified.",
        },
    }
    return {
        "status": integrated["status"],
        "records": items,
        "combined": combined,
        "surface_scenario": surface,
        "catchment_scenarios": catchment_alternatives(
            case, gis, screened, as_of, tariff, occupied, items, links
        ),
        "permit_scenarios": permit_alternatives(case, gis, screened, as_of, tariff),
        "category_context": categories,
        "canopy_scenarios": canopy_scenarios,
        "image_context": {
            "possible_roof_vegetation_geometry": mapping(roof_vegetation),
            "possible_roof_vegetation_sqft": (
                case_area_sqft(roof_vegetation, case)
                if integrated["ai"]["status"] == "modeled"
                else None
            ),
            "claim": "Roof vegetation may be overhanging trees. Pavement classes do not establish permeability; no new treatment is confirmed.",
        },
        "claim": "Record-specific modeled alternatives alongside unchanged evidence-based findings. Combined scenarios use one ledger; unresolved overlaps block calculation.",
    }
