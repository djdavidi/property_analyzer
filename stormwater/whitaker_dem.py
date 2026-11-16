"""Reproduce the explicitly assumed-unit 2025 Whitaker terrain diagnostics offline."""

from collections import defaultdict
from copy import deepcopy
from hashlib import sha256
import json
from pathlib import Path
import zipfile

from .cases import ROOT, CaseStore
from .terrain import prepare_terrain

TILE_HASH = "6baa9e12dd8a7cc41c5ea9baf7bfe27b983d7132b705c392c8235b31bc43b1f5"
TILE_NAME = "27086E264792N.tif"
TILE_URL = "https://www.pasda.psu.edu/download/phillyLiDAR/2025/DEM/tiles/27086E264792N.zip"


def category(label):
    return (
        ":".join(label.split(":")[:2]) if label.startswith("unresolved:") else label.split(":")[0]
    )


def summary(case, result):
    groups = defaultdict(
        lambda: {
            "contributing_area_sqft": 0.0,
            "on_parcel_area_sqft": 0.0,
            "on_parcel_known_ia_sqft": 0.0,
        }
    )
    for c in result["drainage"]["catchments"]:
        s = groups[category(c["outlet"])]
        s["contributing_area_sqft"] += c["contributing_area_sqft"]
        s["on_parcel_area_sqft"] += c["on_parcel_area_sqft"]
        s["on_parcel_known_ia_sqft"] += c["on_parcel_physical_ia_sqft"]
    return {
        "case_id": case["id"],
        "input_sha256": result["input_sha256"],
        "vertical_unit_used": case["terrain"]["vertical_unit"],
        "vertical_unit_status": case["terrain"]["source_quality"]["vertical_units"],
        "status": result["drainage"]["status"],
        "processing_seconds": result["processing_seconds"],
        "rows": len(case["terrain"]["elevations"]),
        "columns": len(case["terrain"]["elevations"][0]),
        "nodata_cells": result["drainage"]["counts"].get("nodata", 0),
        "catchment_display_count": len(result["drainage"]["catchments"]),
        "area_by_terminal_category": dict(groups),
        "documented_inlets": len(case["terrain"].get("inlets", [])),
        "managed_area_sqft": None,
        "independent_validation": {k: v["status"] for k, v in result["validation"].items()},
        "report": str(ROOT / "data/cases" / case["id"] / "report.html"),
    }


def rerun():
    store = CaseStore()
    baseline = store.load("pwd-98627")
    directory = ROOT / "data/public/dem-investigation"
    directory.mkdir(parents=True, exist_ok=True)
    blob = ROOT / "data/public/blobs" / TILE_HASH
    if sha256(blob.read_bytes()).hexdigest() != TILE_HASH:
        raise ValueError("Frozen source archive hash mismatch")
    source = directory / TILE_NAME
    with zipfile.ZipFile(blob) as archive:
        source.write_bytes(archive.read(TILE_NAME))
    findings = json.loads((ROOT / "data/public/whitaker-dem-metadata-findings.json").read_text())
    results = []
    saved = []
    for code, label in [("us-ft", "usft"), ("m", "metres")]:
        evidence = {
            "status": "assumed",
            "source_url": TILE_URL,
            "explanation": f"2025 source vertical units unspecified in TIFF, collection XML and matching LAS header. Treat native Z as {code} solely for this diagnostic; compare alternate positive scale.",
        }
        item = prepare_terrain(
            source,
            baseline["parcel"],
            directory / ("whitaker-crop-" + label + ".tif"),
            crs=baseline["crs"],
            vertical_unit=code,
            unit_evidence=evidence,
            acquisition_date="2025-04",
            buffer_native_units=150,
        )
        case = deepcopy(baseline)
        case["id"] = "pwd-98627-dem-" + label + "-scenario"
        case["name"] = "5300 Whitaker — 2025 DEM, " + label + " vertical assumption"
        case["terrain"] = item["grid"]
        case["sources"].append(item["provenance"])
        case.setdefault("source_quality_reviews", []).append(findings)
        case["warnings"] = [
            w for w in case.get("warnings", []) if not w.startswith("Downloaded DEM excluded:")
        ]
        case["warnings"].extend(
            item["warnings"]
            + [
                "DIAGNOSTIC SCENARIO: 2025 DEM elevation units and vertical datum remain unverified.",
                "2025 TIFF horizontal tag EPSG:2272 differs from matching LAS EPSG:6565 NAD83(2011); native TIFF coordinates retained, alignment uncertainty not resolved.",
                "No verified collection points, private pipes, downspouts or curb/wall observations supplied; system footprints are not inlets.",
                "April 2025 terrain is not verified against unchanged final grading/current site condition.",
            ]
        )
        case["assumptions"].extend(
            [
                evidence["explanation"],
                "Native 3-US-survey-foot grid cropped outward with 150-foot geometric buffer; this does not establish watershed completeness.",
                "D8 steepest descent, flat tolerance zero, no depression fill, no slope eligibility threshold, buildings as unresolved roof masks.",
                "Positive uniform vertical scaling cannot establish absolute elevation or slopes; compare routing topology only.",
            ]
        )
        result = store.save(case)
        saved.append(summary(case, result))
        results.append(result["drainage"])
        print(json.dumps(saved[-1]), flush=True)
    a, b = results
    label_changes = sum(x != y for ra, rb in zip(a["labels"], b["labels"]) for x, y in zip(ra, rb))
    next_changes = sum(
        x != y for ra, rb in zip(a["next_cells"], b["next_cells"]) for x, y in zip(ra, rb)
    )
    report = {
        "source_archive_sha256": TILE_HASH,
        "scenarios": saved,
        "unit_sensitivity": {
            "changed_terminal_labels": label_changes,
            "changed_next_cells": next_changes,
            "same_topology": label_changes == next_changes == 0,
            "scope": "Only unit-scale sensitivity at fixed native resolution, flat tolerance zero and no slope thresholds. Does not resolve actual vertical units or validate drainage.",
        },
        "verified_2025_vertical_unit": None,
        "verified_2025_vertical_datum": None,
        "remaining": [
            "Unchanged grading/current condition",
            "Horizontal datum alignment",
            "Inlets/roof/private pipe topology",
            "Independent drainage boundaries",
            "Complete physical IA",
            "Hydrologic extent and resolution sensitivity",
        ],
    }
    output = ROOT / "data/validation/whitaker-dem-rerun.json"
    output.write_text(json.dumps(report, indent=2) + "\n")
    print(
        json.dumps(
            {"unit_sensitivity": report["unit_sensitivity"], "output": str(output)}, indent=2
        ),
        flush=True,
    )
    return report


if __name__ == "__main__":
    rerun()
