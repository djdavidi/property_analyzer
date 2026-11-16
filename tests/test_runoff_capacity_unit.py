"""Invented local-spill storage units; no site replay, providers or routing.

Expected values are worked out by hand from the invented terrain (see comments),
not copied from code output.
"""

from copy import deepcopy
from math import sqrt
import unittest
from unittest.mock import patch

import numpy as np
from shapely.affinity import scale, translate
from shapely.geometry import Point, Polygon, box, mapping

from drainage_core.engine import canonical, input_hash
from drainage_core.geometry import SQFT_PER_M2, projected_crs
from drainage_core.research import METRES
from drainage_core.runoff_capacity import (
    HEADLINE,
    IMPLAUSIBLE_PONDING,
    SCENARIO_ORDER,
    estimate_capacity,
)


CUFT_PER_M3 = SQFT_PER_M2 / 0.3048
DOCUMENTED_ROWS = (
    "perimeter_cell_minimum",
    "perimeter_bilinear",
    "cell_minimum_inward_half_cell",
    "cell_minimum_outward_half_cell",
    "bilinear_inward_half_cell",
    "bilinear_outward_half_cell",
)


def fixture():
    elevations = [[10.0] * 7 for _ in range(7)]
    for row in range(2, 5):
        for col in range(2, 5):
            elevations[row][col] = 0.0
    case = {
        "id": "invented-capacity",
        "crs": "EPSG:26918",
        "parcel": mapping(box(0, 0, 7, 7)),
        "imagery_age_policy": {"as_of": "2026-11-16"},
        "features": {
            "features": [
                {
                    "id": "garden",
                    "geometry": mapping(box(1, 1, 6, 6)),
                    "properties": {
                        "kind": "system_footprint",
                        "gsi_system_id": "01073",
                        "gsi_system_type": "Rain Garden",
                        "year_installed": 2024,
                    },
                }
            ]
        },
        "terrain": {
            "origin": [0, 7],
            "cell_size": 1.0,
            "horizontal_unit": "m",
            "vertical_unit": "m",
            "crs": "EPSG:26918",
            "elevations": elevations,
        },
    }
    return case, {}


def planar_fixture():
    """15 x 15 one-metre grid, so every offset line stays inside the grid.

    Outside a 3 x 3 bowl (rows/cols 6-8, elevation 0) the cell-centre values lie on
    the plane z = 0.2 + 0.02*col + 0.008*row, i.e. z = 0.306 + 0.02x - 0.008y.
    Bilinear interpolation of a plane is exact, and the footprint box(4, 4, 11, 11)
    perimeter and its half-cell offsets never sample the bowl.
    """
    case, gis = fixture()
    elevations = [[0.2 + 0.02 * c + 0.008 * r for c in range(15)] for r in range(15)]
    for r in range(6, 9):
        for c in range(6, 9):
            elevations[r][c] = 0.0
    case["parcel"] = mapping(box(0, 0, 15, 15))
    case["features"]["features"][0]["geometry"] = mapping(box(4, 4, 11, 11))
    case["terrain"].update(origin=[0, 15], elevations=elevations)
    return case, gis


def rows(result):
    return {row["name"]: row for row in result["scenarios"]}


def with_geometry(case, geometry):
    out = deepcopy(case)
    out["features"]["features"][0]["geometry"] = mapping(geometry)
    return out


def rim_sliver_fixture():
    """Review r1: the outer ring (outside the 5 x 5 garden) is lower than the garden's berm."""
    case, gis = fixture()
    for r in range(7):
        for c in range(7):
            if r in (0, 6) or c in (0, 6):
                case["terrain"]["elevations"][r][c] = 5.0
    return case, gis


def diamond_fixture():
    """Review r1b: diamond edges run through grid vertices; only edge-crossed cells are a berm."""
    case, gis = fixture()
    n = 12
    case["parcel"] = mapping(box(0, 0, n, n))
    diamond = Polygon([(6, 2), (10, 6), (6, 10), (2, 6)])
    el = np.zeros((n, n))
    for r in range(n):
        for c in range(n):
            cell = box(c, n - (r + 1), c + 1, n - r)
            if (
                diamond.exterior.intersection(cell).length > 1e-10
                and cell.intersection(diamond).area > 1e-12
            ):
                el[r, c] = 10.0
    case["terrain"].update(origin=[0, n], elevations=el.tolist())
    return with_geometry(case, diamond), gis


