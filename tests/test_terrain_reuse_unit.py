"""Unit tests for saved-terrain selection; invented local fixtures and mocks only."""

from copy import deepcopy
from hashlib import sha256
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch

from shapely.geometry import box, mapping, shape
from drainage_core.engine import new_case, canonical, input_hash
from drainage_core.geometry import reproject, measure
from stormwater.terrain_reuse import reuse
from stormwater.automatic_terrain import acquire
from stormwater.cases import CaseStore


def fixture():
    c = new_case("Invented same-parcel fixture", crs="EPSG:26918")
    c.update(
        id="pwd-98627",
        parcel=mapping(box(491002, 4431002, 491006, 4431006)),
        boundary_source={"url": "https://stormwater.phila.gov/PwdWebApi/api/v1/parcel/98627"},
        baseline={"keep": "current billing"},
        assessment={"records": []},
    )
    donor = deepcopy(c)
    donor["id"] = "pwd-98627-verified"
    donor["baseline"] = {"ignore": "donor billing"}
    donor["terrain"] = {
        "elevations": [[10 - r - c / 10 for c in range(8)] for r in range(8)],
        "cell_size": 1,
        "crs": c["crs"],
        "horizontal_unit": "m",
        "vertical_unit": "m",
        "origin": [491000, 4431008],
        "settings": {"required_buffer_native_units": 1, "extent_sufficient": False},
        "source_quality": {"vertical_units": "verified"},
    }
    donor["sources"] = [
        {
            "url": "https://example.test/invented-dem.tif",
            "sha256": "a" * 64,
            "metadata_url": "https://example.test/invented-dem.xml",
            "metadata_sha256": "b" * 64,
            "vertical_unit": "m",
            "horizontal_unit": "m",
            "vertical_datum": "NAVD88",
            "crs": c["crs"],
            "height": 8,
            "width": 8,
            "resolution": [1, 1],
            "acquisition_period": ["2024-01-01", "2025-01-01"],
            "vertical_unit_evidence": {"status": "verified", "source_sha256": "b" * 64},
        }
    ]
    return c, donor


def save_donor(root, donor):
    p = root / donor["id"]
    p.mkdir(exist_ok=True)
    (p / "revisions").mkdir(exist_ok=True)
    digest = input_hash(donor)
    (p / "case.json").write_text(canonical(donor))
    (p / "revisions" / (digest + ".json")).write_text(canonical(donor))
    return {
        "schema_version": 1,
        "properties": {
            "98627": {
                "case_id": donor["id"],
                "input_sha256": digest,
                "terrain_sha256": sha256(canonical(donor["terrain"]).encode()).hexdigest(),
                "dem_sha256": "a" * 64,
                "metadata_sha256": "b" * 64,
                "minimum_buffer_m": 1,
            }
        },
    }


class TerrainReuseUnitTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.current, self.donor = fixture()
        self.registry = save_donor(self.root, self.donor)

    def choose(self, c=None, registry=None):
        return reuse(
            c or self.current, self.root, self.root / "cache", registry=registry or self.registry
        )

    def test_reuses_native_grid_and_provenance_without_donor_facts_or_mutation(self):
        before = canonical(self.current)
        p = self.root / self.donor["id"] / "case.json"
        original = p.read_bytes()
        out, status = self.choose()
        self.assertEqual(out["id"], self.current["id"])
        self.assertEqual(out["baseline"], self.current["baseline"])
        self.assertEqual(out["terrain"], self.donor["terrain"])
        self.assertIsNot(out["terrain"], self.donor["terrain"])
        self.assertEqual(status["status"], "reused_verified_saved_terrain")
        self.assertEqual(out["terrain_reuse"]["metadata_sha256"], "b" * 64)
        self.assertIn("b" * 64, {s.get("sha256") for s in out["sources"]})
        self.assertFalse(out["terrain"]["settings"]["extent_sufficient"])
        self.assertEqual(canonical(self.current), before)
        self.assertEqual(p.read_bytes(), original)

    def test_repeated_run_keeps_current_terrain_without_rediscovery(self):
        out, _ = self.choose()
        result, status = self.choose(out)
        self.assertIs(result, out)
        self.assertIsNone(status)

    def test_existing_explicit_terrain_is_not_overwritten(self):
        self.current["terrain"] = {"user": "explicit terrain"}
        out, status = self.choose()
        self.assertIs(out, self.current)
        self.assertIsNone(status)

    def test_changed_donor_or_revision_is_rejected_by_hash(self):
        p = self.root / self.donor["id"]
        self.donor["terrain"]["elevations"][0][0] += 1
        (p / "case.json").write_text(canonical(self.donor))
        out, s = self.choose()
        self.assertIs(out, self.current)
        self.assertIn("pinned input hash", s["error"])
        self.registry = save_donor(self.root, self.donor)
        digest = self.registry["properties"]["98627"]["input_sha256"]
        (p / "revisions" / (digest + ".json")).write_text("{}")
        self.assertIn("revision", self.choose()[1]["error"])

    def test_missing_donor_is_rejected_without_changing_current(self):
        (self.root / self.donor["id"] / "case.json").unlink()
        out, s = self.choose()
        self.assertIs(out, self.current)
        self.assertEqual(s["status"], "saved_terrain_rejected")

    def test_other_property_and_conflicting_source_identity_are_not_reused(self):
        self.current["id"] = "pwd-999"
        self.current["boundary_source"][
            "url"
        ] = "https://stormwater.phila.gov/PwdWebApi/api/v1/parcel/999"
        out, s = self.choose()
        self.assertIs(out, self.current)
        self.assertIsNone(s)
        self.current["id"] = "pwd-98627"
        self.assertIn("identities disagree", self.choose()[1]["error"])

    def test_same_id_but_changed_parcel_boundary_is_rejected(self):
        self.current["parcel"] = mapping(box(491003, 4431002, 491007, 4431006))
        self.assertIn("boundary differs", self.choose()[1]["error"])

    def test_unverified_units_or_missing_exact_metadata_are_rejected(self):
        for edit in ("units", "metadata", "datum", "resolution", "grid_units"):
            _, d = fixture()
            if edit == "units":
                d["terrain"]["source_quality"]["vertical_units"] = "assumed"
            if edit == "metadata":
                d["sources"][0]["vertical_unit_evidence"]["source_sha256"] = "c" * 64
            if edit == "datum":
                d["sources"][0]["vertical_datum"] = "unknown"
            if edit == "resolution":
                d["sources"][0]["resolution"] = [2, 2]
            if edit == "grid_units":
                d["terrain"]["vertical_unit"] = "ft"
            self.registry = save_donor(self.root, d)
            out, s = self.choose()
            self.assertIs(out, self.current)
            self.assertEqual(s["status"], "saved_terrain_rejected")

    def test_insufficient_buffer_or_nodata_are_rejected(self):
        _, d = fixture()
        d["terrain"]["settings"]["required_buffer_native_units"] = 10
        self.registry = save_donor(self.root, d)
        self.assertIn("required buffer", self.choose()[1]["error"])
        _, d = fixture()
        d["terrain"]["elevations"][3][3] = None
        self.registry = save_donor(self.root, d)
        self.assertIn("incomplete", self.choose()[1]["error"])

    def test_project_current_vectors_and_ledgers_without_resampling_grid(self):
        target = "EPSG:2272"
        original_crs = self.current["crs"]
        self.current["parcel"] = mapping(
            reproject(shape(self.current["parcel"]), original_crs, target)
        )
        self.current["crs"] = target
        geom = deepcopy(self.current["parcel"])
        self.current["features"]["features"] = [
            {"id": "roof", "geometry": geom, "properties": {"layer": "surface", "class": "roof"}}
        ]
        self.current["corrections"] = [
            {
                "id": "edit",
                "at": "2026-11-15",
                "reason": "Invented observation",
                "action": "add",
                "feature": {"id": "canopy", "geometry": geom, "properties": {"layer": "canopy"}},
            }
        ]
        self.current["assessment"]["records"] = [
            {
                "id": "r",
                "geometry": geom,
                "footprint_geometry": geom,
                "public_geometry": geom,
                "source": {"crs": target},
            }
        ]
        before = canonical(self.current)
        area = measure(self.current)["ga_sqft"]
        out, s = self.choose()
        self.assertEqual(out["crs"], original_crs)
        self.assertEqual(out["area_crs"], target)
        self.assertAlmostEqual(measure(out)["ga_sqft"], area, places=4)
        self.assertEqual(out["terrain"], self.donor["terrain"])
        self.assertEqual(out["assessment"]["records"][0]["source"]["crs"], original_crs)
        self.assertEqual(canonical(self.current), before)

    def test_keep_original_measurement_pixels_and_align_display_only(self):
        c = self.current
        original = c["crs"]
        c["parcel"] = mapping(reproject(shape(c["parcel"]), original, "EPSG:2272"))
        c["crs"] = "EPSG:2272"
        c["imagery"] = {"sha256": "c" * 64, "crs": c["crs"], "bounds": [0, 0, 1, 1]}
        image = deepcopy(c["imagery"])
        warped = {"sha256": "d" * 64, "crs": original}
        with patch("stormwater.terrain_reuse.warp_display", return_value=warped) as display:
            out, s = self.choose()
        self.assertEqual(out["imagery"], warped)
        self.assertEqual(out["measurement_imagery"], image)
        self.assertIn("d" * 64, {s.get("sha256") for s in out["sources"]})
        display.assert_called_once()
        self.assertEqual(c["imagery"], image)

    def test_missing_display_blob_does_not_force_dem_download(self):
        c = self.current
        original = c["crs"]
        c["parcel"] = mapping(reproject(shape(c["parcel"]), original, "EPSG:2272"))
        c["crs"] = "EPSG:2272"
        c["imagery"] = {"sha256": "c" * 64, "crs": c["crs"]}
        with patch(
            "stormwater.terrain_reuse.warp_display",
            side_effect=FileNotFoundError("fixture missing image"),
        ):
            out, s = self.choose()
        self.assertEqual(s["status"], "reused_verified_saved_terrain")
        self.assertNotIn("imagery", out)
        self.assertIn("measurement_imagery", out)
        self.assertIn("warnings", out)

    def test_preference_precedes_remote_discovery(self):
        registry = self.root / "registry.json"
        registry.write_text(json.dumps(self.registry))
        cache = Mock(root=self.root / "cache")
        with (
            patch("stormwater.terrain_reuse.REGISTRY", registry),
            patch(
                "stormwater.automatic_terrain.rasterio.open",
                side_effect=AssertionError("Remote read"),
            ),
        ):
            out, s = acquire(self.current, cache, case_root=self.root)
        cache.fetch_json.assert_not_called()
        cache.fetch_bytes.assert_not_called()
        self.assertEqual(out["terrain"], self.donor["terrain"])
        self.assertEqual(s["status"], "reused_verified_saved_terrain")

    def test_no_matching_preference_leaves_normal_provider_fallback(self):
        registry = self.root / "registry.json"
        registry.write_text(json.dumps({"schema_version": 1, "properties": {}}))
        cache = Mock(root=self.root / "cache")
        cache.fetch_json.return_value = {"data": {"items": []}}
        with patch("stormwater.terrain_reuse.REGISTRY", registry):
            with self.assertRaisesRegex(ValueError, "No verified-unit"):
                acquire(self.current, cache, case_root=self.root)
        cache.fetch_json.assert_called_once()

    def test_rejected_saved_preference_is_reported_if_remote_provider_is_offline(self):
        registry = self.root / "registry.json"
        registry.write_text(json.dumps(self.registry))
        (self.root / self.donor["id"] / "case.json").unlink()
        cache = Mock(root=self.root / "cache")
        cache.fetch_json.side_effect = OSError("invented network outage")
        with patch("stormwater.terrain_reuse.REGISTRY", registry):
            with self.assertRaisesRegex(
                ValueError, "Saved terrain preference rejected:.*remote discovery unavailable"
            ):
                acquire(self.current, cache, case_root=self.root)

    def test_frozen_gis_artifact_retains_reuse_lineage(self):
        from drainage_core.engine import analyze, result_hash

        out, _ = self.choose()
        result = analyze(out)
        self.assertEqual(result["processing_settings"]["terrain_reuse"], out["terrain_reuse"])
        self.assertEqual(result["analysis_sha256"], result_hash(result))

    def test_assessment_orchestrator_supplies_its_case_store_for_address_flow(self):
        store = CaseStore(self.root)
        c = deepcopy(self.current)
        c["assessment"]["snapshots"] = []
        store.directory(c["id"]).mkdir()
        store.save = Mock(return_value={"unit": "no actual analysis"})
        with (
            patch("stormwater.automatic.acquire", return_value=c) as automatic,
            patch("stormwater.assessment_workflow.gather", side_effect=lambda c, *a, **k: c),
            patch("stormwater.automatic.enrich_candidates", side_effect=lambda c: c),
        ):
            result = store.run_assessment(c, Mock())
        self.assertEqual(automatic.call_args.kwargs["case_root"], self.root)
        self.assertEqual(result["case"]["id"], "pwd-98627")
        store.save.assert_called_once()

    def test_current_ai_geometry_copies_follow_native_terrain_alignment(self):
        from stormwater.automatic import acquire as automatic_acquire
        from drainage_core.projection import project_case

        c = deepcopy(self.current)
        original = c["crs"]
        c["parcel"] = mapping(reproject(shape(c["parcel"]), original, "EPSG:2272"))
        c["crs"] = "EPSG:2272"
        feature = {
            "id": "ai-canopy",
            "geometry": deepcopy(c["parcel"]),
            "properties": {"layer": "canopy_candidate"},
        }
        cover = {
            "features": [feature],
            "coverage_geometry": deepcopy(c["parcel"]),
            "canopy_geometry": deepcopy(c["parcel"]),
            "crs": c["crs"],
            "pixel_crs": c["crs"],
            "source_vintage": "2025",
            "source_snapshots": [],
            "estimates": [],
            "coverage_complete": False,
            "status": "modeled_semantic_estimates",
            "retrieved_at": "2026-11-15",
            "unclassified_sqft": 0,
        }
        image = {"sha256": "c" * 64, "sources": [], "crs": c["crs"], "source_vintage": "2025"}

        def terrain(case, cache, **kwargs):
            out = project_case(case, original)
            out["terrain"] = deepcopy(self.donor["terrain"])
            return out, {"status": "unit-alignment"}

        with (
            patch("stormwater.automatic.now", return_value="2026-11-15T12:00:00Z"),
            patch("stormwater.automatic.buildings", return_value=([], [], False)),
            patch("stormwater.acquisition.acquire_imagery", return_value=image),
            patch("stormwater.automatic.landcover", return_value=cover),
            patch("stormwater.automatic_terrain.acquire", side_effect=terrain),
        ):
            out = automatic_acquire(c, Mock(root=self.root / "cache"), case_root=self.root)
        saved = out["automatic"]["landcover"]
        self.assertEqual(saved["crs"], out["crs"])
        self.assertEqual(saved["pixel_crs"], "EPSG:2272")
        self.assertLess(
            shape(saved["features"][0]["geometry"]).symmetric_difference(shape(out["parcel"])).area,
            1e-7,
        )
        self.assertLess(
            shape(saved["coverage_geometry"]).symmetric_difference(shape(out["parcel"])).area, 1e-7
        )


if __name__ == "__main__":
    unittest.main()
