"""Billing arithmetic and the one live savings ledger.

``billing.calculate_scenarios`` had no production caller and was deleted (final review
fix 9); its scenario checks now exercise ``assessment_policy._economics``, the ledger
every app, report and adapter dollar comes from. Expected dollars are derived by hand
from the tariff effective 2026-09-01: GA $1.003 and IA $7.048 per 500 sq ft unit (units
rounded up), each money step rounded as PWD rounds it (binary double x 100, half to even;
``billing.pwd_cents``, final LIVE-SAVINGS fix 10), Billing & Collection $2.81 per account.
"""

from copy import deepcopy
from datetime import date
import unittest

import json
from pathlib import Path

from shapely.geometry import box, mapping

import stormwater.billing as billing
from drainage_core.engine import new_case
from stormwater.assessment_policy import _economics
from stormwater.billing import monthly_bill, rounded_area
from test_rules import MANAGED

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


def benefit(area=1000, category="management", id="a", geometry=None):
    return {
        "id": id,
        "category": category,
        "area_sqft": area,
        "evidence": dict(MANAGED),
        "basis": "documented",
        "geometry": geometry,
    }


def ledger(baseline, benefits=(), measured=None, as_of="2026-11-15", tariff=None):
    """The live assessment ledger for a bare baseline.

    Benefits are hypothetical alternatives priced exactly as
    ``system_pricing.price_benefit`` prices them; ``measured`` is an optional
    physical measurement (``complete`` must be true to be used).
    """
    case = new_case("Invented ledger check", crs="EPSG:26918")
    case["baseline"] = deepcopy(baseline)
    case["assessment"] = {"records": [], "attachments": []}
    gis = {"measurement": {"complete": False, "geometries": {}, **(measured or {})}}
    return _economics(
        case, gis, [], date.fromisoformat(as_of), tariff, hypothetical=deepcopy(list(benefits))
    )


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

    def test_string_discount_cannot_bypass_verification(self):
        with self.assertRaises(ValueError):
            monthly_bill(10000, 8000, [{"allocation": 1, "discount_factor": "0.75"}])

    def test_invalid_area(self):
        for args in [(100, 101), (100, float("nan")), (-10, 0)]:
            with self.assertRaises(ValueError):
                monthly_bill(*args)

    def test_one_npdes_representation_and_no_dead_scenario_engine(self):
        # Fix 8/9: no charge-percentage NPDES discount and no second scenario engine.
        with self.assertRaises(TypeError):
            monthly_bill(10000, 8000, npdes_fraction=0.07)
        self.assertNotIn("npdes_fraction", monthly_bill(10000, 8000))
        self.assertFalse(hasattr(billing, "calculate_scenarios"))


