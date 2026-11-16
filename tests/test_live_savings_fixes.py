"""Final LIVE-SAVINGS review fixes (2026-11-16): regressions built from frozen live shapes.

Fixtures under ``tests/fixtures`` are trimmed copies of public records seen in the live
cases; no network. Dollar expectations are derived by hand in comments.
"""

from copy import deepcopy
import json
from pathlib import Path
import unittest
from unittest.mock import patch

from shapely.geometry import box, mapping

from stormwater.assessment_sources import discover, normalize_permit
from stormwater.permits import address_key, permit_classification, permit_site_match
from test_modeled_assessment_unit import assess, fixture

FIXTURES = Path(__file__).resolve().parent / "fixtures"
ECHO = json.loads((FIXTURES / "permits" / "echo-rows-2026-11-16.json").read_text())
URL = "https://echodata.epa.gov/echo/cwa_rest_services.get_qid?invented=1"


def permit_records(*cases):
    return [
        normalize_permit(row, URL, {}) for case in cases for row in ECHO["rows"][case]
    ]


def permit_case(address, records):
    c = fixture()
    c["address"] = address
    c["assessment"]["records"] = deepcopy(records)
    return c


def scenarios(c):
    return {s["permit_id"]: s for s in assess(c)["modeled_integration"]["permit_scenarios"]}


class PermitClassificationAndAddressTests(unittest.TestCase):
    def test_permit_program_classes(self):
        for pid, cls in [
            ("PAD510200", "construction_stormwater"),
            ("PAC510165", "construction_stormwater"),
            ("PAG020000", "construction_stormwater"),
            ("PAR900005", "industrial_stormwater"),
            ("PAG030110", "industrial_stormwater"),
            ("PA0054241", "unclassified"),
        ]:
            with self.subTest(pid=pid):
                self.assertEqual(permit_classification(pid)["class"], cls)
        # Discovery records construction coverage as a known-false industrial prerequisite.
        record = permit_records("pwd-98627")[0]
        self.assertEqual(record["facts"]["permit_type"], "construction")

    def test_address_normalization(self):
        self.assertEqual(address_key("3107 SOUTH 61ST STREET"), address_key("3107 S 61ST ST"))
        self.assertEqual(address_key("3350 S. 61 ST"), (3350, 3350, "S 61"))
        self.assertEqual(address_key("1001-99 N DELAWARE AVE"), (1001, 1099, "N DELAWARE"))
        self.assertEqual(address_key("8000 CHEROKEE ST."), address_key("8000 CHEROKEE ST"))
        self.assertIsNone(address_key("SCHUYLKILL RIVER TRAIL"))

    def test_range_parcel_does_not_match_neighbouring_numbers(self):
        c = fixture()
        c["address"] = "1001-99 N DELAWARE AVE"
        outside = {"facts": {"public_street_address": "1121 NORTH DELAWARE AVENUE"}}
        inside = {"facts": {"public_street_address": "1050 N DELAWARE AVE"}}
        self.assertEqual(permit_site_match(outside, c)["status"], "not_matched")
        self.assertEqual(permit_site_match(inside, c)["status"], "matched")


