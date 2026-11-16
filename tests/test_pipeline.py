import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock
import numpy as np
import rasterio
from rasterio.transform import from_origin
from stormwater.acquisition import (
    Cache,
    SourceError,
    arcgis_features,
    normalize_billing,
    quality_checks,
)
from stormwater.raster import import_dem, classify_raster, check_alignment


class CacheTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.opener = Mock(return_value=io.BytesIO(b'{"features":[]}'))
        self.cache = Cache(self.temp.name, opener=self.opener)

    def test_replay_preserves_bytes_timestamp_and_metadata(self):
        first = self.cache.fetch_json(
            "https://example.org/source",
            metadata={"crs": "EPSG:2272", "acquisition_date": "2025-03-10"},
        )
        self.opener.side_effect = OSError("offline")
        second = self.cache.fetch_json("https://example.org/source")
        self.assertEqual(first, second)
        self.assertEqual(self.opener.call_count, 1)
        self.assertEqual(second["provenance"]["acquisition_date"], "2025-03-10")

    def test_refresh_is_explicit_and_keeps_history(self):
        first = self.cache.fetch_json("https://example.org/source")
        self.opener.return_value = io.BytesIO(b'{"features":[1]}')
        second = self.cache.fetch_json("https://example.org/source", refresh=True)
        self.assertNotEqual(first["provenance"]["sha256"], second["provenance"]["sha256"])
        self.assertEqual(len(list((Path(self.temp.name) / "history").glob("*.json"))), 2)
        self.assertTrue((Path(self.temp.name) / "blobs" / first["provenance"]["sha256"]).exists())

    def test_failed_refresh_does_not_replace_old_snapshot(self):
        first = self.cache.fetch_json("https://example.org/source")
        self.opener.side_effect = OSError("source offline")
        with self.assertRaises(SourceError):
            self.cache.fetch_json("https://example.org/source", refresh=True)
        self.assertEqual(first, self.cache.fetch_json("https://example.org/source"))
        failures = (Path(self.temp.name) / "failures.jsonl").read_text()
        self.assertIn("source offline", failures)

    def test_blob_tamper_is_detected(self):
        first = self.cache.fetch_json("https://example.org/source")
        (Path(self.temp.name) / "blobs" / first["provenance"]["sha256"]).write_text("{}")
        with self.assertRaisesRegex(SourceError, "SHA256"):
            self.cache.fetch_json("https://example.org/source")

    def test_api_error_never_becomes_empty_coverage(self):
        self.opener.return_value = io.BytesIO(b'{"error":{"code":500,"message":"unavailable"}}')
        with self.assertRaises(SourceError):
            self.cache.fetch_json("https://example.org/source")

    def test_saved_snapshot_retains_original_retrieval_date(self):
        item = self.cache.import_json(
            "https://example.org/saved", {"value": 3}, retrieved_at="2026-11-07T10:00:00Z"
        )
        self.assertEqual(item["provenance"]["retrieved_at"], "2026-11-07T10:00:00Z")
        self.assertIsNone(item["provenance"]["acquisition_date"])

    def test_bounded_download(self):
        self.cache.max_bytes = 3
        with self.assertRaisesRegex(SourceError, "bounded"):
            self.cache.fetch_json("https://example.org/source")


class PaginationTests(unittest.TestCase):
    def test_all_pages_and_provenance_retained(self):
        cache = Mock()
        cache.fetch_json.side_effect = [
            {
                "data": {"features": [{"id": 1}, {"id": 2}], "exceededTransferLimit": True},
                "provenance": {"page": 1},
            },
            {"data": {"features": [{"id": 3}]}, "provenance": {"page": 2}},
        ]
        data = arcgis_features("https://example.org/FeatureServer/0", cache, page_size=2)
        self.assertEqual([f["id"] for f in data["features"]], [1, 2, 3])
        self.assertEqual(len(data["sources"]), 2)
        self.assertIn("resultOffset=2", cache.fetch_json.call_args.args[0])

    def test_no_progress_detected(self):
        cache = Mock()
        cache.fetch_json.return_value = {
            "data": {"features": [{"id": 1}], "exceededTransferLimit": True},
            "provenance": {},
        }
        with self.assertRaisesRegex(SourceError, "repeated"):
            arcgis_features("https://example.org/0", cache, page_size=1)

    def test_truncated_empty_and_max_pages_rejected(self):
        cache = Mock()
        cache.fetch_json.return_value = {
            "data": {"features": [], "exceededTransferLimit": True},
            "provenance": {},
        }
        with self.assertRaisesRegex(SourceError, "no pagination"):
            arcgis_features("https://example.org/0", cache)
        cache.fetch_json.return_value = {
            "data": {"features": [{"id": 1}], "exceededTransferLimit": True},
            "provenance": {},
        }
        with self.assertRaisesRegex(SourceError, "page limit"):
            arcgis_features("https://example.org/0", cache, page_size=1, max_pages=1)


class RasterTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)

    def write(self, array, crs="EPSG:2272", transform=None):
        path = Path(self.temp.name) / "raster.tif"
        with rasterio.open(
            path,
            "w",
            driver="GTiff",
            height=len(array),
            width=len(array[0]),
            count=1,
            dtype="float32",
            crs=crs,
            transform=transform or from_origin(100, 200, 3, 3),
            nodata=-9999,
        ) as ds:
            ds.write(np.array(array, dtype="float32"), 1)
        return path

    def test_dem_native_units_nodata_and_georeference(self):
        path = self.write([[1, -9999], [2, 3]])
        result = import_dem(path, vertical_unit="m", acquisition_date="2025-02-01")
        self.assertEqual(result["grid"]["elevations"], [[1.0, None], [2.0, 3.0]])
        self.assertEqual(result["grid"]["horizontal_unit"], "us-ft")
        self.assertEqual(result["grid"]["vertical_unit"], "m")
        self.assertEqual(result["grid"]["origin"], [100, 200])
        self.assertEqual(result["provenance"]["resolution"], [3, 3])
        self.assertTrue(result["warnings"])

    def test_degrees_rotated_and_unknown_vertical_rejected(self):
        path = self.write([[1]], crs="EPSG:4326")
        with self.assertRaisesRegex(ValueError, "projected"):
            import_dem(path, vertical_unit="ft")
        path = self.write([[1]], transform=rasterio.Affine(1, 0.1, 0, 0, -1, 1))
        with self.assertRaisesRegex(ValueError, "north-up"):
            import_dem(path, vertical_unit="ft")
        with self.assertRaisesRegex(ValueError, "vertical_unit"):
            import_dem(path, vertical_unit=None)

    def test_surface_map_preserves_unknown_pixels(self):
        result = classify_raster(self.write([[7, 8], [-9999, 99]]), {7: "roof", 8: "pavement"})
        self.assertEqual(result["provenance"]["unknown_cells"], 2)
        from shapely.geometry import shape

        areas = {}
        for feature in result["features"]["features"]:
            cls = feature["properties"]["class"]
            areas[cls] = areas.get(cls, 0) + shape(feature["geometry"]).area
        self.assertEqual(areas, {"roof": 9, "pavement": 9, "unknown": 18})

    def test_alignment_and_gap_between_tiles(self):
        a = {"crs": "EPSG:2272", "resolution": [1, 1], "bounds": [0, 0, 2, 2]}
        b = {"crs": "EPSG:2272", "resolution": [1, 1], "bounds": [3, 0, 5, 2]}
        warnings = check_alignment([a, b], parcel_bounds=[0, 0, 5, 2])
        self.assertTrue(any("gaps/seams" in x for x in warnings))
        c = {**b, "bounds": [2.5, 0, 5, 2]}
        self.assertTrue(any("misaligned" in x for x in check_alignment([a, c])))
        self.assertTrue(
            any("CRS mismatch" in x for x in check_alignment([a, {**b, "crs": "EPSG:26918"}]))
        )

    def test_temporal_conflict_and_missing_dates(self):
        warnings = quality_checks(
            [
                {
                    "url": "one",
                    "acquisition_date": "2017-01-01",
                    "crs": "EPSG:2272",
                    "horizontal_unit": "us-ft",
                },
                {"url": "two"},
            ],
            construction_completed="2018-02-26",
        )
        self.assertTrue(any("predates" in x for x in warnings))
        self.assertTrue(any("acquisition_date unknown" in x for x in warnings))

    def test_normalized_raw_billing_uses_current_account_not_property_rounded_display(self):
        data = {
            "Parcel": {
                "GrossArea": 1000,
                "ImpervArea": 500,
                "GrossCredit": 100,
                "ImpervCredit": 100,
                "FinalGross": 1000,
                "FinalImperv": 500,
                "NPDESCredit": 0,
                "BldgType": "NonRes",
                "WeightedCharge": 10.001,
            },
            "ChargeSummary": {
                "ParcelAccounts": [
                    {
                        "AccountPercentOfCharge": 0.4,
                        "YearlyAccountCharges": [
                            {
                                "RateSchedule": {
                                    "IsCurrent": True,
                                    "StartDate": "2026-09-01T00:00:00",
                                },
                                "TotalWeightedCharge": 5.12,
                            }
                        ],
                    },
                    {
                        "AccountPercentOfCharge": 0.6,
                        "YearlyAccountCharges": [
                            {
                                "RateSchedule": {
                                    "IsCurrent": True,
                                    "StartDate": "2026-09-01T00:00:00",
                                },
                                "TotalWeightedCharge": 7.32,
                            }
                        ],
                    },
                ]
            },
        }
        result = normalize_billing(data)
        self.assertAlmostEqual(result["published_monthly_total"], 12.44)
        self.assertEqual(result["accounts"][1]["allocation"], 0.6)
        self.assertIsNone(result["existing_iar_sqft"])
        self.assertFalse(result["existing_credits_spatially_reconciled"])


if __name__ == "__main__":
    unittest.main()