class LedgerScenarioTests(unittest.TestCase):
    """Former calculate_scenarios checks, now against the live ledger."""

    def test_combined_is_baseline_minus_final(self):
        # Baseline $135.64 (above). 1,000 sq ft managed -> 80% = 800 GA and IA credit.
        # Modeled: GA 9,200 -> 19 units $19.06; IA 7,200 -> 15 units $105.72; $127.59.
        # Measurement only: IA 7,000 -> 14 units $98.672 -> $98.67; GA $20.06; $121.54.
        # Combined: IA 6,200 -> 13 units $91.624 -> $91.62; GA $19.06; $113.49.
        s = ledger(BASE, [benefit()], MEASURED)
        b = s["baseline"]["monthly_total"]
        self.assertEqual(b, 135.64)
        for key, total in (
            ("modeled", 127.59),
            ("measurement_only", 121.54),
            ("modeled_combined", 113.49),
        ):
            self.assertEqual(s[key]["bill"]["monthly_total"], total, key)
            self.assertAlmostEqual(s[key]["gross_monthly_reduction"], round(b - total, 2))
            self.assertAlmostEqual(
                s[key]["gross_annual_reduction"], s[key]["gross_monthly_reduction"] * 12
            )
        self.assertEqual(s["modeled_combined"]["ledger"]["new_ga_credit_sqft"], 800)

    def test_corrected_away_area_cannot_also_earn_benefit(self):
        s = ledger(BASE, [benefit(7500)], MEASURED)
        self.assertEqual(s["modeled"]["status"], "calculated")
        self.assertEqual(s["modeled_combined"]["status"], "blocked")
        self.assertIn(
            "Allocations exceed available physical impervious area",
            s["modeled_combined"]["reasons"],
        )

    def test_existing_benefits_preserved_and_unitemized_overlap_blocks(self):
        b = {**BASE, "existing_ga_credit_sqft": 800, "existing_ia_credit_sqft": 800}
        s = ledger(b, [benefit()], MEASURED)
        self.assertEqual(s["baseline"]["final_ia_sqft"], 7200)
        self.assertEqual(s["modeled_combined"]["status"], "blocked")
        # Booleans alone are not enough: the ledger needs an itemized approved allocation.
        b["existing_credits_spatially_reconciled"] = True
        x = benefit()
        x["existing_overlap_reconciled"] = True
        s = ledger(b, [x], MEASURED)
        self.assertEqual(s["modeled_combined"]["status"], "blocked")
        self.assertIn(
            "Detailed existing credit allocation ledger missing", s["modeled_combined"]["reasons"]
        )

    def test_duplicate_benefit_area_blocks(self):
        same = mapping(box(0, 0, 3.048, 30.48))
        s = ledger(BASE, [benefit(geometry=same), benefit(id="b", geometry=same)])
        self.assertEqual(s["modeled"]["status"], "blocked")
        self.assertTrue(
            any("Overlapping physical allocations" in r for r in s["modeled"]["reasons"])
        )

    def test_documented_and_modeled_not_conflated(self):
        x = benefit()
        x["basis"] = "modeled"
        s = ledger(BASE, [x], MEASURED)
        self.assertEqual(s["modeled"]["status"], "calculated")
        self.assertEqual(s["documented"]["status"], "blocked")

    def test_missing_surfaces_do_not_claim_savings(self):
        s = ledger(BASE, [benefit()], {"ia_sqft": 7000, "ga_sqft": 10000, "complete": False})
        self.assertIsNone(s["modeled_combined"]["gross_annual_reduction"])

    def test_recorded_npdes_is_area_credit_and_combines_with_new_credit(self):
        # Fix 8 (manual 4.3.5.2, area credits). Recorded NPDES, no other credit: 7% x
        # 10,000 = 700 GA, 7% x 8,000 = 560 IA. Final GA 9,300 -> 19 units $19.06; IA
        # 7,440 -> 15 units $105.72; $124.78 + $2.81 = $127.59 (a charge discount gave
        # $126.34). Plus 1,000 managed at 87% = 870; residual 7% x (8,000 - 1,000) = 490 to
        # IA and GA: 1,360 each. GA 8,640 -> 18 units $18.054 -> $18.05; IA 6,640 -> 14
        # units $98.672 -> $98.67; $116.72 + $2.81 = $119.53; reduction $8.06.
        s = ledger({**BASE, "npdes_fraction": 0.07}, [benefit()])
        self.assertEqual(s["baseline"]["monthly_total"], 127.59)
        self.assertEqual(
            (s["baseline"]["final_ga_sqft"], s["baseline"]["final_ia_sqft"]), (9300, 7440)
        )
        m = s["modeled"]
        self.assertEqual(m["status"], "calculated", m.get("reasons"))
        self.assertAlmostEqual(m["ledger"]["new_ia_credit_sqft"], 1360)
        self.assertAlmostEqual(m["ledger"]["new_ga_credit_sqft"], 1360)
        self.assertEqual((m["bill"]["monthly_total"], m["gross_monthly_reduction"]), (119.53, 8.06))
        self.assertNotIn("manual_rule_discontinuity", m)

    def test_uncertified_or_missing_credit_evidence_blocks(self):
        x = benefit()
        x["evidence"] = {}
        s = ledger(BASE, [x], MEASURED)
        self.assertIsNone(s["modeled"]["gross_annual_reduction"])

    def test_empty_benefits_do_not_change_multiaccount_minimum(self):
        # GA 100 -> $1.00; statutory IA 85 -> $7.05; parcel $8.05; halves $4.03 (half-up)
        # are below $20.89, so each account pays $23.70: $47.40 before and after.
        b = {
            **BASE,
            "ga_sqft": 100,
            "ia_sqft": 0,
            "undeveloped": False,
            "accounts": [{"allocation": 0.5}, {"allocation": 0.5}],
        }
        s = ledger(b, [], {"ga_sqft": 100, "ia_sqft": 0, "complete": True})
        self.assertEqual(s["baseline"]["monthly_total"], 47.40)
        self.assertEqual(s["measurement_only"]["gross_monthly_reduction"], 0)

    def test_existing_credit_baseline_uses_same_minimum_policy(self):
        b = {
            **BASE,
            "existing_ga_credit_sqft": 10000,
            "existing_ia_credit_sqft": 8000,
            "accounts": [{"allocation": 0.5}, {"allocation": 0.5}],
        }
        self.assertEqual(ledger(b)["baseline"]["monthly_total"], 47.4)

    def test_actual_bill_difference_retained(self):
        s = ledger({**BASE, "actual_bill_total": 130})
        self.assertEqual(s["baseline"]["actual_bill_difference"], 5.64)

    def test_credit_minimum_parcel_area(self):
        b = {**BASE, "ga_sqft": 400, "ia_sqft": 300, "undeveloped": False}
        s = ledger(b, [benefit(200)])
        self.assertEqual(s["modeled"]["status"], "blocked")
        self.assertIn(
            "Minimum parcel gross area for credit is 500 square feet", s["modeled"]["reasons"]
        )

    def test_npdes_evidence_cannot_create_unverified_factor(self):
        # Evidence claiming NPDES does not make 87%: only a recorded or screened permit does.
        x = benefit()
        x["evidence"] = {**MANAGED, "npdes": True}
        s = ledger(BASE, [x])
        self.assertEqual(s["modeled"]["ledger"]["new_ia_credit_sqft"], 800)


