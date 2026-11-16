"""Discover a public native USGS window; never infer elevation units from values."""

from hashlib import sha256
import json
import math
import re
from urllib.parse import urlencode, urlparse
from pathlib import Path
import rasterio
from rasterio.windows import from_bounds, Window
from shapely.geometry import shape, box
from drainage_core.geometry import reproject
from drainage_core.projection import project_case, warp_display
from drainage_core.raster import import_dem


# NAVD88 is written several ways in USGS metadata.
VERTICAL_DATUM = re.compile(
    r"\bNAVD\s*-?\s*(?:19)?88\b|North American Vertical Datum (?:of )?1988|EPSG\s*:?\s*5703\b", re.I
)


def product_date(item):
    """Product date used to prefer the newest 1 m DEM (publication, then update)."""
    for key in ("publicationDate", "lastUpdated", "dateCreated", "modificationInfo"):
        value = str(item.get(key) or "")[:10]
        if re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
            return value
    return ""


def metadata_facts(xml):
    """Units, vertical datum and capture period stated by FGDC tile metadata."""
    text = " ".join(xml.itertext())
    units = [(e.text or "").strip().lower() for e in xml.iter("altunits")]
    metres = bool(re.search(r"elevation values are in meters", text, re.I)) or any(
        u in ("meters", "metres", "meter", "metre") for u in units
    )
    datum = VERTICAL_DATUM.search(text)
    period = {}
    for tag, key in (
        ("begdate", "capture_start"),
        ("enddate", "capture_end"),
        ("caldate", "capture_date"),
    ):
        value = next(
            (
                e.text.strip()
                for e in xml.iter(tag)
                if e.text and re.fullmatch(r"\d{4}(\d{2}){0,2}", e.text.strip())
            ),
            None,
        )
        if value:
            period[key] = "-".join(x for x in (value[:4], value[4:6], value[6:8]) if x)
    return {
        "metres": metres,
        "vertical_datum": "NAVD88" if datum else None,
        "datum_text": datum.group(0) if datum else None,
        **period,
    }


TNM_PRODUCTS = "https://tnmaccess.nationalmap.gov/api/v1/products?"
METADATA_ROOT = "https://thor-f5.er.usgs.gov/ngtoc/metadata/waf/elevation/1_meter/geotiff/"
ROUTING_BUFFER_M = 45.72
# Adjacent tiles must sit on one grid: offsets within 1/1000 of a cell, values in
# their shared overlap within 1 mm. Nothing is resampled, blended or interpolated.
ALIGNMENT_TOLERANCE_CELLS = 1e-3
OVERLAP_TOLERANCE_M = 1e-3
_GDAL = dict(
    GDAL_DISABLE_READDIR_ON_OPEN="EMPTY_DIR",
    CPL_VSIL_CURL_ALLOWED_EXTENSIONS=".tif",
    GDAL_HTTP_CONNECTTIMEOUT="10",
    GDAL_HTTP_TIMEOUT="20",
)


def _project(url):
    return url.split("/Projects/")[1].split("/")[0]


def _usable(item):
    url = item.get("downloadURL", "")
    parsed = urlparse(url)
    return (
        parsed.scheme == "https"
        and parsed.hostname == "prd-tnm.s3.amazonaws.com"
        and "/1m/Projects/" in url
    )


def _tile_metadata(cache, url):
    """Fetch and check one tile's FGDC metadata: explicit metres and NAVD88 required."""
    filename = url.rsplit("/", 1)[-1]
    metadata_url = METADATA_ROOT + _project(url) + "/" + filename[:-4] + ".xml"
    metadata = cache.fetch_bytes(metadata_url)
    from xml.etree import ElementTree as ET

    facts = metadata_facts(ET.fromstring(metadata["content"]))
    if not facts["metres"] or not facts["vertical_datum"]:
        raise ValueError("Tile metadata does not explicitly establish metre elevations/NAVD88")
    return metadata_url, metadata, facts


def _window(region, transform):
    win = from_bounds(*region.bounds, transform=transform)
    left, top = math.floor(win.col_off), math.floor(win.row_off)
    right, bottom = math.ceil(win.col_off + win.width), math.ceil(win.row_off + win.height)
    return left, top, right, bottom


def _cap(left, top, right, bottom):
    from drainage_core.drainage import MAX_ROUTING_CELLS

    if (right - left) * (bottom - top) > MAX_ROUTING_CELLS:
        raise ValueError(
            f"Native terrain window of {(right - left) * (bottom - top):,} cells exceeds "
            f"{MAX_ROUTING_CELLS:,} cells; no silent downsampling"
        )


