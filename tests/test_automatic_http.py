"""Enter property -> acquire/measure -> save/reopen/export, through real loopback HTTP."""

from copy import deepcopy
from pathlib import Path
import json
import unittest
from unittest.mock import patch
import test_server as baseline
from test_automatic_site import fixture, lc, png
from hashlib import sha256


class AutomaticHTTPTests(unittest.TestCase):
    setUpClass = classmethod(baseline.HTTPWorkflowTests.setUpClass.__func__)
    tearDownClass = classmethod(baseline.HTTPWorkflowTests.tearDownClass.__func__)
    request = baseline.HTTPWorkflowTests.request
    json_request = baseline.HTTPWorkflowTests.json_request

    def setUp(self):
        source = patch(
            "stormwater.automatic.buildings",
            side_effect=OSError("Fixture building layer unavailable"),
        )
        source.start()
        self.addCleanup(source.stop)

    def test_address_to_automatic_measurements_reopen_export_and_rerun(self):
        c = fixture()
        r = lc(c)
        r.update(
            source_snapshots=[],
            status="source_estimate",
            source_vintage="2025",
            retrieved_at="2026-11-15",
        )
        payload = png([[[30, 130, 30], [100, 100, 100]], [[30, 130, 30], [100, 100, 100]]])
        digest = sha256(payload).hexdigest()
        path = Path(self.temp.name) / "image"
        path.write_bytes(payload)
        image = {
            "sha256": digest,
            "blob_path": str(path),
            "bounds": [0, 0, 4, 2],
            "width": 2,
            "height": 2,
            "sources": [],
            "source_vintage": "2025",
        }
        data = {
            "parcel_id": 51,
            "address": "51 SYNTHETIC TEST ST",
            "parcel": c["parcel"],
            "crs": c["crs"],
            "features": c["features"],
            "sources": [],
            "baseline": None,
        }
        discovery = {
            "records": [],
            "observations": [],
            "sources": [],
            "source_status": [{"provider": "fixture", "status": "retrieved"}],
        }
        with (
            patch(
                "stormwater.automatic.lookup",
                return_value={
                    "matches": [{"parcel_id": 51, "address": data["address"]}],
                    "sources": [],
                },
            ),
            patch("stormwater.acquisition.acquire_property", return_value=data) as property_read,
            patch("stormwater.acquisition.acquire_imagery", return_value=image),
            patch(
                "stormwater.automatic_terrain.acquire", side_effect=OSError("Explicit terrain gap")
            ),
            patch("stormwater.assessment_sources.discover", return_value=discovery),
        ):
            code, _, response = self.json_request(
                "/api/property/assess", {"query": "51 Synthetic Test St"}
            )
            self.assertEqual(code, 200, response)
            self.assertIsNone(response["analysis"]["measurement"]["canopy_sqft"])
            self.assertGreater(response["analysis"]["automatic"]["landcover"]["candidate_sqft"], 0)
            self.assertEqual(
                response["analysis"]["automatic"]["landcover"]["source_vintage"], "2025"
            )
            self.assertFalse(response["analysis"]["measurement"]["complete"])
            self.assertEqual(len(response["case"]["assessment"]["snapshots"]), 1)
            case = response["case"]
            old_features = deepcopy(case["features"])
            _, _, reopened = self.json_request("/api/cases/pwd-51")
            self.assertEqual(reopened, case)
            _, _, report = self.request("/exports/pwd-51/report.html")
            self.assertIn(b"Automatically acquired canopy", report)
            self.assertIn(b"not statistical confidence", report)
            # A second property action uses the saved case and keeps its previous run.
            property_read.side_effect = AssertionError("Do not replace a saved case/baseline")
            code, _, second = self.json_request(
                "/api/property/assess", {"query": "51 Synthetic Test St"}
            )
            self.assertEqual(code, 200, second)
            self.assertEqual(second["case"]["features"], old_features)
            self.assertEqual(len(second["case"]["assessment"]["snapshots"]), 2)
            self.assertEqual(len(second["case"]["automatic_runs"]), 2)
            _, _, bundle = self.json_request("/exports/pwd-51/evidence-bundle.json")
            self.assertEqual(len(bundle["assessments"]), 2)
            self.assertFalse(bundle["snapshots_without_content_hash"])

    def test_ambiguous_address_requires_selection_without_acquisition(self):
        matches = [
            {"parcel_id": 601, "address": "601 TEST ST A"},
            {"parcel_id": 602, "address": "601 TEST ST B"},
        ]
        with (
            patch("stormwater.automatic.lookup", return_value={"matches": matches, "sources": []}),
            patch(
                "stormwater.acquisition.acquire_property",
                side_effect=AssertionError("Ambiguity is not a confirmed match"),
            ),
        ):
            code, _, response = self.json_request("/api/property/assess", {"query": "601 Test St"})
        self.assertEqual(code, 200, response)
        self.assertEqual(response["matches"], matches)

    def test_unknown_sources_return_unknown_canopy_and_partial_assessment(self):
        c = fixture()
        data = {
            "parcel_id": 987,
            "address": "987 SYNTHETIC TEST ST",
            "parcel": c["parcel"],
            "crs": c["crs"],
            "features": c["features"],
            "sources": [],
            "baseline": None,
        }
        with (
            patch(
                "stormwater.automatic.lookup",
                return_value={
                    "matches": [{"parcel_id": 987, "address": data["address"]}],
                    "sources": [],
                },
            ),
            patch("stormwater.acquisition.acquire_property", return_value=data),
            patch("stormwater.acquisition.acquire_imagery", side_effect=OSError("image offline")),
            patch("stormwater.automatic.landcover", side_effect=OSError("classification offline")),
            patch("stormwater.automatic_terrain.acquire", side_effect=OSError("elevation offline")),
            patch(
                "stormwater.assessment_sources.discover",
                return_value={
                    "records": [],
                    "observations": [],
                    "sources": [],
                    "source_status": [{"provider": "fixture", "status": "unavailable"}],
                },
            ),
        ):
            code, _, response = self.json_request(
                "/api/property/assess", {"query": "987 Synthetic Test St"}
            )
        self.assertEqual(code, 200, response)
        self.assertIsNone(response["analysis"]["measurement"]["canopy_sqft"])
        self.assertEqual(response["analysis"]["automatic"]["estimates"], [])
        self.assertTrue(
            all(
                s["status"] == "unavailable"
                for s in response["analysis"]["automatic"]["source_status"]
            )
        )
        # Five record categories (fix 3 adds existing_system_management) plus prior credits.
        self.assertEqual(len(response["analysis"]["assessment"]["categories"]), 6)
