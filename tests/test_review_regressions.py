import unittest
from shapely.geometry import box, mapping, Point
from stormwater.cases import analyze
from stormwater.fixtures import synthetic_case
from stormwater.geometry import effective_features


class ReviewRegressions(unittest.TestCase):
    def test_partial_dem_cannot_be_overridden_by_sufficiency_flag(self):
        c = synthetic_case()
        c["features"]["features"] = []
        c["benefits"] = []
        c["terrain"]["elevations"] = [[3, 2], [2, 1]]
        c["terrain"]["settings"]["extent_sufficient"] = True
        result = analyze(c)
        self.assertFalse(result["drainage"]["extent_sufficient"])
        self.assertEqual(result["drainage"]["status"], "partial")
        self.assertTrue(any("Partial routing extent" in w for w in result["warnings"]))

    def test_inlet_move_preserves_documented_connection_id(self):
        c = synthetic_case()
        f = next(f for f in c["features"]["features"] if f["id"] == "drain-A")
        moved = {**f, "geometry": mapping(Point(2690092.5, 249912.5))}
        c["corrections"] = [
            {
                "id": "move",
                "at": "2026-11-15",
                "reason": "Independent survey point",
                "action": "replace",
                "target": "drain-A",
                "feature": moved,
            }
        ]
        self.assertIn("outlet:garden-outlet", analyze(c)["drainage"]["labels"][17])

    def test_legacy_credit_polygon_can_be_replaced_and_removed(self):
        c = synthetic_case()
        b = c["benefits"][0]
        f = next(f for f in effective_features(c) if f["id"] == b["id"])
        f["geometry"] = mapping(box(2690055, 249956, 2690060, 249960))
        c["corrections"] = [
            {
                "id": "b1",
                "at": "2026-11-15",
                "reason": "Surveyed canopy overlap",
                "action": "replace",
                "target": b["id"],
                "feature": f,
            }
        ]
        r = analyze(c)
        s = next(s for s in r["screens"] if s["id"] == b["id"])
        self.assertLess(s["area_sqft"], b["area_sqft"])
        c["corrections"].append(
            {
                "id": "b2",
                "at": "2026-11-15",
                "reason": "Remove unsubstantiated hypothesis",
                "action": "delete",
                "target": b["id"],
            }
        )
        self.assertNotIn(b["id"], [s["id"] for s in analyze(c)["screens"]])

    def test_synthetic_reference_never_means_empirical_validation(self):
        c = synthetic_case()
        c["references"] = [
            {
                "id": "fake",
                "kind": "ia",
                "independent": True,
                "stable_site_verified": True,
                "source_url": "synthetic://known-answer",
                "crs": c["crs"],
                "geometry": c["parcel"],
            }
        ]
        v = analyze(c)["validation"]["ia"]
        self.assertEqual(v["status"], "incomplete")
        self.assertFalse(v["results"])


if __name__ == "__main__":
    unittest.main()