def _check_metres(ds):
    from pyproj import CRS

    if abs(CRS(ds.crs).axis_info[0].unit_conversion_factor - 1) > 1e-9:
        raise ValueError("Automatic native terrain currently requires verified horizontal metres")


def _single(ds, region):
    """One tile covers the parcel and buffer: its native window (unchanged behaviour)."""
    left, top, right, bottom = _window(region, ds.transform)
    _cap(left, top, right, bottom)
    window = Window(left, top, right - left, bottom - top)
    with rasterio.io.MemoryFile() as mem:
        profile = ds.profile.copy()
        profile.update(
            driver="GTiff",
            width=right - left,
            height=bottom - top,
            transform=ds.window_transform(window),
            compress="deflate",
        )
        with mem.open(**profile) as target:
            target.write(ds.read(window=window))
            target.update_tags(**ds.tags())
        content = mem.read()
    return content, [left, top, right - left, bottom - top]


def same_grid(reference, other):
    """Offsets of ``other`` on ``reference``'s grid, or why the two are not one grid."""
    a, b = reference.transform, other.transform
    if reference.crs != other.crs:
        return None, "tiles use different coordinate systems"
    if abs(b.b) > 1e-10 or abs(b.d) > 1e-10 or abs(a.b) > 1e-10 or abs(a.d) > 1e-10:
        return None, "a tile is rotated"
    if abs(a.a - b.a) > 1e-9 * abs(a.a) or abs(a.e - b.e) > 1e-9 * abs(a.e):
        return None, "tiles have different cell sizes"
    if reference.count != 1 or other.count != 1 or reference.dtypes != other.dtypes:
        return None, "tiles differ in band count or data type"
    if reference.nodata != other.nodata:
        return None, "tiles declare different NoData values"
    col = (b.c - a.c) / a.a
    row = (b.f - a.f) / a.e
    if (
        abs(col - round(col)) > ALIGNMENT_TOLERANCE_CELLS
        or abs(row - round(row)) > ALIGNMENT_TOLERANCE_CELLS
    ):
        return None, "tile origins are not aligned to whole cells"
    return (int(round(col)), int(round(row))), None


def mosaic_window(datasets, region, names=None):
    """Native window across adjacent same-grid tiles; first tile wins in overlaps.

    Every tile must share CRS, cell size, data type, NoData and whole-cell alignment
    with the first (reference) tile. Overlapping valid values must agree within
    ``OVERLAP_TOLERANCE_M`` vertical units; otherwise the mosaic is rejected.
    Returns (GeoTIFF bytes, window, per-tile windows, overlap check).
    """
    import numpy as np

    reference = datasets[0]
    offsets = []
    for ds in datasets:
        offset, problem = same_grid(reference, ds)
        if problem:
            raise ValueError("Adjacent tiles are not one native grid: " + problem)
        offsets.append(offset)
    left, top, right, bottom = _window(region, reference.transform)
    _cap(left, top, right, bottom)
    width, height = right - left, bottom - top
    nodata = reference.nodata
    dtype = reference.dtypes[0]
    out = np.full((height, width), nodata if nodata is not None else 0, dtype=dtype)
    filled = np.zeros((height, width), bool)
    parts = []
    largest = 0.0
    for index, (ds, (col, row)) in enumerate(zip(datasets, offsets)):
        # Window in this tile's own pixels, clipped to the tile.
        c0, c1 = max(left - col, 0), min(right - col, ds.width)
        r0, r1 = max(top - row, 0), min(bottom - row, ds.height)
        if c0 >= c1 or r0 >= r1:
            continue
        data = ds.read(1, window=Window(c0, r0, c1 - c0, r1 - r0))
        rows = slice(r0 + row - top, r1 + row - top)
        cols = slice(c0 + col - left, c1 + col - left)
        valid = np.isfinite(data) if nodata is None else (data != nodata) & np.isfinite(data)
        target, have = out[rows, cols], filled[rows, cols]
        both = (
            have
            & valid
            & (np.isfinite(target) if nodata is None else (target != nodata) & np.isfinite(target))
        )
        if both.any():
            difference = float(np.abs(target[both].astype(float) - data[both].astype(float)).max())
            largest = max(largest, difference)
            if difference > OVERLAP_TOLERANCE_M:
                raise ValueError(
                    f"Adjacent tiles disagree by {difference:.4f} m in their overlap; not blended"
                )
        take = ~have
        target[take] = data[take]
        have |= take
        parts.append(
            {
                "index": index,
                "source_url": names[index] if names else ds.name,
                "tile_window": [c0, r0, c1 - c0, r1 - r0],
                "grid_offset_cells": [col, row],
            }
        )
    window = Window(left, top, width, height)
    with rasterio.io.MemoryFile() as mem:
        profile = reference.profile.copy()
        profile.update(
            driver="GTiff",
            width=width,
            height=height,
            transform=reference.window_transform(window),
            compress="deflate",
            count=1,
        )
        with mem.open(**profile) as target:
            target.write(out, 1)
            target.update_tags(**reference.tags())
        content = mem.read()
    check = {
        "max_overlap_difference_m": largest,
        "tolerance_m": OVERLAP_TOLERANCE_M,
        "alignment_tolerance_cells": ALIGNMENT_TOLERANCE_CELLS,
        "unfilled_cells": int((~filled).sum()),
    }
    return content, [left, top, width, height], parts, check