class PermitWhatIfTests(unittest.TestCase):
    def test_whitaker_construction_permit_has_no_dollar_row(self):
        # Live: PAD510200 (5300 Whitaker Ave redevelopment) was priced at $2,620.32/yr.
        s = scenarios(permit_case("5300 WHITAKER AVE", permit_records("pwd-98627")))
        row = s["PAD510200"]
        self.assertEqual(row["site_match"], "matched")
        self.assertEqual(row["status"], "not_applicable")
        self.assertEqual(row["listing"], "not_applicable_construction")
        self.assertIsNone(row["gross_annual_reduction"])
        self.assertIn("manual 4.3.4", row["reasons"][0])

    def test_3107_facility_is_not_priced_at_3060(self):
        # Live: 3060 S 61st St priced PAR900005 (Delaware Valley Recycling, 3107 S 61st St).
        s = scenarios(permit_case("3060 S 61ST ST", permit_records("pwd-538963")))
        self.assertEqual(s["PAR900005"]["listing"], "nearby_not_matched")
        self.assertEqual(s["PAR900005"]["status"], "not_matched")
        self.assertEqual(s["PAD510018"]["listing"], "not_applicable_construction")
        self.assertFalse(any(v["status"] == "calculated" for v in s.values()))

    def test_3107_prices_its_own_permit_once_and_lists_neighbours(self):
        records = permit_records("pwd-124343", "pwd-538963")
        s = scenarios(permit_case("3107 S 61ST ST", records))
        priced = [k for k, v in s.items() if v["status"] == "calculated"]
        self.assertEqual(priced, ["PAR900005"])
        self.assertEqual(s["PAR900005"]["listing"], "priced")
        for nearby in ("PAR900017", "PAG030177", "PAR600066", "PAG030173"):
            self.assertEqual(s[nearby]["listing"], "nearby_not_matched")
        for construction in ("PAD510059", "PAD510018"):
            self.assertEqual(s[construction]["status"], "not_applicable")

    def test_one_industrial_what_if_per_property(self):
        # Brewster: PAG030110 (7575 Brewster Ave) is the one matched industrial permit; a
        # second matched industrial record is listed, not priced again.
        records = permit_records("pwd-190490")
        extra = deepcopy(next(r for r in records if r["facts"]["permit_id"] == "PAG030110"))
        extra.update(id="epa-second")
        extra["facts"]["permit_id"] = "PAR999999"
        s = scenarios(permit_case("7575 BREWSTER AVE", records + [extra]))
        self.assertEqual([k for k, v in s.items() if v["status"] == "calculated"], ["PAG030110"])
        self.assertEqual(s["PAR999999"]["listing"], "another_permit_priced")
        self.assertEqual(s["PAC510165"]["listing"], "not_applicable_construction")


class PermitDiscoveryTests(unittest.TestCase):
    def test_address_query_finds_the_on_site_permit_outside_the_box(self):
        rows_address = [r for r in ECHO["rows"]["pwd-538963"]]
        rows_box = ECHO["rows"]["pwd-124343"]
        seen = []

        class Cache:
            def fetch_json(self, url, *args, **kwargs):
                seen.append(url)
                if "/details" in url:
                    return {"data": {"Parcel": {"Address": "3107 S 61ST ST"}}, "provenance": {}}
                if "get_facilities" in url:
                    rows = rows_address if "p_sa=" in url else rows_box
                    return {
                        "data": {"Results": {"QueryRows": str(len(rows)), "Facilities": rows}},
                        "provenance": {"sha256": "e" * 64, "url": url},
                    }
                raise OSError("city layer offline")

            def _read(self, url):
                return None

        c = fixture()
        c["id"] = "pwd-124343"
        c["parcel"] = mapping(box(480000, 4417000, 480200, 4417200))
        result = discover(c, Cache())
        echo = [u for u in seen if "get_facilities" in u]
        self.assertEqual(len(echo), 2)
        self.assertIn("p_sa=3107+S+61ST+ST", echo[0])
        self.assertIn("p_c1lat", echo[1])
        by_id = {r["facts"]["permit_id"]: r for r in result["records"]}
        self.assertEqual(by_id["PAR900005"]["site_match_screen"]["status"], "matched")
        self.assertEqual(by_id["PAR900017"]["site_match_screen"]["status"], "not_matched")
        self.assertEqual(
            by_id["PAD510018"]["permit_classification"]["class"], "construction_stormwater"
        )
        statuses = {s["provider"]: s["status"] for s in result["source_status"]}
        self.assertEqual(statuses["EPA NPDES"], "retrieved")
        self.assertEqual(statuses["PWD account/credit public record"], "retrieved")


