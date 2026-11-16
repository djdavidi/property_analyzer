"""Philadelphia source acquisition feeding neutral GIS and explicitly uncertain estimates."""

from copy import deepcopy
from hashlib import sha256
import json
import math
import re
from shapely.geometry import shape, mapping
from drainage_core.geometry import case_area_sqft, union
from drainage_core.remote_sensing import vegetation_candidates
from drainage_core.sources import arcgis_features, SourceError, now
from .assessment_sources import _Fallback

PARCELS = (
    "https://services.arcgis.com/fLeGjb7u4uXqeF9q/ArcGIS/rest/services/PWD_PARCELS/FeatureServer/0"
)
LANDCOVER = "https://imagery.pasda.psu.edu/arcgis/rest/services/pasda/PhillyLULC/MapServer"
VERSION = "automatic-site-v3"  # v3: public PWD inlet points (G3)


def imagery_plan(parcel, crs, *, minimum=2048):
    """Choose the imagery request so the semantic model runs within its cell limit.

    The model cell size is chosen first (0.5 m, coarsened to fit 1,000,000
    cells, at most 1 m); the image is then requested fine enough for that cell
    (at least ``minimum`` px on the long side, at most the service's 4096 px).
    A box too large for 1 m cells is recorded as such; RGB fallback then follows
    with that reason instead of a silent rejection.
    """
    from pyproj import CRS
    from drainage_core.semantic_cover import analysis_resolution
    from .acquisition import imagery_bounds, image_size, MAX_IMAGE_SIDE, MAX_IMAGE_PIXELS

    bounds = imagery_bounds(parcel)
    unit = CRS(crs).axis_info[0].unit_conversion_factor
    long_m = max(bounds[2] - bounds[0], bounds[3] - bounds[1]) * unit
    try:
        target = analysis_resolution(bounds, crs)
        reason = None
    except ValueError as exc:
        target = None
        reason = str(exc)
    size = minimum if target is None else max(minimum, math.ceil(long_m / target))
    size = min(size, MAX_IMAGE_SIDE)
    while not _fits(bounds, size, MAX_IMAGE_PIXELS):
        size -= 64
    width, height = image_size(bounds, size)
    native = long_m / size
    model_ready = target is not None and native <= 1
    if target is not None and native > target:
        target = native
    return {
        "analysis_box": bounds,
        "crs": crs,
        "image_size": size,
        "image_pixels": [width, height],
        "native_metres": round(native, 4),
        "model_target_metres": round(target, 4) if model_ready else None,
        "model_within_limit": model_ready,
        "reason": reason
        or (
            None if model_ready else f"Imagery cells of {native:.2f} m exceed the model's 1 m limit"
        ),
    }


def _fits(bounds, size, limit):
    w, h = bounds[2] - bounds[0], bounds[3] - bounds[1]
    other = round(size * min(w, h) / max(w, h))
    return size * max(1, other) <= limit


def _image_generated(feature):
    return feature.get("properties", {}).get("automatic") and str(feature.get("id", "")).startswith(
        ("auto-lc-", "auto-rgb-", "auto-semantic-", "auto-image-vegetation")
    )


def buildings(case, cache, refresh):
    from .acquisition import BUILDINGS
    from pyproj import CRS

    proxy = _Fallback(cache)
    unit = CRS(case["crs"]).axis_info[0].unit_conversion_factor
    bounds = shape(case["parcel"]).buffer(45.72 / unit).bounds
    response = arcgis_features(
        BUILDINGS,
        proxy,
        {
            "geometry": ",".join(map(str, bounds)),
            "geometryType": "esriGeometryEnvelope",
            "inSR": case["crs"].split(":")[-1],
            "outSR": case["crs"].split(":")[-1],
            "spatialRel": "esriSpatialRelIntersects",
        },
        refresh,
        page_size=1000,
        max_pages=5,
    )
    features = []
    for f in response["features"]:
        f = deepcopy(f)
        p = f.setdefault("properties", {})
        f["id"] = "public-roof-" + str(f.get("id", p.get("objectid", p.get("OBJECTID"))))
        p.update(
            kind="roof",
            layer="surface",
            **{"class": "roof"},
            source_family="City buildings",
            source_dependency=True,
            source_kind="observation",
            source_url=BUILDINGS,
            reviewed=False,
            automatic_building=True,
        )
        features.append(f)
    return features, response["sources"], proxy.used_cache


def inlets(case, cache, refresh):
    """PWD inlet points around the parcel (G3); the downstream connection stays unknown."""
    from .acquisition import acquire_inlets

    proxy = _Fallback(cache)
    found = acquire_inlets(case["parcel"], case["crs"], proxy, refresh)
    return found, proxy.used_cache


