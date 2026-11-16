"""Explicit property-level reuse of pinned, previously verified native terrain.

This provider step copies terrain/provenance only, never a donor's policy or facts.
"""

from copy import deepcopy
from hashlib import sha256
import json
import math
from pathlib import Path
import re
from urllib.parse import urlparse

from shapely.geometry import shape, box
from shapely.errors import ShapelyError
from drainage_core.engine import canonical, input_hash
from drainage_core.geometry import projected_crs, reproject
from drainage_core.projection import project_case, warp_display
from drainage_core.drainage import MAX_ROUTING_CELLS

REGISTRY = Path(__file__).resolve().parents[1] / "config/terrain-reuse.json"


def parcel_id(case):
    named = re.fullmatch(r"pwd-(\d+)(?:-.*)?", str(case.get("id", "")))
    named = named.group(1) if named else None
    url = urlparse(str(case.get("boundary_source", {}).get("url", "")))
    source = (
        re.fullmatch(r"/PwdWebApi/api/v1/parcel/(\d+)/?", url.path)
        if url.hostname == "stormwater.phila.gov"
        else None
    )
    source = source.group(1) if source else None
    if named and source and named != source:
        raise ValueError("Case and source parcel identities disagree")
    return source or named


def _validated(case, donor, selection, directory):
    expected = selection["input_sha256"]
    grid = donor.get("terrain")
    if donor.get("id") != selection["case_id"] or input_hash(donor) != expected:
        raise ValueError("Saved terrain case no longer matches the pinned input hash")
    revision = directory / "revisions" / (expected + ".json")
    if (
        revision.is_symlink()
        or not revision.is_file()
        or input_hash(json.loads(revision.read_text())) != expected
    ):
        raise ValueError("Matching frozen terrain revision is unavailable or changed")
    if parcel_id(donor) != parcel_id(case):
        raise ValueError("Saved terrain belongs to another parcel")
    if not grid or sha256(canonical(grid).encode()).hexdigest() != selection["terrain_sha256"]:
        raise ValueError("Saved terrain grid hash mismatch")
    if grid.get("crs") != donor["crs"]:
        raise ValueError("Saved terrain and donor CRS disagree")
    crs = projected_crs(grid["crs"])
    if (
        abs(crs.axis_info[0].unit_conversion_factor - 1) > 1e-9
        or grid.get("horizontal_unit") != "m"
        or grid.get("vertical_unit") != "m"
    ):
        raise ValueError("Reusable terrain requires verified separate metre units")
    if isinstance(grid.get("cell_size"), bool) or grid.get("cell_size") != 1:
        raise ValueError("Pinned terrain must retain its native 1 m grid")
    if grid.get("source_quality", {}).get("vertical_units") != "verified":
        raise ValueError("Terrain vertical units are not verified")
    sources = [
        s
        for s in donor.get("sources", [])
        if s.get("sha256") == selection["dem_sha256"]
        and s.get("metadata_sha256") == selection["metadata_sha256"]
    ]
    if len(sources) != 1:
        raise ValueError("Pinned DEM and exact metadata provenance unavailable or ambiguous")
    source = sources[0]
    evidence = source.get("vertical_unit_evidence", {})
    if (
        source.get("vertical_unit") != "m"
        or source.get("horizontal_unit") != "m"
        or source.get("vertical_datum") != "NAVD88"
        or source.get("crs") != grid["crs"]
        or evidence.get("status") != "verified"
        or evidence.get("source_sha256") != selection["metadata_sha256"]
    ):
        raise ValueError("Exact saved metadata does not verify metre elevations/NAVD88")
    z = grid.get("elevations", [])
    if (
        not z
        or not isinstance(z, list)
        or not isinstance(z[0], list)
        or not z[0]
        or len(z) * len(z[0]) > MAX_ROUTING_CELLS
    ):
        raise ValueError("Invalid saved elevation grid dimensions")
    for row in z:
        if len(row) != len(z[0]) or any(
            isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v)
            for v in row
        ):
            raise ValueError(
                "Saved terrain is incomplete, nonrectangular or contains invalid elevations"
            )
    if (
        source.get("resolution") != [1, 1]
        or source.get("width") != len(z[0])
        or source.get("height") != len(z)
    ):
        raise ValueError("Saved DEM dimensions/resolution disagree with its provenance")
    origin = grid.get("origin")
    if (
        not isinstance(origin, list)
        or len(origin) != 2
        or any(
            isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v)
            for v in origin
        )
    ):
        raise ValueError("Invalid native grid origin")
    parcel = reproject(shape(case["parcel"]), case["crs"], grid["crs"])
    previous = shape(donor["parcel"])
    if not parcel.is_valid or not previous.is_valid or parcel.is_empty or previous.is_empty:
        raise ValueError("Invalid parcel boundary")
    if parcel.symmetric_difference(previous).area > max(0.01, previous.area * 1e-6):
        raise ValueError("Current parcel boundary differs from the saved terrain property")
    minimum = selection.get("minimum_buffer_m", 45.72)
    required = max(minimum, grid.get("settings", {}).get("required_buffer_native_units", 0))
    if not math.isfinite(required) or required < 0:
        raise ValueError("Invalid terrain buffer requirement")
    x, y = origin
    if not box(x, y - len(z), x + len(z[0]), y).covers(parcel.buffer(required)):
        raise ValueError("Saved terrain does not cover the current parcel and required buffer")
    return grid, source


