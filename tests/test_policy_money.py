"""Phase 2 money-correctness regressions (review 2026-11-16 B1-B10, R1, R2, R17, H11).

Every expected dollar amount is derived by hand in a comment from the PWD tariff
effective 2026-09-01 (sections 4.3(a)(2)-(8), 4.5) and the September 2026 Credits
and Appeals Manual (sections 4.3.3-4.3.5, Appendix A), never copied from output:
GA $1.003 and IA $7.048 per 500 sq ft unit (units rounded up), each charge rounded
half-up to cents, minimum SWMS $20.89 per account, Billing & Collection $2.81 per
account. Invented fixtures validate arithmetic and rules, not real-site accuracy.
"""

from datetime import date
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from shapely.geometry import box, mapping

from drainage_core.engine import analyze
from stormwater.acquisition import normalize_billing
from stormwater.assessment_policy import evaluate_assessment
from stormwater.billing import default_tariff, monthly_bill
from stormwater.curve_number import TABLE
from stormwater.renewals import credit_renewals
from stormwater.rules import RULE_CONFIG_PATH, load_rule_config, open_space_factor
from test_assessment_policy import fixture, record, run
from test_billing import ledger

THIRDS = [
    {"allocation": "0.3333333333333333333"},
    {"allocation": "0.3333333333333333333"},
    {"allocation": "0.3333333333333333334"},
]
CANOPY_EVIDENCE = {
    k: True
    for k in (
        "physical_area_confirmed",
        "parcel_allocation_confirmed",
        "account_current",
        "ground_impervious_overlap_confirmed",
    )
}


def canopy(area):
    return {
        "id": "c",
        "category": "canopy",
        "area_sqft": area,
        "evidence": CANOPY_EVIDENCE,
        "basis": "documented",
    }


def with_facts(r, **facts):
    """Add facts and keep the invented reviewer's fact list complete."""
    r["facts"].update(facts)
    r["evidence_review"]["fact_keys"] = list(r["facts"])
    return r


def mixed_site():
    """10,000 sq ft parcel: 8,000 sq ft roof (x 0-24.384 m) and 2,000 sq ft lawn."""
    c, _ = fixture()
    c["baseline"]["ia_sqft"] = 8000
    lawn = mapping(box(24.384, 0, 30.48, 30.48))
    c["features"]["features"] = [
        {
            "id": "roof",
            "geometry": mapping(box(0, 0, 24.384, 30.48)),
            "properties": {"layer": "surface", "class": "roof"},
        },
        {"id": "lawn", "geometry": lawn, "properties": {"layer": "surface", "class": "pervious"}},
    ]
    return c, analyze(c), lawn


class ConfigAndTableTests(unittest.TestCase):
    def test_default_tariff_is_read_from_rule_config(self):
        config = json.loads(Path(RULE_CONFIG_PATH).read_text())
        t = default_tariff()
        self.assertEqual(
            (t["ga_rate"], t["ia_rate"], t["minimum_swms"], t["collection_charge"]),
            (
                config["ga_rate_per_500_sqft"],
                config["ia_rate_per_500_sqft"],
                config["minimum_swms_monthly"],
                config["collection_per_account_monthly"],
            ),
        )

    def test_changing_the_config_changes_the_bill(self):
        with TemporaryDirectory() as folder:
            path = Path(folder) / "rules.json"
            config = load_rule_config()
            config["ia_rate_per_500_sqft"] = "8.000"
            path.write_text(json.dumps(config))
            # 10,000 GA -> 20 units x $1.003 = $20.06; 8,000 IA -> 16 units x $8.000 = $128.00;
            # $148.06 + $2.81 = $150.87 (the shipped $7.048 rate gives $135.64).
            self.assertEqual(
                monthly_bill(10000, 8000, tariff=default_tariff(path))["monthly_total"], 150.87
            )
        self.assertEqual(monthly_bill(10000, 8000)["monthly_total"], 135.64)

    def test_curve_number_table_matches_manual_table_a1(self):
        # Transcribed from manual Appendix A Table A-1 (printed page 35); columns A,B,C,D,Ub.
        # Review B5 is withdrawn: the manual lists brush identical to woods-grass, and
        # porous turf as 70/70/79/84/69.
        manual = {
            "lawn": {
                "poor": [68, 79, 86, 89, 79],
                "fair": [49, 69, 79, 84, 69],
                "good": [39, 61, 74, 80, 61],
            },
            "meadow": {"na": [30, 58, 71, 78, 58]},
            "athletic_field": {"na": [68, 79, 86, 89, 79]},
            "porous_turf": {"na": [70, 70, 79, 84, 69]},
            "brush": {
                "poor": [57, 73, 82, 86, 73],
                "fair": [43, 65, 76, 82, 65],
                "good": [32, 58, 72, 79, 58],
            },
            "woods_grass": {
                "poor": [57, 73, 82, 86, 73],
                "fair": [43, 65, 76, 82, 65],
                "good": [32, 58, 72, 79, 58],
            },
            "woods": {
                "poor": [45, 66, 77, 83, 66],
                "fair": [36, 60, 73, 79, 60],
                "good": [30, 55, 70, 77, 55],
            },
            "gravel": {"na": [76, 85, 89, 91, 89]},
            "dirt": {"na": [72, 82, 87, 89, 87]},
            "water": {"na": [100, 100, 100, 100, 100]},
        }
        self.assertEqual(TABLE, manual)

    def test_table_a2_scale(self):
        # Table A-2: 4% (4.35% with NPDES) per whole CN below 75, capped at CN 55.
        for cn, plain, npdes in (
            (75, 0, 0),
            (80, 0, 0),
            (74, 0.04, 0.0435),
            (61, 0.56, 0.609),
            (55, 0.8, 0.87),
            (40, 0.8, 0.87),
        ):
            self.assertAlmostEqual(open_space_factor(cn), plain)
            self.assertAlmostEqual(open_space_factor(cn, True), npdes)