def _merge_public(result, family, incoming):
    """Replace unreviewed features of one public family; keep those manual edits reference."""
    old = [
        f
        for f in result["features"]["features"]
        if f["properties"].get("source_family") == family
        and f["properties"].get("reviewed") is not True
    ]
    targets = {e.get("target") for e in result.get("corrections", [])}
    new_ids = {f["id"] for f in incoming}
    kept = [f for f in old if f["id"] in targets and f["id"] not in new_ids]
    old_ids = {f["id"] for f in old}
    result["features"]["features"] = (
        [f for f in result["features"]["features"] if f["id"] not in old_ids]
        + list(incoming)
        + kept
    )


# "1001 N DELAWARE AVE", "1001-99 N DELAWARE AVE" (PWD range), "1001R ...", "1001 - 1099 ...".
_ADDRESS = re.compile(r"(\d+)([A-Z]?)(?:\s*-\s*(\d+)([A-Z]?))?\s+([A-Z0-9].*)")


def _range_end(low, text):
    """PWD abbreviates a range end to its trailing digits: 1001-99 is 1001 to 1099."""
    width = len(text)
    if width >= len(str(low)):
        return int(text)
    end = low - low % 10**width + int(text)
    return end + 10**width if end < low else end


def parse_address(text):
    """House number(s), suffix letter and street of a Philadelphia-style address, or None."""
    text = re.sub(r"\s+", " ", str(text).upper()).strip()
    m = _ADDRESS.fullmatch(text)
    if not m:
        return None
    low = int(m.group(1))
    high = _range_end(low, m.group(3)) if m.group(3) else low
    low, high = min(low, high), max(low, high)
    return {
        "text": text,
        "low": low,
        "high": high,
        "range": m.group(3) is not None,
        "suffix": m.group(2) or "",
        "street": m.group(5).strip(),
    }


def _address_match(query, parcel):
    """How a PWD parcel address answers the query, or None (street, then house number)."""
    if parcel is None:
        return None
    if parcel["text"] == query["text"]:
        return "exact_address"
    street = parcel["street"]
    if street != query["street"] and not street.startswith(query["street"] + " "):
        return None
    if query["suffix"] and parcel["suffix"] != query["suffix"]:
        return None
    if query["range"]:
        same = (parcel["low"], parcel["high"]) == (query["low"], query["high"])
        return "same_range" if same else None
    number = query["low"]
    if parcel["low"] == parcel["high"]:
        return "same_number" if parcel["low"] == number else None
    if not parcel["low"] <= number <= parcel["high"]:
        return None
    # Ranges list one side of the street (1001-99 is odd); 1050 is across the street.
    one_side = (parcel["high"] - parcel["low"]) % 2 == 0
    if one_side and (number - parcel["low"]) % 2:
        return None
    return "range_contains"


def lookup(query, cache):
    """Parcel candidates for an address; ambiguity is returned for selection, never resolved.

    PWD stores multi-number parcels as ranges ("1001-99 N DELAWARE AVE"), so a house
    number is matched by numeric containment on the same street (same side), a range
    by its expanded ends, and an identical address string first.
    """
    query = str(query).strip()
    if re.fullmatch(r"[0-9]+", query):
        return {
            "matches": [{"parcel_id": int(query), "address": "PWD parcel " + query}],
            "sources": [],
        }
    query = re.sub(r"\s+", " ", query.upper()).strip()
    query = re.split(r",|\bPHILADELPHIA\b", query)[0].strip()
    parsed = parse_address(query) if len(query) <= 100 else None
    if not parsed or not re.fullmatch(r"[A-Z0-9 .'/&-]+", parsed["street"]):
        raise ValueError("Enter a Philadelphia street address or PWD parcel ID")
    street = parsed["street"].replace("'", "''")
    # Exact/prefix numbers and every range on the street; containment is decided here.
    where = (
        f"UPPER(address) LIKE '{parsed['low']}%{street}%' OR "
        f"(UPPER(address) LIKE '%-%' AND UPPER(address) LIKE '%{street}%')"
    )
    response = arcgis_features(
        PARCELS,
        cache,
        {
            "where": where,
            "outFields": "parcelid,address",
            "returnGeometry": "false",
            "outSR": "2272",
        },
        page_size=1000,
        max_pages=3,
    )
    matches = []
    for f in response["features"]:
        address = str(f["properties"].get("address") or "")
        basis = _address_match(parsed, parse_address(address))
        if basis:
            matches.append(
                {"parcel_id": int(f["properties"]["parcelid"]), "address": address, "match": basis}
            )
    exact = [m for m in matches if m["match"] == "exact_address"]
    return {"matches": exact or matches, "sources": response["sources"]}


