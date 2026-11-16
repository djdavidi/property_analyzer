"""Offline check of the mapped-system to parcel join (no network)."""

import importlib.util
import unittest
from pathlib import Path

from shapely.geometry import Polygon, box, mapping

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "pwd_systems_snapshot", ROOT / "scripts" / "pwd_systems_snapshot.py"
)
systems = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(systems)


def feature(geom, **props):
    return {"type": "Feature", "geometry": mapping(geom), "properties": props}


class SystemJoinTests(unittest.TestCase):
    def test_majority_overlap_assigns_parcel_and_minor_overlap_does_not(self):
        parcels = [
            feature(box(0, 0, 100, 100), parcelid=1, address="A"),
            feature(box(100, 0, 200, 100), parcelid=2, address="B"),
        ]
        found = systems.join(
            [
                feature(
                    box(10, 10, 30, 30), gsi_system_id="S1", project_type="Private - Regulations"
                ),
                feature(box(90, 10, 130, 30), gsi_system_id="S2"),
                feature(box(300, 300, 310, 310), gsi_system_id="S3"),
            ],
            parcels,
        )
        by_id = {row["gsi_system_id"]: row for row in found}
        self.assertEqual(by_id["S1"]["parcelid"], 1)
        self.assertEqual(by_id["S2"]["parcelid"], 2)  # 75% of its footprint is on parcel 2
        self.assertIsNone(by_id["S3"]["parcelid"])  # not on a snapshot parcel: left blank
        self.assertEqual(by_id["S1"]["footprint_sqft"], 400.0)

    def test_invalid_public_polygons_are_repaired_not_fatal(self):
        bowtie = Polygon([(0, 0), (100, 100), (100, 0), (0, 100)])  # self-intersecting
        found = systems.join(
            [feature(box(60, 10, 90, 40), gsi_system_id="S1")],
            [feature(bowtie, parcelid=1, address="A")],
        )
        self.assertEqual(found[0]["parcelid"], 1)


if __name__ == "__main__":
    unittest.main()
