"""Small, hash-checked saved views. No analysis, acquisition or jurisdiction imports."""

from hashlib import sha256
from pathlib import Path
import json
import os
import tempfile
from .engine import canonical, input_hash, ENGINE_VERSION

VIEW_VERSION = 4  # 4: compact display (outlines, no per-cell grids or unused geometry)


def atomic_write(path, content):
    """Write bytes/text through a unique temporary file in the same folder, then replace."""
    path = Path(path)
    data = content.encode() if isinstance(content, str) else content
    descriptor, temp = tempfile.mkstemp(
        dir=path.parent, prefix="." + path.name + ".", suffix=".tmp"
    )
    try:
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(data)
        os.replace(temp, path)
    except BaseException:
        try:
            os.unlink(temp)
        except FileNotFoundError:
            pass
        raise


def atomic_json(path, value):
    atomic_write(path, canonical(value))


# Display catchment outlines are rounded to this many decimals of native units
# (1 mm or 0.001 ft); exact geometries stay in analysis.json and the exports.
DISPLAY_DECIMALS = 3
# Per-cell grids and geometry-only members the browser never draws or reads.
_DRAINAGE_GRIDS = ("labels", "next_cells", "counts", "outlets")
_RUN_GEOMETRY = ("unknown_ground_union_geometry", "known_ia_union_geometry", "micro_basins")
_AI_GEOMETRY = (
    "coverage_geometry",
    "geometries",
    "roof_supplement_geometry",
    "ai_ia_on_unknown_geometry",
    "ai_pervious_on_unknown_geometry",
)
OMITTED_FOR_DISPLAY = {
    "drainage": "per-cell labels, next cells, counts and outlet rows",
    "research_drainage": "rasters; micro-basins and union geometries; sensitivity-run outlines",
    "modeled_integration": "AI-roof research rerun, AI class geometries, outlines after the first run",
    "automatic.landcover": "cover polygons and coverage outlines (drawn from the case features)",
    "precision": f"catchment outlines rounded to {DISPLAY_DECIMALS} decimals of native units",
    "full_result": "analysis.json export (and gis-analysis.json) keep every array and exact geometry",
}


def _rounded(geometry, places=DISPLAY_DECIMALS):
    """GeoJSON geometry with coordinates rounded for display only."""

    def walk(value):
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            return round(value, places)
        if isinstance(value, (list, tuple)):
            return [walk(v) for v in value]
        return value

    if not isinstance(geometry, dict):
        return geometry
    if geometry.get("type") == "GeometryCollection":
        return {**geometry, "geometries": [_rounded(g, places) for g in geometry["geometries"]]}
    return {**geometry, "coordinates": walk(geometry.get("coordinates", []))}


def _outlines(items, keep_geometry=True):
    out = []
    for item in items or []:
        if not isinstance(item, dict):
            out.append(item)
            continue
        row = {k: v for k, v in item.items() if k not in ("geometry", "known_ia_geometry")}
        if keep_geometry and "geometry" in item:
            row["geometry"] = _rounded(item["geometry"])
        out.append(row)
    return out


def _research_view(research):
    def run(value, draw):
        if not isinstance(value, dict):
            return value
        out = {k: v for k, v in value.items() if k not in ("rasters", *_RUN_GEOMETRY)}
        if not draw:
            out.pop("feature_audit", None)
            out.pop("flow_paths", None)
        for key in ("catchments", "outlet_catchments"):
            if key in out:
                out[key] = _outlines(out[key], keep_geometry=draw)
        return out

    out = {k: v for k, v in research.items() if k != "rasters"}
    if isinstance(out.get("primary"), dict):
        out["primary"] = run(out["primary"], True)
    if isinstance(out.get("sensitivity"), list):
        out["sensitivity"] = [run(v, False) for v in out["sensitivity"]]
    return out


def display_analysis(result):
    """Compact browser view of a saved result: findings, areas, money and drawn outlines.

    Keeps measurements, assessment findings, provenance and the map layers the app
    draws (drainage/research/first AI-run outlines, flow paths, map features).
    Per-cell grids, rasters and geometry the app never reads are omitted
    (``OMITTED_FOR_DISPLAY``); the saved analysis.json export keeps all of them.
    """
    from .quality import safe_physical_view

    result = safe_physical_view(result)
    out = dict(result)
    if isinstance(out.get("drainage"), dict):
        out["drainage"] = {k: v for k, v in out["drainage"].items() if k not in _DRAINAGE_GRIDS}
        if "catchments" in out["drainage"]:
            out["drainage"]["catchments"] = _outlines(out["drainage"]["catchments"])
    if isinstance(out.get("research_drainage"), dict):
        out["research_drainage"] = _research_view(out["research_drainage"])
    if isinstance(out.get("modeled_integration"), dict):
        m = dict(out["modeled_integration"])
        m.pop("ai_roof_drainage", None)  # runs already contain its display catchments
        if isinstance(m.get("ai"), dict):
            m["ai"] = {k: v for k, v in m["ai"].items() if k not in _AI_GEOMETRY}
        if isinstance(m.get("measurement"), dict):
            m["measurement"] = {k: v for k, v in m["measurement"].items() if k != "geometries"}
        m.pop("observed_pervious_geometry", None)
        if isinstance(m.get("runs"), list):
            m["runs"] = [
                (
                    {**r, "catchments": _outlines(r.get("catchments"), keep_geometry=i == 0)}
                    if isinstance(r, dict)
                    else r
                )
                for i, r in enumerate(m["runs"])
            ]
        out["modeled_integration"] = m
    automatic = out.get("automatic")
    if isinstance(automatic, dict) and isinstance(automatic.get("landcover"), dict):
        cover = {
            k: v
            for k, v in automatic["landcover"].items()
            if k not in ("features", "coverage_geometry", "canopy_geometry")
        }
        out["automatic"] = {**automatic, "landcover": cover}
    out["display_only"] = True
    out["omitted_for_display"] = OMITTED_FOR_DISPLAY
    return out