def landcover(case, cache, refresh):
    """Use only fresh acquired imagery; never fetch the retired 2018 classifier."""
    from drainage_core.freshness import freshness
    from drainage_core.media import read_blob
    from drainage_core.remote_sensing import rgb_cover_candidates

    image = case.get("measurement_imagery") or case.get("imagery")
    if not image:
        raise SourceError("Recent imagery unavailable; canopy/surface classes remain unknown")
    check = freshness(image, case["imagery_age_policy"])
    if not check["eligible"]:
        raise SourceError("Imagery excluded by three-year limit: " + check["status"])
    payload = read_blob(image)
    if sha256(payload).hexdigest() != image["sha256"]:
        raise SourceError("Aerial source hash mismatch")
    from drainage_core.geometry import reproject

    image_crs = image.get("crs", case["crs"])
    grid_case = case
    if image_crs != case["crs"]:
        grid_case = {
            **case,
            "crs": image_crs,
            "parcel": mapping(reproject(shape(case["parcel"]), case["crs"], image_crs)),
        }
    info = {
        "family": "Philadelphia recent aerial RGB candidates",
        "url": image.get("sources", [{}])[0].get("url") if image.get("sources") else None,
        "sha256": image["sha256"],
        "source_vintage": image.get("source_vintage"),
        "acquisition_date": image.get("acquisition_date"),
    }
    from pathlib import Path
    from drainage_core.semantic_cover import semantic_cover

    root = Path(__file__).resolve().parents[1]
    try:
        result = semantic_cover(
            payload,
            image["bounds"],
            grid_case,
            info,
            runtime=root / "data/model-runtime/bin/python",
            weights=root / "data/models/openearthmap/weights.pth",
            cache=(
                cache.root / "semantic" if isinstance(getattr(cache, "root", None), Path) else None
            ),
        )
    except Exception as exc:
        # Any model failure falls back visibly: the reason is kept next to the result.
        reason = f"{type(exc).__name__}: {exc}"
        result = rgb_cover_candidates(payload, image["bounds"], grid_case, info)
        result["model_unavailable"] = reason
        result["fallback"] = {
            "method": "RGB cover candidates",
            "reason": reason,
            "message": "Semantic model not used; fell back to RGB cover candidates because "
            + reason,
        }
    if image_crs != case["crs"]:
        for f in result["features"]:
            f["geometry"] = mapping(reproject(shape(f["geometry"]), image_crs, case["crs"]))
        result["coverage_geometry"] = mapping(
            reproject(shape(result["coverage_geometry"]), image_crs, case["crs"])
        )
    result["crs"] = case["crs"]
    result["pixel_crs"] = image_crs
    result.update(
        source_snapshots=image.get("sources", []),
        image_sha256=image["sha256"],
        source_vintage=image.get("source_vintage"),
        acquisition_date=image.get("acquisition_date"),
        freshness=check,
        retrieved_at=next(
            (s.get("retrieved_at") for s in image.get("sources", []) if s.get("retrieved_at")), None
        ),
        status=result.get("status", "modeled_image_candidates"),
        method=result["settings"]["algorithm"]
        + "; modeled estimates, not reviewed physical observations",
    )
    return result


# Statuses of a successful earlier physical acquisition that a re-run keeps.
_KEPT_IMAGERY = ("retrieved", "saved_snapshot_kept")
_FAILED_TERRAIN = ("unavailable",)


def _previous_status(previous, provider):
    return next(
        (s for s in (previous or {}).get("source_status", []) if s.get("provider") == provider),
        None,
    )


def _retry_note(previous, status):
    """What an explicit re-run retries: the earlier failed status, its error and run time."""
    return {
        "previous_status": status.get("status") if status else "not_attempted",
        "previous_error": (status or {}).get("error"),
        "previous_run_at": (previous or {}).get("at"),
    }


