"""Cross-module fixtures with independently calculated geometric/routing answers."""

from copy import deepcopy
from pathlib import Path
import json
import tempfile
import unittest

from shapely.geometry import box, Point, LineString, Polygon, mapping

from stormwater.cases import CaseStore, analyze, canonical, input_hash, new_case, routing
from stormwater.geometry import effective_features, measure, SQFT_PER_M2
from stormwater.validation import compare_geometry, validate_case


def feature(identifier, geometry, layer, cls=None, **properties):
    props = {"layer": layer, **properties}
    if cls is not None:
        props["class"] = cls
    return {"id": identifier, "type": "Feature", "geometry": mapping(geometry), "properties": props}


def make_case(features=None, parcel=None):
    case = new_case("Independent synthetic fixture")
    case.update(crs="EPSG:26918", parcel=mapping(parcel if parcel is not None else box(0, 0, 3, 1)))
    case["features"]["features"] = features or []
    return case


def terrain():
    return {
        "elevations": [[3, 2, 1]],
        "origin": [0, 1],
        "cell_size": 1,
        "horizontal_unit": "m",
        "vertical_unit": "m",
        "crs": "EPSG:26918",
        "settings": {"extent_sufficient": True},
    }


class GeometryRoutingIntegrationTests(unittest.TestCase):
    def test_partial_unknown_ia_does_not_become_zero_or_complete(self):
        case = make_case([feature("roof", box(0, 0, 1, 1), "surface", "roof")])
        result = analyze(case)
        self.assertAlmostEqual(result["measurement"]["ia_sqft"], SQFT_PER_M2)
        self.assertAlmostEqual(result["measurement"]["unknown_sqft"], 2 * SQFT_PER_M2)
        self.assertAlmostEqual(result["measurement"]["ia_max_sqft"], 3 * SQFT_PER_M2)
        self.assertFalse(result["measurement"]["complete"])
        self.assertEqual(result["drainage"]["status"], "unavailable")
        self.assertEqual(result["validation"]["ia"]["status"], "incomplete")
        self.assertEqual(result["validation"]["drainage"]["status"], "incomplete")

    def test_ground_catchment_intersects_ia_separately_from_roof_unknown(self):
        case = make_case(
            [
                feature("r", box(0, 0, 1, 1), "surface", "roof"),
                feature("p", box(1, 0, 2, 1), "surface", "pavement"),
                feature("g", box(2, 0, 3, 1), "surface", "pervious"),
                feature("A", Point(2.5, 0.5), "inlet"),
            ]
        )
        case["terrain"] = terrain()
        result = analyze(case)
        catchments = {c["outlet"]: c for c in result["drainage"]["catchments"]}
        self.assertAlmostEqual(result["measurement"]["ia_sqft"], 2 * SQFT_PER_M2)
        self.assertAlmostEqual(catchments["inlet:A"]["on_parcel_physical_ia_sqft"], SQFT_PER_M2)
        self.assertAlmostEqual(catchments["inlet:A"]["contributing_area_sqft"], 2 * SQFT_PER_M2)
        self.assertEqual(result["drainage"]["labels"][0][0], "unresolved:roof:0:0")
        self.assertEqual(result["drainage"]["unresolved_cells"], 1)
        self.assertIn("Not established", catchments["inlet:A"]["eligibility"])

    def test_explicit_roof_pipe_connection_transfers_without_changing_physical_ia(self):
        case = make_case(
            [
                feature("r", box(0, 0, 1, 1), "surface", "roof"),
                feature("p", box(1, 0, 3, 1), "surface", "pavement"),
                feature("A", Point(2.5, 0.5), "inlet"),
                feature(
                    "pipe",
                    LineString([(2.5, 0.5), (4, 0.5)]),
                    "connection",
                    **{"from": "A", "to": "garden", "evidence": "documented"},
                ),
            ]
        )
        case["terrain"] = terrain()
        case["terrain"]["roof_connections"] = [
            {"cell": [0, 0], "to": "A", "evidence": "documented"}
        ]
        result = analyze(case)
        self.assertEqual(result["drainage"]["counts"], {"outlet:garden": 3})
        self.assertAlmostEqual(result["measurement"]["ia_sqft"], 3 * SQFT_PER_M2)
        self.assertAlmostEqual(
            result["drainage"]["catchments"][0]["on_parcel_physical_ia_sqft"], 3 * SQFT_PER_M2
        )
        self.assertEqual(result["screens"], [])

    def test_offparcel_flow_preserved_while_ia_is_parcel_clipped(self):
        case = make_case(
            [
                feature("p", box(0, 0, 3, 1), "surface", "pavement"),
                feature("A", Point(2.5, 0.5), "inlet"),
            ],
            parcel=box(1, 0, 2, 1),
        )
        case["terrain"] = terrain()
        result = analyze(case)
        outlet = result["drainage"]["outlets"][0]
        catchment = result["drainage"]["catchments"][0]
        self.assertAlmostEqual(outlet["on_parcel_area_sqft"], SQFT_PER_M2)
        self.assertAlmostEqual(outlet["off_parcel_area_sqft"], 2 * SQFT_PER_M2)
        self.assertAlmostEqual(catchment["contributing_area_sqft"], 3 * SQFT_PER_M2)
        self.assertAlmostEqual(catchment["on_parcel_physical_ia_sqft"], SQFT_PER_M2)
        self.assertIsNone(catchment["off_parcel_physical_ia_sqft"])
        self.assertAlmostEqual(result["measurement"]["ia_sqft"], SQFT_PER_M2)

    def test_correction_reclassifies_ground_and_replays_roof_routing(self):
        case = make_case(
            [
                feature("p", box(0, 0, 3, 1), "surface", "pavement"),
                feature("A", Point(2.5, 0.5), "inlet"),
            ]
        )
        case["terrain"] = terrain()
        observation = deepcopy(case["features"])
        self.assertEqual(analyze(case)["drainage"]["counts"], {"inlet:A": 3})
        case["corrections"] = [
            {
                "id": "roof-review",
                "at": "2026-11-15T12:00:00Z",
                "action": "add",
                "reason": "Reviewed independent roof outline",
                "feature": feature("r", box(0, 0, 1, 1), "surface", "roof"),
            }
        ]
        self.assertEqual(analyze(case)["drainage"]["unresolved_cells"], 1)
        self.assertEqual(case["features"], observation)
        effective = effective_features(case)
        roof = next(f for f in effective if f["id"] == "r")
        self.assertEqual(roof["properties"]["evidence"], "manual_correction")
        case["corrections"] = []
        self.assertEqual(analyze(case)["drainage"]["counts"], {"inlet:A": 3})

    def test_canopy_over_overlapping_roof_paving_and_lawn_is_ground_only(self):
        case = make_case(
            [
                feature("r", box(0, 0, 4, 10), "surface", "roof"),
                feature("p", box(2, 0, 8, 10), "surface", "pavement"),
                feature("g", box(8, 0, 10, 10), "surface", "pervious"),
                feature("t", box(0, 0, 10, 10), "canopy"),
            ],
            parcel=box(0, 0, 10, 10),
        )
        before = measure(case)
        self.assertAlmostEqual(before["ia_sqft"], 80 * SQFT_PER_M2)
        self.assertAlmostEqual(before["canopy_ground_ia_sqft"], 40 * SQFT_PER_M2)
        self.assertTrue(before["complete"])
        case["features"]["features"].pop()
        after = measure(case)
        self.assertEqual(before["ia_sqft"], after["ia_sqft"])
        # Removing the only canopy layer removes evidence; it does not prove absence.
        self.assertIsNone(after["canopy_ground_ia_sqft"])

    def test_terrain_crs_or_units_mismatch_blocks_integration(self):
        case = make_case([feature("p", box(0, 0, 3, 1), "surface", "pavement")])
        case["terrain"] = terrain()
        case["terrain"]["crs"] = "EPSG:2272"
        with self.assertRaisesRegex(ValueError, "CRS differ"):
            analyze(case)
        case["terrain"]["crs"] = case["crs"]
        case["terrain"]["horizontal_unit"] = "us-ft"
        with self.assertRaisesRegex(ValueError, "horizontal unit"):
            analyze(case)

    def test_nodata_and_barrier_cells_never_become_contributing_catchments(self):
        case = make_case([feature("p", box(0, 0, 3, 1), "surface", "pavement")])
        case["terrain"] = terrain()
        case["terrain"]["elevations"][0][1] = None
        case["terrain"]["barriers"] = [[0, 0]]
        result = analyze(case)
        keys = {c["outlet"] for c in result["drainage"]["catchments"]}
        self.assertNotIn("barrier", keys)
        self.assertNotIn("nodata", keys)
        self.assertEqual(result["drainage"]["nodata_cells"], 1)
        self.assertFalse(result["drainage"]["coverage_complete"])

    def test_pwd_inlet_does_not_make_independent_surface_measurement_circular(self):
        case = make_case(
            [
                feature(
                    "p", box(0, 0, 3, 1), "surface", "pavement", source_family="independent survey"
                ),
                feature("A", Point(2.5, 0.5), "inlet", source_family="PWD"),
            ]
        )
        self.assertEqual(measure(case)["source_dependence"], [])
        case["features"]["features"][0]["properties"]["source_family"] = "PWD"
        self.assertEqual(measure(case)["source_dependence"], ["PWD"])