class CurveNumberRoundingTests(unittest.TestCase):
    def test_float_noise_cannot_remove_a_whole_cn_step(self):
        # Review B4: 61.000000000000014 is CN 61 (14 steps below 75 -> 56%), not 62 (52%).
        self.assertEqual(open_space_factor(61.000000000000014), 0.56)
        # A real fraction keeps only the whole steps it reaches (manual 4.3.3.1):
        # 61.4 is 13.6 below 75 -> 13 whole steps -> 52%.
        self.assertEqual(open_space_factor(61.4), 0.52)

    def test_uniform_cn61_strips_average_exactly_61(self):
        from test_curve_number import fixture as cn_fixture, feature, attach, soil, run as cn_run
        from shapely.geometry import shape

        for cuts in ([500037.3], [500011.7, 500043.9, 500071.3], [500013.37, 500029.11, 500063.77]):
            c = cn_fixture()
            xs = [500000] + cuts + [500100]
            c["features"]["features"] = [
                feature(
                    f"lawn{i}",
                    box(xs[i], 4420000, xs[i + 1], 4420100),
                    cn_cover="lawn",
                    cn_condition="good",
                )
                for i in range(len(xs) - 1)
            ]
            attach(c, [soil(c, shape(c["parcel"]))])
            w = cn_run(c)
            # Lawn/good on B soil is CN 61 everywhere (Table A-1) -> 14 steps -> 56%.
            self.assertEqual((w["average_cn"], w["credit_factor"]), (61.0, 0.56))


class PerAccountMinimumTests(unittest.TestCase):
    def test_canopy_credit_cannot_double_a_three_account_bill(self):
        # Review B2 (repro policy/minimum2.py). GA 6,000 -> 12 units x $1.003 = $12.036 -> $12.04;
        # IA 1,000 -> 2 units x $7.048 = $14.096 -> $14.10; parcel SWMS $26.14; each third
        # $8.71 < $20.89, so each account pays the minimum: 3 x ($20.89 + $2.81) = $71.10.
        # 1,000 sq ft canopy -> IAR 500 -> IA 500 -> 1 unit -> $7.05; parcel $19.09 -> thirds
        # still below the minimum -> $71.10. Savings $0.00, never negative. (Live ledger;
        # billing.calculate_scenarios was deleted, final review fix 9.)
        for area in (800, 1000):
            out = ledger({"ga_sqft": 6000, "ia_sqft": 1000, "accounts": THIRDS}, [canopy(area)])
            self.assertEqual(out["baseline"]["monthly_total"], 71.10)
            self.assertEqual(out["modeled"]["bill"]["monthly_total"], 71.10)
            self.assertEqual(out["modeled"]["gross_monthly_reduction"], 0.0)

    def test_minimum_applies_only_to_accounts_whose_share_is_below_it(self):
        # PWD billing FAQ / manual 4.3.5 step 5: each account's share, then the minimum.
        # GA 10,000 -> $20.06; IA 8,000 -> $112.77; parcel $132.83. 90% share $119.547 -> $119.55;
        # 10% share $13.283 -> $13.28 -> minimum $20.89. ($119.55 + $2.81) + ($20.89 + $2.81) = $146.06.
        b = monthly_bill(10000, 8000, accounts=[{"allocation": 0.9}, {"allocation": 0.1}])
        self.assertEqual([a["swms"] for a in b["accounts"]], [119.55, 20.89])
        self.assertEqual(b["monthly_total"], 146.06)

    def test_savings_are_monotone_in_credit_area(self):
        previous = None
        for area in range(0, 1001, 50):  # canopy cannot exceed the 1,000 sq ft IA
            out = ledger(
                {"ga_sqft": 6000, "ia_sqft": 1000, "accounts": THIRDS},
                [canopy(area)] if area else [],
            )
            total = (
                out["modeled"]["bill"]["monthly_total"]
                if area
                else out["baseline"]["monthly_total"]
            )
            if previous is not None:
                self.assertLessEqual(total, previous)
            previous = total

    def test_management_adapter_has_no_negative_minimum_savings(self):
        # Review H11 (repro new-policy/r4_inherit.py), developed status explicit.
        # GA 1,000 < 5,000 -> statutory IA 85% = 850 -> 2 units x $7.048 = $14.096 -> $14.10;
        # GA 2 units x $1.003 = $2.006 -> $2.01; parcel $16.11 -> halves $8.06 -> minimum each:
        # 2 x ($20.89 + $2.81) = $47.40. A 500 sq ft credit (400 sq ft at 80%) leaves IA 450 ->
        # $7.05, GA 600 -> $2.01, parcel $9.06 -> still $47.40. Savings $0.00 (was -$20.88).
        from test_management_estimates import fixture as m_fixture, rectangle, bind
        from stormwater.management_estimates import estimate_management

        c, g, e = m_fixture()
        c["parcel"] = rectangle(1000)
        g["measurement"]["geometries"]["physical_ia"] = c["parcel"]
        c["features"]["features"][0]["geometry"] = rectangle(100, start=1.524)
        e["footprint_geometry"] = rectangle(
            100, start=1.524
        )  # bed outside the 500 sq ft candidate (H16)
        c["baseline"].update(
            ga_sqft=1000,
            ia_sqft=1000,
            undeveloped=False,
            accounts=[
                {"allocation": 0.5, "discount_factor": 1},
                {"allocation": 0.5, "discount_factor": 1},
            ],
        )
        e["runs"][0]["area_scenarios"] = [
            {"id": "base", "area_sqft": 500, "geometry": rectangle(500), "basis": "x"}
        ]
        r = estimate_management(
            c, g, bind(c, e, g), "2026-11-16"
        )  # lineage bound to the edited case (H9)
        self.assertEqual(r["baseline"]["monthly_total"], 47.40)
        self.assertEqual(r["current_estimate"]["monthly_savings"], 0.0)

    def test_capacity_adapter_has_no_negative_minimum_savings(self):
        # Review H11 through runoff_capacity: same two-account developed 1,000 sq ft parcel
        # ($47.40 baseline, derived above); any managed credit leaves both halves below the
        # $20.89 minimum, so the annual saving is $0.00, not negative.
        from test_runoff_capacity_policy_unit import setup, run as capacity_run

        c, g, e, cap = setup()
        c["baseline"].update(
            ga_sqft=1000,
            ia_sqft=1000,
            undeveloped=False,
            accounts=[
                {"allocation": 0.5, "discount_factor": 1},
                {"allocation": 0.5, "discount_factor": 1},
            ],
        )
        best = capacity_run(c, g, e, cap)["current_estimate"]
        self.assertEqual(best["annual_savings"], 0.0)


