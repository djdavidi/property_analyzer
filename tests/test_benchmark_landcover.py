"""G4: modeled-class agreement with the 2018 land cover; synthetic and frozen inputs only.

No network and no model inference. Known answers are worked out by hand on 1 m
boxes in EPSG:26918 (1 m^2 = 10.7639 sq ft). The frozen-source test replays the
historical 2018 PhillyLULC capture in examples/automatic-public (URLs, retrieval
times and SHA-256 in its manifest). Agreement is not accuracy.
"""

from copy import deepcopy
from hashlib import sha256
import io
import json
from pathlib import Path
import tempfile
import unittest

import numpy as np
from shapely.geometry import box, mapping, shape

from drainage_core.benchmark import agreement, benchmark, class_geometries, stable_strata
from drainage_core.engine import new_case
from drainage_core.geometry import SQFT_PER_M2
from drainage_core.remote_sensing import classified_features
from drainage_core.sources import Cache, SourceError
import network_guard

network_guard.install()

ROOT = Path(__file__).resolve().parents[1]
EXAMPLE = ROOT / "examples" / "automatic-public"
LIBRARY = next(
    e for e in json.loads((EXAMPLE / "manifest.json").read_text()) if e["id"] == "library"
)


def F(identifier, geometry, name, **props):
    return {
        "type": "Feature",
        "id": identifier,
        "geometry": mapping(geometry),
        "properties": {"classification": name, **props},
    }


def small_case():
    c = new_case("Benchmark fixture", crs="EPSG:26918")
    c["parcel"] = mapping(box(0, 0, 10, 10))
    return c


MODELED = [
    F("m-roof", box(0, 0, 5, 10), "roof"),
    F("m-road", box(5, 0, 10, 5), "road"),
    F("m-dev", box(5, 5, 10, 10), "developed_space"),
]
REFERENCE = [
    F("r-roof", box(0, 0, 4, 10), "roof"),
    F("r-grass", box(4, 0, 5, 10), "grass_shrub"),
    F("r-road", box(5, 0, 10, 10), "road"),
]


