"""Phase 3 regressions: geometry clipping, routing robustness and extent tests.

Each case converts a 2026-11-16 review repro (docs/review-2026-11-16-repros/gis,
imagery/r7) into an assertion of the corrected behaviour. Synthetic terrain checks
algorithm behaviour only, not real-site accuracy.
"""

from copy import deepcopy
import unittest

import numpy as np
from shapely.geometry import LineString, Point, Polygon, box, mapping, shape

from drainage_core.drainage import route_grid
from drainage_core.engine import analyze, new_case
from drainage_core.geometry import SQFT_PER_M2, measure
from drainage_core.installation import classify_status, installation_issues, installation_status
from drainage_core.research import (
    _mask,
    accumulate,
    analyze_research,
    condition,
    feature_inputs,
    run_model,
)

UTM = "EPSG:32618"
X, Y = 500000, 4400000


def F(identifier, geometry, **properties):
    return {
        "type": "Feature",
        "id": identifier,
        "geometry": mapping(geometry),
        "properties": properties,
    }


def utm_case(n=20, elevations=None, **settings):
    c = new_case("Invented Phase 3 check", crs=UTM)
    c["id"] = "phase3"
    c["parcel"] = mapping(box(X, Y - n, X + n, Y))
    c["terrain"] = {
        "crs": UTM,
        "origin": [X, Y],
        "cell_size": 1,
        "horizontal_unit": "m",
        "vertical_unit": "m",
        "elevations": elevations
        or [[10 - 0.02 * r - 0.03 * cc for cc in range(n)] for r in range(n)],
        "settings": {"extent_sufficient": False, "max_flow_paths": 5, **settings},
    }
    return c


class ClippingTests(unittest.TestCase):
    """C1 (r17_sideyard, r18_tb): touching neighbours clip to lines/points."""

    def sideyard(self, feats):
        c = new_case("t", crs="EPSG:2272")
        c["id"] = "t17"
        x, y = 2690000, 240000
        c["parcel"] = mapping(box(x, y - 100, x + 30, y))
        c["features"]["features"] = feats(x, y)
        return c

    def test_neighbour_roof_touching_line_or_corner_measures(self):
        layouts = [
            lambda x, y: [
                F("r", box(x, y - 60, x + 20, y), layer="surface", **{"class": "roof"}),
                F("n", box(x + 30, y - 60, x + 50, y), layer="surface", **{"class": "roof"}),
                F("s", box(x + 20, y - 60, x + 30, y), layer="surface", **{"class": "pervious"}),
            ],
            lambda x, y: [
                F("r", box(x, y - 60, x + 20, y), layer="surface", **{"class": "roof"}),
                F("n", box(x + 30, y - 60, x + 50, y), layer="surface", **{"class": "roof"}),
            ],
            lambda x, y: [
                F("r", box(x, y - 60, x + 20, y), layer="surface", **{"class": "roof"}),
                F("n", box(x + 30, y, x + 40, y + 10), layer="surface", **{"class": "roof"}),
            ],
        ]
        factor = (1200 / 3937 / 0.3048) ** 2
        for feats in layouts:
            with self.subTest(layout=feats):
                m = measure(self.sideyard(feats))
                self.assertAlmostEqual(m["ia_sqft"], 1200 * factor, places=6)
                self.assertAlmostEqual(m["roof_sqft"], 1200 * factor, places=6)

    def test_full_analysis_with_touching_neighbour_roof(self):
        c = self.sideyard(
            lambda x, y: [
                F("r", box(x, y - 60, x + 20, y), layer="surface", **{"class": "roof"}),
                F("n", box(x + 30, y - 60, x + 50, y), layer="surface", **{"class": "roof"}),
                F("s", box(x + 20, y - 60, x + 30, y), layer="surface", **{"class": "pervious"}),
            ]
        )
        result = analyze(c)
        self.assertGreater(result["measurement"]["ia_sqft"], 0)
        self.assertGreater(result["measurement"]["pervious_sqft"], 0)


