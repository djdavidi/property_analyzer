"""Invented unit inputs only: no real-site replay, requests or browser checks."""

from copy import deepcopy
from datetime import date
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from shapely.geometry import box, mapping, shape

from drainage_core.engine import canonical, input_hash
from stormwater.management_pilot import (
    _ground_constraint,
    _ground_layers,
    _recorded_ia_family,
    estimate_property,
    main,
    run_saved,
    surface_storage_system,
)
from drainage_core.management_estimates import estimate_system
from drainage_core.surface_estimates import estimate_surfaces
from drainage_core.geometry import case_area_sqft
from tests.test_management_geometry_unit import fixture, candidate

# A 14 x 14 window of 3.048 m cells around the 30.48 m parcel: the whole-parcel
# catchment touches neither the window edge nor NoData, so its route is complete (D2).
GRID = {
    "origin": [-6.096, 36.576],
    "cell_size": 3.048,
    "crs": "EPSG:26918",
    "horizontal_unit": "m",
    "vertical_unit": "m",
}


def complete_route(gis):
    gis["research_drainage"]["primary"].update(
        grid=deepcopy(GRID),
        rasters={"filled_elevations": [[10.0] * 14 for _ in range(14)]},
        coverage={"terrain_covers_parcel_buffer": True},
    )
    return gis


def pilot_fixture(system_type="Rain Garden", system_id="62571"):
    case, gis = fixture(system_id, system_type)
    case["id"] = "pwd-98627"
    case["baseline"] = {
        "ga_sqft": 10000,
        "ia_sqft": 5000,
        "bill_date": "2026-11-16",
        "existing_ga_credit_sqft": 0,
        "existing_ia_credit_sqft": 0,
        "existing_iar_sqft": 0,
        "accounts": [{"allocation": 1, "discount_factor": 1}],
        "actual_bill_verified": False,
        "npdes_fraction": 0,
    }
    # Replace an area of developed appearance with canopy (disjoint classes).
    case["features"]["features"][2] = candidate("developed_space", box(12.192, 0, 18.288, 30.48))
    case["features"]["features"].append(candidate("canopy", box(9.144, 0, 12.192, 30.48)))
    return case, complete_route(gis)


def fake_capacity(volumes=(10.0, 10.0), status="estimated", rain=100.0, **extra):
    """Phase 4a-shaped capacity, bound to the case it is called with."""

    def capacity(case, gis, system_id):
        rows = [
            {"name": name, "status": "estimated", "volume_cuft": v}
            for name, v in zip(("perimeter_cell_minimum", "perimeter_bilinear"), volumes)
        ]
        estimated = status == "estimated"
        return {
            "system_id": str(system_id),
            "status": status,
            "reason": extra.get("reason"),
            "blocking_reasons": [],
            "unavailable_reasons": [] if estimated else ["Invented: no aligned DEM"],
            "review_flags": [],
            "storage_range_cuft": [min(volumes), max(volumes)] if estimated else None,
            "components": (
                [
                    {
                        "component_id": "component-1",
                        "rain_exposure_area_sqft": rain,
                        "scenarios": rows,
                    }
                ]
                if estimated
                else []
            ),
            "source_lineage": {
                "case_sha256": input_hash(case),
                "gis_analysis_sha256": gis.get("analysis_sha256"),
            },
        }

    return capacity


def nominal_rows(policy):
    return next(r for r in policy["runs"] if r["name"] == "nominal")["scenarios"]


