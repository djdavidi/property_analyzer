"""Final code review fixes (probes p1, p3-p7 converted to regressions).

Expected dollars are derived by hand in comments from the PWD tariff effective
2026-09-01 (GA $1.003 and IA $7.048 per 500 sq ft unit, units rounded up, charges
rounded half-up to cents, $2.81 Billing & Collection per account) and the September
2026 Credits and Appeals Manual. Invented fixtures check rules and arithmetic only.
"""

from copy import deepcopy
from datetime import date
import json
from pathlib import Path
import unittest

from shapely.geometry import box, mapping

from drainage_core.engine import ENGINE_VERSION, analyze
from drainage_core.quality import PHYSICAL_INTERPRETATION_VERSION
from stormwater.acquisition import normalize_billing
from stormwater.assessment_policy import RULES, _economics, evaluate_assessment
from stormwater.billing import IAR_SPLIT_BLOCK
from stormwater.billing_reconciliation import reconcile
from stormwater.quality import (
    DERIVED_MONEY_KEYS,
    POLICY_INTERPRETATION_VERSION,
    safe_analysis,
)
from stormwater.rules import load_rule_config
from test_assessment_policy import fixture, record, run
from test_policy_money import mixed_site, with_facts

ROOT = Path(__file__).resolve().parents[1]
EXCERPT = ROOT / "tests" / "fixtures" / "billing" / "pwd-201345-details-excerpt.json"


def public_record(**changes):
    raw = json.loads(EXCERPT.read_text())
    for path, value in changes.items():
        section, key = path.split(".")
        if value is None:
            raw[section].pop(key, None)
        else:
            raw[section][key] = value
    return raw


def all_reasons(economics):
    return [r for v in economics.values() if isinstance(v, dict) for r in v.get("reasons", [])]


class ExistingCreditBaselineTests(unittest.TestCase):
    """Fix 1 (p3): recorded public credits no longer erase the baseline."""

    def test_public_excerpt_still_reproduces_pwd_total(self):
        # GA 190,627 -> 382 units x $1.003 = $383.146 -> $383.15; IA 177,257 -> 355 units x
        # $7.048 = $2,502.04; $2,885.19 x 20% = $577.038 -> $577.04 + $2.81 = $579.85 per
        # account; 5 accounts = $2,899.25, PWD's published total.
        c, g = fixture()
        c["baseline"] = normalize_billing(json.loads(EXCERPT.read_text()))
        e = _economics(c, g, [], date(2026, 11, 16), None)
        self.assertEqual(e["baseline"]["monthly_total"], 2899.25)
        self.assertEqual(e["baseline"]["published_difference"], 0)
        self.assertEqual(e["baseline"]["iar_split"], "recorded")

    def test_recorded_credits_with_unknown_iar_split_bill_and_block_changes_readably(self):
        # p3: GrossCredit = ImpervCredit = 20,000. GA 170,627 -> 342 units -> $343.026 ->
        # $343.03; IA 157,257 -> 315 units -> $2,220.12; $2,563.15 x 20% = $512.63 + $2.81 =
        # $515.44 x 5 = $2,577.20. IAR and IA credit both reduce billed IA (manual 4.3.5
        # steps 1-3), so the unknown split does not change this bill.
        raw = public_record(
            **{
                "Parcel.GrossCredit": 20000,
                "Parcel.ImpervCredit": 20000,
                "ChargeSummary.GrossCreditSqFt": 20000,
                "ChargeSummary.ImpervCreditSqFt": 20000,
            }
        )
        b = normalize_billing(raw)
        self.assertIsNone(b["existing_iar_sqft"])
        c, g = fixture()
        c["baseline"] = b
        e = _economics(c, g, [], date(2026, 11, 16), None)
        base = e["baseline"]
        self.assertEqual(base["monthly_total"], 2577.20)
        self.assertEqual((base["final_ga_sqft"], base["final_ia_sqft"]), (170627, 157257))
        self.assertEqual(base["iar_split"], "unknown")
        self.assertTrue(any("IA-side credit split unknown" in a for a in base["assumptions"]))
        # A change scenario that depends on the split is blocked with a readable reason.
        c["baseline"]["existing_credits_spatially_reconciled"] = True
        c["assessment"]["records"] = [record("permeable_pavement")]
        out = run(c, g)["economics"]
        self.assertEqual(out["baseline"]["monthly_total"], 2577.20)
        self.assertEqual(out["documented"]["status"], "blocked")
        self.assertIn(IAR_SPLIT_BLOCK, out["documented"]["reasons"])
        self.assertFalse(any("value is required" in r for r in all_reasons(out)))
        # The billed-area reconciliation uses the same function and the same areas.
        row = reconcile(b)[0]
        self.assertEqual(
            (row["computed_final_ga_sqft"], row["computed_final_ia_sqft"]),
            (base["final_ga_sqft"], base["final_ia_sqft"]),
        )
        self.assertTrue(any("IA-side credit split unknown" in n for n in row["notes"]))

    def test_missing_npdes_field_uses_charge_summary_or_explains(self):
        # NPDESCredit absent but ChargeSummary.NpdesCreditApplies = false: still $2,899.25.
        c, g = fixture()
        c["baseline"] = normalize_billing(public_record(**{"Parcel.NPDESCredit": None}))
        e = _economics(c, g, [], date(2026, 11, 16), None)
        self.assertEqual(e["baseline"]["monthly_total"], 2899.25)
        # Neither field: unknown is not zero, and the reason is readable.
        c["baseline"] = normalize_billing(
            public_record(**{"Parcel.NPDESCredit": None, "ChargeSummary.NpdesCreditApplies": None})
        )
        self.assertIsNone(c["baseline"]["npdes_fraction"])
        e = _economics(c, g, [], date(2026, 11, 16), None)
        self.assertIsNone(e["baseline"])
        reasons = all_reasons(e)
        self.assertTrue(reasons and all("NPDES credit applies" in r for r in reasons))
        self.assertFalse(any("value is required" in r for r in reasons))

    def test_missing_recorded_area_is_explained_not_a_validator_message(self):
        c, g = fixture()
        c["baseline"]["ia_sqft"] = None
        e = _economics(c, g, [], date(2026, 11, 16), None)
        self.assertIsNone(e["baseline"])
        self.assertIn("recorded impervious area (ImpervArea)", e["documented"]["reasons"][0])