class NpdesResidualTests(unittest.TestCase):
    def big_site(self):
        c, _ = fixture()
        c["parcel"] = mapping(box(0, 0, 30.48, 304.8))  # 100,000 sq ft
        c["baseline"].update(ga_sqft=100000, ia_sqft=20000)
        c["features"]["features"] = [
            {
                "id": "roof",
                "geometry": mapping(box(0, 0, 30.48, 60.96)),
                "properties": {"layer": "surface", "class": "roof"},
            },
            {
                "id": "lawn",
                "geometry": mapping(box(0, 60.96, 30.48, 304.8)),
                "properties": {"layer": "surface", "class": "pervious"},
            },
        ]
        return c, analyze(c)

    def test_literal_residual_after_another_credit_is_a_labelled_discontinuity(self):
        # Fix 6 (manual 4.3.5.2 read literally). Baseline: GA 100,000 -> 200 units x
        # $1.003 = $200.60; IA 20,000 -> 40 units x $7.048 = $281.92; $482.52 + $2.81 = $485.33.
        # NPDES alone (manual 4.3.5.2): 7% x 100,000 = 7,000 GA; 7% x 20,000 = 1,400 IA.
        # Final GA 93,000 -> 186 units -> $186.558 -> $186.56; IA 18,600 -> 38 units ->
        # $267.824 -> $267.82; $454.38 + $2.81 = $457.19; reduction $28.14.
        c, g = self.big_site()
        c["assessment"]["records"] = [record("industrial_npdes")]
        alone = run(c, g)["economics"]
        self.assertEqual(alone["baseline"]["monthly_total"], 485.33)
        self.assertEqual(
            (
                alone["documented"]["ledger"]["new_ga_credit_sqft"],
                alone["documented"]["ledger"]["new_ia_credit_sqft"],
            ),
            (7000, 1400),
        )
        self.assertEqual(
            (
                alone["documented"]["bill"]["monthly_total"],
                alone["documented"]["gross_monthly_reduction"],
            ),
            (457.19, 28.14),
        )
        # Plus a 100 sq ft managed SMP: "Any remaining uncredited IA area will receive 7%
        # credit toward both the IA and GA square footage": 87 + 7% x (20,000 - 100) =
        # 87 + 1,393 = 1,480 to IA and to GA. Final GA 98,520 -> 198 units -> $198.594 ->
        # $198.59; IA 18,520 -> 38 units -> $267.82; $466.41 + $2.81 = $469.22; reduction
        # $16.11. The GA credit falls 7,000 -> 1,480 and the bill rises above NPDES alone:
        # reported as a manual rule discontinuity, not hidden.
        m = record("permeable_pavement")
        m["geometry"] = m["footprint_geometry"] = mapping(box(0, 0, 0.3048, 30.48))
        m["managed_area_sqft"] = 100
        c["assessment"]["records"] = [m, record("industrial_npdes", "permit")]
        both = run(c, g)["economics"]["documented"]
        self.assertAlmostEqual(both["ledger"]["new_ga_credit_sqft"], 1480, places=4)
        self.assertAlmostEqual(both["ledger"]["new_ia_credit_sqft"], 1480, places=4)
        self.assertEqual(
            (both["bill"]["monthly_total"], both["gross_monthly_reduction"]), (469.22, 16.11)
        )
        note = both["manual_rule_discontinuity"]
        self.assertEqual(note["kind"], "manual_rule_discontinuity")
        self.assertEqual(
            (note["npdes_alone_monthly_total"], note["scenario_monthly_total"]), (457.19, 469.22)
        )
        self.assertTrue(note["bill_higher_than_npdes_alone"])
        self.assertAlmostEqual(note["scenario_ga_credit_sqft"], 1480, places=4)
        self.assertIn("manual 4.3.5.2", note["note"])

    def test_ia_credit_is_monotone_and_every_ga_drop_is_labelled(self):
        # IA: 0.87 M + 0.07 (20,000 - M) = 1,400 + 0.80 M >= 1,400 (NPDES alone). GA:
        # 0.87 M + 0.07 (20,000 - M) < 7,000 for M < 7,000, so each row carries the note.
        c, g = self.big_site()
        c["assessment"]["records"] = [record("industrial_npdes")]
        alone = run(c, g)["economics"]["documented"]["ledger"]
        for width in (0.3048, 3.048, 15.24):
            m = record("permeable_pavement")
            m["geometry"] = m["footprint_geometry"] = mapping(box(0, 0, width, 30.48))
            m["managed_area_sqft"] = width / 0.3048 * 100
            c["assessment"]["records"] = [m, record("industrial_npdes", "permit")]
            s = run(c, g)["economics"]["documented"]
            self.assertGreaterEqual(s["ledger"]["new_ia_credit_sqft"], alone["new_ia_credit_sqft"])
            self.assertLess(s["ledger"]["new_ga_credit_sqft"], alone["new_ga_credit_sqft"])
            self.assertIn("manual_rule_discontinuity", s)

    def test_table_a2_open_space_credit_replaces_the_seven_percent_on_open_space(self):
        # 10,000 GA / 8,000 IA / 2,000 lawn. NPDES alone: GA 700, IA 560. Baseline $135.64;
        # final GA 9,300 -> 19 units -> $19.057 -> $19.06; IA 7,440 -> 15 units -> $105.72;
        # $124.78 + $2.81 = $127.59 (reduction $8.05). Table A-2 NPDES column read
        # literally: CN >= 75 is 0.00 (no credit, so 7% of all GA/IA applies); CN 74 is
        # 4.35%: 87 GA + 7% x 8,000 uncredited IA = 560 -> GA 647 < 700 (labelled
        # discontinuity); CN 70 is 21.75%: 435 + 560 = 995. Each bill rounds to $127.59:
        # GA 9,353 or 9,005 -> 19 units, IA 7,440 -> 15 units.
        for cn, expected_ga, note in ((75, 700, False), (74, 647, True), (70, 995, False)):
            c, g, lawn = mixed_site()
            c["assessment"]["records"] = [record("industrial_npdes")]
            c["benefits"] = [
                {
                    "id": "open",
                    "category": "open_space",
                    "geometry": lawn,
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
                        "curve_number": cn,
                    },
                }
            ]
            s = run(c, g)["economics"]["documented"]
            self.assertAlmostEqual(s["ledger"]["new_ga_credit_sqft"], expected_ga, places=4)
            self.assertAlmostEqual(s["ledger"]["new_ia_credit_sqft"], 560, places=4)
            self.assertEqual(
                (s["bill"]["monthly_total"], s["gross_monthly_reduction"]), (127.59, 8.05)
            )
            self.assertEqual("manual_rule_discontinuity" in s, note, cn)