class ManagementPilotUnitTests(unittest.TestCase):
    def test_impervious_area_is_not_estimated_not_zero_r4(self):
        case, gis = pilot_fixture()
        result = estimate_property(case, gis, ["62571"])
        ia = result["impervious_area"]
        self.assertEqual(ia["status"], "not_estimated")
        self.assertIsNone(ia["annual_savings_estimate"])
        self.assertIsNone(ia["estimated_reduction_sqft"])
        self.assertEqual(ia["scenarios"][0]["name"], "retained_recorded_ia")
        self.assertIsNone(ia["scenarios"][0]["annual_change"])
        self.assertFalse(ia["actual_available_savings_verified"])
        self.assertTrue(result["ground_constraint"]["compatible_with_recorded_ia"])
        self.assertEqual(result["canopy"]["uncertainty"]["status"], "not_calibrated")
        self.assertNotIn("confidence", result["canopy"])

    def test_complete_measurement_uses_shared_measured_area_path_r4(self):
        # Measured IA 4000 vs recorded 5000: IA units 10 -> 8; 70.48 -> 56.384 = 56.38;
        # 14.10/month = 169.20/yr. GA unchanged (10000).
        case, gis = pilot_fixture()
        gis["measurement"] = {
            "complete": True,
            "ga_sqft": 10000,
            "ia_sqft": 4000,
            "geometries": {
                "physical_ia": case["parcel"],
                "pervious": {"type": "GeometryCollection", "geometries": []},
            },
        }
        ia = estimate_property(case, gis, ["62571"])["impervious_area"]
        self.assertEqual(ia["status"], "measured_area_scenario")
        self.assertEqual(ia["estimated_reduction_sqft"], 1000)
        self.assertEqual(ia["annual_savings_estimate"], 169.20)

    def test_known_pilot_properties_no_longer_receive_invented_percentages(self):
        def assert_no_numeric_confidence(value):
            if isinstance(value, dict):
                for key, item in value.items():
                    if key in ("confidence_pct", "confidence_percentage", "percentage"):
                        self.assertIsNone(item)
                    assert_no_numeric_confidence(item)
            elif isinstance(value, list):
                for item in value:
                    assert_no_numeric_confidence(item)

        for identifier in ("pwd-98627", "pwd-538963"):
            with self.subTest(identifier=identifier):
                case, gis = pilot_fixture()
                case["id"] = identifier
                result = estimate_property(case, gis, ["62571"])
                assert_no_numeric_confidence(result)
                self.assertNotIn("confidence", result["canopy"])
                self.assertNotIn("confidence", result["impervious_area"])
                self.assertNotIn("confidence", result["systems"][0]["policy"])
                self.assertEqual(
                    result["systems"][0]["policy"]["uncertainty"]["status"], "not_calibrated"
                )

    def test_recorded_ia_family_is_labelled_and_keeps_physical_original(self):
        case, gis = pilot_fixture("Tree Trench")
        result = estimate_property(case, gis, ["62571"])
        system = result["systems"][0]
        rows = {s["id"]: s for s in nominal_rows(system["policy"])}
        self.assertEqual(
            set(rows),
            {
                "low",
                "base",
                "high",
                "recorded_ia_uniform",
                "recorded_ia_allocation_low",
                "recorded_ia_allocation_high",
            },
        )
        # Whole-parcel catchment: the recorded-IA scenarios reproduce the recorded total.
        self.assertAlmostEqual(
            rows["recorded_ia_uniform"]["candidate_ia_sqft"], case["baseline"]["ia_sqft"], places=5
        )
        self.assertAlmostEqual(
            rows["recorded_ia_allocation_low"]["candidate_ia_sqft"], 5000, places=5
        )
        self.assertAlmostEqual(
            rows["recorded_ia_allocation_high"]["candidate_ia_sqft"], 5000, places=5
        )
        self.assertTrue(rows["recorded_ia_uniform"]["fractional_ia_is_assumed"])
        self.assertEqual(rows["base"]["interpretation_scenario"], "road_impervious")
        self.assertFalse(
            any("weighted_components" in s for s in system["physical"]["runs"][0]["area_scenarios"])
        )
        self.assertIsNone(system["policy"]["captured_ia_sqft"])
        self.assertTrue(result["do_not_sum"])

    def test_spatial_allocation_sensitivity_brackets_the_uniform_fraction_r15(self):
        # Catchment = west half (x < 15.24): hard 3000 (observed 1000 + road 2000), crowns 1000,
        # mixed developed 3.048 m strip = 1000. Parcel: hard 3000, uncertain pool = crowns 1000 +
        # developed 2000 = 3000; implied hard = 5000 - 3000 = 2000. Local pool 2000:
        # low = max(0, 2000 - (3000 - 2000)) = 1000 -> 0.5; high = min(2000, 2000) -> 1.0.
        case, gis = pilot_fixture()
        gis["research_drainage"]["primary"]["catchments"][0]["geometry"] = mapping(
            box(0, 0, 15.24, 30.48)
        )
        engineering = estimate_system(case, gis, "62571")
        constraint = _ground_constraint(case, estimate_surfaces(case, gis))
        family = _recorded_ia_family(case, gis, engineering, constraint, 0.5)
        rows = {s["id"]: s for s in family["runs"][0]["area_scenarios"]}
        self.assertAlmostEqual(rows["recorded_ia_allocation_low"]["area_sqft"], 3000 + 1000)
        self.assertAlmostEqual(rows["recorded_ia_allocation_high"]["area_sqft"], 3000 + 2000)
        self.assertLessEqual(
            rows["recorded_ia_allocation_low"]["area_sqft"],
            rows["recorded_ia_uniform"]["area_sqft"],
        )
        self.assertLessEqual(
            rows["recorded_ia_uniform"]["area_sqft"],
            rows["recorded_ia_allocation_high"]["area_sqft"],
        )
        self.assertIn("Spatial-allocation sensitivity", rows["recorded_ia_allocation_low"]["basis"])

    def test_observed_canopy_conceals_unclassified_ground_r5(self):
        case, gis = pilot_fixture()
        case["features"]["features"][3] = candidate("grass_shrub", box(24.384, 0, 30.48, 30.48))
        before = case_area_sqft(_ground_layers(case, gis)["crowns"], case)
        case["features"]["features"].append(
            {
                "id": "observed-crown",
                "geometry": mapping(box(18.288, 0, 24.384, 30.48)),
                "properties": {"layer": "canopy"},
            }
        )
        after = case_area_sqft(_ground_layers(case, gis)["crowns"], case)
        self.assertAlmostEqual(before, 1000)
        self.assertAlmostEqual(after, 3000)

    def test_inputs_immutable_and_policy_does_not_route_infer_or_acquire(self):
        case, gis = pilot_fixture()
        before = canonical([case, gis])
        with (
            patch("drainage_core.engine.analyze", side_effect=AssertionError("no routing")),
            patch("urllib.request.urlopen", side_effect=AssertionError("no network")),
        ):
            result = estimate_property(case, gis, ["62571"])
        self.assertEqual(before, canonical([case, gis]))
        self.assertIsNotNone(result["canopy"]["annual_savings_estimate"])

    def test_incompatible_prior_does_not_silently_price_clipped_best_canopy(self):
        case, gis = pilot_fixture()
        case["baseline"]["ia_sqft"] = 500
        result = estimate_property(case, gis, ["62571"])
        self.assertFalse(result["ground_constraint"]["compatible_with_recorded_ia"])
        self.assertIsNone(result["canopy"]["annual_savings_estimate"])
        self.assertIsNone(result["ground_constraint"]["canopy_ground_ia_estimate_sqft"])

    def test_missing_semantics_cannot_become_zero_canopy(self):
        case, gis = pilot_fixture()
        case["features"]["features"] = [
            f for f in case["features"]["features"] if not f["id"].startswith("ai-")
        ]
        with self.assertRaisesRegex(ValueError, "missing imagery is not zero canopy"):
            estimate_property(case, gis, ["62571"])

    def test_invalid_historical_gis_is_not_reused(self):
        case, gis = pilot_fixture()
        gis["engine_version"] = "gis-engine-v4"
        with self.assertRaisesRegex(ValueError, "Historical or invalidated GIS"):
            estimate_property(case, gis, ["62571"])

    def test_known_failed_canopy_prerequisite_cannot_be_assumed_away(self):
        case, gis = pilot_fixture()
        case["assessment"] = {
            "records": [
                {"category": "canopy", "facts": {"ground_impervious_overlap_confirmed": False}}
            ]
        }
        result = estimate_property(case, gis, ["62571"])
        self.assertIsNone(result["canopy"]["annual_savings_estimate"])

    def test_pending_baseline_refresh_and_existing_occupancy_block_canopy(self):
        case, gis = pilot_fixture()
        case["assessment"] = {"records": [], "baseline_refresh": {"status": "pending_review"}}
        result = estimate_property(case, gis, ["62571"])
        self.assertIsNone(result["canopy"]["annual_savings_estimate"])
        self.assertTrue(all(s["status"] == "blocked" for s in result["canopy"]["scenarios"]))

    def test_published_gap_blocks_prices_and_is_carried_as_warning_h7(self):
        case, gis = pilot_fixture()
        case["baseline"]["published_monthly_total"] = 10.00
        result = estimate_property(case, gis, ["62571"])
        self.assertEqual(result["baseline_gap"]["status"], "exceeds_threshold")
        self.assertIsNone(result["canopy"]["annual_savings_estimate"])
        self.assertTrue(any("published" in w for w in result["baseline_warnings"]))

    def test_assessment_date_is_normalized_and_data_derived_h8(self):
        case, gis = pilot_fixture()
        explicit = estimate_property(case, gis, ["62571"], as_of=date(2026, 11, 16))
        self.assertEqual((explicit["as_of"], explicit["as_of_source"]), ("2026-11-16", "explicit"))
        derived = estimate_property(case, gis, ["62571"])
        self.assertEqual(
            (derived["as_of"], derived["as_of_source"]),
            ("2026-11-15", "case.imagery_age_policy.as_of"),
        )
        case.pop("imagery_age_policy")
        case["baseline"].pop("bill_date")
        with self.assertRaisesRegex(ValueError, "Assessment date unknown"):
            estimate_property(case, gis, ["62571"])

    def test_saved_adapter_reads_and_preserves_exact_bytes_and_cli_as_of(self):
        case, gis = pilot_fixture()
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "input"
            root.mkdir()
            for name, value in [("case", case), ("gis-analysis", gis)]:
                (root / (name + ".json")).write_text(json.dumps(value, indent=2))
            before = {p.name: p.read_bytes() for p in root.iterdir()}
            result = run_saved([(root, ["62571"])], Path(temporary) / "output")
            self.assertEqual(before, {p.name: p.read_bytes() for p in root.iterdir()})
            self.assertEqual(len(result["input_manifest"]), 2)
            self.assertEqual(result["properties"][0]["systems"][0]["policy"]["system_id"], "62571")
            self.assertEqual(result["version"], "saved-three-system-pilot-v4")
            self.assertIn("stormwater/billing.py", result["implementation_sha256"])
            self.assertIn("config/rules-pwd-2026-09.json", result["implementation_sha256"])
            self.assertNotIn("confidence_meaning", result)
            with patch("builtins.print"):
                main(
                    [
                        "--south-61st",
                        str(root),
                        "--only-system",
                        "62571",
                        "--as-of",
                        "2026-11-16",
                        "--output",
                        str(Path(temporary) / "cli"),
                    ]
                )
            saved = json.loads((Path(temporary) / "cli" / "estimates.json").read_text())
            self.assertEqual(saved["as_of"], "2026-11-16")
            self.assertEqual(saved["properties"][0]["as_of"], "2026-11-16")

    def test_capacity_path_is_chosen_by_system_type_not_id_h5(self):
        self.assertTrue(surface_storage_system("Rain Garden"))
        self.assertTrue(surface_storage_system("Bioretention basin"))
        self.assertFalse(surface_storage_system("Subsurface Basin"))
        for system_id in ("62571", "01073", "1234"):
            with self.subTest(system_id=system_id):
                case, gis = pilot_fixture(system_id=system_id)
                with patch(
                    "drainage_core.runoff_capacity.estimate_capacity", side_effect=fake_capacity()
                ):
                    system = estimate_property(case, gis, [system_id])["systems"][0]
                self.assertTrue(system["capacity_path"])
                self.assertEqual(system["policy"]["basis"], "storage_limited_management_range")
        case, gis = pilot_fixture("Tree Trench")
        system = estimate_property(case, gis, ["62571"])["systems"][0]
        self.assertFalse(system["capacity_path"])
        self.assertNotIn("managed_runoff", system)

    def test_system_bed_is_excluded_for_every_system_h16(self):
        # Base = observed 1000 + road 2000 = 3000 sq ft, 100 of it the bed -> 2900 priced.
        # 2320 sq ft credits: GA 10000 -> 7680 (16 units): 20.06 -> 16.05; IA 5000 -> 2680 (6 units):
        # 70.48 -> 42.29. Saving 4.01 + 28.19 = 32.20/month = 386.40/yr.
        case, gis = pilot_fixture("Tree Trench")
        policy = estimate_property(case, gis, ["62571"])["systems"][0]["policy"]
        base = next(s for s in nominal_rows(policy) if s["id"] == "base")
        self.assertAlmostEqual(base["system_bed_ia_excluded_sqft"], 100)
        self.assertAlmostEqual(base["priced_candidate_ia_sqft"], 2900)
        self.assertEqual(base["annual_savings"], 386.40)
        self.assertEqual(policy["current_estimate"]["id"], "base")
        self.assertEqual(policy["headline"]["run"], "nominal")
        case, gis = pilot_fixture()
        with patch(
            "drainage_core.runoff_capacity.estimate_capacity", side_effect=fake_capacity((1e6, 1e6))
        ):
            system = estimate_property(case, gis, ["62571"])["systems"][0]
        row = next(s for s in nominal_rows(system["policy"]) if s["id"].startswith("base/"))
        self.assertAlmostEqual(row["system_bed_ia_excluded_sqft"], 100)
        self.assertAlmostEqual(row["volume_equivalent_managed_ia_sqft"], 2900)
        full = next(
            s for s in nominal_rows(system["full_area_management_scenario"]) if s["id"] == "base"
        )
        self.assertAlmostEqual(full["priced_candidate_ia_sqft"], 2900)

    def test_storage_limited_price_follows_storage_range_not_full_area(self):
        case, gis = pilot_fixture()
        with patch(
            "drainage_core.runoff_capacity.estimate_capacity",
            side_effect=fake_capacity((10.0, 10.0)),
        ):
            system = estimate_property(case, gis, ["62571"])["systems"][0]
        # 10 cu ft storage < 12.5 cu ft of rain on the 100 sq ft bed: no candidate runoff fits.
        self.assertEqual(system["policy"]["headline"]["annual_savings_range"], [0.0, 0.0])
        self.assertGreater(
            system["full_area_management_scenario"]["current_estimate"]["annual_savings"], 0
        )
        self.assertFalse(system["full_area_management_scenario"]["usable_for_current_savings"])
        self.assertIsNone(system["managed_runoff"]["verified_managed_area_sqft"])

    def test_unknown_capacity_withholds_storage_limited_price(self):
        case, gis = pilot_fixture()
        system = estimate_property(case, gis, ["62571"])["systems"][
            0
        ]  # no terrain: physical 'unavailable'
        self.assertEqual(system["capacity"]["status"], "unavailable")
        self.assertEqual(system["policy"]["status"], "unavailable")
        self.assertIsNone(system["policy"]["current_estimate"])
        self.assertIsNotNone(system["full_area_management_scenario"]["current_estimate"])

    def test_route_state_rule_matches_the_app_d2(self):
        case, gis = pilot_fixture("Tree Trench")
        gis["research_drainage"]["primary"]["grid"] = {**GRID, "origin": [0, 30.48]}
        gis["research_drainage"]["primary"]["rasters"] = {
            "filled_elevations": [[10.0] * 10 for _ in range(10)]
        }
        policy = estimate_property(case, gis, ["62571"])["systems"][0]["policy"]
        self.assertEqual(policy["status"], "conditional_estimate")
        self.assertEqual(policy["partial_label"], "partial: true value may be higher")
        case, gis = pilot_fixture("Tree Trench")
        gis["research_drainage"]["primary"]["grid"] = {}
        policy = estimate_property(case, gis, ["62571"])["systems"][0]["policy"]
        self.assertEqual(policy["status"], "blocked")
        self.assertTrue(any("cannot be tested" in r for r in policy["reasons"]))


if __name__ == "__main__":
    unittest.main()
