"""Offline checks for scripts/pwd_snapshot.py row building (no network)."""

import importlib.util
import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("pwd_snapshot", ROOT / "scripts" / "pwd_snapshot.py")
snapshot = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(snapshot)
FIXTURE = ROOT / "tests" / "fixtures" / "billing" / "pwd-201345-details-excerpt.json"


class PwdSnapshotRowTests(unittest.TestCase):
    parcel = {
        "parcelid": 201345,
        "address": "1901 VINE ST",
        "owner1": "EXAMPLE OWNER LLC",
        "owner2": None,
        "gross_area": 191000,
        "bldg_desc": "OFFICE",
    }

    def test_row_uses_public_current_charge(self):
        raw = json.loads(FIXTURE.read_text())
        row = snapshot.snapshot_row(self.parcel, raw, "2026-11-16T00:00:00+00:00")
        # Five accounts at $579.85 each: PWD's own current-period total, $2,899.25/month.
        self.assertEqual(row["monthly_charge"], 2899.25)
        self.assertEqual(row["annual_charge"], 34791.0)
        self.assertEqual(row["accounts"], 5)
        self.assertEqual(row["status"], "ok")
        self.assertEqual(row["owner_screen"], "nongovernment_record")

    def test_unavailable_record_stays_blank_not_zero(self):
        row = snapshot.snapshot_row(self.parcel, None, None, "unavailable: timeout")
        self.assertNotIn("monthly_charge", row)
        self.assertEqual(row["status"], "unavailable: timeout")

    def test_government_owner_is_screened(self):
        parcel = {**self.parcel, "owner1": "CITY OF PHILA"}
        row = snapshot.snapshot_row(parcel, None, None, "unavailable: x")
        self.assertEqual(row["owner_screen"], "government")


if __name__ == "__main__":
    unittest.main()