class ManagedDrainageAreaTests(unittest.TestCase):
    def smp(self, category="permeable_pavement", geometry=None, **facts):
        c, g, lawn = mixed_site()
        r = record(category)
        r["geometry"] = geometry or mapping(box(21.336, 0, 27.432, 30.48))
        r["managed_area_sqft"] = 2000
        if geometry is not None:
            r["managed_area_sqft"] = None
        with_facts(r, **facts)
        c["assessment"]["records"] = [r]
        return run(c, g)

    def test_smp_drainage_area_with_lawn_credits_its_impervious_part(self):
        # Review B3 (repro policy/managed_da.py): 1,000 sq ft roof + 1,000 sq ft lawn.
        # IA credit = GA credit = 80% x 1,000 = 800 (manual 4.3.5.1). Baseline $135.64.
        # Final GA 9,200 -> 19 units -> $19.06; IA 7,200 -> 15 units -> $105.72;
        # $124.78 + $2.81 = $127.59; reduction $8.05. The lawn needs sizing/pre-approval.
        out = self.smp()
        entry = out["categories"][1]["records"][0]
        self.assertEqual(entry["status"], "screen_pass", entry)
        self.assertAlmostEqual(entry["managed_ia_sqft"], 1000, places=4)
        self.assertAlmostEqual(entry["managed_open_space_sqft"], 1000, places=4)
        self.assertEqual(entry["open_space_credit"]["status"], "missing_evidence")
        s = out["economics"]["documented"]
        self.assertAlmostEqual(s["ledger"]["new_ia_credit_sqft"], 800, places=4)
        self.assertAlmostEqual(s["ledger"]["new_ga_credit_sqft"], 800, places=4)
        self.assertEqual((s["bill"]["monthly_total"], s["gross_monthly_reduction"]), (127.59, 8.05))

    def test_preapproved_sized_smp_also_credits_open_space(self):
        # Manual 4.3.3.1 note: open space managed by an SMP sized for it, with design-phase
        # pre-approval, may receive 80%: GA 800 + 800 = 1,600. Final GA 8,400 -> 17 units ->
        # $17.051 -> $17.05; IA 7,200 -> $105.72; $122.77 + $2.81 = $125.58; reduction $10.06.
        s = self.smp(open_space_smp_sizing_confirmed=True, open_space_design_preapproval=True)[
            "economics"
        ]["documented"]
        self.assertAlmostEqual(s["ledger"]["new_ga_credit_sqft"], 1600, places=4)
        self.assertEqual(
            (s["bill"]["monthly_total"], s["gross_monthly_reduction"]), (125.58, 10.06)
        )

    def test_direct_discharge_drainage_area_credits_open_space_at_ninety_percent(self):
        # Manual 4.3.3.1 note + 4.3.5.3: IA 90% x 1,000 = 900; GA 900 + 90% x 1,000 lawn = 1,800.
        # Final GA 8,200 -> 17 units -> $17.05; IA 7,100 -> 15 units -> $105.72; $125.58; $10.06.
        s = self.smp("direct_discharge")["economics"]["documented"]
        self.assertAlmostEqual(s["ledger"]["new_ia_credit_sqft"], 900, places=4)
        self.assertAlmostEqual(s["ledger"]["new_ga_credit_sqft"], 1800, places=4)
        self.assertEqual(
            (s["bill"]["monthly_total"], s["gross_monthly_reduction"]), (125.58, 10.06)
        )

    def test_ga_only_open_space_direct_discharge(self):
        # Review R17: open space alone discharging directly to a water body, 90% GA only
        # (manual 4.3.3.1 note). GA 90% x 2,000 = 1,800 -> final GA 8,200 -> $17.05; IA
        # unchanged 8,000 -> $112.77; $129.82 + $2.81 = $132.63; reduction $3.01.
        out = self.smp("direct_discharge", geometry=mapping(box(24.384, 0, 30.48, 30.48)))
        entry = out["categories"][2]["records"][0]
        s = out["economics"]["documented"]
        self.assertEqual(entry["status"], "screen_pass", entry)
        self.assertAlmostEqual(s["ledger"]["new_ia_credit_sqft"], 0, places=4)
        self.assertAlmostEqual(s["ledger"]["new_ga_credit_sqft"], 1800, places=4)
        self.assertEqual((s["bill"]["monthly_total"], s["gross_monthly_reduction"]), (132.63, 3.01))

    def test_existing_allocation_may_span_ia_and_credited_open_space(self):
        # An approved 2,000 sq ft direct-discharge drainage area: 900 IA + 1,800 GA credits.
        c, g, _ = mixed_site()
        c["baseline"].update(
            existing_ga_credit_sqft=1800,
            existing_ia_credit_sqft=900,
            existing_credits_spatially_reconciled=True,
        )
        c["assessment"]["existing_credit_allocations"] = [
            {
                "id": "prior",
                "category": "direct_discharge",
                "geometry": mapping(box(21.336, 0, 27.432, 30.48)),
                "facts": {"approved_ledger_confirmed": True},
                "evidence_refs": [{"source_url": "https://example.test/invented-ledger"}],
                "ga_credit_sqft": 1800,
                "ia_credit_sqft": 900,
                "iar_sqft": 0,
            }
        ]
        c["assessment"]["records"] = [record("industrial_npdes")]
        s = run(c, g)["economics"]["documented"]
        # NPDES uplift (4.3.5.4): IA 97% x 1,000 = 970; GA 970 + 97% x 1,000 = 1,940. Residual
        # (4.3.5.2, literal): 7% x (8,000 - 1,000 managed IA) = 490 toward IA and toward GA.
        self.assertEqual(s["status"], "calculated", s.get("reasons"))
        self.assertAlmostEqual(s["ledger"]["new_ia_credit_sqft"] + 900, 970 + 490, places=4)
        self.assertAlmostEqual(s["ledger"]["new_ga_credit_sqft"] + 1800, 1940 + 490, places=4)


