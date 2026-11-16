"""Records-only ranking, ownership, parcel association and failure semantics."""

from copy import deepcopy
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
import json
import unittest
from shapely.geometry import box, mapping
from stormwater import prospects as p
from threading import Event


def feature(pid, bounds=(0, 0, 100, 100), **extra):
    return {
        "type": "Feature",
        "geometry": mapping(box(*bounds)),
        "properties": {
            "parcelid": pid,
            "address": f"{pid} TEST ST",
            "owner1": "PRIVATE HOLDINGS LLC",
            "owner2": None,
            **extra,
        },
    }


def system(sid="1", bounds=(10, 10, 20, 20), **extra):
    return {
        "type": "Feature",
        "geometry": mapping(box(*bounds)),
        "properties": {
            "gsi_system_id": sid,
            "objectid": sid,
            "project_type": "Private - Retrofit",
            "year_installed": 2018,
            "gsi_system_type": "Rain Garden",
            "project_number": "TEST-1",
            **extra,
        },
    }


def billing(pid="1", charge=1000, **extra):
    return {
        "Parcel": {
            "ParcelID": pid,
            "Owner1": "PRIVATE HOLDINGS LLC",
            "Owner2": None,
            "Address": f"{pid} TEST ST",
            "GrossArea": 100000,
            "ImpervArea": 80000,
            "NPDESCredit": 0,
            "BldgType": "NonRes",
            **extra,
        },
        "ChargeSummary": {
            "GrossCreditSqFt": 0,
            "ImpervCreditSqFt": 0,
            "Errors": [],
            "ParcelTotals": [
                {
                    "TotalStormwaterCharge": charge,
                    "RateSchedule": {
                        "IsCurrent": True,
                        "StartDate": "2026-09-01T00:00:00",
                        "EndDate": "2027-08-31T00:00:00",
                    },
                }
            ],
        },
        "Pending": {"Expired": 1, "Credits": 0},
    }


class OwnershipTests(unittest.TestCase):
    def test_government_variants_and_coowner_are_excluded(self):
        for name in [
            "CITY OF PHILADELPHIA",
            "COMMONWEALTH OF PENNSYLVANIA",
            "U.S. OF AMERICA",
            "UNITED STATES POSTAL SERVICE",
            "SCHOOL DISTRICT OF PHILA",
            "PHILADELPHIA HOUSING AUTH",
            "SEPTA",
            "PENNSYLVANIA DEPARTMENT OF TRANSPORTATION",
            "PHILADELPHIA AUTHORITY FO",
        ]:
            with self.subTest(name=name):
                self.assertEqual(p.owner_status("PRIVATE LLC", name)["status"], "government")

    def test_private_names_containing_geography_or_federal_are_retained(self):
        for name in [
            "PHILADELPHIA INVESTMENTS LLC",
            "STATE FARM INSURANCE",
            "FEDERAL REALTY INVESTMENT",
            "PHILADELPHIA COMMUNITY DEVELOPMENT CORPORATION",
            "UNIVERSITY OF PENNSYLVANIA",
        ]:
            with self.subTest(name=name):
                self.assertEqual(p.owner_status(name)["status"], "nongovernment_record")

    def test_missing_or_uncertain_public_bodies_require_review(self):
        self.assertEqual(p.owner_status(None, "")["status"], "unknown")
        self.assertEqual(p.owner_status("TEMPLE UNIVERSITY")["status"], "review")
        self.assertEqual(p.owner_status("UNRECOGNIZED AUTHORITY")["status"], "review")