def physical_plan(case, policy, refresh_physical=False):
    """Which physical sources a run keeps and which it (re)acquires.

    A first run, or ``refresh_physical``, acquires everything. Otherwise a re-run keeps
    a successful, still-eligible saved imagery snapshot (and the cover estimates made
    from exactly that snapshot) and retries only what failed or is no longer usable.
    Saved terrain is always kept (automatic_terrain); failed terrain is retried with a
    refreshed product index.
    """
    from drainage_core.freshness import freshness

    previous = case.get("automatic") or {}
    plan = {"keep_imagery": False, "keep_cover": False, "retry": {}}
    if refresh_physical or not previous:
        plan["mode"] = "refresh_all" if previous else "first_run"
        return plan
    plan["mode"] = "retry_failed"
    image_status = _previous_status(previous, "Aerial imagery")
    saved = case.get("measurement_imagery") or case.get("imagery")
    eligible = False
    if saved and case.get("imagery"):
        try:
            eligible = freshness(saved, policy)["eligible"]
        except (KeyError, TypeError, ValueError):
            eligible = False
    if image_status and image_status.get("status") in _KEPT_IMAGERY and eligible:
        plan["keep_imagery"] = True
    else:
        plan["retry"]["Aerial imagery"] = _retry_note(previous, image_status)
    cover_status = _previous_status(previous, "Recent imagery cover candidates")
    cover = previous.get("landcover") or {}
    same_image = bool(saved) and (
        cover.get("image_sha256") == saved.get("sha256")
        or (
            bool(cover.get("source_snapshots"))
            and cover["source_snapshots"] == saved.get("sources")
        )
    )
    if (
        plan["keep_imagery"]
        and cover_status
        and cover_status.get("status") not in (None, "unavailable")
        and not cover_status.get("fallback_reason")
        and cover.get("features") is not None
        and same_image
    ):
        plan["keep_cover"] = True
    else:
        plan["retry"]["Recent imagery cover candidates"] = _retry_note(previous, cover_status)
    terrain_status = _previous_status(previous, "Elevation")
    if not case.get("terrain") and (
        terrain_status is None or terrain_status.get("status") in _FAILED_TERRAIN
    ):
        plan["retry"]["Elevation"] = _retry_note(previous, terrain_status)
    return plan


