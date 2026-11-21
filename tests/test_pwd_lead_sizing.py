"""Offline known-answer checks for scripts/pwd_lead_sizing.py."""

import importlib.util
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "pwd_lead_sizing", ROOT / "scripts" / "pwd_lead_sizing.py"
)
sizing = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(sizing)


class LeadSizingTests(unittest.TestCase):
    parcel = {
        "billing_gross_area_sqft": "86925",
        "billing_impervious_area_sqft": "26675",
        "monthly_charge": "557.92",
    }

    def test_basin_caps_at_billed_ia_and_prices_management_credit(self):
        # 4,000 sq ft basin: low storage 4,000 x 0.8 = 3,200 cu ft / 0.125 = 25,600 sq ft;
        # high far exceeds IA so it caps at 26,675.
        out = sizing.size_parcel(
            self.parcel, [{"gsi_system_type": "Subsurface Basin", "footprint_sqft": "4000"}]
        )
        self.assertEqual(out["est_managed_ia_low_sqft"], 25600)
        self.assertEqual(out["est_managed_ia_high_sqft"], 26675)
        # High: credit 0.8 x 26,675 = 21,340 off GA and IA.
        # GA 174 -> ceil(65,585/500)=132 units: 42 x 1.003 = 42.126
        # IA  54 -> ceil(5,335/500)=11 units:  43 x 7.048 = 303.064; monthly 345.19 -> 4,142.28/yr
        self.assertAlmostEqual(out["est_credit_high_annual"], 4142.28, places=2)

    def test_green_roof_is_iar_without_ga_credit(self):
        out = sizing.size_parcel(
            self.parcel, [{"gsi_system_type": "Green Roof", "footprint_sqft": "1000"}]
        )
        self.assertEqual(out["est_green_roof_iar_sqft"], 1000)
        # IA 54 -> ceil(25,675/500)=52 units: 2 x 7.048 x 12 = 169.15; GA unchanged
        self.assertAlmostEqual(out["est_credit_low_annual"], 169.15, places=2)
        self.assertEqual(out["est_credit_low_annual"], out["est_credit_high_annual"])

    def test_flat_residential_charge_gets_no_credit_estimate(self):
        parcel = {**self.parcel, "monthly_charge": "23.05"}
        out = sizing.size_parcel(
            parcel, [{"gsi_system_type": "Rain Garden", "footprint_sqft": "500"}]
        )
        self.assertEqual(out["est_credit_mid_annual"], "")
        self.assertIn("flat residential", out["sizing_basis"])

    def test_system_kinds(self):
        self.assertEqual(sizing.system_kind("Porous Surface"), "porous")
        self.assertEqual(sizing.system_kind("Pending System Type"), "unknown")
        self.assertEqual(sizing.system_kind("Tree Trench"), "bio")


if __name__ == "__main__":
    unittest.main()