class ReceiverVetoResearchTests(unittest.TestCase):
    """Fix 2 (p4): research scenarios never re-price rejected or vetoed receivers."""

    def research(self, records=()):
        from test_research_drainage import fixture as r_fixture

        c = r_fixture()
        c["baseline"] = {
            "ga_sqft": 6000,
            "ia_sqft": 5001,
            "bill_date": "2026-09-01",
            "property_type": "NonRes",
        }
        c["terrain"]["settings"]["extent_sufficient"] = True
        if records:
            c["assessment"] = {"records": list(records), "attachments": []}
        a = evaluate_assessment(c, analyze(c), as_of="2026-11-15")
        return a["research_drainage_scenarios"]["scenarios"]

    def g1_record(self, decision="rejected", **facts):
        r = record("green_roof", "rej", 0)
        r["geometry"] = r["footprint_geometry"] = mapping(box(3, 3, 4, 4))
        r["managed_area_sqft"] = None
        r["decision"] = decision
        r["facts"]["gsi_id"] = "G1"
        r["facts"].update(facts)
        return r

    def test_unlinked_receiver_is_priced(self):
        rows = self.research()
        self.assertEqual(rows[0]["status"], "calculated")
        self.assertEqual(rows[0]["excluded_receivers"], [])

    def test_rejected_or_known_false_receiver_is_blocked_not_repriced(self):
        # p4 printed "rejected research: calculated 84.6"; the only receiver is G1.
        for r in (self.g1_record(), self.g1_record("confirmed", existing_installation=False)):
            with self.subTest(decision=r["decision"]):
                rows = self.research([r])
                self.assertTrue(rows)
                for s in rows:
                    self.assertEqual(s["status"], "blocked")
                    self.assertIsNone(s["gross_annual_reduction"])
                    self.assertEqual([x["receiver_id"] for x in s["excluded_receivers"]], ["G1"])
                    self.assertTrue(any("Receiver G1 is not re-priced" in x for x in s["reasons"]))