def acquire(case, cache, refresh=True, *, case_root=None, refresh_physical=False):
    """Append run lineage, preserve manual corrections and reuse dated observations on outage.

    An explicit re-run retries failed physical sources and keeps successful saved
    imagery/terrain (see ``physical_plan``); ``refresh_physical`` replaces them.
    Each retry and the per-stage elapsed seconds are recorded with the run.
    """
    import time
    from .acquisition import acquire_imagery

    started = time.perf_counter()
    timings = {}
    result = deepcopy(case)
    previous = result.get("automatic", {})
    record = {
        "version": VERSION,
        "at": now(),
        "source_status": [],
        "estimates": [],
        "claim": "Automatically acquired physical estimates and candidates, not verified eligibility or current-site accuracy.",
    }
    from drainage_core.freshness import age_policy, freshness

    result["imagery_age_policy"] = age_policy(record["at"][:10])
    record["imagery_age_policy"] = deepcopy(result["imagery_age_policy"])
    record["claim"] = (
        "Satellite/aerial imagery must be at most three years old; other datasets retain their own validity rules. Image-derived canopy and surface estimates are modeled, with independent local accuracy unverified."
    )
    plan = physical_plan(result, result["imagery_age_policy"], refresh_physical)
    record["physical_sources"] = {
        "mode": plan["mode"],
        "kept": [
            name
            for name, kept in (
                ("Aerial imagery", plan["keep_imagery"]),
                ("Recent imagery cover candidates", plan["keep_cover"]),
            )
            if kept
        ]
        + (["Elevation"] if result.get("terrain") else []),
        "retried": sorted(plan["retry"]) if plan["mode"] == "retry_failed" else [],
        "claim": "A re-run retries failed physical sources and keeps successful saved ones; "
        "an explicit full refresh replaces them. Earlier runs remain in automatic_history.",
    }
    # Retire previous generated classifications even on outages. Referenced source
    # IDs remain as historical map records so append-only manual edits still replay.
    # Estimates kept from the same saved imagery are not retired.
    generated_before = (
        []
        if plan["keep_cover"]
        else [f for f in result["features"]["features"] if _image_generated(f)]
    )
    prior_canopy = result.get("canopy_observation", {})
    if not plan["keep_cover"] and (
        prior_canopy.get("automatic")
        or (
            prior_canopy.get("source_vintage") == "2018"
            and previous.get("landcover", {}).get("source_vintage") == "2018"
            and not prior_canopy.get("reviewed")
        )
    ):
        result["canopy_observation"] = {"status": "unavailable"}
    if generated_before:
        result.setdefault("historical_automatic_features", []).append(
            {"at": record["at"], "crs": result["crs"], "features": deepcopy(generated_before)}
        )
        targets = {e.get("target") for e in result.get("corrections", [])}
        retained = []
        for f in result["features"]["features"]:
            if not _image_generated(f):
                retained.append(f)
            elif f["id"] in targets:
                f["properties"]["layer"] = "historical"
                retained.append(f)
        result["features"]["features"] = retained
    new_sources = []
    stage = time.perf_counter()
    try:
        roofs, roof_sources, cached = buildings(result, cache, refresh)
        old = [
            f
            for f in result["features"]["features"]
            if f["properties"].get("source_family") == "City buildings"
            and f["properties"].get("reviewed") is not True
        ]
        targets = {e.get("target") for e in result.get("corrections", [])}
        new_ids = {f["id"] for f in roofs}
        roofs.extend(f for f in old if f["id"] in targets and f["id"] not in new_ids)
        old_ids = {f["id"] for f in old}
        result["features"]["features"] = [
            f for f in result["features"]["features"] if f["id"] not in old_ids
        ] + roofs
        new_sources.extend(roof_sources)
        record["source_status"].append(
            {
                "provider": "Building footprints",
                "status": "cached_after_failure" if cached else "source_observation",
                "source_dates": "Acquisition dates unknown; footprint is not exact roof/drainage geometry",
            }
        )
    except Exception as exc:
        record["source_status"].append(
            {
                "provider": "Building footprints",
                "status": (
                    "dated_saved_snapshot"
                    if any(
                        f["properties"].get("class") == "roof"
                        for f in result["features"]["features"]
                    )
                    else "unavailable"
                ),
                "error": str(exc),
            }
        )
    timings["buildings"] = time.perf_counter() - stage
    stage = time.perf_counter()
    try:
        # G3: public storm/wastewater inlets. An outage is recorded, never zero inlets.
        found, cached = inlets(result, cache, refresh)
        _merge_public(result, "PWD inlets", found["features"])
        new_sources.extend(found["sources"])
        record["source_status"].append(
            {
                "provider": "Storm inlets",
                "status": "cached_after_failure" if cached else "source_observation",
                "source_url": found["source_url"],
                "mapped_inlets": len(found["features"]),
                "excluded": found["excluded"],
                "buffer": found["buffer"],
                "query_bounds": found["query_bounds"],
                "crs": found["crs"],
                "source_dates": "Layer edit dates only; inlet survey/installation dates mostly unknown",
                "claim": "Mapped inlet locations only. No mapped inlet in the buffer is not proof that none exists; downstream connections are unknown.",
            }
        )
    except Exception as exc:
        saved = any(
            f["properties"].get("source_family") == "PWD inlets"
            for f in result["features"]["features"]
        )
        record["source_status"].append(
            {
                "provider": "Storm inlets",
                "status": "dated_saved_snapshot" if saved else "unavailable",
                "error": str(exc),
                "claim": "Inlet source unavailable: inlet presence is unknown, not zero inlets.",
            }
        )
    timings["inlets"] = time.perf_counter() - stage
    stage = time.perf_counter()
    if plan["keep_imagery"]:
        kept = result.get("measurement_imagery") or result["imagery"]
        record["imagery_plan"] = deepcopy(previous.get("imagery_plan"))
        record["source_status"].append(
            {
                "provider": "Aerial imagery",
                "status": "saved_snapshot_kept",
                "sha256": kept.get("sha256"),
                "kept_from_run_at": previous.get("at"),
                "freshness": freshness(kept, result["imagery_age_policy"]),
                "source_vintage": kept.get("source_vintage"),
                "claim": "Successful saved imagery kept on re-run; not silently refreshed. "
                "Use an explicit full refresh to replace it.",
            }
        )
    else:
        _acquire_imagery_into(result, record, cache, refresh, new_sources, acquire_imagery)
        if "Aerial imagery" in plan["retry"]:
            record["source_status"][-1]["retry"] = plan["retry"]["Aerial imagery"]
    timings["imagery"] = time.perf_counter() - stage
    stage = time.perf_counter()
    _cover_into(result, record, cache, refresh, new_sources, previous, plan)
    timings["model"] = time.perf_counter() - stage
    if previous:
        result.setdefault("automatic_history", []).append(deepcopy(previous))
    identity = lambda s: (s.get("url"), s.get("sha256"), s.get("retrieved_at"))
    old_sources = {identity(s) for s in result.get("sources", [])}
    result.setdefault("sources", []).extend(
        s for s in new_sources if identity(s) not in old_sources
    )
    stage = time.perf_counter()
    try:
        from .automatic_terrain import acquire as terrain_acquire

        options = {"case_root": case_root} if case_root is not None else {}
        if "Elevation" in plan["retry"] and plan["mode"] == "retry_failed":
            # A retry must see the current product index, not a replayed earlier answer.
            options["refresh_index"] = True
        result, terrain_status = terrain_acquire(result, cache, **options)
        # Native terrain alignment transforms case features. Keep the current
        # run's geometry copies used by candidate enrichment in that same CRS.
        cover = record.get("landcover")
        if cover and cover.get("crs") and cover["crs"] != result["crs"]:
            from drainage_core.geometry import reproject

            source_crs = cover["crs"]
            for f in cover.get("features", []):
                f["geometry"] = mapping(reproject(shape(f["geometry"]), source_crs, result["crs"]))
            for key in ("coverage_geometry", "canopy_geometry"):
                if cover.get(key):
                    cover[key] = mapping(reproject(shape(cover[key]), source_crs, result["crs"]))
            cover["geometry_reprojection"] = {
                "source_crs": source_crs,
                "target_crs": result["crs"],
                "method": "vector only; original pixels/bounds retained",
            }
            cover["crs"] = result["crs"]
        record["source_status"].append(terrain_status)
    except Exception as exc:
        record["source_status"].append(
            {"provider": "Elevation", "status": "unavailable", "error": str(exc)}
        )
    if "Elevation" in plan["retry"] and plan["mode"] == "retry_failed":
        record["source_status"][-1]["retry"] = plan["retry"]["Elevation"]
    timings["terrain"] = time.perf_counter() - stage
    timings["total"] = time.perf_counter() - started
    record["timings_seconds"] = {k: round(v, 3) for k, v in timings.items()}
    record["timings_claim"] = (
        "Elapsed wall-clock seconds on this computer for this run; network and cache dependent."
    )
    result.setdefault("automatic_runs", []).append(
        {
            "version": VERSION,
            "at": record["at"],
            "imagery_age_policy": deepcopy(result["imagery_age_policy"]),
            "source_status": deepcopy(record["source_status"]),
            "estimates": deepcopy(record["estimates"]),
            "source_snapshots": deepcopy(record.get("landcover", {}).get("source_snapshots", [])),
            "physical_sources": deepcopy(record["physical_sources"]),
            "timings_seconds": deepcopy(record["timings_seconds"]),
            "claim": "Full source geometries remain in the corresponding immutable case/assessment revision.",
        }
    )
    result["automatic"] = record
    return result