def system_feature(sid="62571", geometry=None, **props):
    return {
        "type": "Feature",
        "id": "public-system_footprint-" + sid,
        "geometry": mapping(geometry or box(0, 0, 3.048, 30.48)),
        "properties": {
            "kind": "system_footprint",
            "layer": "footprint",
            "gsi_system_id": sid,
            "gsi_system_type": "Rain Garden",
            "project_type": "Private - Regulations",
            "project_number": "2014-INVT-0001-01",
            "year_installed": 2015,
            "status": None,
            "source_url": "https://example.test/GSI_SMP_TYPES",
            **props,
        },
    }


def lead_case(*features, **baseline):
    c = fixture()
    c["baseline"].update({"existing_ga_credit_sqft": 0, "existing_ia_credit_sqft": 0, **baseline})
    c["features"]["features"].extend(features)
    return c


class ExistingSystemLeadTests(unittest.TestCase):
    def test_on_parcel_system_is_a_pcsmp_lead_without_a_figure(self):
        off = system_feature("70000", box(40, 40, 45, 45))  # outside the parcel
        out = assess(lead_case(system_feature(), off))
        leads = out["existing_system_management"]
        self.assertEqual([s["system_id"] for s in leads["systems"]], ["62571"])
        lead = leads["systems"][0]
        self.assertEqual(lead["lead_status"], "lead_request_pcsmp")
        self.assertEqual(lead["lead_label"], "lead: request PCSMP")
        self.assertIsNone(lead["figure"])
        self.assertAlmostEqual(lead["on_parcel_footprint_sqft"], 1000)
        self.assertTrue(lead["priority"])
        self.assertIn("2014-INVT-0001-01", lead["request"])
        self.assertTrue(any("PCSMP" in e for e in lead["evidence_needed"]))
        self.assertEqual(
            [s["system_id"] for s in out["systems_without_recorded_credit"]], ["62571"]
        )

    def test_documented_managed_area_is_priced_as_management(self):
        # Fixture: GA 10,000 / IA 10,000 -> 20 x $1.003 = $20.06 + 20 x $7.048 = $140.96;
        # $161.02 + $2.81 = $163.83. Documented IA Managed 5,000 (manual 4.3.5.1): IA credit
        # 80% = 4,000 and GA credit 4,000 -> GA 6,000 = 12 x $1.003 = $12.036 -> $12.04;
        # IA 6,000 = 12 x $7.048 = $84.576 -> $84.58; $96.62 + $2.81 = $99.43.
        # Reduction $64.40/month, $772.80/year.
        c = lead_case(system_feature())
        c["assessment"]["records"] = [
            {
                "id": "lead-62571",
                "category": "existing_system_management",
                "decision": "candidate",
                "basis": "public_candidate",
                "facts": {"gsi_system_id": "062571", "documented_managed_ia_sqft": 5000},
            }
        ]
        lead = assess(c)["existing_system_management"]["systems"][0]
        self.assertEqual(lead["record_id"], "lead-62571")
        self.assertEqual(lead["lead_status"], "priced_documented_area")
        self.assertEqual(lead["figure"]["status"], "calculated")
        self.assertEqual(lead["figure"]["bill"]["monthly_total"], 99.43)
        self.assertEqual(lead["figure"]["gross_annual_reduction"], 772.80)

    def test_recorded_credit_is_not_reported_as_uncredited(self):
        out = assess(lead_case(system_feature(), existing_ia_credit_sqft=800))
        leads = out["existing_system_management"]
        self.assertEqual(leads["recorded_credit_status"], "recorded_credits_unattributed")
        self.assertEqual(out["systems_without_recorded_credit"], [])
        self.assertEqual(leads["systems"][0]["lead_status"], "lead_request_pcsmp")

    def test_lead_does_not_take_over_the_modeled_catchment_alternative(self):
        from test_modeled_assessment_unit import fake_research, frozen_gis

        c = lead_case()
        c["assessment"]["records"] = [
            {
                "id": "lead-g1",
                "category": "existing_system_management",
                "decision": "candidate",
                "basis": "public_candidate",
                "facts": {"gsi_system_id": "G1"},
            }
        ]
        r = assess(c, frozen_gis(c, fake_research(c)))
        rows = r["modeled_integration"]["catchment_scenarios"]
        self.assertTrue(any(v["receiver_id"] == "G1" and v["status"] == "calculated" for v in rows))
        info = next(i for i in r["modeled_integration"]["records"] if i["record_id"] == "lead-g1")
        self.assertEqual(info["status"], "lead")

    def test_discovery_keeps_only_on_parcel_system_leads(self):
        from stormwater.assessment_sources import _on_parcel_leads, normalize_gsi
        from shapely.geometry import shape

        c = fixture()
        parcel = shape(c["parcel"])
        on = {"id": 1, "geometry": mapping(box(0, 0, 3.048, 30.48)), "properties": {
            "gsi_system_id": "62571", "gsi_system_type": "Subsurface Basin",
            "project_type": "Private - Regulations", "project_number": "2015-X-1-01"}}
        off = {**on, "id": 2, "geometry": mapping(box(40, 40, 45, 45))}
        found = []
        for feature in (on, off):
            found += _on_parcel_leads(normalize_gsi(feature, "u", c["crs"]), c, parcel)
        self.assertEqual([r["category"] for r in found], ["existing_system_management"])
        self.assertEqual(found[0]["facts"]["public_project_number"], "2015-X-1-01")
        self.assertAlmostEqual(found[0]["facts"]["on_parcel_footprint_sqft"], 1000)