class NpdesComplianceWindowTests(unittest.TestCase):
    """Fix 3 (p5): manual 4.3.4 'preceding twelve months', 4.5.5 'previous 12 months'."""

    def npdes(self, **facts):
        c, g = fixture()
        c["assessment"]["records"] = [with_facts(record("industrial_npdes"), **facts)]
        out = run(c, g)  # as_of 2026-11-15
        return out["categories"][3]["records"][0], out["economics"]["documented"]

    def test_year_old_evidence_needs_update_even_when_next_dmr_is_not_due(self):
        for facts in (
            dict(
                compliance_from="2025-01-01",
                compliance_through="2025-11-16",
                next_dmr_due="2026-12-01",
            ),
            dict(
                compliance_from="2025-11-15",
                compliance_through="2025-11-16",
                next_dmr_due="2027-06-01",
            ),
        ):
            with self.subTest(**facts):
                entry, s = self.npdes(**facts)
                self.assertEqual(entry["status"], "missing_evidence")
                self.assertIn("compliance_through_current", entry["missing"])
                self.assertIn("compliance_through", entry["needs_update"])
                self.assertEqual(entry["failed"], [])
                self.assertIsNone(s["gross_monthly_reduction"])

    def test_six_month_lag_boundary_and_period_order(self):
        # Six months before 2026-11-15 is 2026-05-15 (project screening threshold).
        entry, _ = self.npdes(compliance_through="2026-05-15", next_dmr_due="2027-01-01")
        self.assertEqual(entry["status"], "screen_pass", entry)
        entry, _ = self.npdes(compliance_through="2026-05-14", next_dmr_due="2027-01-01")
        self.assertIn("compliance_through_current", entry["missing"])
        # A DMR fell due after the period ended: needs update (existing rule kept).
        entry, _ = self.npdes(compliance_through="2026-09-30", next_dmr_due="2026-10-28")
        self.assertIn("compliance_through_current", entry["missing"])
        entry, _ = self.npdes(compliance_from="2025-11-15", compliance_through="2025-11-01")
        self.assertIn("compliance_period_order", entry["failed"])


class UndevelopedInferenceTests(unittest.TestCase):
    """Fix 4 (p6): one billable alternative is labelled as an inference."""

    def test_recorded_credit_above_undeveloped_statutory_ia_is_labelled(self):
        # GA 4,000 < 5,000: undeveloped statutory IA 25% = 1,000 < the 1,500 recorded IA
        # credit, so only the developed alternative bills: IA 85% = 3,400 - 1,500 = 1,900 ->
        # 4 units x $7.048 = $28.192 -> $28.19; GA 8 units x $1.003 = $8.024 -> $8.02;
        # $36.21 + $2.81 = $39.02.
        c, g = fixture()
        c["baseline"] = {
            "ga_sqft": 4000,
            "ia_sqft": 3400,
            "bill_date": "2026-09-01",
            "existing_ia_credit_sqft": 1500,
            "existing_ga_credit_sqft": 0,
            "existing_iar_sqft": 0,
        }
        e = _economics(c, g, [], date(2026, 11, 16), None)
        self.assertEqual(e["baseline"]["monthly_total"], 39.02)
        label = e["undeveloped_status"]
        self.assertEqual(
            (label["status"], label["basis"], label["inferred"]),
            ("inferred", "inference", "developed"),
        )
        self.assertIn("undeveloped status infeasible given recorded credits", label["note"])
        self.assertEqual(e["baseline"]["undeveloped_status"]["status"], "inferred")
        self.assertEqual(e["baseline"]["undeveloped_basis"], "inference")
        # With a 500 sq ft credit both alternatives bill and stay unverified alternatives.
        c["baseline"]["existing_ia_credit_sqft"] = 500
        e = _economics(c, g, [], date(2026, 11, 16), None)
        self.assertEqual(e["undeveloped_status"]["status"], "unknown_alternatives")