def _acquire_imagery_into(result, record, cache, refresh, new_sources, acquire_imagery):
    """Fetch current eligible imagery; on failure keep a still-eligible saved snapshot."""
    from drainage_core.freshness import freshness

    try:
        from drainage_core.geometry import reproject
        from drainage_core.projection import warp_display

        grid_crs = result.get("area_crs", result["crs"])
        parcel = (
            reproject(shape(result["parcel"]), result["crs"], grid_crs)
            if grid_crs != result["crs"]
            else shape(result["parcel"])
        )
        plan = imagery_plan(mapping(parcel), grid_crs)
        record["imagery_plan"] = plan
        image = acquire_imagery(
            mapping(parcel),
            cache,
            crs=grid_crs,
            refresh=refresh,
            size=plan["image_size"],
            freshness_policy=result["imagery_age_policy"],
        )
        check = freshness(image, result["imagery_age_policy"])
        if not check["eligible"]:
            raise SourceError("Imagery excluded by three-year limit: " + check["status"])
        result["measurement_imagery"] = deepcopy(image)
        if grid_crs != result["crs"]:
            image = warp_display(
                {**result, "crs": grid_crs, "imagery": image}, result["crs"], cache.root
            )
            new_sources.append(
                {
                    "url": None,
                    "sha256": image["sha256"],
                    "crs": result["crs"],
                    "processing": image.get("processing"),
                    "retrieved_at": now(),
                }
            )
        result["imagery"] = image
        new_sources.extend(image["sources"])
        record["source_status"].append(
            {
                "provider": "Aerial imagery",
                "status": "retrieved",
                "warnings": image.get("warnings", []),
                "freshness": check,
                "source_vintage": image.get("source_vintage"),
            }
        )
    except Exception as exc:
        saved = result.get("imagery")
        usable = bool(saved and freshness(saved, result["imagery_age_policy"])["eligible"])
        if saved and not usable:
            result.setdefault("historical_imagery", []).append(deepcopy(saved))
            result.pop("imagery", None)
        original = result.get("measurement_imagery")
        if original and not freshness(original, result["imagery_age_policy"])["eligible"]:
            result.setdefault("historical_imagery", []).append(deepcopy(original))
            result.pop("measurement_imagery", None)
        record["source_status"].append(
            {
                "provider": "Aerial imagery",
                "status": "dated_saved_snapshot" if usable else "unavailable",
                "error": str(exc),
            }
        )