class OverlapPrecedenceTests(unittest.TestCase):
    """C2 (r1_overlap): ordinary layouts route instead of raising."""

    def analyze(self, feats):
        c = utm_case()
        c["terrain"]["elevations"] = [
            [10 - 0.05 * r - 0.01 * cc for cc in range(20)] for r in range(20)
        ]
        c["research_drainage"] = {"sensitivity": False}
        c["features"]["features"] = feats
        return analyze(c)

    def rep(self, result, identifier):
        return next(
            r for r in result["drainage"]["feature_representation"] if r["id"] == identifier
        )

    def test_wall_abutting_or_inside_house_uses_barrier_precedence(self):
        house = F("house", box(X + 2, Y - 10, X + 10, Y - 2), layer="surface", **{"class": "roof"})
        for wall in (
            LineString([(X + 10, Y - 10), (X + 10, Y - 18)]),
            LineString([(X + 9.7, Y - 1), (X + 9.7, Y - 18)]),
        ):
            with self.subTest(wall=wall.wkt):
                r = self.analyze([house, F("wall", wall, layer="barrier")])
                self.assertEqual(self.rep(r, "house")["status"], "represented")
                self.assertEqual(self.rep(r, "wall")["status"], "represented")
                labels = r["drainage"]["labels"]
                self.assertEqual(labels[9][9], "barrier")  # touched by both; barrier wins
                self.assertTrue(any("barrier precedence" in w for w in r["drainage"]["warnings"]))

    def test_inlet_next_to_curb_clears_its_own_cell(self):
        r = self.analyze(
            [
                F("curb", LineString([(X, Y - 15), (X + 20, Y - 15)]), layer="barrier"),
                F("inlet-1", Point(X + 10.5, Y - 15.3), layer="inlet"),
            ]
        )
        inlet = self.rep(r, "inlet-1")
        self.assertEqual(inlet["status"], "represented")
        self.assertEqual(inlet["cleared"], ["barrier"])
        self.assertEqual(r["drainage"]["labels"][15][10], "inlet:inlet-1")
        self.assertGreaterEqual(r["drainage"]["counts"]["inlet:inlet-1"], 1)

    def test_inlet_outside_terrain_is_recorded_not_raised(self):
        r = self.analyze(
            [
                F("inlet-far", Point(X + 30, Y - 5), layer="inlet"),
                F(
                    "pipe",
                    LineString([(X + 30, Y - 5), (X + 40, Y - 5)]),
                    layer="connection",
                    **{"from": "inlet-far", "to": "sewer", "evidence": "documented"},
                ),
            ]
        )
        inlet = self.rep(r, "inlet-far")
        self.assertEqual(inlet["status"], "not_represented_on_grid")
        self.assertEqual(inlet["reason"], "outside terrain extent")
        self.assertTrue(
            any("inlet-far" in w and "not represented" in w for w in r["drainage"]["warnings"])
        )
        self.assertTrue(
            any(
                "Connection from unrepresented inlet inlet-far" in w
                for w in r["drainage"]["warnings"]
            )
        )

    def test_two_inlets_in_one_cell_keep_the_first_and_report_the_other(self):
        r = self.analyze(
            [
                F("a", Point(X + 5.2, Y - 5.2), layer="inlet"),
                F("b", Point(X + 5.8, Y - 5.8), layer="inlet"),
            ]
        )
        self.assertEqual(self.rep(r, "a")["status"], "represented")
        self.assertEqual(self.rep(r, "b")["reason"], "shares a grid cell with inlet a")


