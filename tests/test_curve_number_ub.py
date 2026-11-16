"""B8/A5: UB as an evidence-tagged reviewer choice; worksheet CN to open-space finance.

Known answers come from PWD Table A-1/A-2 (September 2026) and tariff 2026-09-01:
GA charge = ceil(final GA / 500) x $1.003; credit factor = 4% per whole CN below 75.
Synthetic geometry checks the workflow, not real soils or site accuracy.
"""

from copy import deepcopy
from decimal import Decimal, ROUND_CEILING, ROUND_HALF_UP
import unittest

from drainage_core.engine import analyze as analyze_gis
from drainage_core.geometry import SQFT_PER_M2
from stormwater.assessment_policy import evaluate_assessment
from stormwater.curve_number import (
    TABLE,
    SCENARIO_ID,
    components_digest,
    review_soil_group,
    ub_eligibility,
    worksheet,
    review_inputs,
)
from stormwater.rules import load_rule_config
from test_curve_number import fixture

URBAN = [
    {"cokey": "u1", "compname": "Urban land", "comppct_r": 90, "hydgrp": None},
    {"cokey": "u2", "compname": "Udorthents", "comppct_r": 10, "hydgrp": None},
]


def urban_case(cover=None, condition=None):
    """The CN fixture (lawn good 60%, woods good 40%) on an Urban land map unit."""
    c = fixture()
    p = c["assessment"]["soil_snapshot"]["features"][0]["properties"]
    p.update(mukey="1479568", mapunit_name="Urban land", components=deepcopy(URBAN))
    if cover:
        for f in c["features"]["features"]:
            f["properties"].update(cn_cover=cover, cn_condition=condition)
    return c


def run(c):
    return worksheet(c, analyze_gis(c))


def ub(c, reason="Geotechnical report shows disturbed urban fill"):
    return review_soil_group(c, "1479568", "UB", "geotechnical_report", reason)