class NpdesDatesTests(unittest.TestCase):
    def npdes(self, **facts):
        c, g = fixture()
        r = with_facts(record("industrial_npdes"), **facts)
        c["assessment"]["records"] = [r]
        out = run(c, g)
        return out["categories"][3]["records"][0], out["economics"]["documented"]

    def test_lagging_dmr_period_is_missing_evidence_not_failure(self):
        # Review B7 (repro policy/renew_npdes.py): DMR period ending 2026-09-30, assessed 2026-11-15.
        entry, s = self.npdes(compliance_through="2026-09-30")
        self.assertEqual(entry["status"], "missing_evidence")
        self.assertNotIn("compliance_through", entry["failed"])
        self.assertIn("next_dmr_due", entry["missing"])
        self.assertIn("compliance_through", entry["needs_update"])
        self.assertIsNone(s["gross_monthly_reduction"])

    def test_lagging_period_within_reporting_cycle_passes(self):
        # NPDES alone on 10,000/10,000: 700 GA and IA. Baseline GA $20.06 + IA 20 units
        # $140.96 = $161.02 + $2.81 = $163.83. Final 9,300 each -> 19 units: $19.06 +
        # $133.912 -> $133.91 = $152.97 + $2.81 = $155.78; reduction $8.05.
        entry, s = self.npdes(compliance_through="2026-09-30", next_dmr_due="2027-03-31")
        self.assertEqual(entry["status"], "screen_pass", entry)
        self.assertEqual((s["bill"]["monthly_total"], s["gross_monthly_reduction"]), (155.78, 8.05))
        entry, _ = self.npdes(compliance_through="2026-09-30", next_dmr_due="2026-10-28")
        self.assertIn("compliance_through_current", entry["missing"])
        self.assertEqual(entry["status"], "missing_evidence")

    def test_expired_permit_needs_administrative_continuation_evidence(self):
        entry, _ = self.npdes(expires_on="2026-10-01")
        self.assertEqual(entry["status"], "missing_evidence")
        self.assertIn("administratively_continued", entry["missing"])
        entry, s = self.npdes(expires_on="2026-10-01", administratively_continued=True)
        self.assertEqual(entry["status"], "screen_pass", entry)
        self.assertEqual(s["gross_monthly_reduction"], 8.05)
        entry, _ = self.npdes(expires_on="2026-10-01", administratively_continued=False)
        self.assertIn("expires_on", entry["failed"])
        # 25 Pa. Code 92a.75(a): reissuance application at least 180 days before expiry
        # (2026-10-01 - 180 days = 2026-04-04) unless DEP permitted a later date.
        entry, _ = self.npdes(
            expires_on="2026-10-01",
            administratively_continued=True,
            renewal_application_submitted_on="2026-06-01",
        )
        self.assertIn("renewal_application_submitted_on", entry["failed"])
        entry, _ = self.npdes(
            expires_on="2026-10-01",
            administratively_continued=True,
            renewal_application_submitted_on="2026-03-01",
        )
        self.assertEqual(entry["status"], "screen_pass")

    def test_lagging_period_no_longer_blocks_the_permit_what_if(self):
        from test_modeled_assessment_unit import fixture as m_fixture, record as m_record, assess

        c = m_fixture()
        c["assessment"]["records"] = [
            m_record(
                "permit",
                "industrial_npdes",
                facts={"permit_id": "SYNTHETIC-ONLY", "compliance_through": "2026-09-30"},
            )
        ]
        s = assess(c)["modeled_integration"]["permit_scenarios"][0]
        self.assertEqual(s["status"], "calculated")
        self.assertIn("next_dmr_due", s["assumed_prerequisites"])