SNAPSHOT_FIXTURE = (
    Path(__file__).resolve().parent
    / "fixtures"
    / "billing"
    / "pwd-snapshot-rounding-minimum-2026-11-16.json"
)


class PublishedSnapshotReconciliationTests(unittest.TestCase):
    """Fixes 9-10: frozen excerpts of six real PWD parcels (2026-11-16 snapshot)."""

    def setUp(self):
        from stormwater.acquisition import normalize_billing
        from stormwater.billing import bill_terms, default_tariff, recorded_credits

        self.rows = {}
        for raw in json.loads(SNAPSHOT_FIXTURE.read_text())["parcels"]:
            b = normalize_billing(raw)
            common, _ = bill_terms(b, default_tariff())
            terms = recorded_credits(b, b["ga_sqft"], b["ia_sqft"], b.get("undeveloped"))
            bill = monthly_bill(
                b["ga_sqft"],
                b["ia_sqft"],
                ga_credit_sqft=terms["ga_credit_sqft"],
                ia_credit_sqft=terms["ia_credit_sqft"],
                iar_sqft=terms["iar_sqft"],
                **common,
            )
            self.rows[raw["Parcel"]["ParcelID"]] = (raw, b, bill)

    def test_every_fixture_total_matches_the_published_total(self):
        for pid, (_, b, bill) in self.rows.items():
            with self.subTest(parcel=pid):
                self.assertAlmostEqual(bill["monthly_total"], b["published_monthly_total"], places=6)

    def test_ga_charge_tie_rounds_half_even_in_binary(self):
        # 3060 S 61st St: GA 657,500 -> 1,315 units x $1.003 = $1,318.945 (x 100 is the exact
        # binary tie 131,894.5 -> even) -> $1,318.94, as PWD publishes; half-up gave $1,318.95.
        # IA 554,500 -> 1,109 x $7.048 = $7,816.232 -> $7,816.23; SWMS $9,135.17 + $2.81 = $9,137.98.
        raw, _, bill = self.rows[538963]
        row = raw["ChargeSummary"]["ParcelAccounts"][0]["YearlyAccountCharges"][0]
        self.assertEqual(bill["ga_charge"], row["GrossCharge"])
        self.assertEqual((bill["ga_charge"], bill["monthly_total"]), (1318.94, 9137.98))

    def test_account_share_rounds_like_pwd(self):
        # 3000 Walnut St: $1,922.75 + $7,470.88 = $9,393.63; half $4,696.815 is 4,696.81499...
        # in binary -> $4,696.81 per account (+ $2.81) x 2 = $9,399.24, as published.
        _, _, bill = self.rows[328676]
        self.assertEqual([a["swms"] for a in bill["accounts"]], [4696.81, 4696.81])
        self.assertEqual(bill["monthly_total"], 9399.24)

    def test_published_minimum_is_the_parcel_reading(self):
        # 9414 Meadowbrook Ave: parcel SWMS $71.35 >= $20.89; each quarter $17.8375 -> $17.84
        # is billed below the minimum: 4 x ($17.84 + $2.81) = $82.60 (per-account reading: $94.80).
        _, _, bill = self.rows[206992]
        self.assertFalse(bill["minimum_applied"])
        self.assertEqual([a["swms"] for a in bill["accounts"]], [17.84] * 4)
        self.assertEqual(bill["monthly_total"], 82.60)
        # 11350 Norcom Rd: parcel SWMS $0.00 < $20.89 -> $20.89 + $2.81 = $23.70.
        _, _, bill = self.rows[537400]
        self.assertTrue(bill["minimum_applied"])
        self.assertEqual(bill["monthly_total"], 23.70)

    def test_zero_allocation_accounts_pay_nothing(self):
        # 84 S Pier: one account at 100% ($4,910.08 + $2.81) and three at 0% ($0.00 each).
        _, _, bill = self.rows[133710]
        self.assertEqual([a["total"] for a in bill["accounts"]], [4912.89, 0.0, 0.0, 0.0])


if __name__ == "__main__":
    unittest.main()