class CornerBlockingTests(unittest.TestCase):
    """C3 (r2_diag): raised walls/berms do not leak diagonally."""

    def test_router_blocks_diagonal_between_raised_corner_cells(self):
        grid = {
            "elevations": [[3, 4], [4, 0]],
            "cell_size": 1,
            "horizontal_unit": "m",
            "vertical_unit": "m",
        }
        self.assertEqual(route_grid(grid)["next_cells"][0][0], [1, 1])
        blocked = route_grid({**grid, "corner_blocking": [[0, 1], [1, 0]]})
        self.assertIsNone(blocked["next_cells"][0][0])
        self.assertNotEqual(blocked["labels"][0][0], blocked["labels"][1][1])

    def test_diagonal_berm_and_low_offset_wall_have_no_crossing_pointers(self):
        n = 20
        inverse = {
            1: (0, 1),
            2: (1, 1),
            4: (1, 0),
            8: (1, -1),
            16: (0, -1),
            32: (-1, -1),
            64: (-1, 0),
            128: (-1, 1),
        }
        line = LineString([(X, Y), (X + n, Y - n)])
        for role, kwargs in (
            ("berm", {}),
            ("wall", {"offset_scale": 0.5, "inlet_buffer_m": 0.305}),
            ("wall", {}),
        ):
            with self.subTest(role=role, kwargs=kwargs):
                c = utm_case(
                    n, [[10 + 0.05 * (cc - r) + 0.001 * r for cc in range(n)] for r in range(n)]
                )
                c["features"]["features"] = [
                    F("w", line, layer=role),
                    F("g", box(X + 2, Y - 18, X + 6, Y - 14), layer="gsi", gsi_system_id="G1"),
                ]
                out = run_model(c, measure(c), feature_inputs(c)[0], **kwargs)
                self.assertGreater(out["corner_blocking_cells"], 0)
                d = out["rasters"]["direction_d8"]
                crossings = 0
                for r in range(n):
                    for cc in range(n):
                        if d[r][cc] in inverse:
                            dr, dc = inverse[d[r][cc]]
                            crossings += cc > r and (cc + dc) < (r + dr)
                self.assertEqual(crossings, 0)
                walled = Polygon([(X, Y), (X + n, Y), (X + n, Y - n)])
                gsi = shape(out["catchments"][0]["geometry"])
                # Only the wall/berm's own straddling cells can reach the GSI from the high side.
                self.assertLessEqual(gsi.intersection(walled).area, 10)


class CollectionInsideGsiTests(unittest.TestCase):
    """C4 (r11_compete): an inlet inside a GSI footprint is part of that GSI."""

    def run_case(self, extra):
        n = 24
        c = utm_case(n)
        c["features"]["features"] = [
            F("pave", box(X, Y - n, X + n, Y), layer="surface", **{"class": "pavement"}),
            F("rg", box(X + 12, Y - 16, X + 16, Y - 12), layer="gsi", gsi_system_id="G1"),
        ] + extra
        return run_model(c, measure(c), feature_inputs(c)[0])

    def test_overflow_inlet_inside_gsi_does_not_erase_catchment(self):
        alone = self.run_case([])
        with_inlet = self.run_case([F("ovf", Point(X + 15.5, Y - 15.5), layer="inlet")])
        self.assertGreater(alone["known_ia_union_sqft"], 0)
        self.assertGreaterEqual(with_inlet["known_ia_union_sqft"], alone["known_ia_union_sqft"])
        self.assertEqual(with_inlet["contained_collection_features"], {"ovf": ["G1"]})
        self.assertEqual([c["gsi_id"] for c in with_inlet["catchments"]], ["G1"])

    def test_inlet_outside_gsi_without_link_stays_unassigned(self):
        out = self.run_case([F("drain", Point(X + 5.5, Y - 5.5), layer="inlet")])
        self.assertEqual(out["contained_collection_features"], {})
        self.assertTrue(any("Downstream connection" in b["reason"] for b in out["micro_basins"]))


