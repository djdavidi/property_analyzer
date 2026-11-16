"""Replay saved public Whitaker inputs without fetching or modifying the original."""

import argparse
from copy import deepcopy
from hashlib import sha256
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from stormwater.cases import CaseStore
from drainage_core.engine import routing, canonical
from drainage_core.geometry import measure
from drainage_core.research import write_diagnostic_rasters


def build(source, output):
    original = source.read_bytes()
    case = json.loads(original)
    source_hash = sha256(original).hexdigest()
    preserved = {p: sha256(p.read_bytes()).hexdigest() for p in source.parent.glob("*.json")}
    # Match the existing Philadelphia orchestrator's source-dependency declaration.
    old_measure = measure(
        {
            **case,
            "dependent_source_families": case.get(
                "dependent_source_families", ("PWD", "City impervious", "City buildings")
            ),
        }
    )
    old_route, _ = routing(case, old_measure)
    clone = deepcopy(case)
    clone["id"] = "whitaker-research-comparison"
    clone["name"] = case["name"] + " — additional Villanova/Temple comparison"
    clone["research_drainage"] = {
        "enabled": True,
        "sensitivity": True,
        "dem_type": "lidar",
        "parent_case_id": case["id"],
        "original_case_file_sha256": source_hash,
    }
    output.mkdir(parents=True, exist_ok=True)
    result = CaseStore(output.parent).save(clone)
    assert result["measurement"] == old_measure, "Physical measurements changed"
    assert result["drainage"] == old_route, "Conservative drainage changed"
    r = result["research_drainage"]
    files = write_diagnostic_rasters(output / "diagnostic-rasters", r)
    summary = {
        "source_case_file": str(source.relative_to(ROOT)),
        "source_case_file_sha256": source_hash,
        "comparison_case_id": clone["id"],
        "method": r["method"],
        "original_measurement_unchanged": True,
        "original_drainage_unchanged": True,
        "original_files_unchanged": all(
            sha256(p.read_bytes()).hexdigest() == h for p, h in preserved.items()
        ),
        "variants": [],
        "validation": r["validation"],
        "warnings": r["warnings"],
        "diagnostic_rasters": files,
    }
    for name, v in [("nominal", r["primary"])] + [(v["name"], v) for v in r["sensitivity"]]:
        summary["variants"].append(
            {
                "name": name,
                "grid_size": v["grid"]["cell_size"],
                "filled_cells": v["filled_cells"],
                "max_fill_depth_m": v["max_fill_depth_vertical_units"],
                "gsi_catchments": len(v["catchments"]),
                "on_parcel_modeled_ground_sqft": sum(
                    c["on_parcel_area_sqft"] for c in v["catchments"]
                ),
                "on_parcel_known_ia_sqft": v["known_ia_union_sqft"],
                "on_parcel_unknown_surface_sqft": sum(
                    c["on_parcel_unknown_surface_sqft"] for c in v["catchments"]
                ),
                "accounting_invariant": v["invariants"][
                    "terminal_accumulation_equals_routed_cells"
                ],
                "routed_ground_cells": v["routed_ground_cells"],
                "terminal_accumulation_cells": v["terminal_accumulation_cells"],
            }
        )
    summary["conditional_billing"] = result["assessment"]["research_drainage_scenarios"]
    assert summary["original_files_unchanged"]
    (output / "comparison.json").write_text(json.dumps(summary, indent=2) + "\n")
    print(
        json.dumps(
            {
                k: v
                for k, v in summary.items()
                if k not in ("diagnostic_rasters", "warnings", "conditional_billing")
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--source", type=Path, default=ROOT / "data/cases/pwd-98627-usgs-1m/case.json"
    )
    args = parser.parse_args()
    build(args.source, ROOT / "data/cases/whitaker-research-comparison")
