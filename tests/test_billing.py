import unittest
from stormwater.billing import monthly_bill, calculate_scenarios, rounded_area
from test_rules import COMMON, MANAGED

BASE = {
    "ga_sqft": 10000,
    "ia_sqft": 8000,
    "existing_ga_credit_sqft": 0,
    "existing_ia_credit_sqft": 0,
    "existing_iar_sqft": 0,
    "npdes_fraction": 0,
    "accounts": [{"allocation": 1, "discount_factor": 1}],
    "bill_date": "2026-11-15",
}
MEASURED = {"ga_sqft": 10000, "ia_sqft": 7000, "complete": True}


def benefit(area=1000, category="management", id="a"):
    return {
        "id": id,
        "category": category,
        "area_sqft": area,
        "evidence": MANAGED,
        "basis": "documented",
        "ledger_ids": [id],
    }


class BillingTests(unittest.TestCase):
    def test_independent_known_bill(self):
        # 20*1.003 =20.06 GA; 16*7.048=112.768 ->112.77 IA; +2.81.
        b = monthly_bill(10000, 8000)
        self.assertEqual(b["monthly_total"], 135.64)

    def test_whitaker_public_account_reconciles(self):
        b = monthly_bill(255924, 185889)
        self.assertEqual(b["billed_ga_sqft"], 256000)
        self.assertEqual(b["billed_ia_sqft"], 186000)
        self.assertEqual(b["monthly_total"], 3138.21)

    def test_ceiling_exact_and_above_increment(self):
        self.assertEqual(rounded_area(500), 500)
        self.assertEqual(rounded_area("500.0001"), 1000)
        self.assertEqual(rounded_area(0), 0)

    def test_statutory_small_parcel_ia(self):
        b = monthly_bill(4000, 0, undeveloped=False)
        self.assertEqual(b["statutory_ia_sqft"], 3400)
        self.assertEqual(monthly_bill(4000, 3999, undeveloped=True)["statutory_ia_sqft"], 1000)
        # Unknown status is never silently "developed" (decision D6).
        with self.assertRaisesRegex(ValueError, "Undeveloped status is unknown"):
            monthly_bill(4000, 0)

    def test_minimum_and_fee(self):
        self.assertEqual(monthly_bill(100, 0, undeveloped=False)["monthly_total"], 23.70)
        self.assertEqual(
            monthly_bill(10000, 8000, ga_credit_sqft=10000, ia_credit_sqft=8000)["monthly_total"],
            23.70,
        )

    def test_allocation_rounding_and_discount(self):
        a = [
            {"allocation": 0.5, "discount_factor": 1},
            {"allocation": 0.5, "discount_factor": 0.75, "discount_verified": True},
        ]
        b = monthly_bill(10000, 8000, accounts=a)
        self.assertEqual(b["accounts"][0]["total"], 69.23)
        self.assertEqual(b["accounts"][1]["total"], 51.92)
        self.assertEqual(b["monthly_total"], 121.15)

    def test_invalid_allocation_and_unknown_discount(self):
        with self.assertRaises(ValueError):
            monthly_bill(10000, 8000, [{"allocation": 0.9}])
        with self.assertRaises(ValueError):
            monthly_bill(10000, 8000, [{"allocation": 1, "discount_factor": 0.75}])

    def test_tariff_period_enforced(self):
        with self.assertRaises(ValueError):
            monthly_bill(10000, 8000, bill_date="2025-01-01")

    def test_combined_is_baseline_minus_final(self):
        s = calculate_scenarios(BASE, MEASURED, [benefit()])
        b = s["baseline"]["monthly_total"]
        for key in ["appeal_only", "credit_only", "combined"]:
            self.assertAlmostEqual(s[key]["monthly_savings"], round(b - s[key]["monthly_total"], 2))
            self.assertAlmostEqual(s[key]["annual_savings"], s[key]["monthly_savings"] * 12)
        self.assertEqual(s["combined"]["ledger"]["new_ga_credit_sqft"], 800)

    def test_corrected_away_area_cannot_also_earn_benefit(self):
        s = calculate_scenarios(BASE, MEASURED, [benefit(7500)])
        self.assertEqual(s["credit_only"]["status"], "calculated")
        self.assertEqual(s["combined"]["status"], "blocked")

    def test_existing_benefits_preserved_and_overlap_blocks(self):
        b = {**BASE, "existing_ga_credit_sqft": 800, "existing_ia_credit_sqft": 800}
        s = calculate_scenarios(b, MEASURED, [benefit()])
        self.assertEqual(s["baseline"]["final_ia_sqft"], 7200)
        self.assertEqual(s["combined"]["status"], "blocked")
        b["existing_credits_spatially_reconciled"] = True
        x = benefit()
        x["existing_overlap_reconciled"] = True
        s = calculate_scenarios(b, MEASURED, [x])
        self.assertEqual(s["combined"]["final_ia_sqft"], 5400)

    def test_duplicate_benefit_area_blocks(self):
        s = calculate_scenarios(BASE, MEASURED, [benefit(), benefit()])
        self.assertEqual(s["credit_only"]["status"], "blocked")

    def test_documented_and_modeled_not_conflated(self):
        x = benefit()
        x["basis"] = "modeled"
        s = calculate_scenarios(BASE, MEASURED, [x])
        self.assertEqual(s["credit_only"]["basis"], "modeled")
        self.assertEqual(s["documented_credit_only"]["status"], "blocked")

    def test_missing_surfaces_do_not_claim_savings(self):
        s = calculate_scenarios(
            BASE, {"ia_sqft": 7000, "ga_sqft": 10000, "complete": False}, [benefit()]
        )
        self.assertIsNone(s["combined"]["annual_savings"])

    def test_existing_npdes_preserved_new_combo_unresolved(self):
        b = {**BASE, "npdes_fraction": 0.07}
        s = calculate_scenarios(b, MEASURED, [benefit()])
        self.assertEqual(s["baseline"]["npdes_fraction"], 0.07)
        self.assertEqual(s["credit_only"]["status"], "blocked")

    def test_uncertified_or_missing_credit_evidence_blocks(self):
        x = benefit()
        x["evidence"] = {}
        s = calculate_scenarios(BASE, MEASURED, [x])
        self.assertIsNone(s["credit_only"]["annual_savings"])

    def test_string_discount_cannot_bypass_verification(self):
        with self.assertRaises(ValueError):
            monthly_bill(10000, 8000, [{"allocation": 1, "discount_factor": "0.75"}])

    def test_empty_benefits_do_not_change_multiaccount_minimum(self):
        b = {
            **BASE,
            "ga_sqft": 100,
            "ia_sqft": 0,
            "accounts": [{"allocation": 0.5}, {"allocation": 0.5}],
        }
        s = calculate_scenarios(b, {"ga_sqft": 100, "ia_sqft": 0, "complete": True}, [])
        self.assertEqual(s["credit_only"]["monthly_savings"], 0)

    def test_existing_credit_baseline_uses_same_minimum_policy(self):
        b = {
            **BASE,
            "existing_ga_credit_sqft": 10000,
            "existing_ia_credit_sqft": 8000,
            "accounts": [{"allocation": 0.5}, {"allocation": 0.5}],
        }
        s = calculate_scenarios(b, {}, [])
        self.assertEqual(s["baseline"]["monthly_total"], 47.4)

    def test_actual_bill_difference_retained(self):
        s = calculate_scenarios({**BASE, "actual_bill_total": 130}, {}, [])
        self.assertEqual(s["baseline"]["actual_bill_difference"], 5.64)

    def test_credit_minimum_parcel_area(self):
        s = calculate_scenarios({**BASE, "ga_sqft": 400, "ia_sqft": 300}, {}, [benefit(200)])
        self.assertEqual(s["credit_only"]["status"], "blocked")

    def test_npdes_evidence_cannot_create_unverified_factor(self):
        x = benefit()
        x["evidence"] = {**MANAGED, "npdes": True}
        s = calculate_scenarios(BASE, MEASURED, [x])
        self.assertEqual(s["credit_only"]["status"], "blocked")

    def test_invalid_area(self):
        for args in [(100, 101), (100, float("nan")), (-10, 0)]:
            with self.assertRaises(ValueError):
                monthly_bill(*args)


if __name__ == "__main__":
    unittest.main()