class UrbanSoilChoiceTests(unittest.TestCase):
    def test_urban_land_stays_unknown_but_shows_a_ub_candidate(self):
        w = run(urban_case("lawn", "fair"))
        self.assertIsNone(w["average_cn"])
        self.assertIsNone(w["credit_factor"])
        for r in w["rows"]:
            self.assertIsNone(r["curve_number"])
            self.assertIsNone(r["soil_group"])
            self.assertTrue(r["ub_choice_available"])
            self.assertEqual(r["ub_candidate_cn"], TABLE["lawn"]["fair"][4])  # 69
            self.assertIn("Soil hydrologic group missing or unsupported", r["missing"])
        # Both rows lawn fair UB 69: candidate CN 69 -> 75 - 69 = 6 steps x 4% = 24%.
        self.assertEqual(w["ub_candidate"]["status"], "candidate_requires_reviewer_ub_choice")
        self.assertAlmostEqual(w["ub_candidate"]["average_cn"], 69)
        self.assertAlmostEqual(w["ub_candidate"]["credit_factor"], 0.24)
        self.assertIn("reviewer", w["ub_candidate"]["claim"])

    def test_ub_column_differs_from_b_for_gravel(self):
        w = run(urban_case("gravel", None))
        self.assertTrue(
            all(r["ub_candidate_cn"] == 89 for r in w["rows"])
        )  # Table A-1 gravel: B 85, UB 89
        self.assertAlmostEqual(w["ub_candidate"]["average_cn"], 89)
        self.assertEqual(w["ub_candidate"]["credit_factor"], 0)

    def test_reviewer_ub_choice_calculates_and_is_recorded(self):
        c = urban_case()
        before = deepcopy(c)
        reviewed = ub(c)
        self.assertEqual(c, before, "Review returns a new case")
        entry = reviewed["assessment"]["soil_group_reviews"]["1479568"]
        self.assertEqual(
            (entry["group"], entry["evidence_basis"], entry["basis"]),
            ("UB", "geotechnical_report", "manual"),
        )
        self.assertEqual(len(reviewed["assessment"]["soil_group_review_history"]), 1)
        w = run(reviewed)
        # lawn good UB 61 (60%) + woods good UB 55 (40%) = 58.6 -> ceil 59 -> 16 steps -> 64%.
        self.assertAlmostEqual(w["average_cn"], 58.6, places=6)
        self.assertAlmostEqual(w["credit_factor"], 0.64)
        self.assertTrue(
            all(
                r["soil_group"] == "UB"
                and r["soil_basis"] == "reviewer choice (UB, evidence-tagged)"
                for r in w["rows"]
            )
        )
        self.assertTrue(all(r["soil_review"]["status"] == "applied" for r in w["rows"]))
        self.assertIsNone(w["ub_candidate"])
        withdrawn = review_soil_group(
            reviewed, "1479568", None, None, "Field test contradicts the report"
        )
        self.assertNotIn("1479568", withdrawn["assessment"]["soil_group_reviews"])
        self.assertEqual(len(withdrawn["assessment"]["soil_group_review_history"]), 2)
        self.assertIsNone(run(withdrawn)["average_cn"])

    def test_ub_requires_evidence_reason_urban_components_and_known_map_unit(self):
        c = urban_case()
        for args in [
            ("1479568", "UB", "hunch", "why"),
            ("1479568", "UB", "site_soil_test", ""),
            ("1479568", "B", "site_soil_test", "why"),
            ("999", "UB", "site_soil_test", "why"),
            ("1479568", None, None, "nothing to withdraw"),
        ]:
            with self.subTest(args=args), self.assertRaises(ValueError):
                review_soil_group(c, *args)
        natural = urban_case()
        p = natural["assessment"]["soil_snapshot"]["features"][0]["properties"]
        p["components"] = [
            {"compname": "Urban land", "comppct_r": 60, "hydgrp": None},
            {"compname": "Galestown", "comppct_r": 40, "hydgrp": None},
        ]
        with self.assertRaisesRegex(ValueError, "not urban soils: Galestown"):
            review_soil_group(natural, "1479568", "UB", "site_soil_test", "why")
        self.assertFalse(any(r["ub_choice_available"] for r in run(natural)["rows"]))
        p["components"] = [{"compname": "Galestown", "comppct_r": 100, "hydgrp": None}]
        with self.assertRaisesRegex(ValueError, "No Urban land/Udorthents component"):
            review_soil_group(natural, "1479568", "UB", "site_soil_test", "why")

    def test_mixed_map_unit_notes_natural_components(self):
        props = {
            "mukey": "7",
            "components": [
                {"compname": "Urban land", "comppct_r": 70, "hydgrp": None},
                {"compname": "Galestown", "comppct_r": 30, "hydgrp": "B"},
            ],
        }
        eligible, note = ub_eligibility(props)
        self.assertTrue(eligible)
        self.assertIn("Galestown (B)", note)
        self.assertIn("whole mapped polygon", note)
        self.assertEqual(
            ub_eligibility({**props, "components": props["components"][:1]})[1],
            "Soil component percentages do not total 100%",
        )

    def test_changed_soil_record_makes_the_review_stale(self):
        reviewed = ub(urban_case())
        p = reviewed["assessment"]["soil_snapshot"]["features"][0]["properties"]
        p["components"][0]["comppct_r"] = 85
        p["components"][1]["comppct_r"] = 15
        w = run(reviewed)
        self.assertIsNone(w["average_cn"])
        self.assertTrue(all(r["soil_review"]["status"] == "stale" for r in w["rows"]))
        self.assertTrue(
            all(
                "Previous soil review is stale after soil record change" in r["missing"]
                for r in w["rows"]
            )
        )
        # Numeric JSON spelling (90 vs 90.0) does not make a review stale.
        props = {
            "mukey": "1",
            "components": [{"compname": "Urban land", "comppct_r": 90.0, "hydgrp": None}],
        }
        self.assertEqual(
            components_digest(props),
            components_digest(
                {
                    "mukey": "1",
                    "components": [{"compname": "Urban land", "comppct_r": 90, "hydgrp": None}],
                }
            ),
        )

    def test_mapped_b_soil_is_never_replaced_by_a_ub_review(self):
        c = fixture()
        with self.assertRaisesRegex(ValueError, "UB is not available"):
            review_soil_group(c, "1", "UB", "site_soil_test", "why")


