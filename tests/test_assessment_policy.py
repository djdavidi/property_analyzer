"""Known area/charge examples; invented evidence is never empirical validation."""

from copy import deepcopy
import unittest
from unittest.mock import patch
from shapely.geometry import box, mapping
from drainage_core.engine import new_case, analyze, canonical
from stormwater.assessment_policy import evaluate_assessment, COMMON, SMP, PAVEMENT, DIRECT, NPDES
from stormwater.billing import monthly_bill


def fixture():
    c = new_case("Invented existing systems", crs="EPSG:26918")
    c["parcel"] = mapping(box(0, 0, 30.48, 30.48))
    c["features"]["features"] = [
        {
            "type": "Feature",
            "id": "roof",
            "geometry": c["parcel"],
            "properties": {"layer": "surface", "class": "roof"},
        }
    ]
    c["baseline"] = {
        "ga_sqft": 10000,
        "ia_sqft": 10000,
        "bill_date": "2026-11-15",
        "actual_bill_verified": True,
    }
    c["assessment"] = {"records": [], "attachments": []}
    return c, analyze(c)


def record(category="green_roof", identifier="r", start=0):
    geom = mapping(box(start, 0, start + 3.048, 30.48))
    facts = {k: True for k in (*COMMON, *SMP, *PAVEMENT, *DIRECT, *NPDES)}
    facts.update(
        treatment_depth_inches=1.5,
        waterway_name="Invented waterway",
        outfall_id="invented-outfall",
        upstream_smp_present=False,
        permit_id="SYNTHETIC-ONLY",
        effective_from="2020-01-01",
        expires_on="2028-03-23",
        compliance_from="2025-11-15",
        compliance_through="2026-11-15",
    )
    return {
        "id": identifier,
        "category": category,
        "decision": "confirmed",
        "basis": "documented",
        "facts": facts,
        "evidence_review": {
            "support_reviewed": True,
            "property_match": True,
            "period_match": True,
            "fact_keys": list(facts),
            "note": "Invented reviewer checks invented property and period",
        },
        "geometry": geom,
        "footprint_geometry": geom,
        "managed_area_sqft": 1000,
        "evidence_refs": [{"source_url": "https://example.test/synthetic-only", "page": 2}],
    }


def run(c, g):
    return evaluate_assessment(c, g, as_of="2026-11-15")