class IaMeasurementRangeTests(unittest.TestCase):
    def test_both_cover_ends_use_the_measured_ga_and_are_calculated(self):
        # Live shape: recorded GA (9,000) below measured IA + unknown ground (10,000), which
        # blocked the impervious end with "Open-space allocations exceed..." on all 11 parcels.
        # Recorded bill: GA 18 x $1.003 = $18.054 -> $18.05; IA 16 x $7.048 = $112.768 ->
        # $112.77; $130.82 + $2.81 = $133.63.
        # High end (measured GA 10,000, IA 10,000): $20.06 + $140.96 + $2.81 = $163.83 ->
        # change -$30.20/month, -$362.40/year.
        # Low end (IA 0): GA $20.06 < $20.89 minimum -> $20.89 + $2.81 = $23.70 -> change
        # $109.93/month, $1,319.16/year.
        c = fixture()
        c["baseline"].update(ga_sqft=9000, ia_sqft=8000)
        s = assess(c)["modeled_integration"]["surface_scenario"]
        rng = s["ia_measurement_range"]
        self.assertEqual(rng["ga_source"], "measured parcel polygon")
        self.assertAlmostEqual(rng["measured_ga_sqft"], 10000)
        self.assertEqual(rng["high_end"]["status"], "calculated")
        self.assertEqual(rng["low_end"]["status"], "calculated")
        self.assertAlmostEqual(rng["high_end"]["ia_sqft"], 10000)
        self.assertEqual(rng["high_end"]["monthly_total"], 163.83)
        self.assertEqual(rng["high_end"]["annual_change"], -362.40)
        self.assertEqual(rng["low_end"]["monthly_total"], 23.70)
        self.assertEqual(rng["low_end"]["annual_change"], 1319.16)
        self.assertTrue(rng["recorded_ia_within_range"])
        self.assertIn("not an appeal", rng["presentation"])
        for row in s["area_alternatives"]:
            self.assertLessEqual(row["ia_sqft"], row["ga_sqft"])

    def test_unavailable_end_says_why(self):
        # Recorded aggregate credits (no itemized ledger) cannot be re-applied to a new
        # cover; the end is shown unavailable with the ledger's reason, not dropped.
        c = fixture()
        c["baseline"].update(
            ga_sqft=9000,
            ia_sqft=8000,
            existing_ga_credit_sqft=0,
            existing_ia_credit_sqft=4000,
            existing_iar_sqft=0,
        )
        rng = assess(c)["modeled_integration"]["surface_scenario"]["ia_measurement_range"]
        for side in ("low_end", "high_end"):
            self.assertEqual(rng[side]["status"], "blocked")
            self.assertIn("spatial reconciliation", rng[side]["unavailable_reason"])


