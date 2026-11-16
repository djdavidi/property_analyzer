"""Real local HTTP evidence workflow; providers stubbed, original file bytes checked."""

import base64
from copy import deepcopy
from hashlib import sha256
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import test_server as baseline

fixture = baseline.fixture
from stormwater.cases import CaseStore
from stormwater.assessment_workflow import ensure_assessment


class AssessmentHTTPTests(unittest.TestCase):
    setUpClass = classmethod(baseline.HTTPWorkflowTests.setUpClass.__func__)
    tearDownClass = classmethod(baseline.HTTPWorkflowTests.tearDownClass.__func__)
    request = baseline.HTTPWorkflowTests.request
    json_request = baseline.HTTPWorkflowTests.json_request

    def test_attachment_review_rerun_export_portable_import_and_renewals(self):
        case = fixture()
        raw = b"%PDF-1.4\nSynthetic evidence, not a real award.\n"
        code, _, uploaded = self.json_request(
            "/api/assessment/attachment",
            {"case": case, "filename": "award.pdf", "content": base64.b64encode(raw).decode()},
        )
        self.assertEqual(code, 200, uploaded)
        case = uploaded["case"]
        document = uploaded["attachment"]
        record = {
            "id": "green-candidate",
            "category": "green_roof",
            "decision": "candidate",
            "basis": "manual",
            "facts": {},
            "evidence_refs": [{"attachment_id": document["id"], "page": 1}],
        }
        code, _, response = self.json_request(
            "/api/assessment/review", {"case": case, "record": record, "reason": "Candidate only"}
        )
        self.assertEqual(code, 200, response)
        case = response["case"]
        record = {**record, "decision": "rejected", "facts": {"existing_installation": False}}
        code, _, response = self.json_request(
            "/api/assessment/review",
            {"case": case, "record": record, "reason": "Proposed system only"},
        )
        self.assertEqual(code, 200, response)
        case = response["case"]
        event = {
            "id": "award-1",
            "credit_id": "roof-1",
            "category": "green_roof",
            "status": "awarded",
            "effective_from": "2023-01-01",
            "expires_on": "2027-01-01",
            "evidence_refs": [{"attachment_id": document["id"], "page": 1}],
        }
        code, _, response = self.json_request(
            "/api/assessment/history",
            {"case": case, "event": event, "reason": "Synthetic award record"},
        )
        self.assertEqual(code, 200, response)
        case = response["case"]

        def offline(c, *args, **kwargs):
            c = deepcopy(c)
            ensure_assessment(c)["source_status"] = [
                {"provider": "stub", "status": "unavailable", "errors": ["Offline fixture"]}
            ]
            return c

        with patch("stormwater.assessment_workflow.gather", side_effect=offline):
            code, _, response = self.json_request("/api/assessment/run", {"case": case})
        self.assertEqual(code, 200, response)
        case = response["case"]
        first = deepcopy(case)
        self.assertEqual(case["assessment"]["records"][0]["decision"], "rejected")
        self.assertEqual(len(case["assessment"]["reviews"]), 2)
        self.assertEqual(len(case["assessment"]["snapshots"]), 1)
        self.assertEqual(len(response["analysis"]["assessment"]["categories"]), 5)
        code, _, response = self.json_request("/api/renewals")
        self.assertEqual(code, 200, response)
        self.assertIn(case["id"], [p["id"] for p in response["properties"]])
        with patch(
            "stormwater.assessment_workflow.gather",
            side_effect=AssertionError("No acquisition on reopen"),
        ):
            code, _, reopened = self.json_request("/api/cases/" + case["id"])
            self.assertEqual(code, 200, reopened)
            code, _, rerun = self.json_request("/api/analyze", {"case": reopened})
            self.assertEqual(code, 200, rerun)
        self.assertEqual(reopened, first)
        code, headers, download = self.request(
            "/api/attachment/" + case["id"] + "/" + document["sha256"]
        )
        self.assertEqual((code, download), (200, raw))
        self.assertEqual(headers["Content-Disposition"], "attachment")
        self.assertEqual(sha256(download).hexdigest(), document["sha256"])
        code, _, bundle = self.json_request("/exports/" + case["id"] + "/evidence-bundle.json")
        self.assertEqual(code, 200, bundle)
        self.assertEqual(len(bundle["assessments"]), 1)
        self.assertGreaterEqual(len(bundle["revisions"]), 1)
        with tempfile.TemporaryDirectory() as folder:
            imported = CaseStore(folder)
            restored = imported.import_bundle(bundle)
            self.assertEqual(restored["case"], case)
            self.assertEqual(restored["analysis"]["assessment"], rerun["assessment"])
            report = (Path(folder) / case["id"] / "report.html").read_text()
            for title in (
                "Existing green roofs",
                "Existing permeable pavement",
                "Direct surface-water discharge",
                "Industrial NPDES",
                "Prior credits and renewals",
                "Possible historical billing",
            ):
                self.assertIn(title, report)
            for ref in (
                "&lt;script&gt;unsafe()&lt;/script&gt;",
                document["sha256"],
                "page 1",  # evidence references are listed, not dumped as JSON
                "Offline fixture",
            ):
                self.assertIn(ref, report)
        code, _, response = self.json_request("/api/assessment/import", {"bundle": bundle})
        self.assertEqual(code, 200, response)

    def test_failed_sources_preserve_records_and_all_runs(self):
        case = fixture()
        ensure_assessment(case)["records"] = [
            {
                "id": "manual",
                "category": "industrial_npdes",
                "decision": "confirmed",
                "basis": "manual",
                "facts": {},
                "evidence_refs": [],
            }
        ]

        def offline(c, *args, **kwargs):
            c = deepcopy(c)
            ensure_assessment(c)["source_status"] = [
                {"provider": "outage", "status": "unavailable"}
            ]
            return c

        with patch("stormwater.assessment_workflow.gather", side_effect=offline):
            for _ in range(2):
                code, _, response = self.json_request("/api/assessment/run", {"case": case})
                self.assertEqual(code, 200, response)
                case = response["case"]
        self.assertEqual(len(case["assessment"]["snapshots"]), 2)
        self.assertEqual(case["assessment"]["records"][0]["id"], "manual")
        self.assertEqual(
            response["analysis"]["assessment"]["categories"][3]["status"], "missing_evidence"
        )
        code, _, bundle = self.json_request("/exports/" + case["id"] + "/evidence-bundle.json")
        self.assertEqual(len(bundle["assessments"]), 2)

    def test_upload_and_bundle_integrity_boundaries(self):
        case = fixture()
        for filename, content in [
            ("../escape.pdf", b"%PDF-1.4"),
            ("bad.txt", b"#!/bin/sh\necho bad"),
        ]:
            code, _, response = self.json_request(
                "/api/assessment/attachment",
                {"case": case, "filename": filename, "content": base64.b64encode(content).decode()},
            )
            self.assertEqual(code, 400, response)
        code, _, response = self.json_request(
            "/api/assessment/review",
            {
                "case": case,
                "reason": "Review",
                "record": {
                    "category": "green_roof",
                    "decision": "confirmed",
                    "basis": "documented",
                    "evidence_refs": [{"attachment_id": "missing", "page": 1}],
                },
            },
        )
        self.assertEqual(code, 400, response)
        code, _, response = self.json_request(
            "/api/assessment/attachment",
            {
                "case": case,
                "filename": "letter.txt",
                "content": base64.b64encode(b"original").decode(),
            },
        )
        case = response["case"]
        self.json_request("/api/save", {"case": case})
        _, _, bundle = self.json_request("/exports/" + case["id"] + "/evidence-bundle.json")
        bundle["attachments"][0]["content_base64"] = base64.b64encode(b"altered").decode()
        code, _, response = self.json_request("/api/assessment/import", {"bundle": bundle})
        self.assertEqual(code, 400, response)
        _, _, saved = self.json_request("/api/cases/" + case["id"])
        self.assertEqual(saved, case)

    def test_confirmed_candidate_corrections_survive_public_rerun_and_export(self):
        case = fixture()
        a = ensure_assessment(case)
        original = {
            "id": "public-paving",
            "category": "permeable_pavement",
            "decision": "candidate",
            "basis": "public_candidate",
            "facts": {"public_status": "Proposed"},
            "source": {"url": "https://example.test/public-project", "record_id": "public-1"},
            "evidence_refs": [{"source_url": "https://example.test/public-project"}],
        }
        a["records"] = [deepcopy(original)]
        confirmed = {
            **deepcopy(original),
            "decision": "confirmed",
            "basis": "manual",
            "facts": {"existing_installation": True, "material_confirmed": True},
        }
        code, _, response = self.json_request(
            "/api/assessment/review",
            {
                "case": case,
                "record": confirmed,
                "reason": "Synthetic reviewer confirms installation but lacks construction evidence",
            },
        )
        self.assertEqual(code, 200, response)
        case = response["case"]
        self.assertEqual(
            response["analysis"]["assessment"]["categories"][1]["status"], "missing_evidence"
        )
        self.json_request("/api/save", {"case": case})
        _, _, case = self.json_request("/api/cases/" + case["id"])
        discovered = {
            "records": [original],
            "observations": [],
            "sources": [],
            "source_status": [{"provider": "fixture", "status": "unavailable"}],
        }
        with patch("stormwater.assessment_sources.discover", return_value=discovered):
            code, _, response = self.json_request("/api/assessment/run", {"case": case})
        self.assertEqual(code, 200, response)
        case = response["case"]
        self.assertEqual(case["assessment"]["records"][0]["decision"], "confirmed")
        corrected = {
            **case["assessment"]["records"][0],
            "facts": {"existing_installation": True, "construction_documented": False},
        }
        code, _, response = self.json_request(
            "/api/assessment/review",
            {
                "case": case,
                "record": corrected,
                "reason": "Synthetic construction document contradicts earlier assumption",
            },
        )
        self.assertEqual(code, 200, response)
        case = response["case"]
        self.assertEqual(
            response["analysis"]["assessment"]["categories"][1]["status"], "requirements_failed"
        )
        self.json_request("/api/save", {"case": case})
        _, _, exported = self.json_request("/exports/" + case["id"] + "/case.json")
        self.assertEqual(
            exported["assessment"]["records"][0]["facts"]["construction_documented"], False
        )
        self.assertEqual(exported["assessment"]["reviews"][0]["before"], original)
        self.assertEqual(exported["assessment"]["reviews"][1]["before"], confirmed)
        self.assertEqual(exported["assessment"]["records"][0]["source"], original["source"])