def _discover(case, cache, refresh_index):
    from pyproj import CRS

    parcel = shape(case["parcel"])
    unit = CRS(case["crs"]).axis_info[0].unit_conversion_factor
    # The routing buffer may reach a neighbouring tile that the parcel itself does not.
    area = parcel.buffer(ROUTING_BUFFER_M / unit, join_style="mitre")
    ll = reproject(area, case["crs"], "EPSG:4326")
    return cache.fetch_json(
        TNM_PRODUCTS
        + urlencode(
            {
                "bbox": ",".join(map(str, ll.bounds)),
                "datasets": "Digital Elevation Model (DEM) 1 meter",
                "max": 50,
                "outputFormat": "JSON",
            }
        ),
        refresh_index,
    )


def acquire(case, cache, *, case_root=None, refresh_index=False):
    """Saved terrain, a pinned reuse, or a native USGS 1 m window (one tile or a mosaic).

    Products are tried newest project first. Within a project a single tile covering
    the parcel plus routing buffer is used as is; otherwise adjacent tiles of that
    same project and grid are mosaicked without resampling. ``refresh_index`` asks
    the product index again (an explicit retry after a failure).
    """
    if case.get("terrain"):
        return case, {
            "provider": "Elevation",
            "status": "saved_native_grid",
            "claim": "Saved terrain retained; current grading and private connections unverified",
        }
    rejected = None
    if case_root is not None:
        from .terrain_reuse import reuse

        reused, rejected = reuse(case, case_root, cache.root)
        if reused.get("terrain"):
            return reused, rejected
    parcel = shape(case["parcel"])
    try:
        index = _discover(case, cache, refresh_index)
    except Exception as exc:
        if rejected:
            raise ValueError(
                "Saved terrain preference rejected: "
                + rejected.get("error", "unknown")
                + "; remote discovery unavailable: "
                + str(exc)
            ) from exc
        raise
    errors = []
    # Newest product first (TNM order is not guaranteed); its date is recorded.
    items = sorted(
        index["data"].get("items", []),
        key=lambda i: (product_date(i), str(i.get("downloadURL", ""))),
        reverse=True,
    )
    projects = {}
    for item in items:
        if _usable(item):
            projects.setdefault(_project(item["downloadURL"]), []).append(item)
    for project, group in projects.items():
        try:
            found = _from_project(case, cache, parcel, project, group, errors)
        except Exception as exc:
            errors.append(f"{project}: {exc}")
            continue
        if found is None:
            continue
        content, chosen, window, parts, check = found
        return _finish(case, cache, index, rejected, items, content, chosen, window, parts, check)
    raise ValueError(
        "No verified-unit native terrain window available: "
        + ((rejected.get("error", "") + "; ") if rejected else "")
        + "; ".join(errors)
    )


def _from_project(case, cache, parcel, project, group, errors):
    """A single covering tile of this project, else a same-grid mosaic, else None."""
    verified = []
    for item in group:
        try:
            verified.append((item, *_tile_metadata(cache, item["downloadURL"])))
        except Exception as exc:
            errors.append(str(exc))
    if not verified:
        return None
    with rasterio.Env(**_GDAL):
        opened = []
        try:
            region = None
            for entry in verified:
                try:
                    ds = rasterio.open(entry[0]["downloadURL"])
                except Exception as exc:
                    errors.append(str(exc))
                    continue
                opened.append((entry, ds))
                _check_metres(ds)
                if region is None:
                    region = reproject(parcel, case["crs"], ds.crs).buffer(
                        ROUTING_BUFFER_M, join_style="mitre"
                    )
                if box(*ds.bounds).covers(region):
                    content, window = _single(ds, region)
                    return content, [(entry, ds.crs.to_string())], window, None, None
                errors.append("Tile lacks full parcel and routing buffer")
            if region is None or len(opened) < 2:
                return None
            from shapely.ops import unary_union

            touching = [(e, ds) for e, ds in opened if box(*ds.bounds).intersects(region)]
            if not unary_union([box(*ds.bounds) for _, ds in touching]).covers(region):
                errors.append(
                    f"{project}: adjacent tiles together lack the parcel and routing buffer"
                )
                return None
            content, window, parts, check = mosaic_window(
                [ds for _, ds in touching], region, [e[0]["downloadURL"] for e, _ in touching]
            )
            chosen = [
                (touching[p["index"]][0], touching[p["index"]][1].crs.to_string()) for p in parts
            ]
            return content, chosen, window, parts, check
        finally:
            for _, ds in opened:
                ds.close()