class MatchingTests(unittest.TestCase):
    def test_private_existing_only(self):
        self.assertEqual(p.system_status(p.props(system()), "2026-11-15"), "mapped_existing")
        for extra, expected in [
            ({"project_type": "Public - Complete"}, "public_project"),
            ({"status": "Construction"}, "not_completed"),
            ({"year_installed": None}, "installation_unknown"),
            ({"year_installed": 2028}, "installation_unknown"),
        ]:
            self.assertEqual(p.system_status(p.props(system(**extra)), "2026-11-15"), expected)

    def test_duplicate_systems_produce_one_parcel(self):
        matched, held, errors = p.match_systems([system("1"), system("2")], [feature(1)])
        self.assertEqual(list(matched), ["1"])
        self.assertEqual(len(matched["1"]["systems"]), 2)
        self.assertFalse(held + errors)

    def test_shared_footprint_and_point_touch_are_not_assigned(self):
        matched, held, errors = p.match_systems(
            [system(bounds=(40, 10, 60, 20)), system("2", bounds=(100, 0, 110, 10))],
            [feature(1, (0, 0, 50, 100)), feature(2, (50, 0, 100, 100))],
        )
        self.assertFalse(matched)
        self.assertEqual(len(held), 2)
        self.assertFalse(errors)

    def test_dominant_overlap_is_explicit(self):
        matched, held, _ = p.match_systems(
            [system(bounds=(40, 10, 100, 20))],
            [feature(1, (0, 0, 50, 100)), feature(2, (50, 0, 100, 100))],
        )
        self.assertEqual(list(matched), ["2"])
        self.assertGreater(matched["2"]["systems"][0]["footprint_overlap_fraction"], 0.8)


class BillingRankingTests(unittest.TestCase):
    def test_current_parcel_total_is_used_once_and_rounded(self):
        data = billing(charge=1000.005)
        data["Accounts"] = [{"secret": "never export"}]
        out = p.summarize_bill(data, "1", "2026-11-15")
        self.assertEqual(out["monthly_charge"], 1000.01)
        self.assertEqual(out["annual_charge"], 12000.12)
        self.assertNotIn("Accounts", out)

    def test_missing_credits_are_unknown_and_unranked(self):
        data = billing()
        del data["ChargeSummary"]["ImpervCreditSqFt"]
        out = p.summarize_bill(data, "1", "2026-11-15")
        self.assertIsNone(out["ia_credit_sqft"])
        row, reason = p.rank_prospect(
            "1", {"parcel": feature(1), "systems": [p.props(system())]}, out
        )
        self.assertIsNone(row)
        self.assertEqual(reason["status"], "credit_unknown")

    def test_rate_period_identity_multiple_current_and_errors_rejected(self):
        for mutate in [
            lambda x: x["Parcel"].update(ParcelID=2),
            lambda x: x["ChargeSummary"].update(Errors=["source error"]),
            lambda x: x["ChargeSummary"]["ParcelTotals"].append(
                deepcopy(x["ChargeSummary"]["ParcelTotals"][0])
            ),
            lambda x: x["ChargeSummary"]["ParcelTotals"][0]["RateSchedule"].update(
                EndDate="2026-09-02"
            ),
        ]:
            d = billing()
            mutate(d)
            with self.assertRaises(ValueError):
                p.summarize_bill(d, "1", "2026-11-15")

    def test_government_in_billing_vetoes_private_parcel_owner(self):
        out = p.summarize_bill(billing(Owner1="CITY OF PHILADELPHIA"), "1", "2026-11-15")
        row, why = p.rank_prospect("1", {"parcel": feature(1), "systems": []}, out)
        self.assertIsNone(row)
        self.assertEqual(why["status"], "government")

    def test_known_gap_then_annual_charge_deterministic_and_not_savings(self):
        rows = []
        for pid, charge, credit in [
            ("1", 1000, 0),
            ("2", 2000, 0),
            ("3", 10000, 30000),
            ("4", 20000, 70000),
        ]:
            data = billing(pid, charge)
            data["ChargeSummary"]["ImpervCreditSqFt"] = credit
            r, _ = p.rank_prospect(
                pid,
                {
                    "parcel": feature(pid),
                    "systems": [
                        {
                            "system_id": pid,
                            "objectid": pid,
                            "type": "Rain Garden",
                            "project_number": "P",
                        }
                    ],
                },
                p.summarize_bill(data, pid, "2026-11-15"),
            )
            rows.append(r)
        rows.sort(key=p.ordering)
        self.assertEqual([r["parcel_id"] for r in rows], ["4", "3", "2", "1"])
        self.assertTrue(all(r["estimated_savings"] is None for r in rows))
        self.assertIn("no lapse", rows[0]["history_flags"][0])

    def test_unknown_owner_is_not_ranked(self):
        d = billing(Owner1=None)
        row, why = p.rank_prospect(
            "1", {"parcel": feature(1), "systems": []}, p.summarize_bill(d, "1", "2026-11-15")
        )
        self.assertIsNone(row)
        self.assertEqual(why["status"], "unknown")


