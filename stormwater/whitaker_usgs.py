"""Acquire a bounded USGS native-grid window, then reproduce the Whitaker rerun."""

from copy import deepcopy
from datetime import datetime, timezone
from hashlib import sha256
import json
import math
from pathlib import Path
import xml.etree.ElementTree as ET

import rasterio
from rasterio.windows import from_bounds, Window
from shapely.geometry import shape, mapping, box

from .cases import ROOT, CaseStore
from .geometry import reproject
from .terrain import prepare_terrain
from .whitaker_dem import summary
from drainage_core.projection import project_case, warp_display

URL = "https://prd-tnm.s3.amazonaws.com/StagedProducts/Elevation/1m/Projects/PA_17County_D24/TIFF/USGS_1M_18_x49y444_PA_17County_D24.tif"
METADATA_URL = "https://thor-f5.er.usgs.gov/ngtoc/metadata/waf/elevation/1_meter/geotiff/PA_17County_D24/USGS_1M_18_x49y444_PA_17County_D24.xml"
METADATA_HASH = "acc8db0f855ed500b4c14f9f830e8507226de05fa8b4e5fa17ff747c9d663711"


def acquire_window(case, path):
    """GDAL HTTP ranges fetch needed TIFF blocks, not the entire ~395 MB tile."""
    with rasterio.Env(
        GDAL_DISABLE_READDIR_ON_OPEN="EMPTY_DIR",
        CPL_VSIL_CURL_ALLOWED_EXTENSIONS=".tif",
        GDAL_HTTP_CONNECTTIMEOUT="10",
        GDAL_HTTP_TIMEOUT="30",
    ):
        with rasterio.open(URL) as ds:
            projected = reproject(shape(case["parcel"]), case["crs"], ds.crs)
            # Larger acquisition window than analysis crop, no edge clipping.
            region = projected.buffer(65, join_style="mitre")
            if not box(*ds.bounds).covers(region):
                raise ValueError("USGS tile lacks requested surrounding coverage")
            win = from_bounds(*region.bounds, transform=ds.transform)
            left, top = math.floor(win.col_off), math.floor(win.row_off)
            right, bottom = math.ceil(win.col_off + win.width), math.ceil(win.row_off + win.height)
            window = Window(left, top, right - left, bottom - top)
            if window.width * window.height > 250000:
                raise ValueError("Native USGS acquisition exceeds property cell limit")
            profile = ds.profile.copy()
            profile.update(
                driver="GTiff",
                width=int(window.width),
                height=int(window.height),
                transform=ds.window_transform(window),
                compress="deflate",
            )
            path.parent.mkdir(parents=True, exist_ok=True)
            with rasterio.open(path, "w", **profile) as out:
                out.write(ds.read(window=window))
                out.update_tags(**ds.tags())
            record = {
                "url": URL,
                "source_crs": ds.crs.to_string(),
                "source_resolution": list(ds.res),
                "source_dimensions": [ds.width, ds.height],
                "window": {
                    "col_off": left,
                    "row_off": top,
                    "width": right - left,
                    "height": bottom - top,
                },
                "acquisition_method": "GDAL HTTP-range window read of source TIFF blocks; exact network transfer volume not instrumented",
                "native_window_sha256": sha256(path.read_bytes()).hexdigest(),
                "elevation_resampling": "none",
                "horizontal_unit": "m",
                "vertical_unit": "m",
                "vertical_datum": "NAVD88",
                "metadata_sha256": METADATA_HASH,
                "metadata_url": METADATA_URL,
            }
            path.with_suffix(".json").write_text(json.dumps(record, indent=2) + "\n")
            return record