class RasterizationTests(unittest.TestCase):
    """C5 (r12_lowbuf, r9_curbcut): small point/line features stay on the grid."""

    def test_small_buffer_points_and_short_curb_cuts_always_rasterize(self):
        rng = np.random.default_rng(1)
        for size in (1.0, 0.9144, 2.0):
            grid = {
                "cell_size": size,
                "horizontal_unit": "m",
                "origin": [0, 20],
                "elevations": [[0] * 20] * 20,
            }
            for _ in range(300):
                self.assertTrue(_mask(mapping(Point(*rng.uniform(5, 15, 2))), grid, 0.305).any())
        grid = {
            "cell_size": 1,
            "horizontal_unit": "m",
            "origin": [0, 10],
            "elevations": [[0] * 10] * 10,
        }
        for _ in range(300):
            x0, y0 = rng.uniform(3, 6, 2)
            a = rng.uniform(0, np.pi)
            length = rng.uniform(1.5, 3)
            line = LineString([(x0, y0), (x0 + length * np.cos(a), y0 + length * np.sin(a))])
            self.assertTrue(_mask(mapping(line), grid, 0.152).any())

    def test_polygons_remain_centre_rasterized_and_tiny_collection_polygons_fall_back(self):
        grid = {
            "cell_size": 1,
            "horizontal_unit": "m",
            "vertical_unit": "m",
            "origin": [0, 7],
            "elevations": [[10] * 7] * 7,
        }
        out = condition(
            grid,
            [
                {"id": "berm", "role": "berm", "geometry": mapping(box(3.01, 2, 3.05, 5))},
                {"id": "grate", "role": "inlet", "geometry": mapping(box(3.01, 3.01, 3.05, 3.05))},
            ],
            inlet_buffer_m=0,
        )
        audit = {a["id"]: a for a in out["features"]}
        self.assertEqual(audit["berm"]["rasterization"], "centre")
        self.assertEqual(audit["berm"]["raster_cells"], 0)
        self.assertEqual(audit["grate"]["rasterization"], "touched_fallback")
        self.assertGreater(audit["grate"]["raster_cells"], 0)

    def test_unrepresented_features_are_warned_in_every_run(self):
        c = utm_case(10)
        c["research_drainage"] = {
            "sensitivity": True,
            "features": [
                {
                    "id": "G-far",
                    "role": "gsi",
                    "gsi_id": "G9",
                    "geometry": mapping(box(X + 50, Y - 5, X + 52, Y - 3)),
                }
            ],
        }
        r = analyze_research(c, measure(c), {})
        self.assertEqual(r["primary"]["not_represented_features"], ["G-far"])
        for name in ("nominal", "low_offsets", "high_offsets", "coarser_2x"):
            self.assertTrue(any(f"{name} routing grid: G-far" in w for w in r["warnings"]), name)


class CanopyCoverageTests(unittest.TestCase):
    """C6 (r6_canopy): coverage status and outline bound canopy absence."""

    def measure(self, observation, with_tree=True):
        c = new_case("t", crs=UTM)
        c["id"] = "t6"
        c["parcel"] = mapping(box(X, Y - 20, X + 20, Y))
        c["features"]["features"] = [
            F("pave", box(X, Y - 20, X + 20, Y), layer="surface", **{"class": "pavement"})
        ]
        if with_tree:
            c["features"]["features"].append(F("tree", box(X, Y - 5, X + 5, Y), layer="canopy"))
        c["canopy_observation"] = observation
        return measure(c)

    def test_unavailable_status_keeps_full_upper_bound_and_warning(self):
        m = self.measure({"status": "unavailable"})
        self.assertAlmostEqual(m["canopy_ground_ia_upper_sqft"], 400 * SQFT_PER_M2, places=6)
        self.assertAlmostEqual(m["canopy_ground_ia_sqft"], 25 * SQFT_PER_M2, places=6)
        self.assertFalse(m["canopy_coverage_complete"])
        self.assertTrue(any("Canopy coverage unavailable" in w for w in m["warnings"]))

    def test_partial_outline_establishes_absence_only_inside_it(self):
        m = self.measure(
            {"status": "partial", "coverage_geometry": mapping(box(X, Y - 20, X + 5, Y))}
        )
        self.assertAlmostEqual(m["canopy_ground_ia_upper_sqft"], (25 + 300) * SQFT_PER_M2, places=6)
        self.assertAlmostEqual(m["canopy_unobserved_sqft"], 300 * SQFT_PER_M2, places=6)
        self.assertTrue(any("outside the partial coverage outline" in w for w in m["warnings"]))
        m = self.measure(
            {"status": "partial", "coverage_geometry": mapping(box(X, Y - 20, X + 5, Y))},
            with_tree=False,
        )
        self.assertAlmostEqual(m["canopy_ground_ia_upper_sqft"], 300 * SQFT_PER_M2, places=6)

    def test_complete_status_bounds_by_observed_canopy(self):
        m = self.measure({"status": "complete"})
        self.assertAlmostEqual(m["canopy_ground_ia_upper_sqft"], 25 * SQFT_PER_M2, places=6)
        self.assertTrue(m["canopy_coverage_complete"])
        self.assertFalse(any("Canopy coverage" in w for w in m["warnings"]))