class IndependentValidationIntegrationTests(unittest.TestCase):
    def test_point_or_zero_area_reference_rejected(self):
        with self.assertRaises(ValueError):
            compare_geometry(mapping(box(0, 0, 2, 1)), mapping(Point(0, 0)), "EPSG:26918")

    def test_metrics_expose_equal_area_wrong_location(self):
        metrics = compare_geometry(mapping(box(0, 0, 2, 1)), mapping(box(1, 0, 3, 1)), "EPSG:26918")
        self.assertEqual(metrics["absolute_error_percent"], 0)
        self.assertAlmostEqual(metrics["intersection_over_union"], 1 / 3)
        self.assertAlmostEqual(metrics["precision"], 0.5)
        self.assertAlmostEqual(metrics["recall"], 0.5)
        self.assertAlmostEqual(metrics["false_positive_sqft"], SQFT_PER_M2)
        self.assertAlmostEqual(metrics["false_negative_sqft"], SQFT_PER_M2)

    def test_ia_and_drainage_validation_require_distinct_references(self):
        case = make_case(
            [
                feature("p", box(0, 0, 3, 1), "surface", "pavement"),
                feature("A", Point(2.5, 0.5), "inlet"),
            ]
        )
        case["terrain"] = terrain()
        case["references"] = [
            {
                "id": "ia-independent",
                "kind": "ia",
                "independent": True,
                "source_url": "https://example.test/reference/ia",
                "stable_site_verified": True,
                "crs": case["crs"],
                "geometry": mapping(box(0, 0, 3, 1)),
                "holdout": True,
            }
        ]
        result = analyze(case)
        self.assertEqual(result["validation"]["ia"]["status"], "measured")
        self.assertEqual(result["validation"]["drainage"]["status"], "incomplete")
        self.assertTrue(result["validation"]["ia"]["results"][0]["holdout"])
        case["references"].append(
            {
                "id": "drain-independent",
                "kind": "drainage",
                "independent": True,
                "source_url": "https://example.test/reference/drain",
                "stable_site_verified": True,
                "crs": case["crs"],
                "geometry": mapping(box(0, 0, 3, 1)),
                "outlet": "inlet:A",
            }
        )
        result = analyze(case)
        self.assertEqual(result["validation"]["drainage"]["status"], "measured")
        self.assertEqual(
            result["validation"]["drainage"]["results"][0]["metrics"]["intersection_over_union"], 1
        )
        self.assertIsNone(result["validation"]["drainage"]["accuracy_target"])

    def test_nonindependent_or_unstable_reference_does_not_validate(self):
        case = make_case([feature("p", box(0, 0, 3, 1), "surface", "pavement")])
        reference = {
            "id": "circular",
            "kind": "ia",
            "independent": False,
            "source_url": "https://example.test/PWD",
            "stable_site_verified": True,
            "crs": case["crs"],
            "geometry": mapping(box(0, 0, 3, 1)),
        }
        case["references"] = [reference]
        self.assertEqual(analyze(case)["validation"]["ia"]["status"], "incomplete")
        reference.update(independent=True, stable_site_verified=False)
        self.assertEqual(analyze(case)["validation"]["ia"]["status"], "incomplete")