class RouteLabelRenderingTests(unittest.TestCase):
    """Fix 5 (p7): partial rows render their label in report tables."""

    def test_research_and_catchment_tables_render_partial_labels(self):
        from stormwater.assessment_report import modeled_combined_section, research_section

        html = research_section(
            {
                "scenarios": [
                    {
                        "name": "nominal / known_ground_only",
                        "status": "calculated",
                        "gross_monthly_reduction": 7.05,
                        "gross_annual_reduction": 84.6,
                        "route_state": "partial_upstream_unknown",
                        "partial_label": "partial: true value may be higher",
                        "reasons": [],
                    },
                    {
                        "name": "x",
                        "status": "blocked",
                        "route_state": "partial_upstream_unknown",
                        "partial_label": None,
                        "reasons": [],
                    },
                ]
            }
        )
        self.assertIn("partial: true value may be higher", html)
        self.assertIn("Route state: partial_upstream_unknown", html)
        html = modeled_combined_section(
            {
                "claim": "c",
                "combined": [],
                "catchment_scenarios": [
                    {
                        "name": "nominal",
                        "receiver_id": "G1",
                        "bound": "base",
                        "status": "calculated",
                        "area_sqft": 10,
                        "route_state": "partial_upstream_unknown",
                        "partial_label": "partial: true value may be higher",
                    }
                ],
            }
        )
        self.assertIn("partial: true value may be higher", html)

    def test_research_scenario_carries_route_label(self):
        rows = ReceiverVetoResearchTests().research()
        self.assertEqual(rows[0]["route_state"], "partial_upstream_unknown")
        self.assertEqual(rows[0]["partial_label"], "partial: true value may be higher")


class NpdesRepresentationAndGreenRoofTests(unittest.TestCase):
    """Fixes 6-8 (p1): one area NPDES representation, literal residual, green-roof IAR."""

    def test_recorded_npdes_and_permit_record_give_the_same_total(self):
        # Mixed site GA 10,000 / IA 8,000. NPDES alone (manual 4.3.5.2): 700 GA, 560 IA ->
        # GA 9,300 -> 19 units $19.06; IA 7,440 -> 15 units $105.72; $124.78 + $2.81 =
        # $127.59. The former charge discount gave $132.83 x 0.93 = $123.53 + $2.81 = $126.34.
        c, g, _ = mixed_site()
        c["assessment"]["records"] = [record("industrial_npdes", "np")]
        permit = run(c, g)["economics"]["documented"]["bill"]["monthly_total"]
        c, g, _ = mixed_site()
        c["baseline"]["npdes_fraction"] = 0.07
        recorded = run(c, g)["economics"]["baseline"]["monthly_total"]
        self.assertEqual((permit, recorded), (127.59, 127.59))

    def test_public_npdes_flag_becomes_area_credits_in_ledger_and_reconciliation(self):
        # Excerpt with NPDESCredit = 1 (0.07) and no other credit: GA 190,627 x 0.93 =
        # 177,283.11 -> 355 units -> $356.065 -> $356.07; IA 177,257 x 0.93 = 164,849.01 ->
        # 330 units -> $2,325.84; $2,681.91 x 20% = $536.382 -> $536.38 + $2.81 = $539.19;
        # x 5 = $2,695.95.
        b = normalize_billing(public_record(**{"Parcel.NPDESCredit": 1}))
        c, g = fixture()
        c["baseline"] = b
        e = _economics(c, g, [], date(2026, 11, 16), None)
        self.assertEqual(e["baseline"]["monthly_total"], 2695.95)
        self.assertAlmostEqual(e["baseline"]["final_ga_sqft"], 177283.11, places=6)
        row = reconcile(b)[0]
        self.assertAlmostEqual(row["computed_final_ga_sqft"], 177283.11, places=6)
        self.assertAlmostEqual(row["computed_final_ia_sqft"], 164849.01, places=6)
        # NPDES with recorded aggregate credits: unknown composition, readable block.
        c["baseline"] = normalize_billing(
            public_record(
                **{
                    "Parcel.NPDESCredit": 1,
                    "Parcel.GrossCredit": 800,
                    "Parcel.ImpervCredit": 800,
                    "ChargeSummary.GrossCreditSqFt": 800,
                    "ChargeSummary.ImpervCreditSqFt": 800,
                }
            )
        )
        e = _economics(c, g, [], date(2026, 11, 16), None)
        self.assertIsNone(e["baseline"])
        self.assertIn("already include the NPDES 7% area credit", e["documented"]["reasons"][0])

    def test_green_roof_iar_with_npdes_uses_literal_residual(self):
        # p1. Green roof 3.048 m x 30.48 m = 1,000 sq ft on the roof: IAR 1,000 (manual
        # Table 1 / 4.3.2.1). Alone: IA 7,000 -> 14 units -> $98.672 -> $98.67; GA $20.06;
        # $118.73 + $2.81 = $121.54; reduction from $135.64 = $14.10. With NPDES: 7% x
        # (8,000 - 1,000) = 490 toward IA and GA: GA 9,510 -> 20 units $20.06; IA 6,510 ->
        # 14 units $98.67; also $121.54. GA credit 490 < 700 (NPDES alone, $127.59): note.
        c, g, _ = mixed_site()
        c["assessment"]["records"] = [record("green_roof", "gr", 0)]
        alone = run(c, g)["economics"]["documented"]
        self.assertEqual(
            (alone["bill"]["final_ga_sqft"], alone["bill"]["final_ia_sqft"]), (10000, 7000)
        )
        self.assertEqual(
            (alone["bill"]["monthly_total"], alone["gross_monthly_reduction"]), (121.54, 14.10)
        )
        np_ = record("industrial_npdes", "np", 0)
        c["assessment"]["records"] = [record("green_roof", "gr", 0), np_]
        both = run(c, g)["economics"]["documented"]
        self.assertEqual(both["status"], "calculated", both.get("reasons"))
        self.assertAlmostEqual(both["ledger"]["new_iar_sqft"], 1000)
        self.assertAlmostEqual(both["ledger"]["new_ia_credit_sqft"], 490)
        self.assertAlmostEqual(both["ledger"]["new_ga_credit_sqft"], 490)
        self.assertEqual(
            (both["bill"]["monthly_total"], both["gross_monthly_reduction"]), (121.54, 14.10)
        )
        note = both["manual_rule_discontinuity"]
        self.assertEqual(
            (note["npdes_alone_ga_credit_sqft"], note["scenario_ga_credit_sqft"]), (700, 490)
        )
        self.assertEqual(note["npdes_alone_monthly_total"], 127.59)
        self.assertFalse(note["bill_higher_than_npdes_alone"])


