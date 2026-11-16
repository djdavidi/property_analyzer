import unittest
from stormwater.rules import screen, open_space_factor

COMMON = {
    "physical_area_confirmed": True,
    "parcel_allocation_confirmed": True,
    "account_current": True,
}
ROOF = {
    **COMMON,
    "receiving_area_pervious": True,
    "receiving_dimensions_sufficient": True,
    "routing_confirmed": True,
    "receiving_slope_percent": 3,
    "soil_group": "B",
    "area_per_downspout_sqft": 500,
    "ground_impervious_clearance_ft": 15,
    "continuous_flow_path": True,
    "no_dcia_in_flow_path": True,
    "unique_flow_path_per_downspout": True,
}
PAVEMENT = {
    **COMMON,
    "receiving_area_pervious": True,
    "receiving_dimensions_sufficient": True,
    "routing_confirmed": True,
    "receiving_slope_percent": 2,
    "soil_group": "C",
    "impervious_flow_path_ft": 75,
    "contributing_slope_percent": 5,
    "vegetated_receiving_area": True,
    "sheet_flow": True,
}
MANAGED = {
    **COMMON,
    "routing_confirmed": True,
    "approved_record_drawings": True,
    "current_condition_confirmed": True,
    "maintenance_documented": True,
    "professional_reviewed": True,
    "treatment_depth_inches": 1.5,
}


class RuleTests(unittest.TestCase):
    def test_canopy_halves_ground_overlap_without_changing_physical_area(self):
        s = screen("canopy", 200, {**COMMON, "ground_impervious_overlap_confirmed": True})
        self.assertEqual(s["iar_sqft"], 100)
        self.assertEqual(s["area_sqft"], 200)
        self.assertEqual(s["ia_credit_sqft"], 0)

    def test_roof_or_lawn_canopy_not_eligible(self):
        s = screen("canopy", 200, {**COMMON, "ground_impervious_overlap_confirmed": False})
        self.assertEqual(s["status"], "requirements_failed")
        self.assertIsNone(s["iar_sqft"])

    def test_missing_not_zero(self):
        s = screen("roof", 400, {})
        self.assertIn("soil_group", s["missing"])
        self.assertIsNone(s["iar_sqft"])

    def test_roof_boundaries(self):
        self.assertEqual(screen("roof", 500, ROOF)["status"], "screen_pass")
        for field, value in [
            ("area_per_downspout_sqft", 501),
            ("ground_impervious_clearance_ft", 14.9),
            ("receiving_slope_percent", 0),
            ("soil_group", "D"),
        ]:
            self.assertEqual(
                screen("roof", 500, {**ROOF, field: value})["status"], "requirements_failed"
            )

    def test_pavement_sheet_and_point_constraints(self):
        self.assertEqual(screen("pavement", 999, PAVEMENT)["status"], "screen_pass")
        self.assertEqual(
            screen("pavement", 999, {**PAVEMENT, "sheet_flow": False})["status"], "missing_evidence"
        )
        p = {
            **PAVEMENT,
            "sheet_flow": False,
            "area_per_discharge_point_sqft": 1000,
            "erosion_control": True,
        }
        self.assertEqual(screen("pavement", 1000, p)["status"], "screen_pass")
        self.assertEqual(
            screen("pavement", 1001, {**p, "area_per_discharge_point_sqft": 1001})["status"],
            "requirements_failed",
        )

    def test_open_space_is_not_green_pixel_count(self):
        self.assertIsNone(
            screen("open_space", 500, {**COMMON, "curve_number": 60})["ga_credit_sqft"]
        )
        self.assertEqual(open_space_factor(55), 0.8)
        self.assertEqual(open_space_factor(75), 0)
        self.assertAlmostEqual(open_space_factor(74, True), 0.0435)
        self.assertAlmostEqual(open_space_factor(60.1), 0.56)

    def test_management_compliant_letter_does_not_imply_depth(self):
        e = {**MANAGED}
        del e["treatment_depth_inches"]
        self.assertIsNone(screen("managed", 1000, e)["ia_credit_sqft"])
        self.assertEqual(screen("managed", 1000, MANAGED)["ia_credit_sqft"], 800)
        self.assertEqual(
            screen("managed", 1000, {**MANAGED, "treatment_depth_inches": 1})["status"],
            "requirements_failed",
        )
        self.assertEqual(
            screen(
                "managed",
                1000,
                {**MANAGED, "treatment_depth_inches": 1, "old_standard_renewal_verified": True},
            )["status"],
            "screen_pass",
        )

    def test_invalid_numeric_inputs(self):
        for value in [float("nan"), float("inf"), -1, True]:
            with self.assertRaises(ValueError):
                screen("canopy", value, {})


if __name__ == "__main__":
    unittest.main()