class BenefitSpatialIntegrationTests(unittest.TestCase):
    def make_benefit_case(self):
        case = make_case(
            [
                feature("p", box(0, 0, 100, 100), "surface", "pavement"),
                feature("canopy", box(0, 0, 10, 10), "canopy"),
            ],
            parcel=box(0, 0, 100, 100),
        )
        measured = measure(case)
        case["baseline"] = {
            "ga_sqft": measured["ga_sqft"],
            "ia_sqft": measured["ia_sqft"],
            "existing_ga_credit_sqft": 0,
            "existing_ia_credit_sqft": 0,
            "existing_iar_sqft": 0,
            "npdes_fraction": 0,
            "accounts": [{"allocation": 1, "discount_factor": 1}],
            "bill_date": "2026-11-15",
        }
        case["benefits"] = [
            {
                "id": "canopy-credit",
                "category": "canopy",
                "area_sqft": 100 * SQFT_PER_M2,
                "basis": "modeled",
                "evidence": {
                    "physical_area_confirmed": True,
                    "parcel_allocation_confirmed": True,
                    "account_current": True,
                    "ground_impervious_overlap_confirmed": True,
                },
            }
        ]
        return case

    def test_scalar_credit_cannot_bypass_spatial_accounting(self):
        case = self.make_benefit_case()
        result = analyze(case)
        self.assertEqual(result["screens"][0]["status"], "missing_evidence")
        self.assertIn("physical_area_confirmed", result["screens"][0]["missing"])
        self.assertEqual(result["billing"]["credit_only"]["status"], "blocked")

    def test_corrected_away_surface_cannot_retain_credit_eligibility(self):
        case = self.make_benefit_case()
        case["benefits"][0]["geometry"] = mapping(box(0, 0, 10, 10))
        before = analyze(case)
        self.assertEqual(before["screens"][0]["status"], "screen_pass")
        self.assertEqual(before["billing"]["combined"]["status"], "calculated")
        case["corrections"] = [
            {
                "id": "garden",
                "at": "2026-11-15",
                "reason": "Reviewed receiving garden",
                "action": "add",
                "feature": feature("lawn", box(0, 0, 10, 10), "surface", "pervious"),
            }
        ]
        after = analyze(case)
        self.assertEqual(after["screens"][0]["status"], "requirements_failed")
        self.assertIn("physical_area_confirmed", after["screens"][0]["failed"])
        self.assertEqual(after["billing"]["credit_only"]["status"], "blocked")
        self.assertFalse((after["billing"]["combined"].get("ledger") or {}).get("new_iar_sqft"))

    def test_two_spatial_benefits_cannot_double_count_the_same_region(self):
        case = self.make_benefit_case()
        case["benefits"][0]["geometry"] = mapping(box(0, 0, 10, 10))
        second = deepcopy(case["benefits"][0])
        second["id"] = "overlapping-credit"
        case["benefits"].append(second)
        result = analyze(case)
        self.assertEqual(result["screens"][1]["status"], "requirements_failed")
        self.assertIn("parcel_allocation_confirmed", result["screens"][1]["failed"])
        # The single ledger blocks overlapping claims instead of keeping the first.
        self.assertEqual(result["billing"]["combined"]["status"], "blocked")
        self.assertTrue(
            any(
                "Overlapping physical allocations" in x
                for x in result["billing"]["combined"]["reasons"]
            )
        )


