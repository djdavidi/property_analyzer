"""Storage-limited PWD screening over independent surface-storage estimates, without routing.

Inputs are two frozen physical results: ``drainage_core.management_estimates.
estimate_system`` (candidate IA per run, route state, off-parcel area) and
``drainage_core.runoff_capacity.estimate_capacity`` (status, review flags and the
perimeter-line storage range per hydraulic component). Nothing is rerouted.

Physical status is respected: ``blocked`` stays ``blocked`` (with its blocking
reasons), ``unavailable`` stays ``unavailable`` and ``excluded`` stays ``excluded``.
``review_flags`` are carried through and extended.

Range first (decision D4). The headline is the range across the two perimeter-line
storage methods (``storage_range_cuft``: cell minimum and bilinear) and the
named runoff-load assumptions, for every labelled candidate-IA interpretation of
the nominal run. No row is called conservative: storage method, load and
interpretation do not all push in one direction. The storage-limited reference
row is one named row of that range (``current_estimate``), never the headline.

Budget per component (R7). Each component's direct rainfall reserves its own
storage first. With several components and no per-component inflow record, the
split of inflow between them is unknown, so two named splits bracket it:
``pooled`` (inflow divides ideally) and ``all_to_least`` (all inflow reaches the
component with the least remaining storage).

Loads (R6). Off-parcel contributing area (``off_parcel_area_sqft``) and the
remaining on-parcel soft/mixed ground are explicit load ranges, from no runoff to
full first-1.5-inch runoff; both are inflow that a managing system must hold
before any candidate IA counts. The range is bounded only when the run's route
state is ``complete_in_window`` and the off-parcel area is known. Otherwise the
lower end and the reference row are withheld and the in-window figures carry the
D2 partial label.

Separate quantities. ``runoff_supplied_cuft`` and ``runoff_stored_cuft`` are
modeled under each row's assumptions. ``runoff_captured_cuft``,
``runoff_treated_cuft`` and ``qualifying_managed_area_sqft`` stay ``None``: inlets,
bypass, treatment, drawdown and a PWD award are not established. The
volume-equivalent managed area is a labelled hypothesis, not verified qualifying
area, and every dollar comes from the single assessment ledger (D7).
"""

from copy import deepcopy

from shapely.geometry import mapping, shape
from shapely.errors import ShapelyError

from drainage_core.geometry import area_only, case_area_sqft, union
from .billing import decimal
from .management_estimates import (
    HEADLINE_RUN,
    TREATMENT_DEPTH_INCHES,
    _candidate_geometry,
    price_scenario,
    system_context,
)
from .model_assessment import system_identity
from .system_pricing import annual_values, lineage_errors, run_route, value_range

VERSION = "pwd-storage-limited-management-v2"
STORAGE_METHODS = ("perimeter_cell_minimum", "perimeter_bilinear")
# D2 for storage-limited rows: unseen upstream inflow can only consume the measured
# storage, so the true storage-limited value is lower or equal, never higher. The
# generic PARTIAL_LABEL ("true value may be higher") is for contributing-area pricing.
STORAGE_PARTIAL_LABEL = (
    "partial: storage-limited value may be lower or equal (unseen upstream inflow can only "
    "use up storage)"
)


def _storage_label(route):
    return STORAGE_PARTIAL_LABEL if route.get("partial_label") else None


