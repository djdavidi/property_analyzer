"""App-path policy gates added in Phase 4b (invented geometry only; no routing or network).

* D2 / review A2: research-catchment dollars follow the per-catchment route state.
* D3 / review A3: one class-interpretation table for the app and the pilot.
* H16: a surface GSI receiver's own bed is not contributing IA.

Hand arithmetic (GA = IA = 10,000 sq ft, no prior credit; charges rounded half-up):
baseline GA 20 x 1.003 = 20.06, IA 20 x 7.048 = 140.96.
* 5,000 sq ft managed -> 4,000 credits -> billed 6,000 (12 units): GA 12.036 -> 12.04,
  IA 84.576 -> 84.58; 8.02 + 56.38 = 64.40/month = 772.80/yr.
* 4,000 sq ft managed -> 3,200 credits -> billed 6,800 (14 units): GA 14.042 -> 14.04,
  IA 98.672 -> 98.67; 6.02 + 42.29 = 48.31/month = 579.72/yr.
"""

from datetime import date
import unittest

from shapely.geometry import box, mapping, shape

from drainage_core.class_interpretation import SCENARIOS, SYSTEM_SCENARIOS, MEASUREMENT_SCENARIO
from drainage_core.geometry import SQFT_PER_M2, measure
from drainage_core.model_integration import ia_bounds
from stormwater.assessment_policy import research_economics
from test_modeled_assessment_unit import assess, candidate, fake_research, fixture, frozen_gis

DAY = date(2026, 11, 15)
COMPLETE = {"touches_window_edge": False, "touches_nodata": False, "extent_complete": True}


def research_case(bed=False):
    c = fixture()
    c["features"]["features"] = [
        {
            "id": "pave",
            "geometry": c["parcel"],
            "properties": {"layer": "surface", "class": "pavement"},
        }
    ]
    if bed:
        c["research_drainage"] = {
            "features": [
                {
                    "id": "garden",
                    "role": "gsi",
                    "gsi_id": "G1",
                    "geometry": mapping(box(0, 0, 3.048, 30.48)),
                }
            ]
        }
    return c


def research_gis(c, extent=COMPLETE, invariant=True):
    primary = {
        "catchments": [{"gsi_id": "G1", "geometry": c["parcel"], **extent}],
        "invariants": {"terminal_accumulation_equals_routed_cells": invariant},
        "known_ia_union_geometry": mapping(box(0, 0, 15.24, 30.48)),
        "unknown_ground_union_geometry": {"type": "GeometryCollection", "geometries": []},
    }
    return {"measurement": measure(c), "research_drainage": {"primary": primary, "sensitivity": []}}


class ResearchRouteGateTests(unittest.TestCase):
    def nominal(self, c, g):
        return research_economics(c, g, [], DAY, None)["scenarios"][0]

    def test_complete_catchment_prices_normally(self):
        c = research_case()
        s = self.nominal(c, research_gis(c))
        self.assertEqual(s["status"], "calculated")
        self.assertEqual(s["gross_annual_reduction"], 772.80)
        self.assertEqual(s["route_state"], "complete_in_window")
        self.assertIsNone(s["partial_label"])

    def test_partial_catchment_prices_in_window_with_label(self):
        c = research_case()
        s = self.nominal(
            c,
            research_gis(
                c, {"touches_window_edge": True, "touches_nodata": False, "extent_complete": False}
            ),
        )
        self.assertEqual(s["status"], "calculated")
        self.assertEqual(s["gross_annual_reduction"], 772.80)
        self.assertEqual(s["partial_label"], "partial: true value may be higher")

    def test_untestable_extent_or_failed_invariant_blocks(self):
        for extent, invariant in (({}, True), (COMPLETE, False)):
            with self.subTest(extent=extent, invariant=invariant):
                c = research_case()
                s = self.nominal(c, research_gis(c, extent, invariant))
                self.assertEqual(s["status"], "blocked")
                self.assertIsNone(s["gross_annual_reduction"])

    def test_receiver_bed_is_excluded_h16(self):
        c = research_case(bed=True)
        s = self.nominal(c, research_gis(c))
        self.assertAlmostEqual(s["system_bed_ia_excluded_sqft"], 1000)
        self.assertAlmostEqual(s["modeled_unallocated_area_sqft"], 4000)
        self.assertEqual(s["gross_annual_reduction"], 579.72)


class SharedClassTableTests(unittest.TestCase):
    def test_road_is_impervious_only_in_the_labelled_default(self):
        self.assertEqual(SCENARIOS[MEASUREMENT_SCENARIO]["impervious"], ("roof",))
        self.assertIn("road", SCENARIOS["road_impervious"]["impervious"])
        self.assertNotIn("developed_space", SCENARIOS["road_impervious"]["impervious"])
        self.assertIn("grass_shrub", SCENARIOS["road_impervious_soft_pervious"]["pervious"])
        self.assertEqual(dict(SYSTEM_SCENARIOS)["base"], "road_impervious")

    def test_app_bounds_offer_the_same_labelled_road_scenario_as_the_pilot(self):
        c = fixture()
        c["features"]["features"] = [
            candidate("road", box(0, 0, 15.24, 30.48)),
            candidate("grass_shrub", box(15.24, 0, 30.48, 30.48)),
        ]
        g = frozen_gis(c, fake_research(c))
        bounds = ia_bounds(c, g["modeled_integration"], shape(c["parcel"]))
        self.assertAlmostEqual(bounds["observed_ia_only"].area * SQFT_PER_M2, 0)
        self.assertAlmostEqual(bounds["road_impervious"].area * SQFT_PER_M2, 5000)
        self.assertEqual(list(bounds)[:3], ["lower", "observed_ia_only", "upper"])
        rows = assess(c, g)["modeled_integration"]["catchment_scenarios"]
        road = next(r for r in rows if r["receiver_id"] == "G1" and r["bound"] == "road_impervious")
        self.assertIn(SCENARIOS["road_impervious"]["label"], road["assumptions"])


if __name__ == "__main__":
    unittest.main()