class CanopyCapTests(unittest.TestCase):
    def test_hidden_ground_canopy_is_capped_by_recorded_ia(self):
        # Live shape (8000 Cherokee): identified IA + canopy-hidden ground exceeded the
        # recorded IA. Invented: 5,000 sq ft observed roof (identified IA), 5,000 sq ft of
        # canopy over unresolved ground, recorded IA 7,000. Cap = 7,000 - 5,000 = 2,000 sq ft
        # of hidden ground -> canopy IAR 50% = 1,000.
        # Baseline: GA 20 x $1.003 = $20.06; IA 14 x $7.048 = $98.672 -> $98.67;
        # $118.73 + $2.81 = $121.54. Capped: IA 6,000 -> 12 x $7.048 = $84.576 -> $84.58;
        # $104.64 + $2.81 = $107.45 -> $14.09/month, $169.08/year (uncapped would have used
        # 5,000 sq ft: IAR 2,500 -> IA 4,500 -> $86.30, $35.24/month).
        from test_modeled_assessment_unit import candidate

        c = fixture()
        c["baseline"]["ia_sqft"] = 7000
        c["features"]["features"] = [
            candidate("canopy", box(0, 0, 30.48, 15.24)),
            {
                "id": "roof",
                "geometry": mapping(box(0, 15.24, 30.48, 30.48)),
                "properties": {"layer": "surface", "class": "roof"},
            },
        ]
        rows = assess(c)["modeled_integration"]["canopy_scenarios"]
        hidden = next(r for r in rows if r["name"] == "hidden_ground_assumed_impervious")
        cap = hidden["recorded_ia_cap"]
        self.assertTrue(cap["applied"])
        self.assertAlmostEqual(cap["identified_ia_sqft"], 5000)
        self.assertAlmostEqual(cap["uncapped_area_sqft"], 5000)
        self.assertAlmostEqual(cap["credited_area_sqft"], 2000)
        self.assertAlmostEqual(hidden["area_sqft"], 2000)
        self.assertEqual(hidden["status"], "calculated")
        self.assertEqual(hidden["bill"]["monthly_total"], 107.45)
        self.assertEqual(hidden["gross_annual_reduction"], 169.08)
        self.assertIn(cap["label"], hidden["assumptions"])

    def test_no_room_left_blocks_with_a_reason(self):
        from test_modeled_assessment_unit import candidate

        c = fixture()
        c["baseline"]["ia_sqft"] = 5000  # equals the identified roof IA
        c["features"]["features"] = [
            candidate("canopy", box(0, 0, 30.48, 15.24)),
            {
                "id": "roof",
                "geometry": mapping(box(0, 15.24, 30.48, 30.48)),
                "properties": {"layer": "surface", "class": "roof"},
            },
        ]
        rows = assess(c)["modeled_integration"]["canopy_scenarios"]
        hidden = next(r for r in rows if r["name"] == "hidden_ground_assumed_impervious")
        self.assertEqual(hidden["status"], "blocked")
        self.assertIn("Recorded IA leaves no room", hidden["reasons"][0])


