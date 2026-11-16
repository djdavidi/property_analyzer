import copy
import math
import unittest

from stormwater.drainage import compare_labels, route_grid


def fixture(elevations, **overrides):
    result = {
        "elevations": elevations,
        "cell_size": 1,
        "horizontal_unit": "m",
        "vertical_unit": "m",
        "origin": [0, 10],
        "crs": "EPSG:2272",
        "settings": {"extent_sufficient": True},
    }
    result.update(overrides)
    return result


class DrainageTests(unittest.TestCase):
    def test_sloping_plane_reaches_known_outlet(self):
        grid = fixture([[3, 2, 1], [3, 2, 1], [3, 2, 1]], inlets=[{"id": "A", "cell": [1, 2]}])
        result = route_grid(grid)
        self.assertEqual(result["counts"], {"inlet:A": 9})
        self.assertEqual(result["next_cells"][1][0], [1, 1])
        self.assertAlmostEqual(result["outlets"][0]["area_sqft"], 9 / 0.3048**2)
        self.assertIn("downstream treatment", " ".join(result["warnings"]))

    def test_ridge_separates_catchments(self):
        result = route_grid(
            fixture(
                [[0, 1, 3, 1, 0]] * 3,
                inlets=[{"id": "west", "cell": [1, 0]}, {"id": "east", "cell": [1, 4]}],
            )
        )
        self.assertEqual(result["counts"], {"inlet:east": 6, "inlet:west": 9})
        self.assertEqual(result["labels"][1][1], "inlet:west")
        self.assertEqual(result["labels"][1][3], "inlet:east")

    def test_barrier_diverts_and_prevents_corner_cutting(self):
        result = route_grid(
            fixture(
                [[4, 3, 2], [4, 3, 1], [4, 3, 0]],
                barriers=[[1, 1]],
                inlets=[{"id": "drain", "cell": [2, 2]}],
            )
        )
        self.assertEqual(result["labels"][1][1], "barrier")
        self.assertEqual(result["next_cells"][1][0], [0, 0])
        self.assertEqual(result["labels"][1][0], "inlet:drain")
        for path in result["flow_paths"]:
            self.assertNotIn([1, 1], path["cells"])

    def test_documented_inlet_pipe_transfers_but_unknown_stops(self):
        grid = fixture(
            [[2, 1]],
            inlets=[{"id": "A", "cell": [0, 1]}],
            connections=[{"from": "A", "to": "B", "evidence": "documented"}],
        )
        self.assertEqual(route_grid(grid)["counts"], {"outlet:B": 2})
        grid["connections"][0]["evidence"] = "unknown"
        result = route_grid(grid)
        self.assertEqual(result["counts"], {"unresolved:pipe:A": 2})
        self.assertEqual(result["unresolved_cells"], 2)

    def test_scenario_pipe_remains_scenario_through_documented_link(self):
        grid = fixture(
            [[3, 2, 1]],
            inlets=[{"id": "A", "cell": [0, 1]}, {"id": "B", "cell": [0, 2]}],
            connections=[
                {"from": "A", "to": "B", "evidence": "scenario"},
                {"from": "B", "to": "garden", "evidence": "documented"},
            ],
        )
        result = route_grid(grid)
        self.assertEqual(
            result["labels"][0],
            ["scenario:outlet:garden", "scenario:outlet:garden", "outlet:garden"],
        )

    def test_pipe_cycle_is_unresolved(self):
        result = route_grid(
            fixture(
                [[2, 1]],
                inlets=[{"id": "A", "cell": [0, 0]}, {"id": "B", "cell": [0, 1]}],
                connections=[
                    {"from": "A", "to": "B", "evidence": "documented"},
                    {"from": "B", "to": "A", "evidence": "documented"},
                ],
            )
        )
        self.assertEqual(result["unresolved_cells"], 2)
        self.assertIn("connection_cycle", result["labels"][0][0])

    def test_roof_does_not_silently_route_to_nearby_inlet(self):
        grid = fixture([[5, 2, 1]], roofs=[[0, 0]], inlets=[{"id": "A", "cell": [0, 2]}])
        result = route_grid(grid)
        self.assertEqual(result["labels"][0][0], "unresolved:roof:0:0")
        self.assertEqual(result["labels"][0][1], "inlet:A")
        grid["roof_connections"] = [{"cell": [0, 0], "to": "A", "evidence": "documented"}]
        self.assertEqual(route_grid(grid)["counts"], {"inlet:A": 3})

    def test_flat_routes_to_lower_exit_without_cycles(self):
        result = route_grid(fixture([[3, 3, 3, 2, 1]], inlets=[{"id": "A", "cell": [0, 4]}]))
        self.assertEqual(result["counts"], {"inlet:A": 5})
        self.assertEqual(result["next_cells"][0][0], [0, 1])

    def test_closed_flat_and_depression_preserved(self):
        result = route_grid(fixture([[5, 5, 5, 5], [5, 1, 1, 5], [5, 5, 5, 5]]))
        self.assertEqual(result["labels"][1][1], "unresolved:flat:1:1")
        self.assertEqual(result["unresolved_cells"], 12)
        pit = route_grid(fixture([[5, 5, 5], [5, 0, 5], [5, 5, 5]]))
        self.assertEqual(pit["counts"], {"unresolved:depression:1:1": 9})

    def test_known_storage_is_not_filled_or_assumed_to_outflow(self):
        result = route_grid(fixture([[3, 2, 3], [2, 0, 2], [3, 2, 3]], storage=[[1, 1]]))
        self.assertEqual(result["counts"], {"storage:1:1": 9})
        self.assertFalse(result["settings"]["depression_filling"])

    def test_missing_terrain_is_unknown_not_outlet_or_zero(self):
        result = route_grid(fixture([[None, 5, 5], [5, 1, 5], [5, 5, 5]]))
        self.assertEqual(result["nodata_cells"], 1)
        self.assertFalse(result["coverage_complete"])
        self.assertIn("unresolved:nodata", result["labels"][1][1])
        self.assertAlmostEqual(result["nodata_area_sqft"], 1 / 0.3048**2)
        self.assertEqual(sum(result["counts"].values()), 9)

    def test_edge_and_extent_reported(self):
        result = route_grid(fixture([[2, 1]], settings={}))
        self.assertEqual(result["labels"][0][0], "edge:0:1")
        self.assertFalse(result["extent_sufficient"])
        self.assertIn("raster edge", " ".join(result["warnings"]))
        self.assertIn("routing extent", " ".join(result["warnings"]))

    def test_units_and_separate_vertical_conversion(self):
        grid = fixture([[3, 2, 1]], inlets=[{"id": "A", "cell": [0, 2]}])
        metric = route_grid(grid)
        feet = copy.deepcopy(grid)
        feet.update(cell_size=1 / 0.3048, horizontal_unit="ft", vertical_unit="us-ft")
        feet["elevations"] = [[v / (1200 / 3937) for v in row] for row in feet["elevations"]]
        alternate = route_grid(feet)
        self.assertEqual(metric["labels"], alternate["labels"])
        self.assertAlmostEqual(
            metric["outlets"][0]["area_sqft"], alternate["outlets"][0]["area_sqft"]
        )
        self.assertEqual(metric["next_cells"], alternate["next_cells"])

    def test_off_parcel_contributions_remain_separate(self):
        result = route_grid(
            fixture(
                [[3, 2, 1]], inlets=[{"id": "A", "cell": [0, 2]}], parcel_mask=[[False, True, True]]
            )
        )
        outlet = result["outlets"][0]
        self.assertAlmostEqual(outlet["on_parcel_area_sqft"], 2 / 0.3048**2)
        self.assertAlmostEqual(outlet["off_parcel_area_sqft"], 1 / 0.3048**2)
        self.assertAlmostEqual(
            outlet["area_sqft"], outlet["on_parcel_area_sqft"] + outlet["off_parcel_area_sqft"]
        )

    def test_invalid_grid_and_features_rejected(self):
        bad = [
            fixture([[1], [1, 2]]),
            fixture([[math.nan]]),
            fixture([[True]]),
            fixture([[1]], vertical_unit=None),
            fixture([[1]], barriers=[[0, 1]]),
            fixture([[None]], inlets=[{"id": "A", "cell": [0, 0]}]),
            fixture([[1]], roofs=[[0, 0]], barriers=[[0, 0]]),
            fixture([[1]], cell_size=0),
        ]
        for grid in bad:
            with self.subTest(grid=grid), self.assertRaises(ValueError):
                route_grid(grid)

    def test_determinism_and_input_immutable(self):
        grid = fixture([[3, 3, 3], [3, 2, 3], [3, 3, 3]])
        before = copy.deepcopy(grid)
        self.assertEqual(route_grid(grid), route_grid(grid))
        self.assertEqual(grid, before)


class ReferenceMetricTests(unittest.TestCase):
    def test_same_total_area_can_have_critical_routing_disagreements(self):
        result = compare_labels([["A", "B"], ["B", "A"]], [["A", "A"], ["B", "B"]])
        self.assertEqual(result["catchments"]["A"]["area_error_cells"], 0)
        self.assertAlmostEqual(result["catchments"]["A"]["intersection_over_union"], 1 / 3)
        self.assertEqual(result["routing_disagreement_cells"], 2)

    def test_missing_reference_cells_reported(self):
        result = compare_labels([["A", "B"]], [["A", None]])
        self.assertEqual(result["reference_cells"], 1)
        self.assertEqual(result["excluded_reference_cells"], 1)
        self.assertEqual(compare_labels([["A"]], [[None]])["status"], "blocked")


if __name__ == "__main__":
    unittest.main()