class SingleSourceAndWithholdingTests(unittest.TestCase):
    """Fix 9: rule period from config; outdated results show no stale derived dollars."""

    def test_rule_period_is_read_from_config(self):
        config = load_rule_config()
        self.assertEqual(
            (
                RULES["effective_from"],
                RULES["verified_through"],
                RULES["verified_on"],
                RULES["version"],
            ),
            (
                config["tariff_effective_from"],
                config["tariff_verified_through"],
                config["verified_on"],
                config["existing_site_rule_version"],
            ),
        )

    def test_policy_version_and_derived_money_keys(self):
        self.assertEqual(POLICY_INTERPRETATION_VERSION, 4)
        for key in ("in_window_annual_savings_range", "annual_savings_range", "bill"):
            self.assertIn(key, DERIVED_MONEY_KEYS)

    def test_outdated_result_withholds_ranges_and_scenario_bills(self):
        saved = {
            "engine_version": ENGINE_VERSION,
            "physical_interpretation_version": PHYSICAL_INTERPRETATION_VERSION,
            "policy_interpretation_version": POLICY_INTERPRETATION_VERSION - 1,
            "baseline_observation": {"published_monthly_total": 135.64},
            "runoff_capacity": {
                "headline": {
                    "annual_savings_range": [None, 193.32],
                    "in_window_annual_savings_range": [0.0, 193.32],
                },
                "current_estimate": {
                    "status": "calculated",
                    "annual_savings": 96.6,
                    "bill": {"monthly_total": 127.59, "annualized_total": 1531.08},
                },
            },
        }
        out = safe_analysis(deepcopy(saved))
        headline = out["runoff_capacity"]["headline"]
        self.assertIsNone(headline["annual_savings_range"])
        self.assertIsNone(headline["in_window_annual_savings_range"])
        self.assertIsNone(out["runoff_capacity"]["current_estimate"]["bill"])
        self.assertEqual(out["runoff_capacity"]["current_estimate"]["status"], "outdated")
        self.assertEqual(out["baseline_observation"]["published_monthly_total"], 135.64)


if __name__ == "__main__":
    unittest.main()