class WorkflowTests(unittest.TestCase):
    def test_freshness_explicit_dates_and_unknown(self):
        self.assertEqual(p.freshness({}, "2026-11-15")["status"], "unknown")
        self.assertEqual(
            p.freshness({"retrieved_at": "2026-10-16T12:00:00Z"}, "2026-11-15")["status"], "fresh"
        )
        self.assertEqual(
            p.freshness({"retrieved_at": "2026-10-15T00:00:00Z"}, "2026-11-15")["status"], "stale"
        )
        self.assertEqual(
            p.freshness({"retrieved_at": "2026-11-16T12:00:00Z"}, "2026-11-15")["status"],
            "future_date",
        )

    def test_stale_refresh_is_explicit_and_offline_cannot_send(self):
        class Cache:
            calls = 0

            def _read(self, url):
                return ("{}", {"retrieved_at": "2000-01-01T00:00:00Z"})

            def fetch_json(self, *args):
                self.calls += 1
                return {"data": {}, "provenance": {}}

        c = Cache()
        p.CappedCache(c, max_requests=0).fetch_json("saved")
        self.assertEqual(c.calls, 0)
        # Offline cannot send: the stale copy is kept, flagged, and nothing is requested.
        offline = p.CappedCache(c, max_requests=0, refresh_stale=True)
        kept = offline.fetch_json("saved")
        self.assertEqual(c.calls, 0)
        self.assertTrue(kept["provenance"]["refresh_failed"])
        self.assertEqual(offline.stale_reuse[0]["status"], "stale_record_kept_after_failed_refresh")
        p.CappedCache(c, refresh_stale=True).fetch_json("saved")
        self.assertEqual(c.calls, 1)

    def test_cancel_stops_new_cached_and_network_work(self):
        class Cache:
            def _read(self, url):
                raise AssertionError("Stop before any cache/request")

        stop = Event()
        stop.set()
        with self.assertRaises(p.SourceError):
            p.CappedCache(Cache(), cancel=stop).fetch_json("any")

    def test_one_writer_and_cleanup(self):
        with TemporaryDirectory() as root:
            with p.scan_lock(root):
                with self.assertRaises(ValueError):
                    with p.scan_lock(root):
                        pass
            self.assertFalse((Path(root) / "scan.lock").exists())

    def test_worker_and_request_caps_cannot_be_expanded(self):
        with TemporaryDirectory() as root:
            for settings in [{"workers": 3}, {"max_requests": 81}, {"max_seconds": 301}]:
                with self.assertRaises(ValueError):
                    p.run_scan(root, **settings)

    def test_site_grouping_keeps_distinct_owners_and_distant_locations(self):
        rows = []
        for pid, bounds, owner in [
            ("1", (0, 0, 100, 100), "OWNER LLC"),
            ("2", (120, 0, 220, 100), "OWNER LLC"),
            ("3", (500, 0, 600, 100), "OWNER LLC"),
            ("4", (120, 0, 220, 100), "OTHER LLC"),
        ]:
            b = p.summarize_bill(billing(pid, 100, Owner1=owner), pid, "2026-11-15")
            row, _ = p.rank_prospect(
                pid,
                {
                    "parcel": feature(pid, bounds, owner1=owner),
                    "systems": [
                        {
                            "system_id": pid,
                            "objectid": pid,
                            "type": "Rain Garden",
                            "project_number": pid,
                        }
                    ],
                },
                b,
            )
            row["billing_source"] = {"retrieved_at": "2026-11-15T00:00:00Z"}
            rows.append(row)
        sites = p.group_sites(rows, "2026-11-15")
        self.assertEqual(len(sites), 3)
        combined = next(r for r in sites if r["parcel_count"] == 2)
        self.assertEqual(combined["parcel_ids"], ["1", "2"])
        self.assertEqual(combined["billing"]["annual_charge"], 2400)
        self.assertEqual(sum(len(r["member_parcels"]) for r in sites), 4)
        self.assertTrue(all(r["estimated_savings"] is None for r in sites))
        with self.assertRaises(ValueError):
            p.group_sites(rows + [rows[0]], "2026-11-15")

    def test_request_cap_allows_cache_and_blocks_network_after_budget(self):
        class Cache:
            calls = 0

            def _read(self, url):
                return ("{}", {}) if url == "saved" else None

            def fetch_json(self, url, *args):
                if url != "saved":
                    self.calls += 1
                return {"data": {}, "provenance": {}}

        source = Cache()
        bounded = p.CappedCache(source, max_requests=1)
        bounded.fetch_json("one")
        bounded.fetch_json("saved")
        with self.assertRaises(p.SourceError):
            bounded.fetch_json("two")
        self.assertEqual(source.calls, 1)

    def test_time_budget_blocks_new_requests(self):
        class Cache:
            def _read(self, url):
                return None

        with self.assertRaises(p.SourceError):
            p.CappedCache(Cache(), max_seconds=-1).fetch_json("new")

    def test_failed_small_match_stops_expansion(self):
        class Cache:
            pass

        with (
            TemporaryDirectory() as root,
            patch.object(p, "read_inventory", return_value={"features": [system()], "sources": []}),
            patch.object(p, "find_parcels", return_value=([], [], [{"error": "failed"}])) as find,
        ):
            with self.assertRaises(p.SourceError):
                p.run_scan(root, cache=Cache())
            self.assertEqual(find.call_count, 1)

    def test_scan_never_calls_full_flow_and_persists_hash_and_exports(self):
        class Cache:
            def fetch_json(self, url, refresh):
                return {"data": billing(), "provenance": {"url": url, "sha256": "a" * 64}}

        with (
            TemporaryDirectory() as root,
            patch.object(p, "read_inventory", return_value={"features": [system()], "sources": []}),
            patch.object(p, "find_parcels", return_value=([feature(1)], [], [])),
            patch(
                "stormwater.cases._analyze_pair", side_effect=AssertionError("No full assessment")
            ),
        ):
            result = p.run_scan(root, cache=Cache())
            self.assertEqual(len(result["top"]), 1)
            self.assertEqual(p.canonical(p.load_result(root)), p.canonical(result))
            report = p.html_report(result)
            self.assertIn("No imagery", report)
            self.assertIn("12,000.00", report)
            self.assertIn("Unknown — not calculated", p.csv_report(result))
            path = Path(root) / "runs" / result["id"] / "results.json"
            d = json.loads(path.read_text())
            d["counts"]["returned"] = 99
            path.write_text(json.dumps(d))
            with self.assertRaises(ValueError):
                p.load_result(root)

    def test_billing_failure_is_partial_without_fabricated_zero_or_rank(self):
        class Cache:
            def fetch_json(self, *args):
                raise OSError("Source unavailable")

        with (
            TemporaryDirectory() as root,
            patch.object(p, "read_inventory", return_value={"features": [system()], "sources": []}),
            patch.object(p, "find_parcels", return_value=([feature(1)], [], [])),
        ):
            r = p.run_scan(root, cache=Cache())
            self.assertEqual(r["status"], "partial")
            self.assertEqual(r["top"], [])
            self.assertEqual(len(r["failures"]), 1)


if __name__ == "__main__":
    unittest.main()