# (name, off-parcel runoff fraction, other on-parcel ground runoff fraction, meaning)
LOADS = (
    (
        "candidate_ia_and_garden_rain",
        0.0,
        0.0,
        "Only candidate IA runoff and direct garden rainfall load storage",
    ),
    (
        "plus_other_ground_runoff",
        0.0,
        1.0,
        "Adds full first-1.5-inch runoff from remaining on-parcel soft/mixed ground",
    ),
    (
        "plus_off_parcel_runoff",
        1.0,
        0.0,
        "Adds full first-1.5-inch runoff from the off-parcel contributing area (cover unknown)",
    ),
    (
        "plus_off_parcel_and_other_ground_runoff",
        1.0,
        1.0,
        "Adds full runoff from the off-parcel area and remaining on-parcel ground",
    ),
)
SPLITS = {
    "single": "One hydraulic component",
    "pooled": "Inflow split between components ideally (upper split)",
    "all_to_least": "All inflow reaches the component with the least remaining storage (lower split)",
}
REFERENCE = {
    "storage": "perimeter_cell_minimum",
    "candidate": "base",
    "load": "plus_off_parcel_runoff",
}
VOLUME_EQUIVALENT_LABEL = (
    "Hypothetical volume-equivalent: candidate IA whose first 1.5-inch runoff fits in the "
    "storage left after other inflow; not verified qualifying managed area"
)
QUANTITY_STATUS = {
    "runoff_supplied_cuft": "modeled under the row assumptions",
    "runoff_captured_cuft": "not established; the row assumes all supplied runoff reaches storage",
    "runoff_stored_cuft": "modeled dry-start surface storage under the row assumptions",
    "runoff_treated_cuft": "not established; treatment and drawdown are unverified",
    "qualifying_managed_area_sqft": "not established; no verified qualifying area or PWD award",
}


def _volume(value, name):
    return float(decimal(value, name))


def _components(capacity, garden_area):
    """Per-component headline storage and rain exposure; ValueError if inconsistent."""
    rows = capacity.get("components")
    if rows:
        parts = []
        for c in rows:
            named = {s.get("name"): s for s in c.get("scenarios", [])}
            if any(named.get(m, {}).get("status") != "estimated" for m in STORAGE_METHODS):
                raise ValueError(
                    "Component "
                    + str(c.get("component_id"))
                    + " lacks the perimeter-line storage range"
                )
            parts.append(
                {
                    "component_id": c.get("component_id"),
                    "rain_exposure_area_sqft": _volume(
                        c.get("rain_exposure_area_sqft"), "rain exposure"
                    ),
                    "storage_cuft": {
                        m: _volume(named[m]["volume_cuft"], m) for m in STORAGE_METHODS
                    },
                }
            )
    else:
        named = {s.get("name"): s for s in capacity.get("scenarios", [])}
        if any(
            named.get(m, {}).get("status") != "estimated" or named[m].get("volume_cuft") is None
            for m in STORAGE_METHODS
        ):
            raise LookupError(
                "Capacity result lacks the perimeter-line storage range (D4); no storage-limited price"
            )
        exposure = capacity.get("rain_exposure_area_sqft")
        parts = [
            {
                "component_id": "component-1",
                "rain_exposure_area_sqft": (
                    garden_area if exposure is None else _volume(exposure, "rain exposure")
                ),
                "storage_cuft": {m: _volume(named[m]["volume_cuft"], m) for m in STORAGE_METHODS},
            }
        ]
    totals = [sum(p["storage_cuft"][m] for p in parts) for m in STORAGE_METHODS]
    stated = capacity.get("storage_range_cuft")
    if stated is not None and (
        abs(_volume(stated[0], "storage range") - min(totals)) > 0.001
        or abs(_volume(stated[1], "storage range") - max(totals)) > 0.001
    ):
        raise ValueError("Storage range does not match its component volumes")
    if abs(sum(p["rain_exposure_area_sqft"] for p in parts) - garden_area) > 0.1:
        raise ValueError("Capacity rainfall exposure does not match the garden footprint")
    return parts, [min(totals), max(totals)]


def _external_candidate(case, scenario, footprint):
    """Candidate components outside the bed (H16) and their weighted IA."""
    area = decimal(scenario.get("area_sqft"), "candidate area")
    geometry, errors = _candidate_geometry(case, scenario, area, False)
    if errors:
        raise ValueError("; ".join(errors))
    components = scenario.get("weighted_components")
    if components is None:
        components = (
            [
                {
                    "geometry": mapping(geometry),
                    "impervious_fraction": 1.0,
                    "basis": scenario.get("basis") or "Supplied contributing IA hypothesis",
                }
            ]
            if geometry is not None
            else []
        )
    external = []
    for component in components:
        region = area_only(shape(component["geometry"]).difference(footprint))
        if not region.is_empty:
            external.append({**deepcopy(component), "geometry": mapping(region)})
    external_area = sum(
        case_area_sqft(shape(c["geometry"]), case) * float(decimal(c["impervious_fraction"]))
        for c in external
    )
    return external, min(float(area), external_area), max(0.0, float(area) - external_area)