class FlatToleranceTests(unittest.TestCase):
    """C7 (r5_tol): flat_tolerance never creates flow cycles."""

    def test_review_rows_route_without_cycles(self):
        for elevations, tolerance in (
            ([[5.0, 5.9, 4.5]], 1.0),
            ([[10.00, 10.04, 9.98, 10.2], [10.3, 10.3, 10.3, 10.3]], 0.05),
        ):
            out = route_grid(
                {
                    "elevations": elevations,
                    "cell_size": 1,
                    "horizontal_unit": "m",
                    "vertical_unit": "m",
                    "settings": {"flat_tolerance": tolerance},
                }
            )
            self.assertFalse(any("cycle" in label for row in out["labels"] for label in row))
            accumulate(out["next_cells"], out["labels"])
        c = new_case("t", crs=UTM)
        c["id"] = "t5"
        c["parcel"] = mapping(box(X, Y - 2, X + 4, Y))
        c["terrain"] = {
            "crs": UTM,
            "origin": [X, Y],
            "cell_size": 1,
            "horizontal_unit": "m",
            "vertical_unit": "m",
            "elevations": [[10.00, 10.04, 9.98, 10.2], [10.3] * 4],
            "settings": {"flat_tolerance": 0.05},
        }
        self.assertIn("primary", analyze(c)["research_drainage"])

    def test_random_noisy_terrain_with_tolerance_is_acyclic(self):
        rng = np.random.default_rng(7)
        for _ in range(150):
            rows, cols = rng.integers(2, 9, 2)
            z = (
                (
                    10
                    + rng.normal(0, 0.04, (rows, cols))
                    + rng.choice([0, 0.3], (rows, cols), p=[0.8, 0.2])
                )
                .round(3)
                .tolist()
            )
            out = route_grid(
                {
                    "elevations": z,
                    "cell_size": 1,
                    "horizontal_unit": "m",
                    "vertical_unit": "m",
                    "settings": {"flat_tolerance": float(rng.choice([0.02, 0.05, 0.1]))},
                }
            )
            self.assertFalse(any("cycle" in label for row in out["labels"] for label in row), z)
            accumulate(out["next_cells"], out["labels"])

    def test_zero_tolerance_unchanged_for_flat_exit(self):
        out = route_grid(
            {
                "elevations": [[3, 3, 3, 2, 1]],
                "cell_size": 1,
                "horizontal_unit": "m",
                "vertical_unit": "m",
                "inlets": [{"id": "A", "cell": [0, 4]}],
            }
        )
        self.assertEqual(out["counts"], {"inlet:A": 5})
        self.assertEqual(out["next_cells"][0][0], [0, 1])


class ValidationTargetTests(unittest.TestCase):
    """C8 (r4_validation): references can target modeled receiver catchments."""

    def case(self, references):
        n = 20
        c = utm_case(n, [[10 - 0.02 * r - 0.03 * cc for cc in range(n)] for r in range(n)])
        c["features"]["features"] = [
            F("pave", box(X, Y - n, X + n, Y), layer="surface", **{"class": "pavement"}),
            F("rg", box(X + 12, Y - 14, X + 16, Y - 10), layer="gsi", gsi_system_id="G1"),
        ]
        c["research_drainage"] = {"sensitivity": False}
        base = {
            "kind": "drainage",
            "geometry": mapping(box(X + 8, Y - 16, X + 16, Y - 6)),
            "crs": UTM,
            "independent": True,
            "source_url": "https://example.org/survey",
            "stable_site_verified": True,
        }
        c["references"] = [{**base, "id": "ref" + str(i), **r} for i, r in enumerate(references)]
        return analyze(c)["validation"]["drainage"]

    def test_research_and_integration_catchments_are_measurable_by_receiver_id(self):
        v = self.case(
            [
                {"outlet": "G1"},
                {"outlet": "gsi:G1"},
                {"receiver_id": "G1"},
                {"receiver_id": "G1", "model": "integration", "run": "nominal"},
            ]
        )
        self.assertEqual(v["status"], "measured")
        self.assertEqual(v["blockers"], [])
        self.assertEqual(
            [r["target"].get("model") for r in v["results"]], ["research"] * 3 + ["integration"]
        )
        self.assertTrue(all(r["target"]["receiver_id"] == "G1" for r in v["results"]))
        self.assertGreater(v["results"][0]["metrics"]["intersection_over_union"], 0)

    def test_unknown_receiver_stays_incomplete(self):
        v = self.case([{"receiver_id": "G404"}])
        self.assertEqual(v["status"], "incomplete")
        self.assertEqual(v["blockers"], ["No reconstructed catchment for reference outlet"])


