import tempfile
import unittest
from pathlib import Path
import numpy as np
import rasterio
from rasterio.transform import from_origin
from shapely.geometry import box, mapping
from stormwater.terrain import crop_dem, prepare_terrain


class TerrainPreparationTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.source = self.root / "source.tif"
        self.values = np.arange(100, dtype="float32").reshape(10, 10)
        self.values[4, 4] = -9999
        with rasterio.open(
            self.source,
            "w",
            driver="GTiff",
            width=10,
            height=10,
            count=1,
            dtype="float32",
            crs="EPSG:2272",
            transform=from_origin(100, 200, 3, 3),
            nodata=-9999,
        ) as ds:
            ds.write(self.values, 1)
            ds.update_tags(AREA_OR_POINT="Point")
        self.parcel = mapping(box(109.2, 181.2, 117.2, 190.2))

    def test_outward_crop_preserves_native_values_centers_and_nodata(self):
        out = self.root / "crop.tif"
        info = crop_dem(self.source, self.parcel, out, crs="EPSG:2272", buffer_native_units=0)
        self.assertEqual(info["window"], {"col_off": 3, "row_off": 3, "width": 3, "height": 4})
        with rasterio.open(self.source) as src, rasterio.open(out) as ds:
            self.assertEqual(ds.xy(0, 0), src.xy(3, 3))
            np.testing.assert_array_equal(ds.read(1), self.values[3:7, 3:6])
            self.assertTrue(ds.read(1, masked=True).mask[1, 1])
            self.assertEqual(ds.tags()["AREA_OR_POINT"], "Point")

    def test_missing_coverage_and_wrong_crs_fail_without_partial_crop(self):
        for kwargs in [
            dict(crs="EPSG:2272", buffer_native_units=100),
            dict(crs="EPSG:26918", buffer_native_units=0),
        ]:
            with self.assertRaises(ValueError):
                crop_dem(self.source, self.parcel, self.root / "bad.tif", **kwargs)

    def test_no_implicit_resampling_to_bypass_cell_limit(self):
        with self.assertRaises(ValueError):
            crop_dem(
                self.source,
                self.parcel,
                self.root / "bad.tif",
                crs="EPSG:2272",
                buffer_native_units=0,
                max_cells=5,
            )

    def test_unit_evidence_is_required_and_assumptions_remain_explicit(self):
        kwargs = dict(crs="EPSG:2272", vertical_unit="m", buffer_native_units=0)
        with self.assertRaises(ValueError):
            prepare_terrain(
                self.source, self.parcel, self.root / "c.tif", unit_evidence={}, **kwargs
            )
        result = prepare_terrain(
            self.source,
            self.parcel,
            self.root / "c.tif",
            unit_evidence={
                "status": "assumed",
                "source_url": "local:scenario",
                "explanation": "Sensitivity test; source units unknown",
            },
            **kwargs,
        )
        self.assertEqual(result["grid"]["source_quality"]["vertical_units"], "assumed")
        self.assertFalse(result["grid"]["settings"]["extent_sufficient"])
        self.assertIsNone(result["grid"]["elevations"][1][1])
        self.assertTrue(any("assumed" in w for w in result["warnings"]))


if __name__ == "__main__":
    unittest.main()