class RenewalStatusTests(unittest.TestCase):
    SOURCE = {"source_url": "https://example.test/x"}

    def test_future_termination_expired_and_effective_only_award(self):
        # Review B9 (repro policy/renew_npdes.py), assessed 2026-11-15.
        # 2026-11-15 -> 2027-03-01: 15 + 31 + 31 + 28 + 1 = 106 days.
        r = credit_renewals(
            [
                {
                    "id": "a",
                    "status": "terminated",
                    "effective_from": "2024-01-01",
                    "terminated_on": "2027-03-01",
                    **self.SOURCE,
                }
            ],
            as_of="2026-11-15",
        )[0]
        self.assertEqual(
            (r["status"], r["deadline"], r["days_remaining"]),
            ("termination_scheduled", "2027-03-01", 106),
        )
        r = credit_renewals(
            [
                {
                    "id": "b",
                    "status": "expired",
                    "effective_from": "2021-01-01",
                    "expires_on": "2025-01-01",
                    **self.SOURCE,
                }
            ],
            as_of="2026-11-15",
        )[0]
        self.assertEqual((r["status"], r["deadline"]), ("expired", "2025-01-01"))
        self.assertFalse(any("unexplained" in w for w in r["warnings"]))
        # Effective 2024-01-01 + four-year term (tariff 4.5(f)(4)) -> no later than 2028-01-01;
        # 2026-11-15 -> 2028-01-01 = 365 + 47 = 412 days, beyond the 90-day reminder lead.
        r = credit_renewals(
            [{"id": "c", "status": "awarded", "effective_from": "2024-01-01", **self.SOURCE}],
            as_of="2026-11-15",
        )[0]
        self.assertEqual(
            (r["status"], r["deadline"], r["days_remaining"]), ("current", "2028-01-01", 412)
        )
        self.assertIn("no_later_than", r["deadline_basis"])