class RoofAccountingTests(unittest.TestCase):
    """C9 (r10_sliver) and C10 roof connections from case features."""

    def case(self, extra=()):
        n = 20
        c = utm_case(n)
        c["terrain"]["settings"] = {}
        house = box(X + 2.6, Y - 12.4, X + 12.4, Y - 2.6)
        c["features"]["features"] = [
            F("house", house, layer="surface", **{"class": "roof"}),
            F(
                "lawn",
                box(X, Y - n, X + n, Y).difference(house),
                layer="surface",
                **{"class": "pervious"},
            ),
            F("in1", Point(X + 19.5, Y - 19.5), layer="inlet"),
            *extra,
        ]
        c["research_drainage"] = {"enabled": False}
        return analyze(c)["drainage"]

    def test_roof_slivers_are_not_credited_to_ground_outlets(self):
        d = {k["outlet"]: k for k in self.case()["catchments"]}
        self.assertLess(d["inlet:in1"]["on_parcel_physical_ia_sqft"], 1e-6)
        self.assertAlmostEqual(d["unresolved:roof"]["on_parcel_physical_ia_m2"], 81, places=6)

    def test_roof_connection_feature_routes_roof_cells(self):
        d = self.case(
            [
                F(
                    "downspout",
                    LineString([(X + 7, Y - 7), (X + 19.5, Y - 19.5)]),
                    layer="connection",
                    **{"from": "house", "to": "in1", "evidence": "documented"},
                )
            ]
        )
        catchments = {k["outlet"]: k for k in d["catchments"]}
        self.assertNotIn("unresolved:roof", catchments)
        self.assertAlmostEqual(
            catchments["inlet:in1"]["on_parcel_physical_ia_m2"], 9.8 * 9.8, places=6
        )
        self.assertEqual(d["counts"], {"inlet:in1": 400})