def reuse(case, case_root, cache_root, *, registry=None):
    """Return a copied case/status on reuse; failures leave input unchanged.

    Existing explicitly selected terrain wins. A failed preference may fall back to
    the ordinary provider, with the rejection retained in its acquisition status.
    """
    if case.get("terrain"):
        return case, None
    status = {"provider": "Elevation", "status": "saved_terrain_rejected"}
    try:
        identity = parcel_id(case)
        if not identity:
            return case, None
        if registry is None:
            if not REGISTRY.is_file():
                return case, None
            registry = json.loads(REGISTRY.read_text())
        if registry.get("schema_version") != 1:
            raise ValueError("Unsupported terrain preference schema")
        selection = registry.get("properties", {}).get(identity)
        if not selection:
            return case, None
        identifier = selection["case_id"]
        if not re.fullmatch(r"[A-Za-z0-9_-]{1,80}", identifier):
            raise ValueError("Invalid saved terrain reference")
        directory = Path(case_root) / identifier
        path = directory / "case.json"
        if directory.is_symlink() or path.is_symlink():
            raise ValueError("Saved terrain references cannot be symlinks")
        payload = path.read_bytes()
        donor = json.loads(payload)
        grid, source = _validated(case, donor, selection, directory)
        out = project_case(case, grid["crs"]) if case["crs"] != grid["crs"] else deepcopy(case)
        # Preserve original measurement pixels while aligning only map display.
        if case["crs"] != grid["crs"] and case.get("imagery"):
            out.setdefault("measurement_imagery", deepcopy(case["imagery"]))
            out["measurement_imagery"].setdefault("crs", case["crs"])
            try:
                image = warp_display(case, grid["crs"], Path(cache_root))
                if image:
                    out["imagery"] = image
                    out.setdefault("sources", []).append(
                        {
                            "url": None,
                            "sha256": image["sha256"],
                            "crs": grid["crs"],
                            "processing": deepcopy(image.get("processing")),
                            "derived_from_sha256": case["imagery"].get("sha256"),
                            "evidence_role": "Aerial display-only reprojection; measurement pixels retained separately",
                            "retrieved_at": None,
                        }
                    )
            except (OSError, ValueError) as exc:
                out.setdefault("historical_imagery", []).append(deepcopy(case["imagery"]))
                out.setdefault("warnings", []).append(
                    "Saved terrain reused; aerial display reprojection unavailable: " + str(exc)
                )
        out["terrain"] = deepcopy(grid)
        existing = {(s.get("url"), s.get("sha256")) for s in out.get("sources", [])}
        if (source.get("url"), source.get("sha256")) not in existing:
            out.setdefault("sources", []).append(deepcopy(source))
        metadata = {
            "url": source.get("metadata_url"),
            "sha256": selection["metadata_sha256"],
            "evidence_role": "Exact saved tile metadata; referenced by verified vertical-unit evidence",
            "retrieved_at": None,
            "reused_from_case": identifier,
        }
        if (metadata["url"], metadata["sha256"]) not in existing:
            out["sources"].append(metadata)
        lineage = {
            "source_case_id": identifier,
            "source_input_sha256": selection["input_sha256"],
            "source_case_file_sha256": sha256(payload).hexdigest(),
            "terrain_sha256": selection["terrain_sha256"],
            "dem_sha256": selection["dem_sha256"],
            "metadata_sha256": selection["metadata_sha256"],
            "source_url": source.get("url"),
            "metadata_url": source.get("metadata_url"),
            "acquisition_period": deepcopy(source.get("acquisition_period")),
            "vertical_unit": "m",
            "vertical_datum": "NAVD88",
            "native_cell_size_m": 1,
            "method": "Copy frozen native grid; transform current vectors/display only; no elevation resampling",
            "claim": "Source units verified; current grading, watershed extent and drainage accuracy remain unverified",
        }
        out["terrain_reuse"] = lineage
        out.setdefault("processing_history", []).append(
            {
                "operation": "Reuse saved verified terrain",
                "parcel_id": identity,
                **deepcopy(lineage),
            }
        )
        status.update(status="reused_verified_saved_terrain", **deepcopy(lineage))
        return out, status
    except (OSError, ValueError, TypeError, KeyError, ShapelyError) as exc:
        status["error"] = str(exc)
        return case, status