class AgreementTests(unittest.TestCase):
    def test_hand_derived_confusion_and_interpretation(self):
        c = small_case()
        region = shape(c["parcel"])
        m, _, _ = class_geometries(MODELED)
        r, _, _ = class_geometries(REFERENCE)
        out = agreement(m, r, region, c)
        mat = out["confusion_sqft"]
        self.assertAlmostEqual(mat["roof"]["roof"], 40 * SQFT_PER_M2)
        self.assertAlmostEqual(mat["roof"]["grass_shrub"], 10 * SQFT_PER_M2)
        self.assertAlmostEqual(mat["road"]["road"], 25 * SQFT_PER_M2)
        self.assertAlmostEqual(mat["developed_space"]["road"], 25 * SQFT_PER_M2)
        self.assertAlmostEqual(out["compared_sqft"], 100 * SQFT_PER_M2)
        self.assertAlmostEqual(out["overall_agreement"], 0.65)
        rows = {x["class"]: x for x in out["per_modeled_class"]}
        self.assertAlmostEqual(rows["roof"]["agreement_share"], 0.8)
        self.assertAlmostEqual(rows["road"]["agreement_share"], 1)
        self.assertEqual(rows["developed_space"]["agreement_share"], 0)
        self.assertIsNone(
            rows["canopy"]["agreement_share"], "No modeled canopy: share unknown, not zero"
        )
        cols = {x["class"]: x for x in out["per_reference_class"]}
        self.assertAlmostEqual(cols["road"]["agreement_share"], 0.5)
        self.assertEqual(cols["grass_shrub"]["agreement_share"], 0)
        check = {x["modeled_class"]: x for x in out["interpretation_check"]}
        self.assertAlmostEqual(check["developed_space"]["reference_group_share"]["impervious"], 1)
        self.assertAlmostEqual(check["roof"]["reference_group_share"]["pervious"], 0.2)
        self.assertIn("D3", check["road"]["scenario_under_test"])
        self.assertEqual(out["neither_classified_sqft"], 0)

    def test_unclassified_area_is_neither_agreement_nor_disagreement(self):
        c = small_case()
        region = shape(c["parcel"])
        m, _, _ = class_geometries(
            [F("m", box(0, 0, 10, 6), "road")]
        )  # low-score model gap above y=6
        r, _, _ = class_geometries(
            [F("r", box(0, 2, 10, 10), "road")]
        )  # reference NoData below y=2
        out = agreement(m, r, region, c)
        self.assertAlmostEqual(out["compared_sqft"], 40 * SQFT_PER_M2)
        self.assertAlmostEqual(out["overall_agreement"], 1)
        self.assertAlmostEqual(out["modeled_only_unclassified_reference_sqft"], 20 * SQFT_PER_M2)
        self.assertAlmostEqual(out["reference_only_unclassified_modeled_sqft"], 40 * SQFT_PER_M2)
        empty = agreement({}, r, region, c)
        self.assertEqual(empty["compared_sqft"], 0)
        self.assertIsNone(empty["overall_agreement"])

    def test_overlapping_modeled_classes_become_conflict_not_double_count(self):
        m, conflict, parts = class_geometries(
            [F("a", box(0, 0, 6, 10), "roof"), F("b", box(4, 0, 10, 10), "road")]
        )
        self.assertAlmostEqual(conflict.area, 20)
        self.assertAlmostEqual(m["roof"].area, 40)
        self.assertAlmostEqual(m["road"].area, 40)
        self.assertEqual(parts, {"roof": 1, "road": 1})

    def test_stable_strata_select_footprints_and_roads(self):
        c = small_case()
        region = shape(c["parcel"])
        r, _, _ = class_geometries(REFERENCE)
        strata = stable_strata(
            region, r, [("fp1", mapping(box(0, 0, 5, 10))), ("fp2", mapping(box(5, 5, 10, 10)))], c
        )
        b = strata["stable_building_footprints"]
        self.assertEqual((b["footprints_considered"], b["footprints_stable"]), (2, 1))
        self.assertAlmostEqual(b["footprints"][0]["reference_building_fraction"], 0.8)
        self.assertTrue(b["footprints"][0]["stable"])
        self.assertFalse(b["footprints"][1]["stable"])
        self.assertAlmostEqual(b["geometry"].area, 50)
        self.assertAlmostEqual(
            strata["stable_roads"]["geometry"].area, 25
        )  # road outside both footprints
        eroded = stable_strata(region, r, [("fp1", mapping(box(0, 0, 5, 10)))], c, edge=0.5)
        self.assertAlmostEqual(eroded["stable_building_footprints"]["geometry"].area, 4 * 9)
        strict = stable_strata(
            region, r, [("fp1", mapping(box(0, 0, 5, 10)))], c, min_footprint_fraction=0.81
        )
        self.assertEqual(strict["stable_building_footprints"]["footprints_stable"], 0)

    def test_benchmark_tables_from_a_tiny_reference_raster(self):
        c = small_case()
        # 2 x 10 cells of 5 m x 1 m: columns are x, rows are y (top row first).
        classes = np.zeros((10, 2), dtype="uint8")
        classes[:, 0] = 5
        classes[:, 1] = 6
        classes[:5, 1] = 7
        ref = classified_features(
            classes,
            [0, 0, 10, 10],
            c,
            {"family": "synthetic", "url": "local:test", "sha256": "a" * 64, "vintage": "2018"},
        )
        modeled = [
            F("m-roof", box(0, 0, 5, 10), "roof"),
            F("m-road", box(5, 0, 10, 5), "road"),
            F("m-dev", box(5, 5, 10, 10), "other_pavement"),
        ]  # historical OEM label for developed space
        out = benchmark(
            c,
            modeled,
            ref["features"],
            [("fp", mapping(box(0, 0, 5, 10)))],
            modeled_aliases={"other_pavement": "developed_space"},
        )
        whole = out["strata"]["all_compared_area"]
        self.assertFalse(whole["stable"])
        self.assertAlmostEqual(whole["overall_agreement"], 1)
        self.assertAlmostEqual(
            whole["confusion_sqft"]["developed_space"]["other_pavement"], 25 * SQFT_PER_M2
        )
        self.assertAlmostEqual(out["strata"]["stable_building_footprints"]["overall_agreement"], 1)
        self.assertAlmostEqual(out["strata"]["stable_roads"]["compared_sqft"], 25 * SQFT_PER_M2)
        self.assertEqual(out["strata"]["stable_building_footprints"]["modeled_parts"]["roof"], 1)
        self.assertAlmostEqual(out["parcel_sqft"], 100 * SQFT_PER_M2)
        json.dumps(out)  # serializable result