def elevations_digest(elevations):
    return sha256(canonical(elevations).encode()).hexdigest()


def compact_case(case, saved_cases=()):
    """Case for a browser response without the per-cell elevation grid.

    Only when an identical grid is in a saved case (``saved_cases``: callables or
    case dicts) is the grid replaced by ``terrain.elevations_omitted`` (hash and
    shape); ``restore_case`` puts it back on the way in. Otherwise the case is
    returned unchanged, so nothing that cannot be restored is ever dropped.
    """
    terrain = case.get("terrain") if isinstance(case, dict) else None
    grid = terrain.get("elevations") if isinstance(terrain, dict) else None
    if not grid or not isinstance(grid, list) or not isinstance(grid[0], list):
        return case
    for saved in saved_cases:
        saved = saved() if callable(saved) else saved
        other = ((saved or {}).get("terrain") or {}).get("elevations")
        if other is grid or other == grid:
            break
    else:
        return case
    compact = {k: v for k, v in terrain.items() if k != "elevations"}
    compact["elevations_omitted"] = {
        "sha256": elevations_digest(grid),
        "rows": len(grid),
        "cols": len(grid[0]),
        "restore": "Restored from the saved case on the next request; full grid in the case.json export",
    }
    return {**case, "terrain": compact}


def restore_case(case, saved_cases=()):
    """Inverse of ``compact_case``; refuses rather than guessing a missing grid."""
    terrain = case.get("terrain") if isinstance(case, dict) else None
    marker = terrain.get("elevations_omitted") if isinstance(terrain, dict) else None
    if not marker:
        return case
    for saved in saved_cases:
        saved = saved() if callable(saved) else saved
        grid = ((saved or {}).get("terrain") or {}).get("elevations")
        if (
            isinstance(grid, list)
            and grid
            and len(grid) == marker.get("rows")
            and len(grid[0]) == marker.get("cols")
            and elevations_digest(grid) == marker.get("sha256")
        ):
            restored = {k: v for k, v in terrain.items() if k != "elevations_omitted"}
            restored["elevations"] = grid
            return {**case, "terrain": restored}
    raise ValueError(
        "The elevation grid omitted from this compact case is not in any saved revision; "
        "reopen the saved case before editing"
    )


def saved_view(folder, case):
    """Small cached display view. The cache key includes the current interpretation
    versions, so a version bump re-evaluates quality instead of serving a stale label."""
    from .quality import current_versions

    folder = Path(folder)
    source = folder / "analysis.json"
    expected = input_hash(case)
    if not source.exists():
        return {
            "case": case,
            "analysis": None,
            "saved_status": {
                "state": "missing",
                "message": "No saved result. Run explicitly when ready.",
                "revision": expected,
            },
        }
    content = source.read_bytes()
    digest = sha256(content).hexdigest()
    versions = current_versions()
    viewfile = folder / "analysis-view.json"
    manifestfile = folder / "analysis-view-manifest.json"
    if viewfile.exists() and manifestfile.exists():
        manifest = json.loads(manifestfile.read_text())
        if (
            manifest.get("source_sha256") == digest
            and manifest.get("input_sha256") == expected
            and manifest.get("view_version") == VIEW_VERSION
            and manifest.get("interpretation_versions") == versions
        ):
            payload = viewfile.read_bytes()
            if sha256(payload).hexdigest() != manifest["view_sha256"]:
                raise ValueError("Saved display hash mismatch")
            result = json.loads(payload)
            return {"case": case, "analysis": result, "saved_status": _status(result, expected)}
    result = json.loads(content)
    if result.get("input_sha256") != expected:
        return {
            "case": case,
            "analysis": None,
            "saved_status": {
                "state": "input_changed",
                "message": "Saved result does not match current inputs. Recalculate explicitly.",
                "revision": expected,
            },
        }
    view = display_analysis(result)
    atomic_json(viewfile, view)
    atomic_json(
        manifestfile,
        {
            "view_version": VIEW_VERSION,
            "source_sha256": digest,
            "input_sha256": expected,
            "interpretation_versions": versions,
            "view_sha256": sha256(viewfile.read_bytes()).hexdigest(),
        },
    )
    return {"case": case, "analysis": view, "saved_status": _status(view, expected)}


def _status(result, revision=None):
    old = result.get("engine_version") != ENGINE_VERSION
    q = result.get("quality_review", {})
    if q.get("status") in ("outdated", "invalidated"):
        return {
            "state": "outdated",
            "message": q["reason"],
            "label": q.get("label"),
            "engine_changed": old,
            "recompute_available": True,
            "revision": revision,
            "assessment_as_of": result.get("assessment", {}).get("as_of"),
        }
    return {
        "state": "historical" if old else "saved",
        "message": "Showing saved results; no recalculation or source refresh."
        + (" Saved engine version differs from current code." if old else ""),
        "engine_changed": old,
        "recompute_available": False,
        "revision": revision,
        "assessment_as_of": result.get("assessment", {}).get("as_of"),
    }