class PersistenceIntegrationTests(unittest.TestCase):
    def test_input_hash_changes_with_source_snapshot_and_corrections(self):
        case = make_case([feature("p", box(0, 0, 3, 1), "surface", "pavement")])
        initial = input_hash(case)
        case["sources"] = [{"url": "https://example.test/ground", "sha256": "aaa"}]
        self.assertNotEqual(input_hash(case), initial)
        prior = input_hash(case)
        case["sources"][0]["sha256"] = "bbb"
        self.assertNotEqual(input_hash(case), prior)
        self.assertEqual(input_hash(case), input_hash(json.loads(canonical(case))))

    def test_save_reopen_preserves_manual_correction_and_report_without_acquisition(self):
        case = make_case([feature("p", box(0, 0, 3, 1), "surface", "pavement")])
        case["sources"] = [
            {
                "url": "https://example.test/ground",
                "sha256": "synthetic-fixture",
                "acquisition_date": "2026-11-01",
                "retrieved_at": "2026-11-15T12:00:00Z",
            }
        ]
        case["corrections"] = [
            {
                "id": "edit",
                "action": "add",
                "reason": "Known garden fixture",
                "at": "2026-11-15T12:01:00Z",
                "feature": feature("g", box(0, 0, 1, 1), "surface", "pervious"),
            }
        ]
        with tempfile.TemporaryDirectory() as temp:
            store = CaseStore(temp)
            first = store.save(case)
            saved = store.load(case["id"])
            second = analyze(saved)
            self.assertEqual(canonical(saved), canonical(case))
            self.assertEqual(first["measurement"], second["measurement"])
            self.assertEqual(first["input_sha256"], second["input_sha256"])
            folder = Path(temp) / case["id"]
            self.assertTrue((folder / "revisions" / (first["input_sha256"] + ".json")).exists())
            self.assertTrue((folder / "report.html").exists())
            self.assertTrue((folder / "measurements.geojson").exists())
            store.save(saved)
            self.assertEqual(len(list((folder / "revisions").glob("*.json"))), 1)


if __name__ == "__main__":
    unittest.main()