class ImageGreenRoofCandidateTests(unittest.TestCase):
    def test_saved_image_candidate_is_labelled_and_never_blocks_combined_rows(self):
        # Live (8000 Cherokee, 1001-99 N Delaware): combined rows were blocked by
        # "Overlapping physical allocations: image-roof-vegetation-...". Saved records
        # still carry basis public_candidate; the policy reads them as image candidates.
        from test_modeled_assessment_unit import record

        c = fixture()
        public = record("public-roof", "green_roof")
        image = record(
            "image-roof-vegetation-abc",
            "green_roof",
            facts={"existing_installation": None, "image_vegetation_candidate": True},
        )
        c["assessment"]["records"] = [public, image]
        out = assess(c)
        combined = out["modeled_integration"]["combined"]
        self.assertTrue(combined)
        for row in combined:
            self.assertFalse(
                any("Overlapping physical allocations" in r for r in row.get("reasons", []))
            )
            self.assertIn(
                "image-roof-vegetation-abc", [x["record_id"] for x in row["excluded_records"]]
            )
        roofs = next(cat for cat in out["categories"] if cat["category"] == "green_roof")
        bases = {r["id"]: r["basis"] for r in roofs["records"]}
        self.assertEqual(bases["image-roof-vegetation-abc"], "image_candidate")
        self.assertEqual(bases["public-roof"], "public_candidate")
        info = next(
            i for i in out["modeled_integration"]["records"]
            if i["record_id"] == "image-roof-vegetation-abc"
        )
        self.assertEqual(info["record_basis"], "image_candidate")


class CatchmentStorageCheckTests(unittest.TestCase):
    # Frozen pilot result for system 62571 (5300 Whitaker Ave, 2026-11-16): surface storage
    # 2.39-2.87 cu ft below the perimeter spill level, flag vertical_unit_status_unrecorded.
    PILOT_62571 = {
        "version": "frozen-pilot",
        "status": "estimated",
        "storage_range_cuft": [2.3862877914026983, 2.8719966287712815],
        "storage_range_scenarios": ["perimeter_cell_minimum", "perimeter_bilinear"],
        "review_flags": [{"code": "vertical_unit_status_unrecorded", "message": "x"}],
        "reason": None,
    }

    def run_case(self, system_type):
        from test_modeled_assessment_unit import fake_research, frozen_gis

        c = lead_case(system_feature("G1", gsi_system_type=system_type))
        with patch(
            "drainage_core.runoff_capacity.estimate_capacity", return_value=self.PILOT_62571
        ) as cap:
            r = assess(c, frozen_gis(c, fake_research(c)))
        rows = r["modeled_integration"]["catchment_scenarios"]
        return rows, cap

    def test_surface_system_row_carries_the_terrain_storage_check(self):
        rows, cap = self.run_case("Rain Garden")
        v = next(v for v in rows if v["receiver_id"] == "G1" and v["bound"] == "upper")
        # The dollar figure is unchanged (test_modeled_assessment_unit: $112.71/month).
        self.assertEqual(v["gross_monthly_reduction"], 112.71)
        check = v["storage_check"]
        self.assertEqual(
            check["label"], "Assumes full 1.5-inch treatment; terrain cannot see engineered storage"
        )
        self.assertTrue(check["applies"])
        self.assertEqual(check["status"], "estimated")
        self.assertEqual(check["review_flags"], ["vertical_unit_status_unrecorded"])
        # 9,000 sq ft managed IA x 1.5 in = 1,125 cu ft required; 2.39-2.87 cu ft visible.
        self.assertAlmostEqual(check["required_treatment_volume_cuft"], 1125)
        self.assertFalse(check["terrain_storage_covers_required"])
        self.assertIn("below the 1.5-inch volume", check["flag"])
        self.assertEqual(cap.call_count, 1)  # once per receiver, reused across bounds
        union = next(
            v for v in rows if v["receiver_id"] == "all_unassigned_gsi" and v["bound"] == "upper"
        )
        self.assertEqual(union["storage_checks"][0]["receiver_id"], "G1")

    def test_subsurface_system_is_labelled_not_applicable(self):
        rows, cap = self.run_case("Subsurface Basin")
        v = next(v for v in rows if v["receiver_id"] == "G1" and v["bound"] == "upper")
        self.assertFalse(v["storage_check"]["applies"])
        self.assertEqual(v["storage_check"]["status"], "not_applicable")
        cap.assert_not_called()