class RunoffCapacityUnitTests(unittest.TestCase):
    def test_known_bowl_volume_uses_local_spill_and_explicit_rain_area(self):
        case, gis = fixture()
        result = estimate_capacity(case, gis, "01073")
        self.assertEqual(result["status"], "estimated")
        self.assertEqual(result["selected_scenario"], "perimeter_cell_minimum")
        self.assertAlmostEqual(result["surface_storage_volume_cuft"], 90 * CUFT_PER_M3)
        self.assertAlmostEqual(result["wetted_area_sqft"], 9 * SQFT_PER_M2)
        self.assertAlmostEqual(result["rain_exposure_area_sqft"], 25 * SQFT_PER_M2)
        self.assertEqual(result["scenarios"][0]["component_spill_elevations_m"], [10.0])
        self.assertTrue(
            all(
                row["rain_exposure_area_sqft"] == result["footprint_area_sqft"]
                for row in result["scenarios"]
            )
        )
        self.assertNotIn("managed_area_sqft", result)
        self.assertNotIn(
            "conservative",
            (result["basis"] + result["selected_scenario_role"])
            .lower()
            .replace("neither a bound nor conservative", ""),
        )

    def test_frozen_fill_or_burned_rasters_cannot_set_storage(self):
        # Positive control first: the same bowl with a 0.91 m paper burn in the
        # source grid itself changes storage (10.91 m x 9 m2), so the assertion
        # below would fail if the frozen burned or filled grids were used instead.
        case, gis = fixture()
        burned = deepcopy(case["terrain"]["elevations"])
        for r in range(2, 5):
            for c in range(2, 5):
                burned[r][c] -= 0.91
        control = deepcopy(case)
        control["terrain"]["elevations"] = burned
        self.assertAlmostEqual(
            estimate_capacity(control, gis, "01073")["surface_storage_volume_cuft"],
            98.19 * CUFT_PER_M3,
        )
        gis["research_drainage"] = {
            "primary": {
                "grid": {
                    k: case["terrain"][k] for k in ("origin", "cell_size", "crs", "vertical_unit")
                },
                "rasters": {
                    "fill_depth": [[1000.0] * 7 for _ in range(7)],
                    "filled_elevations": [[20.0] * 7 for _ in range(7)],
                    "conditioned_elevations": burned,
                },
            }
        }
        result = estimate_capacity(case, gis, "01073")
        self.assertAlmostEqual(result["surface_storage_volume_cuft"], 90 * CUFT_PER_M3)
        self.assertEqual(result["storage_range_cuft"], [90 * CUFT_PER_M3, 90 * CUFT_PER_M3])

    def test_low_spill_lowers_capacity_without_quantile_or_median_substitution(self):
        # Berm cell (row 1, col 3) at 2 m on the top edge y=6. Cell minimum: 2 m,
        # so 9 bowl cells x 2 m = 18 m3. Bilinear on y=6 averages row 0 (10) and
        # row 1; at x=3.5 that is (10+2)/2 = 6 m. Then the bowl holds 9 x 6 = 54 m3
        # and the lowered 1 m2 berm cell inside the footprint holds 6-2 = 4 m3: 58 m3.
        case, gis = fixture()
        case["terrain"]["elevations"][1][3] = 2.0
        result = estimate_capacity(case, gis, "01073")
        by = rows(result)
        self.assertEqual(by["perimeter_cell_minimum"]["component_spill_elevations_m"], [2.0])
        self.assertAlmostEqual(result["surface_storage_volume_cuft"], 18 * CUFT_PER_M3)
        self.assertAlmostEqual(by["perimeter_bilinear"]["component_spill_elevations_m"][0], 6.0)
        self.assertAlmostEqual(by["perimeter_bilinear"]["volume_cuft"], 58 * CUFT_PER_M3)
        self.assertAlmostEqual(by["perimeter_bilinear"]["wetted_area_sqft"], 10 * SQFT_PER_M2)
        self.assertAlmostEqual(result["storage_range_cuft"][0], 18 * CUFT_PER_M3)
        self.assertAlmostEqual(result["storage_range_cuft"][1], 58 * CUFT_PER_M3)

    def test_flat_covered_terrain_is_zero_modeled_surface_storage_not_missing(self):
        case, gis = fixture()
        case["terrain"]["elevations"] = [[10.0] * 7 for _ in range(7)]
        result = estimate_capacity(case, gis, "01073")
        self.assertEqual(result["status"], "estimated")
        self.assertEqual(result["surface_storage_volume_cuft"], 0.0)
        self.assertEqual(result["storage_range_cuft"], [0.0, 0.0])

    def test_nodata_inside_facility_does_not_become_zero_capacity(self):
        case, gis = fixture()
        case["terrain"]["elevations"][3][3] = None
        result = estimate_capacity(case, gis, "01073")
        self.assertEqual(result["status"], "unavailable")
        self.assertIsNone(result["surface_storage_volume_cuft"])
        self.assertIsNone(result["storage_range_cuft"])
        self.assertEqual(result["volume_range_missing_scenarios"], list(SCENARIO_ORDER))

    def test_footprint_beyond_grid_has_unknown_capacity(self):
        case, gis = fixture()
        case["features"]["features"][0]["geometry"] = mapping(box(-1, 1, 6, 6))
        result = estimate_capacity(case, gis, "01073")
        self.assertEqual(result["status"], "unavailable")
        self.assertIsNone(result["surface_storage_volume_cuft"])

    def test_missing_or_unverified_vertical_units_are_unknown(self):
        case, gis = fixture()
        case["terrain"]["vertical_unit"] = None
        self.assertIsNone(estimate_capacity(case, gis, "01073")["surface_storage_volume_cuft"])
        case.pop("terrain")
        self.assertIsNone(estimate_capacity(case, gis, "01073")["surface_storage_volume_cuft"])

    def test_vertical_foot_values_equal_metre_volume(self):
        case, gis = fixture()
        feet = deepcopy(case)
        feet["terrain"]["vertical_unit"] = "ft"
        feet["terrain"]["elevations"] = (
            np.asarray(feet["terrain"]["elevations"]) / 0.3048
        ).tolist()
        self.assertAlmostEqual(
            estimate_capacity(case, gis, "01073")["surface_storage_volume_cuft"],
            estimate_capacity(feet, gis, "01073")["surface_storage_volume_cuft"],
        )

    def test_us_survey_foot_vertical_values_equal_metre_volume_and_differ_from_international_feet(
        self,
    ):
        case, gis = fixture()
        usft = deepcopy(case)
        usft["terrain"]["vertical_unit"] = "us-ft"
        usft["terrain"]["elevations"] = (
            np.asarray(usft["terrain"]["elevations"]) / METRES["us-ft"]
        ).tolist()
        metres = estimate_capacity(case, gis, "01073")
        converted = estimate_capacity(usft, gis, "01073")
        for first, second in zip(metres["scenarios"], converted["scenarios"]):
            self.assertAlmostEqual(first["volume_cuft"], second["volume_cuft"])
            self.assertAlmostEqual(first["max_ponding_depth_m"], second["max_ponding_depth_m"])
        # The same values mislabelled as international feet lose 2 ppm (0.0064 cu ft here).
        mislabelled = deepcopy(usft)
        mislabelled["terrain"]["vertical_unit"] = "ft"
        self.assertNotAlmostEqual(
            estimate_capacity(mislabelled, gis, "01073")["surface_storage_volume_cuft"],
            metres["surface_storage_volume_cuft"],
            places=3,
        )

    def test_native_horizontal_feet_match_metre_geometry_and_volume(self):
        case, gis = fixture()
        feet = deepcopy(case)
        factor = projected_crs("EPSG:2272").axis_info[0].unit_conversion_factor
        feet["crs"] = feet["terrain"]["crs"] = "EPSG:2272"
        feet["terrain"].update(
            horizontal_unit="us-ft", cell_size=1 / factor, origin=[0, 7 / factor]
        )
        feet["parcel"] = mapping(
            scale(box(0, 0, 7, 7), xfact=1 / factor, yfact=1 / factor, origin=(0, 0))
        )
        feet["features"]["features"][0]["geometry"] = mapping(
            scale(box(1, 1, 6, 6), xfact=1 / factor, yfact=1 / factor, origin=(0, 0))
        )
        first = estimate_capacity(case, gis, "01073")
        second = estimate_capacity(feet, gis, "01073")
        self.assertAlmostEqual(
            first["surface_storage_volume_cuft"], second["surface_storage_volume_cuft"]
        )
        self.assertAlmostEqual(first["footprint_area_sqft"], second["footprint_area_sqft"])
        self.assertAlmostEqual(
            first["contact_tolerance_native"] * 1, second["contact_tolerance_native"] * factor
        )

    def test_conflicting_horizontal_units_cannot_produce_a_volume(self):
        case, gis = fixture()
        case["terrain"]["horizontal_unit"] = "ft"
        result = estimate_capacity(case, gis, "01073")
        self.assertEqual(result["status"], "unavailable")
        self.assertIsNone(result["surface_storage_volume_cuft"])

    def test_terrain_in_another_crs_is_not_aligned(self):
        case, gis = fixture()
        case["terrain"]["crs"] = "EPSG:2272"
        result = estimate_capacity(case, gis, "01073")
        self.assertEqual(result["status"], "unavailable")
        self.assertIn("aligned to the case CRS", result["reason"])

    def test_common_non_grid_translation_changes_nothing(self):
        # Translating terrain origin and footprint together by a non-grid vector
        # keeps every contact and value, so all six rows are unchanged.
        case, gis = planar_fixture()
        moved = deepcopy(case)
        moved["terrain"]["origin"] = [0.37, 15 - 0.21]
        moved["parcel"] = mapping(translate(box(0, 0, 15, 15), 0.37, -0.21))
        moved["features"]["features"][0]["geometry"] = mapping(
            translate(box(4, 4, 11, 11), 0.37, -0.21)
        )
        first, second = rows(estimate_capacity(case, gis, "01073")), rows(
            estimate_capacity(moved, gis, "01073")
        )
        for name in DOCUMENTED_ROWS:
            self.assertAlmostEqual(
                first[name]["volume_cuft"], second[name]["volume_cuft"], places=6
            )

    def test_interior_hole_is_an_excluded_island_not_a_spillway(self):
        # Hole over bowl cell (row 3, col 2). Treated as a spillway, the level would
        # be 0 (no storage). Ignored, it would give 90 m3. As an island: 8 cells x 10 m.
        case, gis = fixture()
        holed = Polygon(box(1, 1, 6, 6).exterior.coords, [box(2, 3, 3, 4).exterior.coords])
        result = estimate_capacity(with_geometry(case, holed), gis, "01073")
        self.assertEqual(result["status"], "estimated")
        for name in HEADLINE:
            self.assertEqual(rows(result)[name]["component_spill_elevations_m"], [10.0])
            self.assertAlmostEqual(rows(result)[name]["volume_cuft"], 80 * CUFT_PER_M3)
        self.assertAlmostEqual(result["footprint_area_sqft"], 24 * SQFT_PER_M2)

    def test_every_documented_scenario_row_matches_hand_values(self):
        # Plane z = 0.306 + 0.02x - 0.008y off the bowl (see planar_fixture).
        #  cell minimum, mapped line: cell (row 3, col 3) touches corner (4, 11): 0.2+0.06+0.024 = 0.284
        #  bilinear, mapped line: plane at corner (4, 11): 0.306+0.08-0.088 = 0.298
        #  both methods, inward line box(4.5, 4.5, 10.5, 10.5): cell (4, 4) / plane at (4.5, 10.5) = 0.312
        #  cell minimum, outward line: touches cell (3, 3) only near the corner: 0.284
        #  bilinear, outward round corner: 0.298 - 0.5*sqrt(0.02^2 + 0.008^2)
        # Only the 9 bowl cells (z = 0) lie below every level, so volume = 9 m2 x level.
        case, gis = planar_fixture()
        result = estimate_capacity(case, gis, "01073")
        by = rows(result)
        expected = {
            "perimeter_cell_minimum": 0.284,
            "perimeter_bilinear": 0.298,
            "cell_minimum_inward_half_cell": 0.312,
            "bilinear_inward_half_cell": 0.312,
            "cell_minimum_outward_half_cell": 0.284,
            "bilinear_outward_half_cell": 0.298 - 0.5 * sqrt(0.02**2 + 0.008**2),
        }
        self.assertEqual([r["name"] for r in result["scenarios"]], list(DOCUMENTED_ROWS))
        self.assertEqual(result["status"], "estimated")
        self.assertEqual(result["volume_range_status"], "complete")
        self.assertEqual(result["volume_range_missing_scenarios"], [])
        for name, level in expected.items():
            with self.subTest(name=name):
                row = by[name]
                self.assertEqual(row["status"], "estimated")
                self.assertAlmostEqual(row["component_spill_elevations_m"][0], level, places=5)
                self.assertAlmostEqual(row["volume_cuft"], 9 * level * CUFT_PER_M3, places=3)
                self.assertAlmostEqual(row["wetted_area_sqft"], 9 * SQFT_PER_M2)
                self.assertAlmostEqual(row["max_ponding_depth_m"], level, places=5)
                self.assertAlmostEqual(row["mean_ponding_depth_m"], level, places=5)
                self.assertEqual(row["ponding_depth_check"], "within_screening_threshold")
                self.assertEqual(
                    row["method"], "cell_minimum" if "cell_minimum" in name else "bilinear"
                )
                self.assertEqual(row["matching_zero_offset_scenario"], "perimeter_" + row["method"])
        # Sensitivities are relative to the same method (H17), not to the cell-minimum primary.
        self.assertAlmostEqual(
            by["bilinear_inward_half_cell"]["volume_change_fraction_vs_matching"],
            (0.312 - 0.298) / 0.298,
        )
        self.assertAlmostEqual(
            by["cell_minimum_inward_half_cell"]["volume_change_fraction_vs_matching"],
            (0.312 - 0.284) / 0.284,
        )
        self.assertAlmostEqual(result["storage_range_cuft"][0], 9 * 0.284 * CUFT_PER_M3)
        self.assertAlmostEqual(result["storage_range_cuft"][1], 9 * 0.298 * CUFT_PER_M3)
        self.assertAlmostEqual(result["volume_range_cuft"][1], 9 * 0.312 * CUFT_PER_M3)
        self.assertNotIn("implausible_ponding_depth", [f["code"] for f in result["review_flags"]])

    def test_volume_range_lists_missing_scenarios_instead_of_dropping_them(self):
        # Footprint 0.6 m from the west grid edge: the outward line (x = 0.1) needs
        # a bilinear neighbour west of the grid; cell minimum touches column 0 only.
        case, gis = fixture()
        result = estimate_capacity(with_geometry(case, box(0.6, 1, 6, 6)), gis, "01073")
        self.assertEqual(result["status"], "estimated")
        self.assertEqual(result["volume_range_missing_scenarios"], ["bilinear_outward_half_cell"])
        self.assertEqual(result["volume_range_status"], "incomplete")
        self.assertEqual(rows(result)["cell_minimum_outward_half_cell"]["status"], "estimated")
        self.assertIn("off-grid", rows(result)["bilinear_outward_half_cell"]["reason"])

    def test_tiny_shift_cannot_change_status_availability_or_volume(self):
        # Contacts and availability must not change at all. Volumes may move only
        # continuously (shift x terrain gradient x area, plus a sliver x depth), so
        # 10 ppm here. Before the fix, the same shifts moved volumes by 50-100%.
        cases = {
            "bowl": fixture(),
            "rim_sliver": rim_sliver_fixture(),
            "diamond": diamond_fixture(),
            "planar": planar_fixture(),
        }
        nodata = fixture()
        nodata[0]["terrain"]["elevations"][0][3] = None
        cases["nodata_neighbour"] = nodata
        edge = fixture()
        cases["grid_edge"] = (with_geometry(edge[0], box(0, 1, 6, 6)), edge[1])
        for label, (case, gis) in cases.items():
            geometry = Polygon(case["features"]["features"][0]["geometry"]["coordinates"][0])
            first = estimate_capacity(case, gis, "01073")
            variants = [
                translate(geometry, dx, dy)
                for dx, dy in ((1e-6, 0), (-1e-6, 0), (0, 1e-6), (0, -1e-6))
            ]
            variants += [
                geometry.buffer(1e-6, join_style="mitre"),
                geometry.buffer(-1e-6, join_style="mitre"),
            ]
            for index, moved in enumerate(variants):
                with self.subTest(case=label, variant=index):
                    second = estimate_capacity(with_geometry(case, moved), gis, "01073")
                    self.assertEqual(first["status"], second["status"])
                    for a, b in zip(first["scenarios"], second["scenarios"], strict=True):
                        self.assertEqual(a["status"], b["status"], a["name"])
                        if a["volume_cuft"] is not None:
                            self.assertAlmostEqual(
                                a["volume_cuft"],
                                b["volume_cuft"],
                                delta=1e-5 * max(1.0, a["volume_cuft"]),
                                msg=a["name"],
                            )
                            self.assertAlmostEqual(
                                a["component_spill_elevations_m"][0],
                                b["component_spill_elevations_m"][0],
                                delta=1e-4,
                                msg=a["name"],
                            )
        self.assertEqual(
            estimate_capacity(*cases["nodata_neighbour"], "01073")["status"], "unavailable"
        )
        self.assertEqual(estimate_capacity(*cases["grid_edge"], "01073")["status"], "unavailable")

    def test_edge_aligned_perimeter_reads_both_sides_of_the_line(self):
        # Review r1: outer ring 5 m, berm 10 m. The perimeter x=1 / y=6 lines are
        # cell edges between the 5 m ring and the berm: cell minimum 5 m (45 m3).
        # Bilinear midway is 7.5 m; at the corner (1, 6) three 5 m cells and one
        # 10 m cell average to 6.25 m (56.25 m3).
        case, gis = rim_sliver_fixture()
        for shift in (0.0, 1e-6, 1e-4):
            with self.subTest(shift=shift):
                by = rows(
                    estimate_capacity(with_geometry(case, box(1 - shift, 1, 6, 6)), gis, "01073")
                )
                self.assertAlmostEqual(
                    by["perimeter_cell_minimum"]["component_spill_elevations_m"][0], 5.0
                )
                self.assertAlmostEqual(
                    by["perimeter_cell_minimum"]["volume_cuft"], 45 * CUFT_PER_M3, delta=1e-2
                )
                self.assertAlmostEqual(
                    by["perimeter_bilinear"]["component_spill_elevations_m"][0], 6.25, places=3
                )
                self.assertAlmostEqual(
                    by["perimeter_bilinear"]["volume_cuft"], 56.25 * CUFT_PER_M3, delta=0.1
                )

    def test_corner_contacts_count_for_the_cell_minimum(self):
        # Review r1b: low cells touch the diamond only at vertices. The 8-connected
        # cell model leaks there (0 m, 0 m3); bilinear reads 5 m over 24 interior
        # cells of 1 m2 (120 m3). The pair is reported as the range.
        case, gis = diamond_fixture()
        result = estimate_capacity(case, gis, "01073")
        by = rows(result)
        self.assertEqual(by["perimeter_cell_minimum"]["component_spill_elevations_m"], [0.0])
        self.assertEqual(by["perimeter_cell_minimum"]["volume_cuft"], 0.0)
        self.assertAlmostEqual(by["perimeter_bilinear"]["component_spill_elevations_m"][0], 5.0)
        self.assertAlmostEqual(by["perimeter_bilinear"]["volume_cuft"], 120 * CUFT_PER_M3)
        self.assertEqual(result["storage_range_cuft"][0], 0.0)
        self.assertAlmostEqual(result["storage_range_cuft"][1], 120 * CUFT_PER_M3)

    def test_disconnected_components_have_distinct_local_spills_and_separate_budgets(self):
        # Garden 1 in 10 m terrain, garden 2 inside a 20 m plateau (cols 7+) and
        # not edge-aligned with the step: spills 10 and 20 m, 90 and 180 m3.
        case, gis = fixture()
        array = np.full((7, 14), 10.0)
        array[:, 7:] = 20.0
        array[2:5, 2:5] = 0.0
        array[2:5, 9:12] = 0.0
        case["terrain"]["elevations"] = array.tolist()
        case["parcel"] = mapping(box(0, 0, 14, 7))
        case["features"]["features"][0]["geometry"] = mapping(
            box(1, 1, 6, 6).union(box(8, 1, 13, 6))
        )
        result = estimate_capacity(case, gis, "01073")
        self.assertEqual(result["component_count"], 2)
        self.assertTrue(result["per_component_budget_required"])
        self.assertIn("disconnected_components", [f["code"] for f in result["review_flags"]])
        self.assertEqual(
            sorted(result["scenarios"][0]["component_spill_elevations_m"]), [10.0, 20.0]
        )
        self.assertAlmostEqual(result["surface_storage_volume_cuft"], 270 * CUFT_PER_M3)
        by_id = {c["component_id"]: c for c in result["components"]}
        self.assertEqual(set(by_id), {"component-1", "component-2"})
        volumes = sorted(c["storage_range_cuft"][0] for c in result["components"])
        self.assertAlmostEqual(volumes[0], 90 * CUFT_PER_M3)
        self.assertAlmostEqual(volumes[1], 180 * CUFT_PER_M3)
        for component in result["components"]:
            self.assertAlmostEqual(component["footprint_area_sqft"], 25 * SQFT_PER_M2)
            self.assertEqual(Polygon(component["geometry"]["coordinates"][0]).area, 25)
            self.assertEqual([r["name"] for r in component["scenarios"]], list(SCENARIO_ORDER))
        self.assertEqual(sorted(result["scenarios"][0]["component_volumes_cuft"]), volumes)

    def test_overlapping_duplicate_footprints_not_double_counted(self):
        case, gis = fixture()
        duplicate = deepcopy(case["features"]["features"][0])
        duplicate["id"] = "duplicate"
        case["features"]["features"].append(duplicate)
        result = estimate_capacity(case, gis, "01073")
        self.assertAlmostEqual(result["surface_storage_volume_cuft"], 90 * CUFT_PER_M3)
        self.assertEqual(result["component_count"], 1)

    def test_underground_or_proposed_record_is_not_surface_storage_estimate(self):
        case, gis = fixture()
        case["features"]["features"][0]["properties"]["gsi_system_type"] = "Subsurface Basin"
        self.assertIsNone(estimate_capacity(case, gis, "01073")["surface_storage_volume_cuft"])
        case["features"]["features"][0]["properties"].update(
            gsi_system_type="Rain Garden", status="proposed"
        )
        self.assertEqual(estimate_capacity(case, gis, "01073")["status"], "excluded")

    def test_mapped_inlet_or_curb_cut_in_footprint_blocks_the_dem_spill(self):
        case, gis = fixture()
        case["features"]["features"].append(
            {
                "id": "overflow",
                "geometry": mapping(Point(3.5, 3.5).buffer(0.3)),
                "properties": {"layer": "inlet", "drainage_role": "inlet", "rim_elevation_m": 0.3},
            }
        )
        case["features"]["features"].append(
            {
                "id": "curbcut",
                "geometry": mapping(box(1, 3, 1.2, 4)),
                "properties": {"layer": "curb_cut"},
            }
        )
        result = estimate_capacity(case, gis, "01073")
        self.assertEqual(result["status"], "blocked")
        self.assertIsNone(result["surface_storage_volume_cuft"])
        self.assertIsNone(result["storage_range_cuft"])
        found = {s["id"]: s for s in result["drainage_structures_in_footprint"]}
        self.assertEqual(
            {k: v["role"] for k, v in found.items()}, {"overflow": "inlet", "curbcut": "curb_cut"}
        )
        self.assertEqual(found["overflow"]["rim_elevation_m"], 0.3)
        self.assertIn("inlet", result["reason"])

    def test_structures_outside_or_not_built_do_not_block(self):
        case, gis = fixture()
        case["features"]["features"].append(
            {
                "id": "street-inlet",
                "geometry": mapping(Point(6.6, 3.5)),
                "properties": {"layer": "inlet"},
            }
        )
        case["features"]["features"].append(
            {
                "id": "planned-outlet",
                "geometry": mapping(Point(3.5, 3.5)),
                "properties": {"drainage_role": "outlet", "status": "proposed"},
            }
        )
        result = estimate_capacity(case, gis, "01073")
        self.assertEqual(result["status"], "estimated")
        self.assertEqual(result["drainage_structures_in_footprint"], [])

    def test_terrain_inlet_cell_inside_footprint_blocks(self):
        case, gis = fixture()
        case["terrain"]["inlets"] = [{"id": "grid-inlet", "cell": [3, 3]}]
        result = estimate_capacity(case, gis, "01073")
        self.assertEqual(result["status"], "blocked")
        self.assertEqual(
            result["drainage_structures_in_footprint"][0]["source"], "terrain inlet cell"
        )

    def test_ponding_depth_reported_and_implausible_depth_flagged(self):
        # The 10 m deep invented bowl is far deeper than any surface rain garden.
        case, gis = fixture()
        result = estimate_capacity(case, gis, "01073")
        row = rows(result)["perimeter_cell_minimum"]
        self.assertEqual(row["max_ponding_depth_m"], 10.0)
        self.assertAlmostEqual(row["mean_ponding_depth_m"], 10.0)
        self.assertEqual(row["ponding_depth_check"], IMPLAUSIBLE_PONDING)
        self.assertEqual(result["ponding_depth_screening_threshold_m"], 1.0)
        self.assertIn("implausible_ponding_depth", [f["code"] for f in result["review_flags"]])
        self.assertEqual(result["status"], "estimated")
        # Mean over wetted area differs from max on an uneven bed: depths 10 and 5 m.
        case["terrain"]["elevations"][2][2] = 5.0
        row = rows(estimate_capacity(case, gis, "01073"))["perimeter_cell_minimum"]
        self.assertEqual(row["max_ponding_depth_m"], 10.0)
        self.assertAlmostEqual(row["mean_ponding_depth_m"], 85 / 9)

    def test_dem_predating_installation_blocks_and_dem_date_enters_lineage(self):
        case, gis = fixture()
        case["sources"] = [
            {"acquisition_date": "2015-04-01", "vertical_unit": "m", "sha256": "d" * 64}
        ]
        case["terrain"]["acquisition_date"] = "2015-04-01"
        result = estimate_capacity(case, gis, "01073")
        self.assertEqual(result["status"], "blocked")
        self.assertIn("Terrain predates system", result["reason"])
        self.assertIsNone(result["surface_storage_volume_cuft"])
        timing = result["source_lineage"]["terrain_timing"]
        self.assertEqual(
            (timing["status"], timing["dem_capture_latest"], timing["installation_year"]),
            ("predates_installation", "2015-04-01", 2024),
        )

    def test_dem_date_from_elevation_source_period_and_overlap(self):
        cases = [
            ({"acquisition_date": "2015"}, "predates_installation", "blocked"),
            (
                {"capture_period": {"capture_start": "2025-03-01", "capture_end": "2025-04-02"}},
                "after_installation",
                "estimated",
            ),
            (
                {"acquisition_period": ["2024-04-14", "2025-04-02"]},
                "overlaps_installation_year",
                "estimated",
            ),
        ]
        for record, timing, status in cases:
            with self.subTest(record=record):
                case, gis = fixture()
                case["sources"] = [
                    {"url": "image", "acquisition_date": "2010-01-01"},
                    {"url": "dem", "vertical_unit": "m", **record},
                ]
                result = estimate_capacity(case, gis, "01073")
                self.assertEqual(result["terrain_timing"]["status"], timing)
                self.assertEqual(result["status"], status)
        flags = [f["code"] for f in result["review_flags"]]
        self.assertIn("dem_overlaps_installation_year", flags)

    def test_unknown_dem_date_or_installation_year_is_flagged_not_assumed(self):
        case, gis = fixture()
        result = estimate_capacity(case, gis, "01073")
        self.assertEqual(result["status"], "estimated")
        self.assertEqual(result["terrain_timing"]["status"], "dem_date_unknown")
        self.assertIn("dem_date_unknown", [f["code"] for f in result["review_flags"]])
        case["terrain"]["acquisition_date"] = "2025-04"
        case["features"]["features"][0]["properties"].pop("year_installed")
        result = estimate_capacity(case, gis, "01073")
        self.assertEqual(result["terrain_timing"]["status"], "installation_year_unknown")
        self.assertIn("installation_year_unknown", [f["code"] for f in result["review_flags"]])

    def test_vertical_unit_status_is_carried_labelled_or_blocked(self):
        case, gis = fixture()
        self.assertEqual(
            estimate_capacity(case, gis, "01073")["vertical_unit_status"], "unrecorded"
        )
        case["terrain"]["source_quality"] = {"vertical_units": "verified"}
        verified = estimate_capacity(case, gis, "01073")
        self.assertEqual(verified["vertical_unit_status"], "verified")
        self.assertFalse([f for f in verified["review_flags"] if f["code"].startswith("vertical")])
        case["terrain"]["source_quality"] = {"vertical_units": "assumed"}
        assumed = estimate_capacity(case, gis, "01073")
        self.assertEqual(
            (assumed["status"], assumed["vertical_unit_status"]), ("estimated", "assumed")
        )
        self.assertEqual(assumed["source_lineage"]["vertical_unit_status"], "assumed")
        self.assertIn("vertical_units_assumed", [f["code"] for f in assumed["review_flags"]])
        self.assertTrue(
            all(any("assumed" in a for a in row["assumptions"]) for row in assumed["scenarios"])
        )
        for change in (
            {"source_quality": {"vertical_units": "contradicted"}},
            {"source_quality": {"vertical_units": "verified", "vertical_unit": "us-ft"}},
        ):
            with self.subTest(change=change):
                bad = deepcopy(case)
                bad["terrain"].update(change)
                result = estimate_capacity(bad, gis, "01073")
                self.assertEqual(
                    (result["status"], result["vertical_unit_status"]), ("blocked", "contradictory")
                )
                self.assertIsNone(result["surface_storage_volume_cuft"])
        reused = deepcopy(case)
        reused["terrain"]["vertical_unit"] = "ft"
        reused["terrain_reuse"] = {"vertical_unit": "m"}
        self.assertEqual(estimate_capacity(reused, gis, "01073")["status"], "blocked")

    def test_invalid_grid_parameters_rejected(self):
        for value in (0, -1, True, float("nan"), float("inf")):
            case, gis = fixture()
            case["terrain"]["cell_size"] = value
            with self.subTest(value=value), self.assertRaises(ValueError):
                estimate_capacity(case, gis, "01073")

    def test_inputs_immutable_and_no_acquisition_or_rerouting(self):
        case, gis = fixture()
        gis["input_sha256"] = input_hash(case)
        before = canonical([case, gis])
        with (
            patch("drainage_core.engine.analyze", side_effect=AssertionError("no routing")),
            patch("urllib.request.urlopen", side_effect=AssertionError("no network")),
        ):
            result = estimate_capacity(case, gis, "01073")
        self.assertEqual(result["status"], "estimated")
        self.assertEqual(canonical([case, gis]), before)
        gis["input_sha256"] = "0" * 64
        with self.assertRaisesRegex(ValueError, "does not match"):
            estimate_capacity(case, gis, "01073")


if __name__ == "__main__":
    unittest.main()
