"""Location-neutral physical GIS analysis. No tariffs, credits or city providers."""

from copy import deepcopy
from datetime import datetime, timezone
from hashlib import sha256
import json
import re
import time
import uuid
from shapely.geometry import shape, box, mapping
from .geometry import (
    measure,
    effective_features,
    area_sqft,
    case_area_sqft,
    union,
    projected_crs,
    area_only,
)
from .validation import validate_case

ENGINE_VERSION = "gis-engine-v5"


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


def input_hash(case):
    return sha256(canonical(case).encode()).hexdigest()


def new_case(name="New GIS project", *, crs):
    return {
        "schema_version": 1,
        "id": str(uuid.uuid4()),
        "name": name,
        "crs": crs,
        "parcel": None,
        "features": {"type": "FeatureCollection", "features": []},
        "sources": [],
        "corrections": [],
        "references": [],
        "terrain": None,
        "assumptions": [],
        "manual_review_minutes": None,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }


def validate_input(case):
    if case.get("schema_version") != 1:
        raise ValueError("Unsupported case schema version")
    if not re.fullmatch(r"[A-Za-z0-9_-]{1,80}", case.get("id", "")):
        raise ValueError("Invalid case ID")
    if len(case.get("features", {}).get("features", [])) > 20000:
        raise ValueError("Property case exceeds 20,000 feature limit")
    canonical(case)
    projected_crs(case["crs"])
    if not case.get("parcel"):
        raise ValueError("A parcel polygon is required")


def _feature_cells(geometry, rows, cols, x, y, size, touched):
    """Cells a feature occupies: touched cells for barriers, covered centres for roofs."""
    import math
    import numpy as np
    import shapely

    if geometry.is_empty:
        return set()
    minx, miny, maxx, maxy = geometry.bounds
    c0 = max(0, int(math.floor((minx - x) / size)) - 1)
    c1 = min(cols, int(math.ceil((maxx - x) / size)) + 1)
    r0 = max(0, int(math.floor((y - maxy) / size)) - 1)
    r1 = min(rows, int(math.ceil((y - miny) / size)) + 1)
    if r0 >= r1 or c0 >= c1:
        return set()
    rr, cc = np.mgrid[r0:r1, c0:c1]
    if touched:
        hit = shapely.intersects(
            geometry,
            shapely.box(x + cc * size, y - (rr + 1) * size, x + (cc + 1) * size, y - rr * size),
        )
    else:
        hit = shapely.covers(geometry, shapely.points(x + (cc + 0.5) * size, y - (rr + 0.5) * size))
    return {(int(r), int(c)) for r, c in zip(rr[hit], cc[hit])}