def _cover_into(result, record, cache, refresh, new_sources, previous, plan):
    """Cover estimates from current imagery; kept unchanged when the same saved image is kept."""
    from drainage_core.freshness import freshness

    if plan["keep_cover"]:
        lc = deepcopy(previous["landcover"])
        record["landcover"] = lc
        record["estimates"] = deepcopy(lc.get("estimates", []))
        record["source_status"].append(
            {
                "provider": "Recent imagery cover candidates",
                "status": "saved_estimates_kept",
                "model_status": lc.get("status"),
                "kept_from_run_at": previous.get("at"),
                "retrieved_at": lc.get("retrieved_at"),
                "unknown_sqft": lc.get("unclassified_sqft"),
                "source_vintage": lc.get("source_vintage"),
                "freshness": freshness(lc, result["imagery_age_policy"]),
                "claim": "Estimates made from the same kept imagery snapshot; not reprocessed.",
            }
        )
        return
    try:
        lc = landcover(result, cache, refresh)
        check = freshness(lc, result["imagery_age_policy"])
        if not check["eligible"]:
            raise SourceError("Classification excluded by three-year limit: " + check["status"])
        record["landcover"] = lc
        record["estimates"] = lc["estimates"]
        new_sources.extend(lc["source_snapshots"])
        old = {f["id"]: f for f in result["features"]["features"] if _image_generated(f)}
        generated = {f["id"]: f for f in lc["features"]}
        targets = {e.get("target") for e in result.get("corrections", [])}
        for key in targets & (old.keys() - generated.keys()):
            generated[key] = old[key]
            record.setdefault("warnings", []).append(
                "Historic automatic feature retained because a manual edit references " + key
            )
        removed = [
            f
            for f in result["features"]["features"]
            if _image_generated(f) and f["id"] not in targets
        ]
        if removed:
            result.setdefault("historical_automatic_features", []).append(
                {"at": record["at"], "crs": result["crs"], "features": deepcopy(removed)}
            )
        result["features"]["features"] = [
            f
            for f in result["features"]["features"]
            if not _image_generated(f) or f["id"] in targets
        ] + [f for key, f in generated.items() if key not in targets or key not in old]
        if lc["coverage_complete"]:
            result["canopy_observation"] = {
                "status": "complete",
                "automatic": True,
                "source_vintage": lc["source_vintage"],
                "coverage_geometry": lc["coverage_geometry"],
                "source_snapshots": lc["source_snapshots"],
            }
        else:
            result.setdefault("canopy_observation", {"status": "unavailable"})
        status = {
            "provider": "Recent imagery cover candidates",
            "status": lc["status"],
            "retrieved_at": lc["retrieved_at"],
            "unknown_sqft": lc["unclassified_sqft"],
            "source_vintage": lc["source_vintage"],
            "freshness": check,
        }
        if lc.get("fallback"):
            status.update(fallback_reason=lc["fallback"]["reason"], claim=lc["fallback"]["message"])
            record.setdefault("warnings", []).append(lc["fallback"]["message"])
        record["source_status"].append(status)
    except Exception as exc:
        # Old classifications and estimates are history, never an outage fallback.
        record["source_status"].append(
            {
                "provider": "Recent imagery cover candidates",
                "status": "unavailable",
                "error": str(exc),
            }
        )
        result.setdefault("canopy_observation", {"status": "unavailable"})
    if plan["mode"] == "retry_failed" and "Recent imagery cover candidates" in plan["retry"]:
        record["source_status"][-1]["retry"] = plan["retry"]["Recent imagery cover candidates"]