class UnknownStatusAndAllocationTests(unittest.TestCase):
    def test_public_record_leaves_undeveloped_and_allocation_unknown(self):
        data = {
            "Parcel": {
                "GrossArea": 4000,
                "ImpervArea": 0,
                "GrossCredit": 0,
                "ImpervCredit": 0,
                "BldgType": "NonRes",
            },
            "ChargeSummary": {
                "ParcelAccounts": [{"YearlyAccountCharges": []}, {"YearlyAccountCharges": []}]
            },
        }
        b = normalize_billing(data)
        self.assertIsNone(b["undeveloped"])
        self.assertEqual([a["allocation"] for a in b["accounts"]], [None, None])
        self.assertEqual(b["account_allocation_status"], "unknown")
        self.assertTrue(normalize_billing({**data, "undeveloped": True})["undeveloped"])

    def test_vacant_lot_shows_both_statutory_alternatives(self):
        # Decision D6 / review B10. GA 4,000 -> 8 units x $1.003 = $8.024 -> $8.02.
        # Developed (85%): IA 3,400 -> 7 units x $7.048 = $49.336 -> $49.34; $57.36 + $2.81 = $60.17.
        # Undeveloped (25%, tariff 1.0(p)): IA 1,000 -> 2 units -> $14.096 -> $14.10;
        # $22.12 >= $20.89, so $22.12 + $2.81 = $24.93.
        out = ledger({"ga_sqft": 4000, "ia_sqft": 0, "bill_date": "2026-11-15"})
        base = out["baseline"]
        self.assertEqual(base["status"], "unverified_alternatives")
        self.assertIsNone(base["monthly_total"])
        self.assertEqual(
            (
                base["alternatives"]["developed"]["monthly_total"],
                base["alternatives"]["undeveloped"]["monthly_total"],
            ),
            (60.17, 24.93),
        )
        self.assertEqual(out["measurement_only"]["status"], "blocked")
        self.assertIn("alternatives", out["measurement_only"])

    def test_immaterial_unknown_status_keeps_one_bill(self):
        # GA 100: 85 or 25 sq ft both round to one IA unit; $1.00 + $7.05 < $20.89 -> $23.70.
        out = ledger({"ga_sqft": 100, "ia_sqft": 0})
        self.assertEqual(out["baseline"]["monthly_total"], 23.70)
        self.assertEqual(out["undeveloped_status"]["status"], "unknown_immaterial")

    def test_assessment_ledger_also_shows_alternatives(self):
        c, g = fixture()
        c["baseline"].update(ga_sqft=4000, ia_sqft=0)
        econ = run(c, g)["economics"]
        self.assertEqual(econ["baseline"]["status"], "unverified_alternatives")
        self.assertEqual(econ["baseline"]["alternatives"]["undeveloped"]["monthly_total"], 24.93)

    def test_unknown_allocation_uses_labelled_equal_default(self):
        # Tariff 4.3(a)(8) default: $132.83 / 2 = $66.415 -> $66.42 each; 2 x ($66.42 + $2.81) = $138.46.
        out = ledger(
            {
                "ga_sqft": 10000,
                "ia_sqft": 8000,
                "accounts": [{"allocation": None}, {"allocation": None}],
            }
        )
        self.assertEqual(out["baseline"]["monthly_total"], 138.46)
        self.assertEqual(out["baseline"]["allocation_status"]["status"], "unknown")
        self.assertIn("Account allocation unknown", out["baseline"]["allocation_status"]["note"])
        partial = ledger(
            {
                "ga_sqft": 10000,
                "ia_sqft": 8000,
                "accounts": [{"allocation": 0.5}, {"allocation": None}],
            }
        )
        self.assertIsNone(partial["baseline"])
        self.assertIn("partial", " ".join(partial["documented"]["reasons"]))

    def test_unknown_allocation_flags_minimum_sensitivity(self):
        # $26.14 / 2 = $13.07 per account < $20.89: 2 x $23.70 = $47.40, allocation-sensitive
        # (ported from calculate_scenarios into the live ledger, fix 9).
        out = ledger(
            {
                "ga_sqft": 6000,
                "ia_sqft": 1000,
                "accounts": [{"allocation": None}, {"allocation": None}],
            }
        )
        self.assertEqual(out["baseline"]["monthly_total"], 47.40)
        self.assertTrue(out["allocation_sensitive"])
        self.assertTrue(out["baseline"]["allocation_sensitive"])
        self.assertTrue(any("per-account minimum" in a for a in out["baseline"]["assumptions"]))
        # A known allocation is not flagged: 0.5 / 0.5 recorded.
        known = ledger(
            {
                "ga_sqft": 6000,
                "ia_sqft": 1000,
                "accounts": [{"allocation": 0.5}, {"allocation": 0.5}],
            }
        )
        self.assertNotIn("allocation_sensitive", known)


class BilledAreaCheckTests(unittest.TestCase):
    def test_pwd_billed_area_mismatch_is_visible(self):
        # Review G1: GA 10,000 and IA 8,000 bill as 10,000 and 8,000 sq ft (exact units).
        base = {"ga_sqft": 10000, "ia_sqft": 8000, "billed_ga_sqft": 10000, "billed_ia_sqft": 8000}
        self.assertEqual(ledger(base)["billed_area_check"]["status"], "consistent")
        out = ledger({**base, "billed_ia_sqft": 7500})
        self.assertEqual(out["billed_area_check"]["status"], "mismatch")
        self.assertIn("PWD billed area differs", out["billed_area_check"]["warning"])
        c, g = fixture()
        c["baseline"].update(billed_ga_sqft=10000, billed_ia_sqft=7500)
        flags = run(c, g)["historical_flags"]
        self.assertEqual([f["kind"] for f in flags], ["billed_area_discrepancy"])
        self.assertIsNone(flags[0]["refund_entitlement"])

    def test_adapter_warns_on_mismatch(self):
        from test_jurisdiction_adapter import fixture as j_fixture
        from stormwater.jurisdictions.philadelphia import apply

        case, gis, policy = j_fixture()
        policy["baseline"].update(billed_ga_sqft=10000, billed_ia_sqft=9000)
        result = apply(case, gis, policy, as_of="2026-11-15")
        self.assertTrue(any("PWD billed area differs" in w for w in result["warnings"]))