def _finish(case, cache, index, rejected, items, content, chosen, window, parts, check):
    facts = [entry[3] for entry, _ in chosen]
    first, target_crs = chosen[0][0], chosen[0][1]
    item, url, metadata_url, metadata = first[0], first[0]["downloadURL"], first[1], first[2]
    starts = [f.get("capture_start") or f.get("capture_date") for f in facts]
    starts = [s for s in starts if s]
    period = {}
    for key, pick in (("capture_start", min), ("capture_end", max), ("capture_date", min)):
        values = [f[key] for f in facts if key in f]
        if values:
            period[key] = pick(values)
    mosaic = parts is not None
    stored = {
        "source_url": url,
        "metadata_url": metadata_url,
        "metadata_sha256": metadata["provenance"]["sha256"],
        "crs": target_crs,
        "horizontal_unit": "m",
        "vertical_unit": "m",
        "vertical_datum": "NAVD88",
        "product_title": item.get("title"),
        "product_date": product_date(item) or None,
        "acquisition_date": min(starts) if starts else None,
        "capture_period": period,
        "window": window,
        "processing": "Native HTTP range window; no elevation resampling",
    }
    if mosaic:
        stored.update(
            source_urls=[entry[0]["downloadURL"] for entry, _ in chosen],
            metadata_urls=[entry[1] for entry, _ in chosen],
            metadata_sha256s=[entry[2]["provenance"]["sha256"] for entry, _ in chosen],
            mosaic={"tiles": parts, **check},
            processing="Native HTTP range windows from adjacent tiles of one USGS project on "
            "one grid; first tile wins in overlaps; no resampling, blending or interpolation",
        )
    _, provenance = cache._store(
        ("derived:usgs-native-mosaic-" if mosaic else "derived:usgs-native-window-")
        + sha256(content).hexdigest(),
        content,
        stored,
    )
    path = cache.root / "blobs" / provenance["sha256"]
    terrain = import_dem(path, vertical_unit="m")
    out = project_case(case, target_crs) if case["crs"] != target_crs else case
    if case["crs"] != target_crs:
        out["imagery"] = warp_display(case, target_crs, cache.root)
        if out.get("imagery"):
            out["sources"].append(
                {
                    "sha256": out["imagery"]["sha256"],
                    "url": None,
                    "crs": target_crs,
                    "processing": out["imagery"].get("processing"),
                    "retrieved_at": provenance["retrieved_at"],
                }
            )
    terrain["grid"]["settings"] = {
        "extent_sufficient": False,
        "required_buffer_native_units": ROUTING_BUFFER_M,
        "max_flow_paths": 30,
    }
    out["terrain"] = terrain["grid"]
    out["sources"].extend(
        [index["provenance"], *(entry[2]["provenance"] for entry, _ in chosen), provenance]
    )
    first_facts = facts[0]
    status = {
        "provider": "Elevation",
        "status": "source_model",
        "source_url": url,
        "sha256": provenance["sha256"],
        "saved_terrain_attempt": rejected,
        "metadata_sha256": metadata["provenance"]["sha256"],
        "vertical_unit": "m",
        "vertical_datum": "NAVD88",
        "vertical_datum_text": first_facts["datum_text"],
        "product_title": item.get("title"),
        "product_date": product_date(item) or None,
        "capture_period": period,
        "candidates_considered": len(items),
        "claim": "Modeled surface routing; roofs/private connections and sufficient watershed extent remain unresolved. Current grading since the stated capture period is unverified.",
    }
    if mosaic:
        status.update(
            source_urls=stored["source_urls"],
            mosaic={"tiles": len(parts), **check},
            claim=status["claim"]
            + " Window assembled from adjacent tiles of one project on one native grid.",
        )
    return out, status