def _scaled(components, candidate, managed, row_id, assumptions, label):
    share = managed / candidate if candidate else 0.0
    scaled = [
        {
            **deepcopy(c),
            "impervious_fraction": float(c["impervious_fraction"]) * share,
            "basis": c["basis"] + "; scaled to the storage-limited volume-equivalent",
        }
        for c in components
    ]
    out = {"id": row_id, "area_sqft": managed, "basis": label, "assumptions": assumptions}
    if scaled:
        # The whole possible geometry is kept even at zero managed area, so the
        # ledger's overlap checks apply to every row of this candidate.
        out.update(
            geometry=mapping(area_only(union([shape(c["geometry"]) for c in scaled]))),
            weighted_components=scaled,
        )
    else:
        out["geometry"] = None
    return out


def _budget(parts, method, split, depth, external_area, loads):
    rain = [p["rain_exposure_area_sqft"] * depth for p in parts]
    storage = [p["storage_cuft"][method] for p in parts]
    available = [max(0.0, s - r) for s, r in zip(storage, rain)]
    pool = min(available) if split == "all_to_least" else sum(available)
    other_inflow = sum(loads)
    for_external = max(0.0, pool - other_inflow)
    managed = min(external_area, for_external / depth)
    inflow = external_area * depth + other_inflow
    return {
        "surface_storage_volume_cuft": sum(storage),
        "component_storage_cuft": storage,
        "direct_garden_rainfall_cuft": sum(rain),
        "storage_after_garden_rain_cuft": pool,
        "noncreditable_inflow_cuft": other_inflow,
        "available_storage_for_candidate_runoff_cuft": for_external,
        "volume_equivalent_managed_ia_sqft": managed,
        "quantities": {
            "runoff_supplied_cuft": sum(rain) + inflow,
            "runoff_captured_cuft": None,
            "runoff_stored_cuft": sum(min(r, s) for r, s in zip(rain, storage)) + min(inflow, pool),
            "runoff_treated_cuft": None,
            "qualifying_managed_area_sqft": None,
        },
        "unaccommodated_candidate_runoff_cuft": max(0.0, external_area * depth - managed * depth),
    }


def _skeleton(engineering, capacity):
    return {
        "version": VERSION,
        "system_id": engineering.get("system_id"),
        "system_type": engineering.get("system_type"),
        "status": "unavailable",
        "capacity_status": capacity.get("status"),
        "blocking_reasons": list(capacity.get("blocking_reasons") or []),
        "unavailable_reasons": list(capacity.get("unavailable_reasons") or []),
        "review_flags": deepcopy(capacity.get("review_flags") or []),
        "headline": None,
        "current_estimate": None,
        "current_estimate_withheld_reason": None,
        "runs": [],
        "range": None,
        "storage_range_cuft": deepcopy(capacity.get("storage_range_cuft")),
        "storage_sensitivity_range_cuft": deepcopy(capacity.get("volume_range_cuft")),
        "storage_sensitivity_missing_scenarios": deepcopy(
            capacity.get("volume_range_missing_scenarios") or []
        ),
        "verified_managed_area_sqft": None,
        "verified_treatment_capacity_cuft": None,
        "quantity_status": deepcopy(QUANTITY_STATUS),
        "volume_equivalent_label": VOLUME_EQUIVALENT_LABEL,
        "source_lineage": deepcopy(engineering.get("source_lineage") or {}),
        "capacity_source_lineage": deepcopy(capacity.get("source_lineage") or {}),
        "uncertainty": {
            "status": "not_calibrated",
            "basis": "Explicit storage, load and surface hypotheses; no numerical confidence",
        },
        "do_not_sum": True,
        "reasons": [],
        "basis": "Dry-start surface storage below the perimeter-line spill level; direct garden rain and other inflow are held before candidate IA",
        "limitations": [
            "Volume-equivalent IA is a hypothesis, not a demonstrated qualifying drainage subarea",
            "Infiltration/media/underdrain recovery are excluded from capacity, not assumed measured zero",
            "Capture, treatment, drawdown and current operation remain unverified",
        ],
        "priced_by": "assessment_policy._economics",
    }