def rerun():
    store = CaseStore()
    original = store.load("pwd-98627")
    folder = ROOT / "data/public/dem-investigation"
    folder.mkdir(parents=True, exist_ok=True)
    native = folder / "whitaker-usgs-native-window.tif"
    source = (
        json.loads(native.with_suffix(".json").read_text())
        if native.exists()
        else acquire_window(original, native)
    )
    if sha256(native.read_bytes()).hexdigest() != source["native_window_sha256"]:
        raise ValueError("USGS window hash mismatch")
    if not source.get("retrieved_at"):
        source["retrieved_at"] = datetime.fromtimestamp(
            native.stat().st_mtime, timezone.utc
        ).isoformat()
        native.with_suffix(".json").write_text(json.dumps(source, indent=2) + "\n")
    metadata = ROOT / "data/public/blobs" / METADATA_HASH
    if sha256(metadata.read_bytes()).hexdigest() != METADATA_HASH:
        raise ValueError("USGS metadata hash mismatch")
    xml = ET.fromstring(metadata.read_bytes())
    abstract = xml.findtext(".//abstract", "")
    if "All bare earth elevation values are in meters" not in abstract or "NAVD88" not in abstract:
        raise ValueError(
            "Expected explicit USGS elevation-unit and vertical-datum evidence missing"
        )
    evidence = {
        "status": "verified",
        "source_url": METADATA_URL,
        "source_sha256": METADATA_HASH,
        "explanation": "Exact USGS tile metadata specifies bare-earth elevation metres relative to NAVD88; horizontal native UTM NAD83 metres.",
    }
    case = project_case(original, source["source_crs"])
    case["id"] = "pwd-98627-usgs-1m"
    case["name"] = "5300 Whitaker — USGS 1 m drainage (verified units)"
    item = prepare_terrain(
        native,
        case["parcel"],
        folder / "whitaker-usgs-analysis-crop.tif",
        crs=case["crs"],
        vertical_unit="m",
        unit_evidence=evidence,
        acquisition_date=None,
        buffer_native_units=45.72,
    )
    item["provenance"].update(
        url=URL,
        acquisition_period=["2024-04-14", "2025-04-02"],
        vertical_datum="NAVD88",
        metadata_url=METADATA_URL,
        metadata_sha256=METADATA_HASH,
        source_window=source,
        retrieved_at=source["retrieved_at"],
    )
    # The acquisition period is verified; an exact parcel flight day is not.
    item["warnings"] = [
        w for w in item["warnings"] if not w.startswith("Elevation acquisition date unknown")
    ]
    item["warnings"].append(
        "USGS acquisition period is 2024-04-14 through 2025-04-02; exact parcel flight day and unchanged final grading are unverified"
    )
    case["terrain"] = item["grid"]
    case["sources"].append(item["provenance"])
    case["imagery"] = warp_display(original, case["crs"], ROOT / "data/public")
    case.setdefault("source_quality_reviews", []).append(
        {
            "status": "verified alternate terrain selected",
            "source": source,
            "vertical_unit": "m",
            "vertical_datum": "NAVD88",
            "metadata_url": METADATA_URL,
            "acquisition_period": ["2024-04-14", "2025-04-02"],
            "excluded_city_2025": "Vertical units/datum unspecified; TIFF/LAS horizontal tag discrepancy and unrelated sidecar retained as separate audit/scenarios",
        }
    )
    case["warnings"] = [
        w for w in case.get("warnings", []) if not w.startswith("Downloaded DEM excluded:")
    ]
    case["warnings"] = [
        w.replace("canopy-understory, elevation, soils", "canopy-understory, soils")
        for w in case["warnings"]
    ]
    case["warnings"].extend(
        item["warnings"]
        + [
            "USGS source replaces the undocumented City 2025 vertical units for this run; no units inferred from elevation magnitudes.",
            "No verified collection points, private pipes, downspouts or curb/wall observations supplied; mapped system footprints are not inlets.",
            "Building footprints remain unreviewed observations; their masks block ground flow and roof drainage stays unresolved.",
        ]
    )
    case["assumptions"].extend(
        [
            "Native 1-metre USGS bare-earth DEM window; no elevation resampling, vertical conversion or depression filling.",
            "All case vectors explicitly transformed to native "
            + case["crs"]
            + "; physical and catchment area accounting retained in "
            + case["area_crs"]
            + " to avoid a projection-induced billing discrepancy.",
            "45.72-metre (150 international foot) geometric analysis buffer; sufficient surrounding watershed extent remains unverified.",
            "No inferred system inlet or private conveyance; current grading and independent drainage boundaries remain unverified.",
        ]
    )
    result = store.save(case)
    record = summary(case, result)
    record.update(
        source_url=URL,
        metadata_url=METADATA_URL,
        vertical_datum="NAVD88",
        acquisition_period=["2024-04-14", "2025-04-02"],
        crs=case["crs"],
        cell_size_m=1,
        source_quality_resolution="Verified-unit USGS replacement; original City 2025 metadata remains unresolved",
    )
    output = ROOT / "data/validation/whitaker-usgs-rerun.json"
    output.write_text(json.dumps(record, indent=2) + "\n")
    print(json.dumps(record, indent=2), flush=True)
    return record


if __name__ == "__main__":
    rerun()