def enrich_candidates(case):
    """Measure public polygons automatically, without confirming installation or drainage served."""
    out = deepcopy(case)
    a = out.setdefault("assessment", {})
    parcel = shape(out["parcel"])
    footprints = []
    for record in a.get("records", []):
        geom = record.get("public_geometry")
        if (
            not geom
            or record.get("source", {}).get("crs") != out["crs"]
            or geom.get("type") not in ("Polygon", "MultiPolygon")
        ):
            continue
        try:
            region = shape(geom).intersection(parcel)
            if not region.is_valid:
                raise ValueError("Invalid public system polygon")
        except Exception as exc:
            record["automatic_footprint_error"] = str(exc)
            continue
        if region.is_empty:
            continue
        if not record.get("footprint_geometry") and "footprint" in record.get(
            "public_geometry_role", ""
        ):
            record["footprint_geometry"] = mapping(region)
            record["automatic_footprint"] = {
                "area_sqft": case_area_sqft(region, out),
                "basis": "Mapped public-system footprint; current installation unverified",
            }
        footprints.append(
            {
                "id": record["id"],
                "category": record["category"],
                "area_sqft": case_area_sqft(region, out),
                "geometry": mapping(region),
                "source": record.get("source"),
                "basis": "source-reported candidate; footprint does not establish managed catchment",
            }
        )
    automatic = out.setdefault("automatic", {})
    automatic["system_footprints"] = footprints
    # Greenness on known roof polygons nominates a candidate; tree overhang/roof coatings remain alternatives.
    for key in (
        "image_vegetation_candidate_sqft",
        "image_green_overlap_historical_canopy_sqft",
        "roof_vegetation_candidate_sqft",
        "image_method",
    ):
        automatic.pop(key, None)
    if out.get("imagery"):
        try:
            from drainage_core.media import read_blob
            from drainage_core.geometry import effective_features

            image = out.get("measurement_imagery") or out["imagery"]
            if out.get("imagery_age_policy"):
                from drainage_core.freshness import freshness

                check = freshness(image, out["imagery_age_policy"])
                if not check["eligible"]:
                    raise SourceError(
                        "RGB candidates excluded by three-year limit: " + check["status"]
                    )
            cover = automatic.get("landcover", {})
            from_cover = cover.get("status") in (
                "modeled_image_candidates",
                "modeled_semantic_estimates",
            )
            if from_cover:
                green = union(
                    [
                        shape(f["geometry"])
                        for f in cover["features"]
                        if f["properties"].get("layer")
                        in ("vegetation_candidate", "canopy_candidate")
                    ]
                )
            else:
                # Image bounds are in the image's CRS; measure there with the parcel
                # reprojected, then bring the candidates back to the case CRS.
                from drainage_core.geometry import reproject

                image_crs = image.get("crs") or out["crs"]
                if image_crs != out["crs"]:
                    grid = {
                        **out,
                        "crs": image_crs,
                        "parcel": mapping(reproject(shape(out["parcel"]), out["crs"], image_crs)),
                    }
                    green = reproject(
                        vegetation_candidates(read_blob(image), image["bounds"], grid),
                        image_crs,
                        out["crs"],
                    )
                else:
                    green = vegetation_candidates(read_blob(image), image["bounds"], out)
            automatic["image_vegetation_candidate_sqft"] = case_area_sqft(green, out)
            canopy = union(
                [
                    shape(f["geometry"])
                    for f in effective_features(out)
                    if f["properties"].get("layer") == "canopy"
                ]
            )
            automatic["image_green_overlap_historical_canopy_sqft"] = (
                case_area_sqft(green.intersection(canopy), out) if not canopy.is_empty else None
            )
            out["features"]["features"] = [
                f for f in out["features"]["features"] if f.get("id") != "auto-image-vegetation"
            ]
            if not green.is_empty and not from_cover:
                out["features"]["features"].append(
                    {
                        "type": "Feature",
                        "id": "auto-image-vegetation",
                        "geometry": mapping(green),
                        "properties": {
                            "layer": "vegetation_candidate",
                            "automatic": True,
                            "source_kind": "modeled image candidate",
                            "source_sha256": image["sha256"],
                            "source_method": "RGB excess-green heuristic v1",
                            "source_vintage": image.get("source_vintage"),
                            "acquisition_date": image.get("acquisition_date"),
                            "claim": "Grass, trees, coatings or other green objects; no ground permeability or tree identity inferred",
                        },
                    }
                )
            roof = union(
                [
                    shape(f["geometry"])
                    for f in effective_features(out)
                    if f["properties"].get("class") == "roof"
                ]
            )
            roof_green = green.intersection(roof)
            automatic["roof_vegetation_candidate_sqft"] = (
                case_area_sqft(roof_green, out) if not roof.is_empty else None
            )
            if case_area_sqft(roof_green, out) >= 50:
                identity = (
                    "image-roof-vegetation-"
                    + sha256(json.dumps(mapping(roof_green), sort_keys=True).encode()).hexdigest()[
                        :20
                    ]
                )
                if not any(r["id"] == identity for r in a.setdefault("records", [])):
                    a["records"].append(
                        {
                            "id": identity,
                            "category": "green_roof",
                            "decision": "candidate",
                            "basis": "public_candidate",
                            "facts": {
                                "existing_installation": None,
                                "image_vegetation_candidate": True,
                            },
                            "footprint_geometry": mapping(roof_green),
                            "source": {
                                "url": "local:cached-aerial",
                                "sha256": image["sha256"],
                                "crs": out["crs"],
                            },
                            "evidence_refs": [],
                            "notes": "RGB greenness on a mapped roof. Could be tree overhang, coating or vegetation; not proof of a green roof.",
                        }
                    )
                automatic["roof_vegetation_candidate_sqft"] = case_area_sqft(roof_green, out)
            automatic["image_method"] = {
                "algorithm": "RGB excess-green thresholds v1",
                "minimum_patch_sqft": 50,
                "claim": "Vegetation candidate heuristic only; not a tree-canopy classifier, green-roof confirmation or permeability measurement.",
                "source_sha256": image["sha256"],
                "capture_date": image.get("acquisition_date"),
                "source_vintage": image.get("source_vintage"),
                "thresholds": {
                    "green_red_ratio": 1.12,
                    "green_blue_ratio": 1.08,
                    "minimum_green": 45,
                    "minimum_excess_green": 25,
                },
                "bounds": image["bounds"],
                "crs": image.get("crs") or out["crs"],
            }
            if from_cover:
                automatic["image_method"] = {
                    **cover["settings"],
                    "claim": cover["claim"],
                    "source_vintage": image.get("source_vintage"),
                    "capture_date": image.get("acquisition_date"),
                }
        except Exception as exc:
            automatic.setdefault("warnings", []).append(
                "RGB candidate extraction unavailable: " + str(exc)
            )
    return out