def _flag(result, code, message):
    if not any(f.get("code") == code for f in result["review_flags"]):
        result["review_flags"].append({"code": code, "message": message})


def estimate_capacity_management(
    case, frozen_gis, engineering, capacity, as_of, tariff=None, context=None
):
    """Range of storage-limited management prices for one surface system (see module docstring)."""
    result = _skeleton(engineering, capacity)
    try:
        if system_identity(capacity.get("system_id")) != system_identity(
            engineering.get("system_id")
        ):
            raise ValueError("Capacity belongs to a different system")
        ctx = context or system_context(case, frozen_gis, engineering, as_of, tariff)
        result["as_of"] = ctx["day"].isoformat()
        result["warnings"] = list(ctx["warnings"])
        result["baseline"] = deepcopy(ctx["baseline"])
        lineage = lineage_errors(
            capacity.get("source_lineage"), ctx["case_sha256"], frozen_gis, "Capacity"
        )
        if lineage:
            raise ValueError("; ".join(lineage))
        if (
            ctx["excluded"]
            or capacity.get("status") == "excluded"
            or engineering.get("status") == "excluded"
        ):
            reasons = (
                ctx["excluded_reasons"]
                if ctx["excluded"] or engineering.get("status") == "excluded"
                else []
            ) + (
                [capacity["reason"]]
                if capacity.get("status") == "excluded" and capacity.get("reason")
                else []
            )
            result.update(
                status="excluded",
                reasons=list(dict.fromkeys(reasons or ["Physical layer excluded this system"])),
            )
            return result
        if capacity.get("status") == "blocked":
            # Physical contradiction (structure in footprint, terrain predates the
            # system, contradictory units) is not "unavailable" evidence.
            reasons = result["blocking_reasons"] or (
                [capacity["reason"]] if capacity.get("reason") else []
            )
            result.update(
                status="blocked",
                reasons=list(dict.fromkeys(reasons or ["Physical capacity result is blocked"])),
            )
            return result
        if capacity.get("status") != "estimated":
            result.update(
                status="unavailable",
                reasons=list(
                    dict.fromkeys(
                        result["unavailable_reasons"]
                        or ([capacity["reason"]] if capacity.get("reason") else [])
                        or [
                            "Usable local surface-storage estimate unavailable; no storage-limited price"
                        ]
                    )
                ),
            )
            return result
        full_footprint = area_only(shape(engineering["footprint_geometry"]))
        if full_footprint.difference(shape(case["parcel"])).area > 1e-8:
            raise ValueError("Cross-parcel system storage allocation is unknown")
        footprint = area_only(full_footprint.intersection(shape(case["parcel"])))
        if footprint.is_empty:
            raise ValueError("On-parcel garden footprint unavailable")
        garden_area = case_area_sqft(footprint, case)
        parts, storage_range = _components(capacity, garden_area)
        if len(parts) > 1:
            _flag(
                result,
                "disconnected_components",
                "Footprint has disconnected parts; each component is budgeted separately and the inflow split is bracketed",
            )
        depth = float(TREATMENT_DEPTH_INCHES / 12)
        splits = ("single",) if len(parts) == 1 else ("pooled", "all_to_least")
        result.update(
            garden_area_sqft=garden_area,
            treatment_depth_inches=float(TREATMENT_DEPTH_INCHES),
            component_count=len(parts),
            storage_range_cuft=storage_range,
            components=[
                {
                    k: deepcopy(p[k])
                    for k in ("component_id", "rain_exposure_area_sqft", "storage_cuft")
                }
                for p in parts
            ],
        )
        memo = {}
        for run in engineering.get("runs", []):
            route = run_route(run)
            off_area = run.get("off_parcel_area_sqft")
            off_area = None if off_area is None else _volume(off_area, "off_parcel_area_sqft")
            bounded = route["route_state"] == "complete_in_window" and off_area is not None
            rows = []
            candidates = [
                s
                for s in run.get("area_scenarios", [])
                if run.get("name") == HEADLINE_RUN or s.get("id") == "base"
            ]
            for candidate in candidates:
                components, external_area, bed = _external_candidate(case, candidate, footprint)
                region = area_only(
                    shape(run.get("on_parcel_geometry") or case["parcel"]).difference(footprint)
                )
                other_ground = max(0.0, case_area_sqft(region, case) - external_area)
                for method in STORAGE_METHODS:
                    for split in splits:
                        for load, off_fraction, other_fraction, meaning in LOADS:
                            row_id = "/".join((candidate.get("id"), method, split, load))
                            assumptions = [
                                "Surface storage starts empty for the event",
                                "System bed is noncreditable; its direct rainfall reserves its own component storage first",
                                "Other inflow reaching the system is held before candidate IA counts as managed",
                                "No infiltration/media/outlet recovery added to capacity",
                                meaning,
                                SPLITS[split],
                                "Static accommodation does not verify capture, treatment or drawdown",
                            ]
                            row = {
                                "id": row_id,
                                "candidate_scenario": candidate.get("id"),
                                "interpretation_scenario": candidate.get("interpretation_scenario"),
                                "storage_method": method,
                                "inflow_split": split,
                                "load": load,
                                "off_parcel_runoff_fraction": off_fraction,
                                "other_ground_runoff_fraction": other_fraction,
                                "off_parcel_area_sqft": off_area,
                                "other_ground_area_sqft": other_ground,
                                "candidate_ia_sqft": candidate.get("area_sqft"),
                                "candidate_ia_outside_bed_sqft": external_area,
                                "system_bed_ia_excluded_sqft": bed,
                                "route_state": route["route_state"],
                                "partial_label": _storage_label(route),
                                "volume_equivalent_is_hypothetical": True,
                                "assumptions": assumptions,
                                "monthly_savings": None,
                                "annual_savings": None,
                                "status": "pending",
                                "reasons": [],
                            }
                            if off_fraction and off_area is None:
                                row.update(
                                    status="unavailable",
                                    reasons=[
                                        "Off-parcel contributing area unknown; its load cannot be budgeted"
                                    ],
                                )
                                rows.append(row)
                                continue
                            loads = [
                                off_fraction * (off_area or 0.0) * depth,
                                other_fraction * other_ground * depth,
                            ]
                            row.update(_budget(parts, method, split, depth, external_area, loads))
                            managed = row["volume_equivalent_managed_ia_sqft"]
                            key = (run.get("name"), candidate.get("id"), round(managed, 6))
                            if key not in memo:
                                memo[key] = price_scenario(
                                    ctx,
                                    case,
                                    _scaled(
                                        components,
                                        external_area,
                                        managed,
                                        row_id,
                                        assumptions,
                                        "Storage-limited volume-equivalent hypothesis",
                                    ),
                                    route=route,
                                )
                            priced = memo[key]
                            row.update(
                                status=priced["status"],
                                reasons=list(priced["reasons"]),
                                monthly_savings=priced["monthly_savings"],
                                annual_savings=priced["annual_savings"],
                                priced={
                                    k: deepcopy(priced.get(k))
                                    for k in (
                                        "bill",
                                        "ledger",
                                        "alternatives",
                                        "weighted_components",
                                        "fractional_ia_is_assumed",
                                        "priced_by",
                                    )
                                },
                            )
                            if priced.get("alternatives"):
                                row["alternatives"] = deepcopy(priced["alternatives"])
                            rows.append(row)
            result["runs"].append(
                {
                    "name": run.get("name"),
                    "route_state": route["route_state"],
                    "route_state_reason": route["route_state_reason"],
                    "partial_label": _storage_label(route),
                    "off_parcel_area_sqft": off_area,
                    "load_bounded": bounded,
                    "scenarios": rows,
                }
            )
        _headline(result, ctx)
    except LookupError as exc:
        result.update(
            status="unavailable", headline=None, current_estimate=None, reasons=[str(exc)]
        )
    except (ValueError, KeyError, TypeError, AttributeError, ShapelyError) as exc:
        result.update(status="blocked", headline=None, current_estimate=None, reasons=[str(exc)])
    return result