class _Response(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()


def frozen_library_cache(root, *, expect_urls=None):
    """Cache whose opener serves the historical PhillyLULC capture for the library parcel."""
    snapshots = {
        s["url"].split("?")[0].rsplit("/", 1)[-1]: (EXAMPLE / "sources" / s["file"]).read_bytes()
        for s in LIBRARY["source_snapshots"]
    }
    files = {"2": snapshots["2"], "legend": snapshots["legend"], "export": snapshots["export"]}
    png = (EXAMPLE / "sources" / LIBRARY["source_snapshots"][3]["file"]).read_bytes()
    seen = []

    def opener(request, timeout=None):
        url = getattr(request, "full_url", request)
        seen.append(url)
        if url.endswith(".png"):
            return _Response(png)
        key = url.split("?")[0].rsplit("/", 1)[-1]
        if key not in files:
            raise OSError("unexpected " + url)
        return _Response(files[key])

    return Cache(root, opener=opener), seen


def library_case():
    c = new_case("Frozen 2018 replay (1901 Vine St parcel)", crs="EPSG:2272")
    c["id"] = "benchmark-library"
    c["parcel"] = deepcopy(LIBRARY["parcel"])
    return c


def oem_from(reference_features, relabel=None):
    """Synthetic 'model output': the reference polygons with OEM names, optionally relabelled."""
    out = []
    for f in reference_features:
        name = f["properties"]["classification"]
        name = (relabel or {}).get(name, "developed_space" if name == "other_pavement" else name)
        out.append(
            {
                "type": "Feature",
                "id": "auto-semantic-" + name + "-" + f["id"],
                "geometry": f["geometry"],
                "properties": {
                    "layer": "surface_candidate",
                    "classification": name,
                    "source_kind": "modeled semantic estimate",
                    "model_sha256": "b" * 64,
                    "source_sha256": "c" * 64,
                    "source_vintage": "2025",
                    "interpretation_version": "oem-appearance-v2",
                },
            }
        )
    return out


class FrozenReferenceTests(unittest.TestCase):
    """Replays real 2018 bytes through the provider; ~1 m cells and no pad, as captured."""

    def test_provider_decodes_the_frozen_capture_exactly(self):
        from stormwater.benchmark_landcover import fetch_reference, reference_features

        for s in LIBRARY["source_snapshots"]:
            self.assertEqual(
                sha256((EXAMPLE / "sources" / s["file"]).read_bytes()).hexdigest(), s["sha256"]
            )
        with tempfile.TemporaryDirectory() as root:
            cache, seen = frozen_library_cache(root)
            ref = fetch_reference(library_case(), cache, cell_ft=3.28, pad_cells=0)
        self.assertEqual(ref["size"], [136, 164])
        self.assertEqual(ref["layer_name"], "Philadelphia Land Cover 2018")
        self.assertTrue(any("layers=show%3A2" in u and "RSP_NearestNeighbor" in u for u in seen))
        features, unclassified = reference_features(ref, library_case())
        areas = {}
        for f in features:
            areas[f["properties"]["classification"]] = (
                areas.get(f["properties"]["classification"], 0) + shape(f["geometry"]).area
            )
        for name, expected in LIBRARY["expected_source_areas_sqft"].items():
            # EPSG:2272 US survey feet -> international sq ft is within 4e-6 relative.
            self.assertAlmostEqual(
                areas.get(name, 0), expected, delta=max(0.01, expected * 5e-6), msg=name
            )

    def test_provider_rejects_wrong_crs_size_or_layer(self):
        from stormwater.benchmark_landcover import fetch_reference

        with tempfile.TemporaryDirectory() as root:
            cache, _ = frozen_library_cache(root)
            with self.assertRaisesRegex(SourceError, "rendering is 136x164"):
                fetch_reference(library_case(), cache, cell_ft=1.0)
            other = library_case()
            other["crs"] = "EPSG:26918"
            other["parcel"] = mapping(box(0, 0, 10, 10))
            with self.assertRaisesRegex(SourceError, "CRS"):
                fetch_reference(other, cache, cell_ft=3.28, pad_cells=0)

    def test_run_and_cli_on_frozen_reference_with_synthetic_model_output(self):
        from stormwater.benchmark_landcover import fetch_reference, main, reference_features, run

        with tempfile.TemporaryDirectory() as root:
            cache, _ = frozen_library_cache(Path(root) / "cache")
            c = library_case()
            ref_features, _ = reference_features(
                fetch_reference(c, cache, cell_ft=3.28, pad_cells=0), c
            )
            roofs = [f for f in ref_features if f["properties"]["classification"] == "roof"]
            c["features"]["features"] = oem_from(ref_features, {"road": "developed_space"}) + [
                {
                    "type": "Feature",
                    "id": "public-roof-1",
                    "geometry": roofs[0]["geometry"],
                    "properties": {
                        "layer": "surface",
                        "class": "roof",
                        "source_family": "City buildings",
                    },
                }
            ]
            before = deepcopy(c)
            result = run(c, cache, cell_ft=3.28, pad_cells=0, edge_buffer_m=0)
            self.assertEqual(c, before, "Benchmark must not change the case")
            case_dir = Path(root) / "case"
            case_dir.mkdir()
            (case_dir / "case.json").write_text(json.dumps(c))
            out = Path(root) / "agreement.json"
            code = main(
                [
                    "--case",
                    str(case_dir),
                    "--output",
                    str(out),
                    "--cache",
                    str(Path(root) / "cache"),
                    "--reference-cell-ft",
                    "3.28",
                    "--reference-pad-cells",
                    "0",
                    "--edge-buffer-m",
                    "0",
                ]
            )
            saved = json.loads(out.read_text())
        self.assertEqual(code, 0)
        self.assertEqual(saved["result_sha256"], result["result_sha256"])
        whole = result["strata"]["all_compared_area"]
        road = LIBRARY["expected_source_areas_sqft"]["road"]
        # Every class agrees except the 2018 road the synthetic model called developed space.
        self.assertAlmostEqual(whole["confusion_sqft"]["developed_space"]["road"], road, delta=1)
        self.assertAlmostEqual(
            whole["agreeing_sqft"],
            whole["compared_sqft"] - whole["confusion_sqft"]["developed_space"]["road"],
            places=3,
        )
        roads = result["strata"]["stable_roads"]
        self.assertEqual(roads["overall_agreement"], 0)
        check = {x["modeled_class"]: x for x in roads["interpretation_check"]}
        self.assertAlmostEqual(check["developed_space"]["reference_group_share"]["impervious"], 1)
        footprints = result["strata"]["stable_building_footprints"]
        self.assertEqual(
            (footprints["footprints_considered"], footprints["footprints_stable"]), (1, 1)
        )
        self.assertAlmostEqual(footprints["overall_agreement"], 1, places=6)
        self.assertEqual(
            result["kind"], "agreement with an independent older product; not accuracy"
        )
        self.assertTrue(
            any(
                "Temporal change: reference 2018 versus imagery 2025" in x
                for x in result["caveats"]
            )
        )
        self.assertEqual(result["modeled"]["model_sha256"], "b" * 64)
        self.assertEqual(len(result["reference"]["sources"]), 4)
        # Final LIVE-SAVINGS fix 4b: the saved paved-reference input for the assessment.
        paved = result["paved_reference_input"]
        self.assertEqual(paved["classes"], ["road", "other_pavement"])
        self.assertGreaterEqual(paved["paved_sqft"], road - 1)
        self.assertEqual(
            paved["agreement"]["stable_building_footprints"]["overall_agreement"],
            footprints["overall_agreement"],
        )
        self.assertIn("qualifies", paved["qualification"])
        self.assertEqual(saved["paved_reference_input"]["paved_sqft"], paved["paved_sqft"])

    def test_rgb_fallback_or_missing_model_output_is_refused(self):
        from stormwater.benchmark_landcover import modeled_features

        c = library_case()
        c["features"]["features"] = [
            {
                "type": "Feature",
                "id": "auto-rgb-1",
                "geometry": c["parcel"],
                "properties": {
                    "layer": "vegetation_candidate",
                    "source_kind": "modeled image candidate",
                },
            }
        ]
        with self.assertRaisesRegex(ValueError, "nothing to benchmark"):
            modeled_features(c)


if __name__ == "__main__":
    unittest.main()