class ExtentTests(unittest.TestCase):
    """A2 (r7_extent): measured coverage and per-catchment edge/NoData contact."""

    def test_run_extent_honours_measured_coverage_and_nodata(self):
        n = 20
        elevations = [[10 - 0.02 * r - 0.03 * cc for cc in range(n)] for r in range(n)]
        for r in range(15, 20):
            for cc in range(5):
                elevations[r][cc] = None
        c = utm_case(n, elevations, extent_sufficient=True, required_buffer_native_units=45)
        c["parcel"] = mapping(box(X, Y - 30, X + 30, Y))
        c["features"]["features"] = [
            F("pave", box(X, Y - 30, X + 30, Y), layer="surface", **{"class": "pavement"}),
            F("rg", box(X + 12, Y - 14, X + 16, Y - 10), layer="gsi", gsi_system_id="G1"),
        ]
        c["research_drainage"] = {"sensitivity": False}
        r = analyze(c)
        p = r["research_drainage"]["primary"]
        self.assertFalse(r["drainage"]["extent_sufficient"])
        self.assertFalse(p["extent_sufficient"])
        self.assertFalse(p["coverage"]["terrain_covers_parcel_buffer"])
        self.assertEqual(p["coverage"]["nodata_cells_in_parcel_buffer"], 25)
        self.assertEqual(
            [run["extent_sufficient"] for run in r["modeled_integration"]["runs"]], [False]
        )
        self.assertFalse(p["catchments"][0]["extent_complete"])

    def dome(self, nodata=None):
        n = 9
        z = [[10 - 0.5 * max(abs(r - 4), abs(cc - 4)) for cc in range(n)] for r in range(n)]
        if nodata:
            z[nodata[0]][nodata[1]] = None
        c = new_case("Invented dome", crs=UTM)
        c["id"] = "dome"
        c["parcel"] = mapping(box(X, Y - n, X + n, Y))
        c["terrain"] = {
            "crs": UTM,
            "origin": [X, Y],
            "cell_size": 1,
            "horizontal_unit": "m",
            "vertical_unit": "m",
            "elevations": z,
            "settings": {"extent_sufficient": False},
        }
        c["research_drainage"] = {
            "sensitivity": False,
            "features": [
                {
                    "id": "top",
                    "role": "gsi",
                    "gsi_id": "G1",
                    "geometry": mapping(box(X + 4.2, Y - 4.8, X + 4.8, Y - 4.2)),
                },
                {
                    "id": "side",
                    "role": "gsi",
                    "gsi_id": "G2",
                    "geometry": mapping(box(X + 8.2, Y - 4.8, X + 8.8, Y - 4.2)),
                },
            ],
        }
        return analyze(c)

    def test_interior_catchment_is_complete_and_edge_catchment_is_not(self):
        r = self.dome()
        p = r["research_drainage"]["primary"]
        rows = {c["gsi_id"]: c for c in p["catchments"]}
        self.assertTrue(p["coverage"]["coverage_complete"])
        self.assertEqual(
            {
                k: rows["G1"][k]
                for k in ("touches_window_edge", "touches_nodata", "extent_complete")
            },
            {"touches_window_edge": False, "touches_nodata": False, "extent_complete": True},
        )
        self.assertTrue(rows["G2"]["touches_window_edge"])
        self.assertFalse(rows["G2"]["extent_complete"])
        # The reviewer flag stays false; the per-catchment test does not depend on it.
        self.assertFalse(p["extent_sufficient"])
        integration = {
            c["receiver_id"]: c for c in r["modeled_integration"]["runs"][0]["catchments"]
        }
        self.assertTrue(integration["G1"]["extent_complete"])
        self.assertFalse(integration["G2"]["extent_complete"])

    def test_nodata_next_to_catchment_marks_contact(self):
        r = self.dome(nodata=(3, 3))
        rows = {c["gsi_id"]: c for c in r["research_drainage"]["primary"]["catchments"]}
        self.assertTrue(rows["G1"]["touches_nodata"])
        self.assertFalse(rows["G1"]["extent_complete"])


class EdgeErosionTests(unittest.TestCase):
    """D1 (imagery/r7_edge_lower): pixel-edge erosion never erodes the parcel line."""

    def rowhouse(self, classes_fn):
        from drainage_core.remote_sensing import classified_features

        x0, y0 = 2691200.0, 238600.0
        case = {"crs": "EPSG:2272", "parcel": mapping(box(x0, y0, x0 + 16, y0 + 60))}
        bounds = [x0 - 100, y0 - 100, x0 + 116, y0 + 160]
        w = int(np.ceil(216 * 0.3048006 / 0.5))
        h = int(np.ceil(260 * 0.3048006 / 0.5))
        classes = classes_fn(w, h)
        r = classified_features(
            classes,
            bounds,
            case,
            {"family": "t", "url": None, "sha256": "0" * 64, "vintage": "2025"},
        )
        return {e["feature"]: e for e in r["estimates"]}, 216 / w, 260 / h

    def test_fully_roofed_rowhouse_lower_bound_is_full_area(self):
        rows, _, _ = self.rowhouse(lambda w, h: np.full((h, w), 5, dtype="uint8"))
        self.assertAlmostEqual(
            rows["roof"]["area_sqft"], 960 * (1200 / 3937 / 0.3048) ** 2, places=3
        )
        self.assertAlmostEqual(rows["roof"]["edge_lower_sqft"], rows["roof"]["area_sqft"], places=6)

    def test_lower_bound_erodes_only_the_internal_class_edge(self):
        def split(w, h):
            a = np.full((h, w), 5, dtype="uint8")
            a[:, int(108 / (216 / w)) :] = 6
            return a

        rows, pw, ph = self.rowhouse(split)
        band = 60 * (pw**2 + ph**2) ** 0.5 / 2 * (1200 / 3937 / 0.3048) ** 2
        for name in ("roof", "road"):
            self.assertAlmostEqual(
                rows[name]["area_sqft"] - rows[name]["edge_lower_sqft"], band, places=3
            )

    def test_composition_lower_bound_keeps_parcel_line(self):
        from drainage_core.model_integration import composition, EMPTY

        c = new_case("t", crs=UTM)
        c["parcel"] = mapping(box(X, Y - 10, X + 10, Y))
        ai = {
            "status": "modeled",
            "edge_distance_native": 0.5,
            "coverage_geometry": c["parcel"],
            "uncertainty": [],
            "geometries": {"roof": c["parcel"]},
        }
        observation = {"geometries": {"physical_ia": EMPTY, "unknown": c["parcel"]}}
        roof = next(
            row
            for row in composition(c, ai, observation, c["parcel"])["classes"]
            if row["class"] == "roof"
        )
        self.assertAlmostEqual(roof["edge_lower_sqft"], roof["area_sqft"], places=6)


