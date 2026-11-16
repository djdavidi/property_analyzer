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


if __name__ == "__main__":
    unittest.main()