def _headline(result, ctx):
    nominal = next((r for r in result["runs"] if r["name"] == HEADLINE_RUN), None)
    all_rows = [s for r in result["runs"] for s in r["scenarios"]]
    if nominal is None:
        result["status"] = "blocked"
        result["reasons"] = list(
            dict.fromkeys(
                ctx["errors"]
                + ["No nominal run; sensitivity runs never substitute for the headline"]
            )
        )
        return
    rows = nominal["scenarios"]
    values = value_range(rows)
    reference_id = "/".join(
        (
            REFERENCE["candidate"],
            REFERENCE["storage"],
            "single" if result.get("component_count") == 1 else "pooled",
            REFERENCE["load"],
        )
    )
    reference = next((s for s in rows if s["id"] == reference_id), None)
    # H2: the nominal reference row is the gate; a blocked nominal headline blocks
    # the result and no sensitivity run or other interpretation substitutes.
    if values is None or reference is None or reference["status"] == "blocked":
        result["status"] = "blocked"
        result["reasons"] = list(
            dict.fromkeys(
                ctx["errors"]
                + ((reference or {}).get("reasons") or [r for s in rows for r in s["reasons"]])
                or ["No priced nominal storage scenario"]
            )
        )
        return
    bounded = nominal["load_bounded"]
    withheld = None
    if not bounded:
        withheld = (
            "Upstream extent is partial: the off-parcel load may be larger, so storage-limited savings may be lower"
            if nominal["route_state"] == "partial_upstream_unknown"
            else "Off-parcel contributing area is unknown, so its load is unbounded"
        )
        _flag(result, "off_parcel_load_unbounded", withheld)
    quantity = lambda key: value_range(
        [{"status": "calculated", key: s["quantities"][key]} for s in rows if "quantities" in s],
        key,
    )
    blocked_rows = any(s["status"] == "blocked" for s in rows)
    result["headline"] = {
        "run": HEADLINE_RUN,
        "status": (
            "partial_range" if not bounded else "range_incomplete" if blocked_rows else "range"
        ),
        "route_state": nominal["route_state"],
        "partial_label": nominal["partial_label"],
        "annual_savings_range": values if bounded else [None, values[1]],
        "in_window_annual_savings_range": values,
        "lower_bound_withheld_reason": withheld,
        "storage_range_cuft": deepcopy(result["storage_range_cuft"]),
        "storage_methods": list(STORAGE_METHODS),
        "loads": [name for name, *_ in LOADS],
        "inflow_splits": sorted({s["inflow_split"] for s in rows}),
        "interpretation_scenarios": sorted({str(s["candidate_scenario"]) for s in rows}),
        "volume_equivalent_managed_ia_range_sqft": value_range(
            rows, "volume_equivalent_managed_ia_sqft"
        ),
        "volume_equivalent_label": VOLUME_EQUIVALENT_LABEL,
        "runoff_supplied_range_cuft": quantity("runoff_supplied_cuft"),
        "runoff_stored_range_cuft": quantity("runoff_stored_cuft"),
        "runoff_captured_cuft": None,
        "runoff_treated_cuft": None,
        "qualifying_managed_area_sqft": None,
        "reference_scenario": reference_id,
        "blocked_scenarios": [
            {"id": s["id"], "reasons": s["reasons"]} for s in rows if s["status"] == "blocked"
        ],
        "unavailable_scenarios": [
            {"id": s["id"], "reasons": s["reasons"]} for s in rows if s["status"] == "unavailable"
        ],
        "basis": (
            "Range across perimeter-line storage methods, runoff-load assumptions and labelled candidate-IA "
            "interpretations of the nominal run; not a confidence interval and not a bound on all error"
        ),
    }
    if bounded and reference is not None and annual_values(reference):
        result["current_estimate"] = {
            "run": HEADLINE_RUN,
            "role": (
                "Storage-limited reference row: one named row of "
                "the range; not a bound, best estimate or conservative figure"
            ),
            **deepcopy(reference),
        }
    else:
        result["current_estimate_withheld_reason"] = (
            withheld or "Reference storage-limited row is not priced"
        )
    result["status"] = "storage_limited_range"
    priced = [s for s in all_rows if annual_values(s)]
    result["range"] = {
        "annual_savings": value_range(priced),
        "volume_equivalent_managed_ia_sqft": value_range(
            priced, "volume_equivalent_managed_ia_sqft"
        ),
        "basis": "Envelope of every run, storage method, load and interpretation; not a confidence interval",
    }
    result["reasons"] = list(dict.fromkeys(ctx["errors"]))