class AssessmentPolicyTests(unittest.TestCase):
    def test_each_category_missing_evidence_and_known_answer(self):
        for category in (
            "green_roof",
            "permeable_pavement",
            "direct_discharge",
            "industrial_npdes",
        ):
            with self.subTest(category=category):
                c, g = fixture()
                r = record(category)
                c["assessment"]["records"] = [r]
                result = run(c, g)
                entry = next(x for x in result["categories"] if x["category"] == category)[
                    "records"
                ][0]
                self.assertEqual(entry["status"], "screen_pass", entry)
                self.assertEqual(result["economics"]["documented"]["status"], "calculated")
                r["facts"] = {}
                entry = next(x for x in run(c, g)["categories"] if x["category"] == category)[
                    "records"
                ][0]
                self.assertEqual(entry["status"], "missing_evidence")
                self.assertIn("account_current", entry["missing"])

    def test_candidate_rejection_and_proposed_record_cannot_become_credit(self):
        c, g = fixture()
        r = record()
        c["assessment"]["records"] = [r]
        for decision, status in [("candidate", "candidate"), ("rejected", "rejected")]:
            r["decision"] = decision
            result = run(c, g)
            self.assertEqual(result["categories"][0]["records"][0]["status"], status)
            self.assertIsNone(result["economics"]["documented"]["gross_monthly_reduction"])
        r["decision"] = "confirmed"
        r["facts"]["existing_installation"] = False
        self.assertEqual(run(c, g)["categories"][0]["records"][0]["status"], "requirements_failed")

    def test_managed_footprint_and_physical_ia_are_separate_and_unchanged(self):
        # An approved SMP (permeable pavement): IA credit is for the managed drainage
        # area, not the footprint (manual 4.3.2.2): 80% x 1,000 = 800.
        c, g = fixture()
        r = record("permeable_pavement")
        r["footprint_geometry"] = mapping(box(0, 0, 1.524, 30.48))
        c["assessment"]["records"] = [r]
        frozen = canonical(g)
        result = run(c, g)
        entry = result["categories"][1]["records"][0]
        self.assertAlmostEqual(entry["managed_area_sqft"], 1000)
        self.assertAlmostEqual(entry["footprint_area_sqft"], 500)
        self.assertEqual(canonical(g), frozen)
        self.assertAlmostEqual(g["measurement"]["ia_sqft"], 10000)
        self.assertEqual(result["economics"]["documented"]["ledger"]["new_ia_credit_sqft"], 800)
        # 9200 final square feet rounds up to 9500, not footprint or zero IA.
        self.assertEqual(result["economics"]["documented"]["bill"]["billed_ia_sqft"], 9500)

    def test_green_roof_is_an_impervious_area_reduction_of_its_footprint(self):
        # Manual Table 1 / 4.3.2.1: "Rooftop Disconnection via Green Roof" is an IAR, a
        # direct reduction of billable IA. A 1.524 m x 30.48 m footprint = 500 sq ft on the
        # roof; the 1,000 sq ft contributing geometry is not credited by the IAR.
        # Baseline: GA 20 units x $1.003 = $20.06; IA 20 units x $7.048 = $140.96;
        # $161.02 + $2.81 = $163.83. Final IA 9,500 -> 19 units x $7.048 = $133.912 ->
        # $133.91; GA unchanged $20.06; $153.97 + $2.81 = $156.78; reduction $7.05.
        c, g = fixture()
        r = record("green_roof")
        r["footprint_geometry"] = mapping(box(0, 0, 1.524, 30.48))
        c["assessment"]["records"] = [r]
        result = run(c, g)
        entry = result["categories"][0]["records"][0]
        self.assertEqual(entry["status"], "screen_pass", entry)
        self.assertEqual(entry["credit_path"], "impervious_area_reduction")
        self.assertAlmostEqual(entry["iar_area_sqft"], 500)
        s = result["economics"]["documented"]
        self.assertAlmostEqual(s["ledger"]["new_iar_sqft"], 500)
        self.assertEqual(
            (s["ledger"]["new_ia_credit_sqft"], s["ledger"]["new_ga_credit_sqft"]), (0, 0)
        )
        self.assertEqual((s["bill"]["final_ia_sqft"], s["bill"]["final_ga_sqft"]), (9500, 10000))
        self.assertEqual((s["bill"]["monthly_total"], s["gross_monthly_reduction"]), (156.78, 7.05))
        # Manual 4.5.1: an IAR needs a site plan and recent photographs, not SMP depth.
        for key in ("site_plan_documented", "photographs_current"):
            r2 = record("green_roof")
            r2["facts"][key] = False
            c["assessment"]["records"] = [r2]
            self.assertIn(key, run(c, g)["categories"][0]["records"][0]["failed"])
        r3 = record("green_roof")
        r3["facts"]["treatment_depth_inches"] = 0.5
        r3.pop("geometry")
        c["assessment"]["records"] = [r3]
        self.assertEqual(run(c, g)["categories"][0]["records"][0]["status"], "screen_pass")
        r3["facts"]["credit_path"] = "management"
        self.assertIn("unsupported_credit_path", run(c, g)["categories"][0]["records"][0]["failed"])

    def test_pavement_depth_and_construction_are_required(self):
        for category, key, value in [
            ("permeable_pavement", "treatment_depth_inches", 1.49),
            ("permeable_pavement", "construction_documented", False),
        ]:
            c, g = fixture()
            r = record(category)
            r["facts"][key] = value
            c["assessment"]["records"] = [r]
            entry = next(x for x in run(c, g)["categories"] if x["category"] == category)[
                "records"
            ][0]
            self.assertIn(key, entry["failed"])

    def test_direct_discharge_city_infrastructure_route_and_condition_blocks(self):
        for key in (
            "no_city_infrastructure",
            "route_confirmed",
            "outfall_confirmed",
            "ownership_confirmed",
            "no_erosion_or_detriment",
        ):
            c, g = fixture()
            r = record("direct_discharge")
            r["facts"][key] = False
            c["assessment"]["records"] = [r]
            entry = run(c, g)["categories"][2]["records"][0]
            self.assertIn(key, entry["failed"])
        r["facts"] = record("direct_discharge")["facts"]
        r["facts"]["upstream_smp_present"] = True
        self.assertIn("upstream_smp_compliant", run(c, g)["categories"][2]["records"][0]["missing"])

    def test_direct_factor_is_ninety_percent(self):
        c, g = fixture()
        c["assessment"]["records"] = [record("direct_discharge")]
        self.assertEqual(run(c, g)["economics"]["documented"]["ledger"]["new_ia_credit_sqft"], 900)

    def test_npdes_identity_inactive_construction_and_compliance_period_rejected(self):
        # A lagging DMR period or an expiry with possible administrative continuation
        # is missing evidence, not a failed permit (review B7; tests in test_policy_money).
        for key, value in [
            ("site_match", False),
            ("operator_match", False),
            ("active", False),
            ("industrial_stormwater", False),
            ("permit_type", "construction"),
            ("compliance_from", "2025-11-16"),
            ("compliance_previous_12_months", False),
            ("terminated_on", "2026-11-01"),
        ]:
            with self.subTest(key=key):
                c, g = fixture()
                r = record("industrial_npdes")
                r["facts"][key] = value
                c["assessment"]["records"] = [r]
                self.assertIn(key, run(c, g)["categories"][3]["records"][0]["failed"])
                self.assertIsNone(run(c, g)["economics"]["documented"]["gross_monthly_reduction"])

    def test_npdes_alone_seven_percent_area_ledger_before_rounding(self):
        c, g = fixture()
        c["assessment"]["records"] = [record("industrial_npdes")]
        scenario = run(c, g)["economics"]["documented"]
        self.assertEqual(scenario["ledger"]["new_ga_credit_sqft"], 700)
        self.assertEqual(scenario["ledger"]["new_ia_credit_sqft"], 700)
        self.assertEqual(scenario["bill"]["monthly_total"], 155.78)
        self.assertEqual(scenario["gross_monthly_reduction"], 8.05)
        self.assertEqual(scenario["gross_annual_reduction"], 96.6)

    def test_npdes_plus_management_uses_uplift_and_residual_once(self):
        # Manual 4.3.5.2: 87% x 1,000 managed = 870 IA and GA; remaining uncredited IA
        # 10,000 - 1,000 = 9,000 x 7% = 630 toward both: 1,500 each. Final 8,500 each ->
        # 17 units: GA $17.051 -> $17.05; IA $119.816 -> $119.82; $136.87 + $2.81 = $139.68.
        c, g = fixture()
        c["assessment"]["records"] = [
            record("permeable_pavement"),
            record("industrial_npdes", "permit"),
        ]
        scenario = run(c, g)["economics"]["documented"]
        self.assertEqual(scenario["ledger"]["new_ga_credit_sqft"], 1500)
        self.assertEqual(scenario["ledger"]["new_ia_credit_sqft"], 1500)
        self.assertNotIn("npdes_fraction", scenario["bill"])
        self.assertEqual(scenario["bill"]["monthly_total"], 139.68)
        self.assertEqual(scenario["gross_monthly_reduction"], 24.15)
        self.assertEqual(scenario["gross_annual_reduction"], 289.8)

    def test_new_npdes_reconciles_itemized_existing_credit_ledger(self):
        c, g = fixture()
        existing = record()
        c["baseline"].update(
            existing_ga_credit_sqft=800,
            existing_ia_credit_sqft=800,
            existing_credits_spatially_reconciled=True,
        )
        c["assessment"]["existing_credit_allocations"] = [
            {
                "id": "old-award",
                "category": "management",
                "geometry": existing["geometry"],
                "ga_credit_sqft": 800,
                "ia_credit_sqft": 800,
                "iar_sqft": 0,
                "facts": {"approved_ledger_confirmed": True},
                "evidence_refs": existing["evidence_refs"],
            }
        ]
        new = record("permeable_pavement", "new-roof", 3.048)
        new["facts"]["existing_overlap_reconciled"] = True
        new["evidence_review"]["fact_keys"].append("existing_overlap_reconciled")
        c["assessment"]["records"] = [new, record("industrial_npdes", "permit")]
        scenario = run(c, g)["economics"]["documented"]
        self.assertEqual(scenario["status"], "calculated", scenario)
        # Prior 800 replaced by uplifted 870; new 870; residual 7% x (10,000 - 2,000 managed)
        # = 560 (manual 4.3.5.2): IA credits 2,300, i.e. 1,500 more than the recorded 800.
        self.assertEqual(scenario["ledger"]["new_ia_credit_sqft"], 1500)
        self.assertEqual(scenario["bill"]["final_ia_sqft"], 7700)
        c["assessment"]["existing_credit_allocations"][0]["ia_credit_sqft"] = 700
        self.assertEqual(run(c, g)["economics"]["documented"]["status"], "blocked")
        c["assessment"]["existing_credit_allocations"][0]["ia_credit_sqft"] = 800
        c["assessment"]["records"][0]["geometry"] = existing["geometry"]
        self.assertEqual(run(c, g)["economics"]["documented"]["status"], "blocked")

    def test_npdes_with_open_space_uses_table_factor_and_residual_impervious(self):
        c, g = fixture()
        impervious = mapping(box(0, 0, 24.384, 30.48))
        open_space = mapping(box(24.384, 0, 30.48, 30.48))
        c["baseline"]["ia_sqft"] = 8000
        c["features"]["features"] = [
            {
                "id": "roof",
                "geometry": impervious,
                "properties": {"layer": "surface", "class": "roof"},
            },
            {
                "id": "lawn",
                "geometry": open_space,
                "properties": {"layer": "surface", "class": "pervious"},
            },
        ]
        g = analyze(c)
        c["benefits"] = [
            {
                "id": "open",
                "category": "open_space",
                "geometry": open_space,
                "area_sqft": 2000,
                "basis": "documented",
                "evidence": {
                    "physical_area_confirmed": True,
                    "parcel_allocation_confirmed": True,
                    "account_current": True,
                    "cover_confirmed": True,
                    "soil_confirmed": True,
                    "runoff_characteristics_confirmed": True,
                    "non_impervious_confirmed": True,
                    "curve_number": 55,
                },
            }
        ]
        c["assessment"]["records"] = [record("industrial_npdes")]
        scenario = run(c, g)["economics"]["documented"]
        self.assertEqual(scenario["ledger"]["new_ga_credit_sqft"], 2300)
        self.assertEqual(scenario["ledger"]["new_ia_credit_sqft"], 560)
        self.assertEqual(scenario["bill"]["monthly_total"], 124.58)
        self.assertEqual(scenario["gross_monthly_reduction"], 11.06)

    def test_npdes_with_iar_uses_literal_residual_and_reports_discontinuity(self):
        # Manual 4.3.5.2 literally: canopy IAR 50% x 1,000 = 500 (4.3.2.1) is an IA credit
        # option, so NPDES gives 7% of remaining uncredited IA: (10,000 - 500) x 7% = 665
        # toward both IA and GA. Final GA 9,335 -> 19 units -> $19.057 -> $19.06; final IA
        # 10,000 - 500 - 665 = 8,835 -> 18 units -> $126.864 -> $126.86; $145.92 + $2.81 =
        # $148.73; reduction from $163.83 is $15.10. NPDES alone gives GA 700 / IA 700
        # ($155.78), so the GA credit falls 700 -> 665: a labelled manual rule discontinuity.
        c, g = fixture()
        canopy = record()["geometry"]
        g["measurement"]["geometries"]["canopy_ground_ia"] = canopy
        c["benefits"] = [
            {
                "id": "canopy",
                "category": "canopy",
                "geometry": canopy,
                "area_sqft": 1000,
                "basis": "documented",
                "evidence": {
                    "physical_area_confirmed": True,
                    "parcel_allocation_confirmed": True,
                    "account_current": True,
                    "ground_impervious_overlap_confirmed": True,
                },
            }
        ]
        c["assessment"]["records"] = [record("industrial_npdes")]
        scenario = run(c, g)["economics"]["documented"]
        self.assertEqual(scenario["status"], "calculated", scenario.get("reasons"))
        self.assertAlmostEqual(scenario["ledger"]["new_iar_sqft"], 500)
        self.assertAlmostEqual(scenario["ledger"]["new_ia_credit_sqft"], 665)
        self.assertAlmostEqual(scenario["ledger"]["new_ga_credit_sqft"], 665)
        self.assertEqual(
            (scenario["bill"]["monthly_total"], scenario["gross_monthly_reduction"]),
            (148.73, 15.10),
        )
        note = scenario["manual_rule_discontinuity"]
        self.assertEqual(
            (note["npdes_alone_ga_credit_sqft"], note["scenario_ga_credit_sqft"]), (700, 665)
        )
        self.assertEqual(note["npdes_alone_monthly_total"], 155.78)
        self.assertFalse(note["bill_higher_than_npdes_alone"])
        self.assertTrue(any("Manual rule discontinuity" in a for a in scenario["assumptions"]))

    def test_npdes_plus_surface_discharge_uses_ninety_seven_percent(self):
        c, g = fixture()
        c["assessment"]["records"] = [
            record("direct_discharge"),
            record("industrial_npdes", "permit"),
        ]
        scenario = run(c, g)["economics"]["documented"]
        self.assertEqual(scenario["ledger"]["new_ia_credit_sqft"], 1600)
        self.assertEqual(scenario["ledger"]["allocations"][0]["factor"], 0.97)

    def test_multiple_categories_overlap_blocks_combined_not_eligibility_screen(self):
        c, g = fixture()
        c["assessment"]["records"] = [record(), record("permeable_pavement", "p")]
        result = run(c, g)
        self.assertEqual(result["categories"][0]["status"], "screen_pass")
        self.assertEqual(result["categories"][1]["status"], "screen_pass")
        self.assertEqual(result["economics"]["documented"]["status"], "blocked")
        c["assessment"]["records"][1] = record("permeable_pavement", "p", 3.048)
        # Green roof: 1,000 sq ft IAR (manual 4.3.2.1); pavement: 80% x 1,000 = 800 IA credit.
        ledger = run(c, g)["economics"]["documented"]["ledger"]
        self.assertEqual((ledger["new_iar_sqft"], ledger["new_ia_credit_sqft"]), (1000, 800))

    def test_physical_ia_geometry_and_scalar_mismatch_are_explicit(self):
        c, g = fixture()
        r = record()
        c["assessment"]["records"] = [r]
        r["managed_area_sqft"] = 2000
        self.assertIn(
            "managed_area_matches_geometry", run(c, g)["categories"][0]["records"][0]["failed"]
        )
        r["geometry"] = mapping(box(100, 100, 110, 110))
        self.assertIn(
            "managed_geometry_inside_parcel", run(c, g)["categories"][0]["records"][0]["failed"]
        )
        r["geometry"] = {"type": "Polygon", "coordinates": []}
        self.assertIn("managed_area_geometry", run(c, g)["categories"][0]["records"][0]["failed"])

    def test_unknown_surface_not_zero_and_correction_only_when_complete(self):
        c, g = fixture()
        c["assessment"]["records"] = [record()]
        g["measurement"]["complete"] = False
        result = run(c, g)
        self.assertEqual(result["economics"]["documented"]["status"], "calculated")
        self.assertIsNone(result["economics"]["documented_combined"]["gross_monthly_reduction"])
        self.assertIsNone(result["economics"]["measurement_only"]["gross_monthly_reduction"])
        self.assertEqual(result["categories"][1]["managed_area_sqft"], None)

    def test_combined_preserves_totals_and_cannot_credit_corrected_away_area(self):
        c, g = fixture()
        c["assessment"]["records"] = [record("permeable_pavement")]
        g["measurement"]["ia_sqft"] = 8000
        result = run(c, g)["economics"]
        scenario = result["documented_combined"]
        self.assertEqual(scenario["bill"]["physical_ga_sqft"], 10000)
        self.assertEqual(scenario["bill"]["physical_ia_sqft"], 8000)
        self.assertEqual(scenario["bill"]["final_ia_sqft"], 7200)
        self.assertEqual(result["measurement_only"]["bill"]["final_ia_sqft"], 8000)
        g["measurement"]["ia_sqft"] = 500
        self.assertEqual(run(c, g)["economics"]["documented_combined"]["status"], "blocked")

    def test_existing_credits_preserved_and_reconciliation_required(self):
        c, g = fixture()
        r = record("permeable_pavement")
        c["assessment"]["records"] = [r]
        c["baseline"].update(existing_ga_credit_sqft=800, existing_ia_credit_sqft=800)
        self.assertEqual(run(c, g)["economics"]["baseline"]["final_ia_sqft"], 9200)
        self.assertEqual(run(c, g)["economics"]["documented"]["status"], "blocked")
        c["baseline"]["existing_credits_spatially_reconciled"] = True
        r["facts"]["existing_overlap_reconciled"] = True
        r["evidence_review"]["fact_keys"].append("existing_overlap_reconciled")
        self.assertEqual(run(c, g)["economics"]["documented"]["status"], "blocked")
        c["assessment"]["existing_credit_allocations"] = [
            {
                "id": "old-award",
                "category": "management",
                "geometry": record(start=3.048)["geometry"],
                "ga_credit_sqft": 800,
                "ia_credit_sqft": 800,
                "iar_sqft": 0,
                "facts": {"approved_ledger_confirmed": True},
                "evidence_refs": r["evidence_refs"],
            }
        ]
        self.assertEqual(run(c, g)["economics"]["documented"]["bill"]["final_ia_sqft"], 8400)
        c["assessment"]["records"].append(record("industrial_npdes", "permit"))
        self.assertEqual(run(c, g)["economics"]["documented"]["status"], "calculated")

    def test_existing_npdes_alone_does_not_generate_increment(self):
        c, g = fixture()
        c["baseline"]["npdes_fraction"] = 0.07
        c["assessment"]["records"] = [record("industrial_npdes")]
        out = run(c, g)["economics"]
        s = out["documented"]
        # One area representation (manual 4.3.5.2): the recorded NPDES baseline already
        # holds 700 GA + 700 IA credits ($155.78), so the permit record adds nothing.
        self.assertEqual(out["baseline"]["monthly_total"], 155.78)
        self.assertEqual(out["baseline"]["npdes_credit"]["ga_credit_sqft"], 700)
        self.assertEqual(s["gross_monthly_reduction"], 0)
        self.assertEqual(s["bill"]["monthly_total"], 155.78)

    def test_legacy_benefit_and_new_system_share_one_spatial_ledger(self):
        c, g = fixture()
        r = record("permeable_pavement")
        c["assessment"]["records"] = [r]
        c["benefits"] = [
            {
                "id": "legacy",
                "category": "management",
                "geometry": r["geometry"],
                "area_sqft": 1000,
                "evidence": {**r["facts"], "npdes": False},
                "basis": "documented",
            }
        ]
        self.assertEqual(run(c, g)["economics"]["documented"]["status"], "blocked")
        c["benefits"][0]["geometry"] = record(start=3.048)["geometry"]
        s = run(c, g)["economics"]["documented"]
        self.assertEqual(s["ledger"]["new_ia_credit_sqft"], 1600)
        self.assertEqual(s["bill"]["physical_ga_sqft"], 10000)
        self.assertEqual(s["bill"]["physical_ia_sqft"], 10000)

    def test_manual_and_modeled_inputs_not_documented_savings(self):
        for basis in ("manual", "modeled"):
            c, g = fixture()
            r = record()
            r["basis"] = basis
            c["assessment"]["records"] = [r]
            result = run(c, g)
            self.assertEqual(result["economics"]["documented"]["status"], "blocked")
            self.assertEqual(result["economics"]["modeled"]["basis"], "conditional")
        r["basis"] = "documented"
        r["evidence_refs"] = []
        self.assertIn(
            "supporting_document_or_source_reference",
            run(c, g)["categories"][0]["records"][0]["missing"],
        )

    def test_attachment_ref_must_exist(self):
        c, g = fixture()
        r = record()
        r["evidence_refs"] = [{"attachment_id": "missing", "page": 2}]
        c["assessment"]["records"] = [r]
        with self.assertRaisesRegex(ValueError, "missing from this case"):
            run(c, g)
        r["evidence_refs"][0]["attachment_id"] = "a" * 64
        c["assessment"]["attachments"] = [
            {"id": "a" * 64, "sha256": "a" * 64, "filename": "review.txt", "size_bytes": 10}
        ]
        self.assertEqual(run(c, g)["categories"][0]["status"], "screen_pass")

    def test_no_billing_baseline_or_unverified_bill_remains_partial(self):
        c, g = fixture()
        c["assessment"]["records"] = [record()]
        del c["baseline"]
        self.assertEqual(run(c, g)["categories"][0]["status"], "screen_pass")
        self.assertIsNone(run(c, g)["economics"]["documented"]["gross_monthly_reduction"])
        c["baseline"] = {"ga_sqft": 10000, "ia_sqft": 10000, "actual_bill_verified": False}
        self.assertEqual(run(c, g)["economics"]["documented"]["basis"], "conditional")

    def test_current_period_and_minimum_allocation_remain_enforced(self):
        c, g = fixture()
        c["assessment"]["records"] = [record()]
        self.assertEqual(
            evaluate_assessment(c, g, as_of="2028-01-01")["economics"]["documented"]["status"],
            "blocked",
        )
        c["baseline"].update(
            ga_sqft=10000, ia_sqft=10000, accounts=[{"allocation": 0.5}, {"allocation": 0.5}]
        )
        s = run(c, g)["economics"]["documented"]
        self.assertEqual(len(s["bill"]["accounts"]), 2)
        c["baseline"]["accounts"][1]["allocation"] = 0.4
        self.assertEqual(run(c, g)["economics"]["documented"]["status"], "blocked")

    def test_historical_flags_no_refund_and_missing_period_unknown(self):
        c, g = fixture()
        c["baseline"]["published_monthly_total"] = 100
        del c["baseline"]["bill_date"]
        result = run(c, g)
        flag = result["historical_flags"][0]
        self.assertIsNone(flag["affected_from"])
        self.assertIsNone(flag["refund_entitlement"])
        self.assertEqual(flag["status"], "review_only")
        self.assertEqual(flag["observed_discrepancy"], 63.83)
        self.assertNotIn("historical_recovery", result["economics"])

    def test_reproducible_hash_and_no_mutation_or_routing(self):
        c, g = fixture()
        c["assessment"]["records"] = [record()]
        before = canonical((c, g))
        with patch("drainage_core.engine.analyze", side_effect=AssertionError("No rerouting")):
            first = run(c, g)
            second = run(c, g)
        self.assertEqual(first["assessment_sha256"], second["assessment_sha256"])
        self.assertEqual(canonical((c, g)), before)

    def test_non_boolean_upstream_presence_cannot_bypass_smp_evidence(self):
        for value in (1, 0, "true", "false", []):
            c, g = fixture()
            r = record("direct_discharge")
            r["facts"]["upstream_smp_present"] = value
            c["assessment"]["records"] = [r]
            entry = run(c, g)["categories"][2]["records"][0]
            self.assertEqual(entry["status"], "requirements_failed")
            self.assertIn("upstream_smp_present", entry["failed"])

    def test_malformed_or_duplicate_records_are_rejected_before_source_lookup(self):
        malformed = [
            None,
            [],
            {"records": None},
            {"records": [None]},
            {"records": [{"id": "r", "category": "green_roof", "facts": []}]},
        ]
        for assessment in malformed:
            c, g = fixture()
            c["assessment"] = assessment
            with self.assertRaises(ValueError):
                run(c, g)
        c, g = fixture()
        c["assessment"]["records"] = [record(), record("industrial_npdes")]
        with self.assertRaisesRegex(ValueError, "Duplicate"):
            run(c, g)
        c["assessment"]["records"] = [{**record(), "id": None}]
        with self.assertRaisesRegex(ValueError, "ID"):
            run(c, g)
        c["assessment"]["records"] = [{**record(), "category": "unknown"}]
        with self.assertRaisesRegex(ValueError, "category"):
            run(c, g)
        c["assessment"]["records"] = [{**record(), "evidence_refs": ["invalid"]}]
        with self.assertRaisesRegex(ValueError, "references"):
            run(c, g)

    def test_invalid_source_url_is_not_supporting_evidence(self):
        c, g = fixture()
        r = record()
        r["evidence_refs"] = [{"source_url": "https://"}]
        c["assessment"]["records"] = [r]
        self.assertIn(
            "supporting_document_or_source_reference",
            run(c, g)["categories"][0]["records"][0]["missing"],
        )

    def test_itemized_existing_physical_area_cannot_be_reused_below_recorded_ia(self):
        c, g = fixture()
        old = record()
        new = record(identifier="new", start=3.048)
        c["baseline"].update(
            ia_sqft=1700,
            existing_ga_credit_sqft=800,
            existing_ia_credit_sqft=800,
            existing_credits_spatially_reconciled=True,
        )
        c["assessment"]["existing_credit_allocations"] = [
            {
                "id": "old",
                "category": "management",
                "geometry": old["geometry"],
                "ga_credit_sqft": 800,
                "ia_credit_sqft": 800,
                "iar_sqft": 0,
                "facts": {"approved_ledger_confirmed": True},
                "evidence_refs": old["evidence_refs"],
            }
        ]
        new["facts"]["existing_overlap_reconciled"] = True
        c["assessment"]["records"] = [new]
        new["evidence_review"]["fact_keys"].append("existing_overlap_reconciled")
        result = run(c, g)["economics"]
        self.assertEqual(result["documented"]["status"], "blocked")
        self.assertTrue(any("physical impervious" in r for r in result["documented"]["reasons"]))
        self.assertEqual(result["documented_combined"]["status"], "calculated")

    def test_aggregate_credit_does_not_establish_reserved_physical_capacity(self):
        c, g = fixture()
        r = record()
        r["geometry"] = mapping(box(0, 0, 28.956, 30.48))
        r["managed_area_sqft"] = 9500
        r["facts"]["existing_overlap_reconciled"] = True
        c["assessment"]["records"] = [r]
        r["evidence_review"]["fact_keys"].append("existing_overlap_reconciled")
        c["baseline"].update(
            existing_ga_credit_sqft=800,
            existing_ia_credit_sqft=800,
            existing_credits_spatially_reconciled=True,
        )
        # Scalar credits800 plus new7600 fit IA10000, but their physical
        # occupancy is unknown: an old1000 region plus new9500 would not fit.
        result = run(c, g)["economics"]
        self.assertEqual(result["documented"]["status"], "blocked")
        self.assertTrue(
            any("allocation ledger missing" in reason for reason in result["documented"]["reasons"])
        )
        self.assertEqual(result["measurement_only"]["status"], "blocked")
        self.assertEqual(result["baseline"]["final_ia_sqft"], 9200)

    def test_contradictory_supplied_existing_ledger_blocks_without_npdes(self):
        c, g = fixture()
        old = record()
        new = record(identifier="new", start=3.048)
        c["baseline"].update(
            existing_ga_credit_sqft=800,
            existing_ia_credit_sqft=800,
            existing_credits_spatially_reconciled=True,
        )
        c["assessment"]["existing_credit_allocations"] = [
            {
                "id": "old",
                "category": "management",
                "geometry": old["geometry"],
                "ga_credit_sqft": 800,
                "ia_credit_sqft": 700,
                "iar_sqft": 0,
                "facts": {"approved_ledger_confirmed": True},
                "evidence_refs": old["evidence_refs"],
            }
        ]
        new["facts"]["existing_overlap_reconciled"] = True
        c["assessment"]["records"] = [new]
        new["evidence_review"]["fact_keys"].append("existing_overlap_reconciled")
        self.assertEqual(run(c, g)["economics"]["documented"]["status"], "blocked")

    def test_open_space_allocations_need_recorded_capacity_before_correction(self):
        c, g = fixture()
        impervious = mapping(box(0, 0, 21.336, 30.48))
        open_space = mapping(box(21.336, 0, 30.48, 30.48))
        c["baseline"]["ia_sqft"] = 8000
        c["features"]["features"] = [
            {
                "id": "roof",
                "geometry": impervious,
                "properties": {"layer": "surface", "class": "roof"},
            },
            {
                "id": "lawn",
                "geometry": open_space,
                "properties": {"layer": "surface", "class": "pervious"},
            },
        ]
        g = analyze(c)
        c["benefits"] = [
            {
                "id": "open",
                "category": "open_space",
                "geometry": open_space,
                "area_sqft": 3000,
                "basis": "documented",
                "evidence": {
                    "physical_area_confirmed": True,
                    "parcel_allocation_confirmed": True,
                    "account_current": True,
                    "cover_confirmed": True,
                    "soil_confirmed": True,
                    "runoff_characteristics_confirmed": True,
                    "non_impervious_confirmed": True,
                    "curve_number": 55,
                },
            }
        ]
        result = run(c, g)["economics"]
        self.assertEqual(result["documented"]["status"], "blocked")
        self.assertTrue(any("physical open space" in r for r in result["documented"]["reasons"]))
        self.assertEqual(result["documented_combined"]["status"], "calculated")

    def test_credit_minimum_does_not_block_measurement_only_appeal(self):
        c, g = fixture()
        c["baseline"].update(ga_sqft=400, ia_sqft=300)
        g["measurement"].update(ga_sqft=400, ia_sqft=300)
        self.assertEqual(run(c, g)["economics"]["measurement_only"]["status"], "calculated")

    def test_custom_tariff_does_not_enable_current_rules_in_other_period(self):
        from stormwater.billing import default_tariff

        c, g = fixture()
        r = record()
        c["assessment"]["records"] = [r]
        c["baseline"]["bill_date"] = "2028-11-15"
        tariff = default_tariff()
        tariff.update(effective_from="2028-09-01", verified_through="2029-08-31")
        result = evaluate_assessment(c, g, as_of="2028-11-15", tariff=tariff)
        self.assertEqual(result["rules"]["applicability"], "outside_verified_period")
        self.assertEqual(result["economics"]["documented"]["status"], "blocked")
        self.assertEqual(result["economics"]["modeled"]["status"], "blocked")

    def test_leap_year_compliance_boundary(self):
        c, g = fixture()
        r = record("industrial_npdes")
        c["assessment"]["records"] = [r]
        r["facts"].update(compliance_from="2023-02-28", compliance_through="2024-02-29")
        result = evaluate_assessment(c, g, as_of="2024-02-29")
        entry = result["categories"][3]["records"][0]
        self.assertEqual(entry["status"], "missing_evidence")
        self.assertIn("applicable_rule_version", entry["missing"])
        self.assertNotIn("compliance_from", entry["failed"])
        self.assertEqual(result["rules"]["applicability"], "outside_verified_period")


if __name__ == "__main__":
    unittest.main()
