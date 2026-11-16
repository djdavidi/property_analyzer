"""Independent GIS editor HTTP workflow, without jurisdiction modules or browser."""

from http.client import HTTPConnection
from http.server import ThreadingHTTPServer
import json
from pathlib import Path
import tempfile
from threading import Thread
import unittest
from shapely.geometry import mapping, Point

from drainage_core.cli import demo_case
from drainage_core.server import Handler
from drainage_core.workspace import ProjectStore


class GenericHTTPTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.store = ProjectStore(cls.tmp.name)
        cls.case = demo_case()
        cls.store.save(cls.case)

        class TestHandler(Handler):
            def log_message(self, *args):
                pass

        TestHandler.store = cls.store
        cls.server = ThreadingHTTPServer(("127.0.0.1", 0), TestHandler)
        cls.thread = Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join()
        cls.tmp.cleanup()

    def request(self, path, payload=None, headers=None):
        conn = HTTPConnection("127.0.0.1", self.server.server_port, timeout=15)
        try:
            conn.request(
                "POST" if payload is not None else "GET",
                path,
                json.dumps(payload).encode() if payload is not None else None,
                headers or {},
            )
            r = conn.getresponse()
            return r.status, r.read()
        finally:
            conn.close()

    def test_generic_config_and_shared_editable_map_assets(self):
        status, body = self.request("/api/config")
        self.assertEqual(status, 200)
        self.assertEqual(json.loads(body)["mode"], "gis")
        self.assertEqual(json.loads(body)["jurisdictions"], [])
        status, body = self.request("/")
        self.assertEqual(status, 200)
        self.assertIn(b'data-mode="gis"', body)
        self.assertIn(b"boundary-import", body)
        status, body = self.request("/app.js")
        self.assertEqual(status, 200)
        self.assertIn(b"renderGisResults", body)

    def test_save_rerun_and_exports_contain_physical_evidence_without_policy(self):
        status, body = self.request("/api/save", {"case": self.case})
        self.assertEqual(status, 200, body)
        result = json.loads(body)
        self.assertNotIn("billing", result)
        self.assertNotIn("screens", result)
        self.assertAlmostEqual(result["measurement"]["ia_m2"], 700)
        status, body = self.request("/api/cases/" + self.case["id"])
        self.assertEqual(json.loads(body), json.loads(json.dumps(self.case)))
        status, body = self.request("/api/analyze", {"case": json.loads(body)})
        self.assertEqual(status, 200)
        self.assertEqual(json.loads(body)["analysis_sha256"], result["analysis_sha256"])
        for name in ("case.json", "analysis.json", "measurements.geojson", "report.html"):
            status, body = self.request("/exports/" + self.case["id"] + "/" + name)
            self.assertEqual(status, 200, name)
            if name == "report.html":
                self.assertNotIn(b"PWD", body)
                self.assertNotIn(b"Billing", body)
                self.assertNotIn(b"tariff", body)
            else:
                json.loads(body)
        self.assertTrue(
            (Path(self.tmp.name) / "revisions" / (result["input_sha256"] + ".json")).exists()
        )

    def test_other_location_boundary_and_conveyance_feature_import(self):
        boundary = {
            "type": "Polygon",
            "coordinates": [
                [
                    [151.2, -33.9],
                    [151.201, -33.9],
                    [151.201, -33.899],
                    [151.2, -33.899],
                    [151.2, -33.9],
                ]
            ],
        }
        status, body = self.request(
            "/api/import-boundary", {"geojson": boundary, "name": "Sydney input"}
        )
        self.assertEqual(status, 200, body)
        case = json.loads(body)
        self.assertEqual(case["crs"], "EPSG:32756")
        self.assertNotIn("baseline", case)
        features = {
            "type": "FeatureCollection",
            "features": [
                {
                    "type": "Feature",
                    "id": "inlet-1",
                    "geometry": mapping(Point(151.2005, -33.8995)),
                    "properties": {"layer": "inlet"},
                },
                {
                    "type": "Feature",
                    "id": "pipe-1",
                    "geometry": {
                        "type": "LineString",
                        "coordinates": [[151.2005, -33.8995], [151.201, -33.8995]],
                    },
                    "properties": {
                        "layer": "connection",
                        "from": "inlet-1",
                        "to": "outfall",
                        "evidence": "documented",
                    },
                },
            ],
        }
        status, body = self.request(
            "/api/import-features", {"geojson": features, "target_crs": case["crs"]}
        )
        self.assertEqual(status, 200, body)
        f = json.loads(body)["features"]
        self.assertEqual(f[0]["id"], "inlet-1")
        self.assertEqual(f[1]["properties"]["from"], f[0]["id"])
        self.assertGreater(f[0]["geometry"]["coordinates"][0], 100000)

    def test_native_dem_alignment_keeps_physical_area_accounting(self):
        status, body = self.request(
            "/api/align-case", {"case": self.case, "target_crs": "EPSG:28356"}
        )
        self.assertEqual(status, 200, body)
        aligned = json.loads(body)
        self.assertEqual(aligned["area_crs"], self.case["crs"])
        self.assertIsNone(aligned["terrain"])
        status, body = self.request("/api/analyze", {"case": aligned})
        self.assertEqual(status, 200, body)
        self.assertAlmostEqual(json.loads(body)["measurement"]["ga_m2"], 900, places=3)

    def test_foreign_origin_host_and_provider_endpoint_are_rejected(self):
        self.assertEqual(self.request("/api/config", headers={"Host": "external.example"})[0], 403)
        self.assertEqual(
            self.request(
                "/api/analyze", {"case": self.case}, headers={"Origin": "https://external.example"}
            )[0],
            403,
        )
        self.assertEqual(self.request("/api/acquire", {"parcel_id": 123})[0], 404)
        self.assertEqual(self.request("/exports/" + self.case["id"] + "/../case.json")[0], 404)


if __name__ == "__main__":
    unittest.main()