AGREEMENT = {
    # Frozen from the 2026-11-16 benchmark runs (stormwater.benchmark_landcover).
    "5300 Whitaker": {
        "all_compared_area": {"overall_agreement": 0.8004623058448573, "compared_sqft": 232993.75},
        "stable_building_footprints": {"overall_agreement": 0.9840332945685185, "compared_sqft": 91913.18},
    },
    "3060 S 61st (rebuilt)": {
        "all_compared_area": {"overall_agreement": 0.20889645, "compared_sqft": 629334.47},
        "stable_building_footprints": {"overall_agreement": None, "compared_sqft": 0.0},
    },
    "8000 Cherokee": {
        "all_compared_area": {"overall_agreement": 0.65740, "compared_sqft": 876187.69},
        "stable_building_footprints": {"overall_agreement": 0.72126, "compared_sqft": 137666.27},
    },
}


class PavedReferenceBasisTests(unittest.TestCase):
    def test_qualification_threshold_on_live_agreement(self):
        from drainage_core.benchmark import reference_qualification

        verdict = {k: reference_qualification(v)["qualifies"] for k, v in AGREEMENT.items()}
        self.assertEqual(
            verdict,
            {"5300 Whitaker": True, "3060 S 61st (rebuilt)": False, "8000 Cherokee": False},
        )
        reasons = reference_qualification(AGREEMENT["3060 S 61st (rebuilt)"])["reasons"]
        self.assertTrue(any("site may have changed" in r for r in reasons))

    def reference(self, agreement):
        return {
            "kind": "reference land-cover paved classes",
            "paved_geometry": mapping(box(0, 0, 15.24, 30.48)),
            "agreement": agreement,
        }

    def test_developed_on_paved_bound_prices_a_ground_catchment(self):
        # The observed-IA-only bound (formerly "nominal") is empty in a ground catchment.
        # With a qualifying reference, developed-space appearance (x 0-15.24 m) inside 2018
        # paved area becomes a labelled hypothesis: 5,000 sq ft minus the receiver bed
        # (1,000) = 4,000 sq ft managed. IA/GA credit 80% = 3,200 -> GA 6,800 = 14 x
        # $1.003 = $14.042 -> $14.04; IA 6,800 = 14 x $7.048 = $98.672 -> $98.67;
        # $112.71 + $2.81 = $115.52 vs $163.83 -> $48.31/month, $579.72/year.
        from test_modeled_assessment_unit import fake_research, frozen_gis

        c = fixture()
        c["landcover_reference"] = self.reference(AGREEMENT["5300 Whitaker"])
        r = assess(c, frozen_gis(c, fake_research(c)))["modeled_integration"]
        rows = {v["bound"]: v for v in r["catchment_scenarios"] if v["receiver_id"] == "G1"}
        self.assertEqual(rows["observed_ia_only"]["status"], "blocked")
        paved = rows["developed_on_2018_paved"]
        self.assertAlmostEqual(paved["area_sqft"], 4000)
        self.assertEqual(paved["status"], "calculated")
        self.assertEqual(paved["bill"]["monthly_total"], 115.52)
        self.assertEqual(paved["gross_annual_reduction"], 579.72)
        self.assertTrue(any("Labelled hypothesis" in a for a in paved["assumptions"]))
        self.assertEqual(r["paved_reference_basis"]["status"], "offered")

    def test_rebuilt_site_reference_is_not_offered(self):
        from test_modeled_assessment_unit import fake_research, frozen_gis

        c = fixture()
        c["landcover_reference"] = self.reference(AGREEMENT["3060 S 61st (rebuilt)"])
        r = assess(c, frozen_gis(c, fake_research(c)))["modeled_integration"]
        bounds = {v["bound"] for v in r["catchment_scenarios"]}
        self.assertNotIn("developed_on_2018_paved", bounds)
        self.assertEqual(r["paved_reference_basis"]["status"], "not_offered")
        self.assertTrue(r["paved_reference_basis"]["qualification"]["reasons"])