class InstallationAllowlistTests(unittest.TestCase):
    """D2: status allowlist; unknown is not a failure."""

    def test_not_existing_statuses_fail(self):
        for state in (
            "Construction",
            "Under Construction",
            "Planned",
            "Bid",
            "Inactive",
            "Abandoned",
            "Design Complete",
            "Proposed",
            "Removed",
            "Incomplete",
            "Not Installed",
            "Pre-Construction",
        ):
            with self.subTest(state=state):
                self.assertTrue(installation_issues({"status": state}, "2026-11-16"))
                self.assertEqual(
                    installation_status({"status": state}, "2026-11-16")["status"], "contradicted"
                )

    def test_allowlisted_and_year_establish_existing(self):
        for props in (
            {"status": "Complete"},
            {"status": "Constructed"},
            {"public_status": "Construction Complete"},
            {"status": "In Service"},
            {"year_installed": 2019},
        ):
            with self.subTest(props=props):
                self.assertEqual(
                    installation_status(props, "2026-11-16"), {"status": "existing", "issues": []}
                )

    def test_unknown_status_is_unverified_not_failed(self):
        for props in (
            {},
            {"status": "unknown"},
            {"status": "Active"},
            {"public_status": "Private Project"},
        ):
            with self.subTest(props=props):
                self.assertEqual(
                    installation_status(props, "2026-11-16"), {"status": "unknown", "issues": []}
                )
        self.assertEqual(classify_status("Planting"), "unknown")

    def test_construction_gsi_is_not_a_research_receiver(self):
        c = utm_case(7)
        c["features"]["features"] = [
            F(
                "rg",
                box(X + 3, Y - 4, X + 4, Y - 3),
                layer="gsi",
                gsi_system_id="G1",
                status="Under Construction",
            )
        ]
        features, omitted = feature_inputs(c)
        self.assertEqual(features, [])
        self.assertIn("under construction", omitted[0]["reason"])

    def test_public_candidate_construction_is_proposed_only(self):
        from stormwater.assessment_sources import normalize_gsi

        def record(state):
            return normalize_gsi(
                {"id": 1, "properties": {"gsi_system_type": "Green Roof", "status": state}},
                "https://example.test/gsi",
                "EPSG:2272",
            )[0]["facts"]

        self.assertTrue(record("Construction")["proposed_only"])
        self.assertTrue(record("Bid")["proposed_only"])
        self.assertFalse(record("Complete")["proposed_only"])
        self.assertFalse(record("Removed")["proposed_only"])
        self.assertTrue(installation_issues(record("Removed"), "2026-11-16"))


class InvariantLabelTests(unittest.TestCase):
    """C10: accounting invariants are not presented as validation checks."""

    def test_research_reports_invariant_not_conservation_check(self):
        from drainage_core.report import render_report

        c = utm_case(7)
        c["research_drainage"] = {"sensitivity": False}
        result = analyze(c)
        p = result["research_drainage"]["primary"]
        self.assertNotIn("area_conservation_pass", p)
        self.assertTrue(p["invariants"]["terminal_accumulation_equals_routed_cells"])
        html = render_report(c, result)
        self.assertNotIn("<th>Conservation</th>", html)
        self.assertIn("not validation evidence", html)


if __name__ == "__main__":
    unittest.main()