class FinanceScenarioTests(unittest.TestCase):
    AS_OF = "2026-11-16"

    @staticmethod
    def with_baseline(c):
        c["baseline"] = {
            "ga_sqft": 120000,
            "ia_sqft": 10000,
            "existing_ga_credit_sqft": 0,
            "existing_ia_credit_sqft": 0,
            "existing_iar_sqft": 0,
            "npdes_fraction": 0,
            "property_type": "NonRes",
            "undeveloped": False,
            "accounts": [{"allocation": 1, "discount_factor": 1}],
            "bill_date": "2026-11-16",
        }
        return c

    def scenario(self, c):
        return evaluate_assessment(c, analyze_gis(c), as_of=self.AS_OF)["open_space_curve_number"][
            "finance_scenario"
        ]

    def reviewed(self, c):
        c = review_inputs(c, "lawn", "lawn", "good", "Site visit: maintained turf")
        return review_inputs(c, "woods", "woods", "good", "Site visit: wooded buffer")

    def test_mapped_attributes_alone_require_review_and_price_nothing(self):
        s = self.scenario(self.with_baseline(fixture()))
        self.assertEqual(s["status"], "requires_review")
        self.assertEqual(s["unreviewed_rows"], ["lawn", "woods"])
        self.assertIsNone(s["gross_monthly_reduction"])

    def test_reviewed_inputs_price_a_conditional_scenario_by_hand(self):
        c = self.reviewed(self.with_baseline(fixture()))
        s = self.scenario(c)
        self.assertEqual(s["status"], "conditional")
        self.assertEqual(s["soil_basis"]["mapped_ssurgo"], ["lawn", "woods"])
        self.assertTrue(all(s["assumed_prerequisites"].values()))
        cfg = load_rule_config()
        rate = Decimal(cfg["ga_rate_per_500_sqft"])
        area = Decimal(str(10000 * SQFT_PER_M2))
        factor = Decimal("16") * Decimal(cfg["open_space_cn_step_factor"])
        self.assertAlmostEqual(s["ga_credit_sqft"], float(area * factor), places=3)
        units = lambda sqft: (sqft / Decimal(500)).to_integral_value(rounding=ROUND_CEILING)
        cents = lambda v: v.quantize(Decimal(".01"), rounding=ROUND_HALF_UP)
        # IA charge (20 units) and the $2.81 collection charge are unchanged by a GA-only credit.
        expected = cents(units(Decimal(120000)) * rate) - cents(
            units(Decimal(120000) - area * factor) * rate
        )
        self.assertEqual(expected, Decimal("137.41"))  # (240 - 103) units x $1.003
        self.assertAlmostEqual(s["gross_monthly_reduction"], float(expected))
        self.assertEqual(s["increment"]["status"], "calculated")
        self.assertAlmostEqual(s["increment"]["gross_annual_reduction"], float(expected * 12))
        row = next(x for x in s["ledger"]["allocations"] if x["id"] == SCENARIO_ID)
        self.assertEqual(row["category"], "open_space")
        # Never part of the documented or ordinary modeled ledgers.
        result = evaluate_assessment(c, analyze_gis(c), as_of=self.AS_OF)
        self.assertEqual(result["economics"]["documented"]["status"], "blocked")
        self.assertEqual(result["economics"]["modeled"]["status"], "blocked")

    def test_reviewer_ub_soil_feeds_the_scenario(self):
        c = self.reviewed(self.with_baseline(urban_case()))
        self.assertEqual(self.scenario(c)["status"], "unavailable")
        s = self.scenario(ub(c))
        self.assertEqual(s["status"], "conditional")
        self.assertEqual(s["soil_basis"]["reviewer_ub"], ["lawn", "woods"])
        self.assertAlmostEqual(s["curve_number"], 58.6, places=6)

    def test_manual_cn_fact_stays_authoritative(self):
        c = self.reviewed(self.with_baseline(fixture()))
        c["benefits"] = [
            {
                "id": "manual",
                "category": "open_space",
                "area_sqft": 1,
                "evidence": {"curve_number": 65},
            }
        ]
        s = self.scenario(c)
        self.assertEqual(s["status"], "manual_fact_authoritative")
        self.assertEqual(
            s["manual_cn_facts"], [{"id": "manual", "source": "benefit", "curve_number": 65}]
        )
        self.assertIsNone(s["gross_monthly_reduction"])

    def test_existing_credits_or_period_block_instead_of_assuming(self):
        c = self.reviewed(self.with_baseline(fixture()))
        c["baseline"]["existing_ga_credit_sqft"] = 1000
        s = self.scenario(c)
        self.assertEqual(s["status"], "blocked")
        self.assertIsNone(s["gross_monthly_reduction"])
        self.assertTrue(any("reconcil" in r for r in s["reasons"]))
        out = evaluate_assessment(
            self.reviewed(self.with_baseline(fixture())), analyze_gis(fixture()), as_of="2030-01-01"
        )
        self.assertEqual(
            out["open_space_curve_number"]["finance_scenario"]["status"], "unavailable"
        )

    def test_zero_factor_cn_prices_nothing(self):
        c = self.with_baseline(fixture())
        c["assessment"]["soil_snapshot"]["features"][0]["properties"]["components"][0][
            "hydgrp"
        ] = "D"
        c = self.reviewed(c)
        s = self.scenario(c)
        self.assertEqual(s["status"], "no_credit_at_this_cn")
        self.assertIsNone(s["gross_monthly_reduction"])

    def test_outdated_saved_result_withholds_scenario_money(self):
        from stormwater.quality import safe_analysis

        c = self.reviewed(self.with_baseline(fixture()))
        a = evaluate_assessment(c, analyze_gis(c), as_of=self.AS_OF)
        view = safe_analysis({"policy_interpretation_version": 0, "assessment": a})
        s = view["assessment"]["open_space_curve_number"]["finance_scenario"]
        self.assertIsNone(s["gross_monthly_reduction"])
        self.assertIsNone(s["increment"]["gross_monthly_reduction"])


if __name__ == "__main__":
    unittest.main()