class PavedReferenceAttachTests(unittest.TestCase):
    def test_attach_saves_the_input_as_a_new_case_revision(self):
        import tempfile

        from stormwater.benchmark_landcover import fetch_reference, main, reference_features
        from test_benchmark_landcover import frozen_library_cache, library_case, oem_from

        with tempfile.TemporaryDirectory() as root:
            cache, _ = frozen_library_cache(Path(root) / "cache")
            c = library_case()
            refs, _ = reference_features(fetch_reference(c, cache, cell_ft=3.28, pad_cells=0), c)
            c["features"]["features"] = oem_from(refs)
            folder = Path(root) / "cases" / "library"
            folder.mkdir(parents=True)
            (folder / "case.json").write_text(json.dumps({**c, "id": "library"}))
            with patch("stormwater.cases.CaseStore.save") as save:
                code = main(
                    [
                        "--case", str(folder),
                        "--output", str(Path(root) / "agreement.json"),
                        "--cache", str(Path(root) / "cache"),
                        "--reference-cell-ft", "3.28",
                        "--reference-pad-cells", "0",
                        "--edge-buffer-m", "0",
                        "--attach",
                    ]
                )
        self.assertEqual(code, 0)
        saved_case = save.call_args.args[0]
        self.assertEqual(saved_case["landcover_reference"]["classes"], ["road", "other_pavement"])
        self.assertIsNotNone(save.call_args.kwargs["expected_revision"])


class ResearchRouteScopeTests(unittest.TestCase):
    def test_off_parcel_catchment_edge_contact_does_not_mark_on_parcel_figure_partial(self):
        from datetime import date

        from drainage_core.geometry import measure
        from stormwater.assessment_policy import research_economics

        c = fixture()
        c["baseline"].update(existing_ga_credit_sqft=0, existing_ia_credit_sqft=0)
        on_parcel = box(0, 0, 15.24, 30.48)
        known = mapping(on_parcel)
        complete = {"touches_window_edge": False, "touches_nodata": False, "extent_complete": True}
        edge = {"touches_window_edge": True, "touches_nodata": False, "extent_complete": True}
        primary = {
            "catchments": [
                {
                    "gsi_id": "ON",
                    "geometry": known,
                    "known_ia_geometry": known,
                    "on_parcel_area_sqft": 5000,
                    "on_parcel_known_ia_sqft": 5000,
                    "on_parcel_unknown_surface_sqft": 0,
                    **complete,
                },
                {
                    "gsi_id": "OFF",
                    "geometry": mapping(box(40, 0, 60, 30.48)),
                    "known_ia_geometry": {"type": "GeometryCollection", "geometries": []},
                    "on_parcel_area_sqft": 0,
                    "on_parcel_known_ia_sqft": 0,
                    "on_parcel_unknown_surface_sqft": 0,
                    **edge,
                },
            ],
            "invariants": {"terminal_accumulation_equals_routed_cells": True},
            "known_ia_union_geometry": known,
            "unknown_ground_union_geometry": {"type": "GeometryCollection", "geometries": []},
        }
        m = measure(c)
        m["geometries"]["physical_ia"] = known
        gis = {"measurement": m, "research_drainage": {"primary": primary, "sensitivity": []}}
        out = research_economics(c, gis, [], date(2026, 11, 15), None)
        row = out["scenarios"][0]
        self.assertEqual(row["route_state"], "complete_in_window")
        self.assertIsNone(row["partial_label"])
        self.assertIn("1 of 2", row["route_scope"])
        # The same artifact with the edge contact on the contributing catchment is partial.
        primary["catchments"][0].update(edge)
        row = research_economics(c, gis, [], date(2026, 11, 15), None)["scenarios"][0]
        self.assertEqual(row["route_state"], "partial_upstream_unknown")


if __name__ == "__main__":
    unittest.main()