def routing(case, measurement):
    from .drainage import route_grid
    from .extent import coverage as terrain_coverage

    if not case.get("terrain"):
        return {
            "status": "unavailable",
            "warnings": [
                "No suitable elevation grid supplied; no drainage reconstruction performed"
            ],
        }, {}
    grid = deepcopy(case["terrain"])
    if grid.get("crs") != case["crs"]:
        raise ValueError("Terrain and case CRS differ; align explicitly before routing")
    heights = grid["elevations"]
    rows = len(heights)
    cols = len(heights[0])
    if rows * cols > 250000:
        raise ValueError("Terrain exceeds 250,000-cell property limit; crop before import")
    size = grid["cell_size"]
    x, y = grid["origin"]
    buffer_size = grid.get("settings", {}).get("required_buffer_native_units", 0)
    if buffer_size < 0:
        raise ValueError("Routing buffer must be nonnegative")
    expected_unit = projected_crs(case["crs"]).axis_info[0].unit_conversion_factor
    unit_scale = {"m": 1.0, "ft": 0.3048, "us-ft": 1200 / 3937}.get(grid.get("horizontal_unit"))
    if unit_scale is None or abs(expected_unit - unit_scale) > 1e-9:
        raise ValueError("Terrain horizontal unit does not match CRS")
    # Run-level extent honours measured coverage (envelope and NoData), not only the setting.
    extent = terrain_coverage(case, grid)
    coverage_warnings = []
    if not extent["coverage_complete"]:
        grid.setdefault("settings", {})["extent_sufficient"] = False
        if not extent["terrain_covers_parcel_buffer"]:
            coverage_warnings.append(
                "Partial routing extent: terrain does not cover the parcel and requested buffer"
            )
        if extent["nodata_cells_in_parcel_buffer"]:
            coverage_warnings.append(
                "Partial routing extent: NoData cells lie within the parcel and requested buffer"
            )
    features = effective_features(case)
    parcel = shape(case["parcel"])
    in_grid = lambda p: 0 <= p[0] < rows and 0 <= p[1] < cols
    nodata = {(r, c) for r, row in enumerate(heights) for c, v in enumerate(row) if v is None}
    storage = {tuple(v) for v in grid.get("storage", [])}
    # Barriers rasterize by touched cell and roofs by covered centre. Overlaps are
    # resolved by precedence (barrier > roof), never by aborting the run (C2).
    barrier_cells = {
        f["id"]: _feature_cells(shape(f["geometry"]), rows, cols, x, y, size, True)
        for f in features
        if f["properties"].get("layer") == "barrier"
    }
    roof_features = [
        f
        for f in features
        if f["properties"].get("class") == "roof" and f["properties"].get("layer") == "surface"
    ]
    roof_cells = {
        f["id"]: _feature_cells(shape(f["geometry"]), rows, cols, x, y, size, False)
        for f in roof_features
    }
    unusable = nodata | storage
    barrier = {tuple(v) for v in grid.get("barriers", [])} | {
        p for cells in barrier_cells.values() for p in cells if p not in unusable
    }
    roof_all = {tuple(v) for v in grid.get("roofs", [])} | {
        p for cells in roof_cells.values() for p in cells if p not in unusable
    }
    roof = roof_all - barrier
    representation = []
    notes = []
    if roof_all & barrier:
        notes.append(
            f"{len(roof_all&barrier)} roof cell(s) overlapping barriers were routed as barriers (barrier precedence)"
        )
    # Inlets: one per cell, inside valid terrain; an inlet clears its own cell.
    sources = {str(i["id"]): ("terrain", tuple(i["cell"])) for i in grid.get("inlets", [])}
    for f in features:
        if f["properties"].get("layer") == "inlet":
            pt = shape(f["geometry"])
            if pt.geom_type != "Point":
                pt = pt.representative_point()
            sources[str(f["id"])] = ("feature", (int((y - pt.y) // size), int((pt.x - x) // size)))
    inlets = []
    taken = {}
    dropped = set()
    for identifier in sorted(sources):
        origin, cell = sources[identifier]
        reason = None
        if not in_grid(cell):
            reason = "outside terrain extent"
        elif cell in nodata:
            reason = "falls on a NoData cell"
        elif cell in storage:
            reason = "falls on an explicit storage cell"
        elif cell in taken:
            reason = "shares a grid cell with inlet " + taken[cell]
        if reason:
            dropped.add(identifier)
            representation.append(
                {
                    "id": identifier,
                    "layer": "inlet",
                    "cells": 0,
                    "status": "not_represented_on_grid",
                    "reason": reason,
                }
            )
            continue
        cleared = [name for name, cells in (("barrier", barrier), ("roof", roof)) if cell in cells]
        barrier.discard(cell)
        roof.discard(cell)
        taken[cell] = identifier
        inlets.append({"id": identifier, "cell": list(cell)})
        representation.append(
            {
                "id": identifier,
                "layer": "inlet",
                "cells": 1,
                "status": "represented",
                **({"cleared": cleared} if cleared else {}),
            }
        )
        if cleared:
            notes.append(
                f'Inlet {identifier} clears the {"/".join(cleared)} designation of its own cell'
            )
    for identifier, cells in sorted(barrier_cells.items()):
        n = len(cells & barrier)
        representation.append(
            {
                "id": identifier,
                "layer": "barrier",
                "cells": n,
                "status": "represented" if n else "not_represented_on_grid",
                **({} if n else {"reason": "no valid terrain cell touched"}),
            }
        )
    for identifier, cells in sorted(roof_cells.items()):
        n = len(cells & roof)
        representation.append(
            {
                "id": identifier,
                "layer": "roof",
                "cells": n,
                "status": "represented" if n else "not_represented_on_grid",
                **(
                    {} if n else {"reason": "no valid terrain cell centre covered outside barriers"}
                ),
            }
        )
    # Pipe links from inlet sources; links from a roof feature become roof connections.
    roof_ids = {f["id"] for f in roof_features}
    links = []
    roof_links = {}
    for link in grid.get("connections", []):
        if str(link.get("from")) in dropped:
            notes.append(f'Connection from unrepresented inlet {link.get("from")} omitted')
        else:
            links.append(link)
    for f in features:
        p = f["properties"]
        if p.get("layer") != "connection":
            continue
        source = p.get("from")
        entry = {"to": p.get("to"), "evidence": p.get("evidence", "unknown")}
        if source in roof_ids:
            for cell in roof_cells[source] & roof:
                roof_links.setdefault(cell, []).append(entry)
        elif str(source) in dropped:
            notes.append(f"Connection from unrepresented inlet {source} omitted")
        else:
            links.append({"from": source, **entry})
    roof_connections = [c for c in grid.get("roof_connections", []) if tuple(c["cell"]) in roof]
    if len(roof_connections) < len(grid.get("roof_connections", [])):
        notes.append(
            f'{len(grid["roof_connections"])-len(roof_connections)} supplied roof connection(s) omitted: cell is no longer a roof cell'
        )
    explicit = {tuple(c["cell"]) for c in roof_connections}
    conflicts = 0
    for cell, entries in sorted(roof_links.items()):
        if cell in explicit:
            continue
        if len({(e["to"], e["evidence"]) for e in entries}) > 1:
            conflicts += 1
            continue
        roof_connections.append({"cell": list(cell), **entries[0]})
    if conflicts:
        notes.append(
            f"{conflicts} roof cell(s) with conflicting roof connections remain unresolved"
        )
    grid["barriers"] = [list(p) for p in sorted(barrier)]
    grid["roofs"] = [list(p) for p in sorted(roof)]
    grid["inlets"] = inlets
    grid["connections"] = links
    grid["roof_connections"] = roof_connections
    import numpy as np
    import shapely

    rr, cc = np.mgrid[0:rows, 0:cols]
    grid["parcel_mask"] = shapely.covers(
        parcel, shapely.points(x + (cc + 0.5) * size, y - (rr + 0.5) * size)
    ).tolist()
    output = route_grid(grid)
    output["warnings"].extend(coverage_warnings)
    missing = [r["id"] for r in representation if r["status"] == "not_represented_on_grid"]
    if missing:
        output["warnings"].append(
            "Features not represented on the routing grid: " + ", ".join(missing)
        )
    output["warnings"].extend(notes)
    output["feature_representation"] = representation
    output["extent_coverage"] = extent
    output["status"] = (
        "modeled" if output["coverage_complete"] and output["extent_sufficient"] else "partial"
    )
    grouped = {}
    for r, row in enumerate(output["labels"]):
        for c, label in enumerate(row):
            if label is not None and label not in ("barrier", "nodata"):
                # Unknown roof pixels are not individual collection outlets.
                # Keep detailed labels in the grid, aggregate their display union.
                display_label = "unresolved:roof" if label.startswith("unresolved:roof:") else label
                grouped.setdefault(display_label, []).append(
                    box(x + c * size, y - (r + 1) * size, x + (c + 1) * size, y - r * size)
                )
    physical = shape(measurement["geometries"]["physical_ia"])
    geoms = {key: mapping(union(v)) for key, v in grouped.items()}

    # Roofs route only through their own cells and explicit connections. Exact roof
    # polygons are removed from every other catchment's IA, so roof slivers inside
    # ground cells are never credited to a ground outlet (C9).
    def display(label):
        return "unresolved:roof" if label.startswith("unresolved:roof:") else label

    roof_label = {}
    for f in roof_features:
        labels = {display(output["labels"][r][c]) for r, c in roof_cells[f["id"]] & roof}
        roof_label[f["id"]] = next(iter(labels)) if len(labels) == 1 else None
    by_label = {}
    for f in roof_features:
        by_label.setdefault(roof_label[f["id"]], []).append(shape(f["geometry"]))
    all_roofs = union([g for items in by_label.values() for g in items])
    others_cache = {}

    def ground_ia(key, geom):
        ia = area_only(geom.intersection(physical))
        if key in by_label and key not in others_cache:
            others_cache[key] = union(
                [g for label, items in by_label.items() if label != key for g in items]
            )
        others = others_cache.get(key, all_roofs)
        if ia.is_empty or others.is_empty or not ia.intersects(others):
            return ia
        return area_only(ia.difference(others))

    output["catchments"] = [
        {
            "outlet": key,
            "geometry": geom,
            "contributing_area_sqft": case_area_sqft(shape(geom), case),
            "on_parcel_area_sqft": case_area_sqft(shape(geom).intersection(parcel), case),
            "on_parcel_physical_ia_sqft": case_area_sqft(ground_ia(key, shape(geom)), case),
            "off_parcel_physical_ia_sqft": None,
            "eligibility": "Not established by routing",
        }
        for key, geom in geoms.items()
    ]
    for catchment in output["catchments"]:
        for key, value in list(catchment.items()):
            if key.endswith("_sqft"):
                catchment[key[:-5] + "_m2"] = None if value is None else value * 0.09290304
    output["origin"] = grid["origin"]
    output["cell_size"] = size
    output["crs"] = case["crs"]
    output["display_grouping"] = (
        "Unconnected roof cells grouped as unresolved:roof; per-cell routing labels retained separately"
    )
    output["area_accounting_crs"] = case.get("area_crs", case["crs"])
    output["grid_area_basis"] = (
        "outlets/counts use native grid-cell areas; catchment geometry areas use area_accounting_crs"
    )
    output["roof_ia_basis"] = (
        "Exact roof polygons count only toward the catchment their roof cells route to"
    )
    return output, geoms


def result_hash(result):
    """Deterministic content digest; elapsed processing time is observational."""
    return sha256(
        canonical(
            {k: v for k, v in result.items() if k not in ("analysis_sha256", "processing_seconds")}
        ).encode()
    ).hexdigest()


def analyze(case, *, source_dependencies=None):
    """Measure/reroute a frozen GIS case without importing jurisdiction code.

    source_dependencies is an explicit legacy-data interpretation option; it is
    recorded in the artifact and never changes source observations or geometry.
    New providers should mark source_dependency=True on dependent observations.
    """
    from .sources import quality_checks

    start = time.perf_counter()
    validate_input(case)
    view = (
        case
        if source_dependencies is None
        else {**case, "dependent_source_families": list(source_dependencies)}
    )
    measurement = measure(view)
    quality = quality_checks(
        [s for s in case.get("sources", []) if s.get("crs") or s.get("resolution")],
        construction_completed=case.get("construction_completed"),
    )
    drainage, geometries = routing(case, measurement)
    from .research import analyze_research

    research = analyze_research(case, measurement, drainage)
    from .model_integration import build as integrate_models

    modeled = integrate_models(case, measurement, drainage, research)
    warnings = (
        list(case.get("warnings", [])) + measurement["warnings"] + drainage.get("warnings", [])
    )
    if quality:
        warnings.append(
            "Source metadata quality has unresolved dates, units, coverage or temporal checks; see source_quality_issues"
        )
    validation = validate_case(case, measurement, geometries, research=research, modeled=modeled)
    for kind, v in validation.items():
        if v["status"] == "incomplete":
            warnings.append(
                kind.upper() + " independent validation incomplete: " + "; ".join(v["blockers"])
            )
    result = {
        "schema_version": 1,
        "result_type": "gis-analysis",
        "engine_version": ENGINE_VERSION,
        "input_sha256": input_hash(case),
        "measurement": measurement,
        "drainage": drainage,
        "research_drainage": research,
        "modeled_integration": modeled,
        "map_features": effective_features(case),
        "source_quality_issues": quality,
        "validation": validation,
        "warnings": list(dict.fromkeys(warnings)),
        "processing_settings": {
            "dependent_source_families": list(view.get("dependent_source_families", []))
        },
        "processing_seconds": round(time.perf_counter() - start, 6),
        "manual_review_minutes": case.get("manual_review_minutes"),
        "claim": "Physical GIS screening; source suitability, site conditions and independent validation remain explicit",
    }
    if case.get("imagery_age_policy"):
        result["processing_settings"]["imagery_age_policy"] = deepcopy(case["imagery_age_policy"])
    if case.get("terrain_reuse"):
        result["processing_settings"]["terrain_reuse"] = deepcopy(case["terrain_reuse"])
    # Explicit interpretation version; library versions are provenance only.
    from .quality import PHYSICAL_INTERPRETATION_VERSION, library_versions

    result["physical_interpretation_version"] = PHYSICAL_INTERPRETATION_VERSION
    result["library_versions"] = library_versions()
    result["analysis_sha256"] = result_hash(result)
    return result