class OneLedgerTests(unittest.TestCase):
    def test_report_table_and_ledger_agree(self):
        # Review B6 / decision D7 (repro policy/two_engines.py): one answer, not two.
        c, _, lawn = mixed_site()
        c["baseline"].update(
            existing_ia_credit_sqft=800,
            existing_ga_credit_sqft=800,
            existing_credits_spatially_reconciled=True,
        )
        c["benefits"] = [
            {
                "id": "open",
                "category": "open_space",
                "geometry": lawn,
                "area_sqft": 2000,
                "basis": "documented",
                "existing_overlap_reconciled": True,
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
        g = analyze(c)
        from stormwater.jurisdictions.philadelphia import apply

        with patch("stormwater.renewals.today", lambda: date(2026, 11, 15)):
            out = apply(c, g)
        b = out["billing"]["documented_credit_only"]
        a = out["assessment"]["economics"]["documented"]
        self.assertEqual(
            (b["status"], b["monthly_savings"]), (a["status"], a["gross_monthly_reduction"])
        )
        self.assertEqual(b["status"], "blocked")

    def test_calculated_rows_are_ledger_rows(self):
        # Canopy 1,100 sq ft -> IAR 550 -> IA 9,450 -> 19 units x $7.048 = $133.912 -> $133.91;
        # GA $20.06; $153.97 + $2.81 = $156.78 against $163.83: $7.05.
        from test_jurisdiction_adapter import fixture as j_fixture
        from stormwater.jurisdictions.philadelphia import apply

        case, gis, policy = j_fixture()
        result = apply(case, gis, policy, as_of="2026-11-15")
        row = result["billing"]["credit_only"]
        ledger = result["assessment"]["economics"]["modeled"]
        self.assertEqual((row["monthly_total"], row["monthly_savings"]), (156.78, 7.05))
        self.assertEqual(
            (ledger["bill"]["monthly_total"], ledger["gross_monthly_reduction"]), (156.78, 7.05)
        )
        self.assertEqual(row["ledger_scenario"], "modeled")


class KnownFalsePrerequisiteTests(unittest.TestCase):
    def setUp(self):
        import warnings

        warnings.simplefilter("ignore")

    def test_known_false_account_blocks_every_alternative(self):
        # Review R1 (repro second/account_and_rejection.py #1).
        from test_modeled_assessment_unit import (
            fixture as m_fixture,
            candidate,
            fake_research,
            frozen_gis,
            assess,
        )

        c = m_fixture()
        c["baseline"]["account_current"] = False
        c["features"]["features"] = [candidate("canopy", box(0, 0, 30.48, 30.48))]
        rows = assess(c)["modeled_integration"]["canopy_scenarios"]
        self.assertTrue(
            rows
            and all(r["status"] == "blocked" and r["gross_annual_reduction"] is None for r in rows)
        )
        self.assertTrue(any("account_current" in x for x in rows[1]["reasons"]))
        c = m_fixture()
        c["baseline"]["account_current"] = False
        rows = assess(c, frozen_gis(c, fake_research(c)))["modeled_integration"][
            "catchment_scenarios"
        ]
        self.assertTrue(rows and all(r["status"] == "blocked" for r in rows))

    def test_record_level_false_account_reaches_generic_and_record_paths(self):
        from test_modeled_assessment_unit import (
            fixture as m_fixture,
            record as m_record,
            fake_research,
            frozen_gis,
            assess,
        )

        c = m_fixture()
        c["assessment"]["records"] = [
            m_record(category="green_roof", facts={"account_current": False}),
            m_record("other", category="green_roof", x=15.24),
        ]
        r = assess(c, frozen_gis(c, fake_research(c)))["modeled_integration"]
        values = (
            [s for info in r["records"] for run_ in info["runs"] for s in run_["scenarios"]]
            + r["catchment_scenarios"]
            + r["combined"]
        )
        self.assertTrue(values)
        self.assertFalse(any(v["status"] == "calculated" for v in values))

    def test_research_scenarios_honour_known_false_account(self):
        from test_research_drainage import fixture as r_fixture

        c = r_fixture()
        c["baseline"] = {
            "ga_sqft": 6000,
            "ia_sqft": 5001,
            "bill_date": "2026-09-01",
            "property_type": "NonRes",
        }
        c["terrain"]["settings"]["extent_sufficient"] = True
        before = evaluate_assessment(c, analyze(c), as_of="2026-11-15")[
            "research_drainage_scenarios"
        ]["scenarios"][0]
        self.assertEqual(before["status"], "calculated")
        c["baseline"]["account_current"] = False
        after = evaluate_assessment(c, analyze(c), as_of="2026-11-15")[
            "research_drainage_scenarios"
        ]["scenarios"]
        self.assertTrue(
            all(
                s["status"] == "blocked" and any("account_current" in x for x in s["reasons"])
                for s in after
            )
        )

    def test_documented_ledger_honours_baseline_account_fact(self):
        c, g = fixture()
        c["baseline"]["account_current"] = False
        c["assessment"]["records"] = [record()]
        s = run(c, g)["economics"]["documented"]
        self.assertEqual(s["status"], "blocked")
        self.assertTrue(any("account_current" in x for x in s["reasons"]))

    def test_rejected_record_receiver_is_not_repriced_as_unassigned(self):
        # Review R2 (repro second/account_and_rejection.py #2).
        from test_modeled_assessment_unit import (
            fixture as m_fixture,
            record as m_record,
            fake_research,
            frozen_gis,
            assess,
        )

        c = m_fixture()
        c["assessment"]["records"] = [
            m_record(gsi_id="G1", decision="rejected", facts={"existing_installation": False})
        ]
        r = assess(c, frozen_gis(c, fake_research(c)))["modeled_integration"]
        rows = r["catchment_scenarios"]
        self.assertTrue(rows and all(v["status"] == "blocked" for v in rows))
        self.assertTrue(
            all(
                any("manually rejected" in x for x in v["reasons"])
                for v in rows
                if v["receiver_id"] == "G1"
            )
        )
        self.assertFalse(any(v["receiver_id"] == "all_unassigned_gsi" for v in rows))
        info = next(i for i in r["records"] if i["record_id"] == "r")
        self.assertEqual(info["status"], "rejected")
        self.assertIn("G1", info["linked_receiver_ids"]["nominal"])


if __name__ == "__main__":
    unittest.main()
