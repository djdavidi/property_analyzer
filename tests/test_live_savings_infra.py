"""LIVE-SAVINGS review infrastructure fixes: lookup ranges, failed-source retry,
terrain mosaics and routing cap, compact responses, slim report, owner summary and
stage timings. Hermetic: no network, no data/ directory."""

from copy import deepcopy
from hashlib import sha256
import io
import json
from pathlib import Path
import random
import tempfile
import unittest
from unittest.mock import Mock, patch

import numpy as np
import rasterio
from rasterio.io import MemoryFile
from rasterio.transform import from_origin
from shapely.geometry import box, mapping

import network_guard
import reference_algorithms as ref
import test_server as baseline_http
from test_automatic_site import fixture, lc, png


def setUpModule():
    network_guard.install()


# ---------------------------------------------------------------- 1. lookup


def parcels(*addresses):
    cache = Mock()
    cache.fetch_json.return_value = {
        "data": {
            "features": [
                {"id": i + 1, "properties": {"parcelid": 100 + i, "address": a}}
                for i, a in enumerate(addresses)
            ]
        },
        "provenance": {"sha256": "a" * 64},
    }
    return cache


class AddressLookupTests(unittest.TestCase):
    STREET = (
        "1000-10 N DELAWARE AVE",
        "1001-99 N DELAWARE AVE",
        "1020-84 N DELAWARE AVE",
        "1001 S DELAWARE AVE",
        "1007-13 NEW DELAWARE AVE",
    )

    def lookup(self, query, *addresses):
        from stormwater.automatic import lookup

        cache = parcels(*(addresses or self.STREET))
        return lookup(query, cache), cache

    def test_range_addresses_parse_with_abbreviated_ends(self):
        from stormwater.automatic import parse_address, _range_end

        self.assertEqual(parse_address("1001-99 N Delaware Ave")["high"], 1099)
        self.assertEqual(parse_address("608-24 N DELAWARE AVE")["high"], 624)
        self.assertEqual(parse_address("1603-05 N DELAWARE AVE")["high"], 1605)
        self.assertEqual(parse_address("1001 - 1099 N DELAWARE AVE")["high"], 1099)
        self.assertEqual(_range_end(1098, "02"), 1102)
        self.assertEqual(parse_address("1001R N DELAWARE AVE")["suffix"], "R")
        self.assertIsNone(parse_address("Philadelphia"))

    def test_hyphenated_input_is_accepted_and_matches_the_stored_range(self):
        found, cache = self.lookup("1001-99 N Delaware Ave, Philadelphia PA")
        self.assertEqual([m["address"] for m in found["matches"]], ["1001-99 N DELAWARE AVE"])
        self.assertEqual(found["matches"][0]["match"], "exact_address")
        url = cache.fetch_json.call_args.args[0]
        self.assertIn("LIKE+%271001%25N+DELAWARE+AVE%25%27", url)
        self.assertIn("LIKE+%27%25-%25%27", url)

    def test_house_number_inside_a_range_on_the_same_side_and_street(self):
        found, _ = self.lookup("1001 N Delaware Ave")
        self.assertEqual(
            [(m["parcel_id"], m["match"]) for m in found["matches"]], [(101, "range_contains")]
        )
        found, _ = self.lookup("1057 N Delaware Ave")
        self.assertEqual([m["address"] for m in found["matches"]], ["1001-99 N DELAWARE AVE"])
        # 1050 is on the even side: inside 1020-84, never the odd 1001-99 range.
        found, _ = self.lookup("1050 N Delaware Ave")
        self.assertEqual([m["address"] for m in found["matches"]], ["1020-84 N DELAWARE AVE"])
        found, _ = self.lookup("1001-1099 N Delaware Ave")
        self.assertEqual([m["match"] for m in found["matches"]], ["same_range"])

    def test_other_streets_and_numbers_do_not_match(self):
        found, _ = self.lookup("1101 N Delaware Ave")
        self.assertEqual(found["matches"], [])
        found, _ = self.lookup("1009 Delaware Ave")
        self.assertEqual(found["matches"], [])

    def test_ambiguity_is_returned_for_selection_never_resolved_silently(self):
        found, _ = self.lookup(
            "1003 N Delaware Ave", "1001-99 N DELAWARE AVE", "1003 N DELAWARE AVE REAR"
        )
        self.assertEqual(len(found["matches"]), 2)
        found, _ = self.lookup("5300 Test Ave", "5300 TEST AVE A", "5300 TEST AVE B")
        self.assertEqual(len(found["matches"]), 2)


# ---------------------------------------------------------------- 2. retry


def image_record(path, raw):
    return {
        "sha256": sha256(raw).hexdigest(),
        "blob_path": str(path),
        "bounds": [0, 0, 4, 2],
        "width": 2,
        "height": 2,
        "sources": [{"url": "https://example.test/image", "sha256": sha256(raw).hexdigest()}],
        "source_vintage": "2025",
    }


def cover_for(case, image):
    r = lc(case)
    r.update(
        source_snapshots=image["sources"],
        image_sha256=image["sha256"],
        status="modeled_semantic_estimates",
        source_vintage="2025",
        retrieved_at="2026-11-15",
    )
    return r


class RetryFailedPhysicalSourcesTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.raw = png([[[30, 130, 30], [100, 100, 100]], [[30, 130, 30], [100, 100, 100]]])
        self.path = Path(self.temp.name) / "image"
        self.path.write_bytes(self.raw)
        self.image = image_record(self.path, self.raw)
        buildings = patch("stormwater.automatic.buildings", return_value=([], [], False))
        buildings.start()
        self.addCleanup(buildings.stop)

    def run_acquire(self, case, *, image, cover, terrain, refresh_physical=False):
        from stormwater.automatic import acquire

        with (
            patch("stormwater.acquisition.acquire_imagery", **image) as imagery,
            patch("stormwater.automatic.landcover", **cover) as model,
            patch("stormwater.automatic_terrain.acquire", **terrain) as elevation,
        ):
            out = acquire(case, Mock(root=Path(self.temp.name)), refresh_physical=refresh_physical)
        return out, imagery, model, elevation

    @staticmethod
    def status(out, provider):
        return next(s for s in out["automatic"]["source_status"] if s["provider"] == provider)

    def test_failed_imagery_and_terrain_are_retried_on_rerun_with_history(self):
        c = fixture()
        first, *_ = self.run_acquire(
            c,
            image={"side_effect": OSError("imagery outage")},
            cover={"side_effect": OSError("no image")},
            terrain={"side_effect": OSError("index outage")},
        )
        self.assertEqual(self.status(first, "Aerial imagery")["status"], "unavailable")
        second, imagery, model, elevation = self.run_acquire(
            first,
            image={"return_value": self.image},
            cover={"return_value": cover_for(c, self.image)},
            terrain={"side_effect": OSError("still no terrain")},
        )
        imagery.assert_called_once()
        model.assert_called_once()
        self.assertEqual(elevation.call_args.kwargs.get("refresh_index"), True)
        image_status = self.status(second, "Aerial imagery")
        self.assertEqual(image_status["status"], "retrieved")
        self.assertEqual(image_status["retry"]["previous_status"], "unavailable")
        self.assertEqual(image_status["retry"]["previous_error"], "imagery outage")
        self.assertEqual(
            self.status(second, "Elevation")["retry"]["previous_error"], "index outage"
        )
        plan = second["automatic"]["physical_sources"]
        self.assertEqual(plan["mode"], "retry_failed")
        self.assertIn("Aerial imagery", plan["retried"])
        self.assertEqual(len(second["automatic_runs"]), 2)
        self.assertEqual(second["automatic_history"][-1]["at"], first["automatic"]["at"])
        self.assertEqual(second["imagery"]["sha256"], self.image["sha256"])

    def test_successful_saved_imagery_and_estimates_are_kept_not_refreshed(self):
        c = fixture()
        first, *_ = self.run_acquire(
            c,
            image={"return_value": self.image},
            cover={"return_value": cover_for(c, self.image)},
            terrain={"side_effect": OSError("no terrain")},
        )
        features = deepcopy(first["features"])
        second, imagery, model, _ = self.run_acquire(
            first,
            image={"side_effect": AssertionError("Successful imagery must not be refetched")},
            cover={"side_effect": AssertionError("Same image; estimates are kept")},
            terrain={"side_effect": OSError("no terrain")},
        )
        imagery.assert_not_called()
        model.assert_not_called()
        self.assertEqual(self.status(second, "Aerial imagery")["status"], "saved_snapshot_kept")
        self.assertEqual(
            self.status(second, "Recent imagery cover candidates")["status"],
            "saved_estimates_kept",
        )
        self.assertEqual(second["features"], features)
        self.assertEqual(second["automatic"]["estimates"], first["automatic"]["estimates"])
        self.assertEqual(second["canopy_observation"], first["canopy_observation"])
        # An explicit full refresh replaces them.
        third, imagery, model, _ = self.run_acquire(
            second,
            image={"return_value": self.image},
            cover={"return_value": cover_for(c, self.image)},
            terrain={"side_effect": OSError("no terrain")},
            refresh_physical=True,
        )
        imagery.assert_called_once()
        model.assert_called_once()
        self.assertEqual(third["automatic"]["physical_sources"]["mode"], "refresh_all")

    def test_run_records_per_stage_acquisition_timings(self):
        out, *_ = self.run_acquire(
            fixture(),
            image={"side_effect": OSError("offline")},
            cover={"side_effect": OSError("offline")},
            terrain={"side_effect": OSError("offline")},
        )
        timings = out["automatic"]["timings_seconds"]
        for key in ("buildings", "inlets", "imagery", "model", "terrain", "total"):
            self.assertGreaterEqual(timings[key], 0)
        self.assertEqual(out["automatic_runs"][-1]["timings_seconds"], timings)


class AssessmentTimingTests(unittest.TestCase):
    def test_assessment_result_reports_stage_timings_without_changing_hashes(self):
        from drainage_core.engine import analyze, result_hash
        from stormwater.cases import CaseStore

        c = fixture()
        c["features"]["features"] = [
            {
                "type": "Feature",
                "id": "pave",
                "geometry": c["parcel"],
                "properties": {"layer": "surface", "class": "pavement"},
            }
        ]
        gis = analyze(c)
        for key in ("measurement", "routing", "research_routing", "modeled_routing"):
            self.assertIn(key, gis["stage_seconds"])
        self.assertEqual(gis["analysis_sha256"], result_hash({**gis, "stage_seconds": {"x": 9}}))
        with tempfile.TemporaryDirectory() as root:
            store = CaseStore(root)
            with patch("stormwater.assessment_workflow.gather", side_effect=lambda x, *a, **k: x):
                response = store.run_assessment(c)
        timings = response["timings_seconds"]
        for key in ("public_records", "analysis_and_exports", "snapshot", "total"):
            self.assertGreaterEqual(timings[key], 0)
        self.assertIn("policy", timings["analysis_stages"])
        self.assertIn("routing", response["analysis"]["stage_seconds"])


# ---------------------------------------------------------------- 3. terrain


TNM = "https://tnmaccess.nationalmap.gov/api/v1/products?"
TILE = "https://prd-tnm.s3.amazonaws.com/StagedProducts/Elevation/1m/Projects/{p}/TIFF/USGS_1M_18_{t}_{p}.tif"
METADATA = (
    b"<metadata><idinfo><timeperd><timeinfo><rngdates><begdate>20240414</begdate>"
    b"<enddate>20250402</enddate></rngdates></timeinfo></timeperd></idinfo>"
    b"<eainfo>Elevation values are in meters. Vertical datum NAVD88.</eainfo></metadata>"
)
X0, Y0 = 479994.0, 4430006.0


def surface(col, row):
    """Same values wherever adjacent tiles overlap (global cell coordinates)."""
    return (50 + 0.1 * col + 0.05 * row + 0.001 * ((col * 7 + row * 3) % 11)).astype("float32")


def tile_bytes(left_col, cols=200, rows=200, shift=0.0, res=1.0, offset=0.0):
    rr, cc = np.mgrid[0:rows, left_col : left_col + cols]
    data = surface(cc, rr) + np.float32(offset)
    with MemoryFile() as mem:
        with mem.open(
            driver="GTiff",
            width=cols,
            height=rows,
            count=1,
            dtype="float32",
            nodata=-999999.0,
            crs="EPSG:26918",
            transform=from_origin(X0 + left_col + shift, Y0, res, res),
        ) as ds:
            ds.write(data, 1)
        return mem.read()


class TerrainMosaicTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)

    def opened(self, *blobs):
        files = [MemoryFile(b) for b in blobs]
        datasets = [f.open() for f in files]
        self.addCleanup(lambda: [d.close() for d in datasets] + [f.close() for f in files])
        return datasets

    def test_same_grid_tiles_mosaic_without_resampling(self):
        from stormwater.automatic_terrain import mosaic_window

        a, b = self.opened(tile_bytes(0), tile_bytes(194))
        region = box(X0 + 150, Y0 - 120, X0 + 260, Y0 - 20)
        content, window, parts, check = mosaic_window([a, b], region, ["a", "b"])
        self.assertEqual(check["max_overlap_difference_m"], 0.0)
        self.assertEqual(check["unfilled_cells"], 0)
        self.assertEqual([p["source_url"] for p in parts], ["a", "b"])
        left, top, width, height = window
        with MemoryFile(content) as mem, mem.open() as ds:
            values = ds.read(1)
            self.assertEqual(ds.transform.c, X0 + left)
            self.assertEqual(ds.res, (1.0, 1.0))
        rr, cc = np.mgrid[top : top + height, left : left + width]
        np.testing.assert_array_equal(values, surface(cc, rr))

    def test_misaligned_resolution_or_disagreeing_tiles_are_rejected(self):
        from stormwater.automatic_terrain import mosaic_window

        region = box(X0 + 150, Y0 - 120, X0 + 260, Y0 - 20)
        for other, message in [
            (tile_bytes(194, shift=0.5), "not aligned"),
            (tile_bytes(194, res=2.0), "cell sizes"),
            (tile_bytes(194, offset=0.25), "disagree"),
        ]:
            a, b = self.opened(tile_bytes(0), other)
            with self.assertRaisesRegex(ValueError, message):
                mosaic_window([a, b], region)

    def acquire_with_tiles(self, tiles, parcel):
        from drainage_core.sources import Cache
        from stormwater.automatic_terrain import acquire

        items = [
            {"downloadURL": TILE.format(p=p, t=t), "publicationDate": date}
            for p, t, date, _ in tiles
        ]
        blobs = {TILE.format(p=p, t=t): content for p, t, _, content in tiles}

        def opener(request, timeout):
            url = request.full_url
            if url.startswith(TNM):
                return io.BytesIO(json.dumps({"items": items, "total": len(items)}).encode())
            if url.endswith(".xml"):
                return io.BytesIO(METADATA)
            raise AssertionError("Unexpected request " + url)

        original = rasterio.open

        def fake_open(path, *args, **kwargs):
            if str(path).startswith("https://"):
                return MemoryFile(blobs[str(path)]).open()
            return original(path, *args, **kwargs)

        case = fixture()
        case["parcel"] = mapping(parcel)
        cache = Cache(Path(self.temp.name) / "public", opener=opener)
        with patch("rasterio.open", side_effect=fake_open):
            return acquire(case, cache)

    def test_adjacent_tiles_of_one_project_cover_a_parcel_no_single_tile_covers(self):
        parcel = box(X0 + 184, Y0 - 110, X0 + 204, Y0 - 90)
        out, status = self.acquire_with_tiles(
            [
                ("NEW_D24", "x47y443", "2026-10-23", tile_bytes(0)),
                ("NEW_D24", "x48y443", "2026-10-23", tile_bytes(194)),
                ("OLD_2015", "x47y443", "2020-03-30", tile_bytes(0)),
            ],
            parcel,
        )
        self.assertEqual(status["status"], "source_model")
        self.assertEqual(len(status["source_urls"]), 2)
        self.assertTrue(all("NEW_D24" in u for u in status["source_urls"]))
        self.assertEqual(status["mosaic"]["tiles"], 2)
        self.assertEqual(status["capture_period"]["capture_start"], "2024-04-14")
        grid = out["terrain"]
        z = np.array(grid["elevations"], dtype=float)
        self.assertFalse(np.isnan(z).any())
        col0 = int(round(grid["origin"][0] - X0))
        row0 = int(round(Y0 - grid["origin"][1]))
        rr, cc = np.mgrid[row0 : row0 + z.shape[0], col0 : col0 + z.shape[1]]
        np.testing.assert_array_equal(z, surface(cc, rr).astype(float))
        self.assertGreater(grid["origin"][0] + z.shape[1], X0 + 200)  # crosses the tile edge

    def test_window_cap_is_the_shared_routing_cap(self):
        parcel = box(X0 + 184, Y0 - 110, X0 + 204, Y0 - 90)
        with patch("drainage_core.drainage.MAX_ROUTING_CELLS", 1000):
            with self.assertRaisesRegex(ValueError, "exceeds 1,000 cells"):
                self.acquire_with_tiles(
                    [
                        ("NEW_D24", "x47y443", "2026-10-23", tile_bytes(0)),
                        ("NEW_D24", "x48y443", "2026-10-23", tile_bytes(194)),
                    ],
                    parcel,
                )

    def test_every_physical_stage_uses_one_cap(self):
        from drainage_core import drainage, research

        grid = {
            "elevations": [[float(r + c) for c in range(11)] for r in range(11)],
            "cell_size": 1,
            "horizontal_unit": "m",
            "vertical_unit": "m",
        }
        with (
            patch.object(drainage, "MAX_ROUTING_CELLS", 100),
            patch.object(research, "MAX_ROUTING_CELLS", 100),
        ):
            with self.assertRaisesRegex(ValueError, "100 cells"):
                drainage.route_grid(grid)
            with self.assertRaisesRegex(ValueError, "100 cells"):
                research.fill_dem(grid["elevations"])
            route = drainage.route_grid(
                {**grid, "elevations": [r[:9] for r in grid["elevations"][:9]]}
            )
            self.assertEqual(route["rows"], 9)
        self.assertGreaterEqual(drainage.MAX_ROUTING_CELLS, 467376)  # largest live parcel window


# ---------------------------------------------------------------- equivalence


def random_grid(seed, rows, cols):
    rnd = random.Random(seed)
    rng = np.random.default_rng(seed)
    levels = rnd.choice([3, 6, 50, None])
    z = rng.random((rows, cols)) * 5
    if levels:
        z = np.round(z * levels / 5) * 5 / levels  # plateaus and exact ties
    grid = {
        "elevations": z.tolist(),
        "cell_size": rnd.choice([1, 0.5, 2.0]),
        "origin": [100.0, 200.0],
        "horizontal_unit": rnd.choice(["m", "ft"]),
        "vertical_unit": rnd.choice(["m", "us-ft"]),
        "crs": "EPSG:32618",
        "settings": {
            "flat_tolerance": rnd.choice([0, 0, 0.1, 0.5]),
            "max_flow_paths": rnd.choice([0, 5, 30]),
            "extent_sufficient": rnd.random() < 0.3,
        },
    }
    cells = [(r, c) for r in range(rows) for c in range(cols)]
    rnd.shuffle(cells)
    k = len(cells)
    cut = [0, k // 15, k // 15 + k // 12, k // 15 + k // 12 + k // 10]
    nodata, barriers, roofs = (cells[cut[i] : cut[i + 1]] for i in range(3))
    storage, rest = cells[cut[3] : cut[3] + 2], cells[cut[3] + 2 :]
    for r, c in nodata:
        grid["elevations"][r][c] = None
    grid.update(
        barriers=[list(p) for p in barriers],
        roofs=[list(p) for p in roofs],
        storage=[list(p) for p in storage],
        corner_blocking=[list(p) for p in rest[:3]],
        inlets=[{"id": f"i{j}", "cell": list(p)} for j, p in enumerate(rest[3:7])],
        connections=[
            {"from": "i0", "to": "i1", "evidence": "documented"},
            {"from": "i1", "to": "out", "evidence": "scenario"},
            {"from": "i2", "evidence": "unknown"},
        ],
        roof_connections=(
            [{"cell": list(roofs[0]), "to": "i3", "evidence": "documented"}] if roofs else []
        ),
    )
    if rnd.random() < 0.6:
        grid["parcel_mask"] = (rng.random((rows, cols)) < 0.5).tolist()
    return grid


class VectorizedAlgorithmEquivalenceTests(unittest.TestCase):
    """Old per-cell algorithms (tests/reference_algorithms.py) vs vectorized versions."""

    def test_route_grid_identical_on_random_grids(self):
        from drainage_core.drainage import route_grid

        sinks = 0
        for seed in range(160):
            rnd = random.Random(seed)
            rows, cols = rnd.randint(4, 26), rnd.randint(4, 26)
            grid = random_grid(seed, rows, cols)
            old = ref.route_grid(json.loads(json.dumps(grid)))
            new = route_grid(json.loads(json.dumps(grid)))
            self.assertEqual(json.dumps(old, sort_keys=True), json.dumps(new, sort_keys=True), seed)
            sinks += sum(1 for k in new["counts"] if "flat" in k or "depression" in k)
        self.assertGreater(sinks, 100)  # plateau/pit resolution was exercised

    def test_fill_and_accumulation_identical_on_random_grids(self):
        from drainage_core.drainage import route_grid
        from drainage_core.research import fill_dem, accumulate, _json_grid

        for seed in range(60):
            grid = random_grid(seed, 6 + seed % 17, 5 + seed % 13)
            np.testing.assert_array_equal(
                fill_dem(grid["elevations"]), ref.fill_dem(grid["elevations"])
            )
            flow = route_grid(grid)
            np.testing.assert_array_equal(
                accumulate(flow["next_cells"], flow["labels"]),
                ref.accumulate(flow["next_cells"], flow["labels"]),
            )
            values = np.array(grid["elevations"], dtype=float)
            self.assertEqual(
                _json_grid(values),
                [[None if not np.isfinite(v) else float(v) for v in row] for row in values],
            )
        zero = [[0.0, -0.0, 0.0], [-0.0, 5.0, -0.0], [0.0, -0.0, 0.0]]
        self.assertEqual(
            json.dumps(_json_grid(fill_dem(zero))), json.dumps(_json_grid(ref.fill_dem(zero)))
        )

    def test_coarse_block_means_identical_to_per_block_mean(self):
        rng = np.random.default_rng(3)
        source = rng.random((37, 51)) * 100
        source[rng.random(source.shape) < 0.05] = np.nan
        rows, cols = source.shape
        expected = np.full(((rows + 1) // 2, (cols + 1) // 2), np.nan)
        for r in range(0, rows - 1, 2):
            for c in range(0, cols - 1, 2):
                block = source[r : r + 2, c : c + 2]
                if np.isfinite(block).all():
                    expected[r // 2, c // 2] = block.mean()
        from drainage_core.research import coarse_2x

        np.testing.assert_array_equal(coarse_2x(source), expected)

    def test_catchment_outlines_identical_to_per_cell_box_union(self):
        from shapely.geometry import box as cell_box
        from drainage_core.engine import analyze
        from drainage_core.geometry import union

        c = fixture()
        c["parcel"] = mapping(box(2, 2, 14, 10))
        rng = np.random.default_rng(5)
        z = np.round(rng.random((12, 16)) * 3, 1)
        c["terrain"] = {
            "elevations": z.tolist(),
            "cell_size": 1,
            "origin": [0, 12],
            "crs": c["crs"],
            "horizontal_unit": "m",
            "vertical_unit": "m",
            "settings": {"max_flow_paths": 0},
        }
        c["features"]["features"] = [
            {
                "type": "Feature",
                "id": "roof",
                "geometry": mapping(box(5, 5, 8, 8)),
                "properties": {"layer": "surface", "class": "roof"},
            }
        ]
        drainage = analyze(c)["drainage"]
        grouped = {}
        for r, row in enumerate(drainage["labels"]):
            for col, label in enumerate(row):
                if label not in ("barrier", "nodata"):
                    key = "unresolved:roof" if label.startswith("unresolved:roof:") else label
                    grouped.setdefault(key, []).append(cell_box(col, 12 - (r + 1), col + 1, 12 - r))
        expected = {k: mapping(union(v)) for k, v in grouped.items()}
        self.assertEqual(
            json.dumps([[c["outlet"], c["geometry"]] for c in drainage["catchments"]]),
            json.dumps([[k, v] for k, v in expected.items()]),
        )


# ---------------------------------------------------------------- 4. compact responses


def terrain_case(name="compact-case"):
    c = fixture()
    c["id"] = name
    c["parcel"] = mapping(box(2, 2, 10, 8))
    c["features"]["features"] = [
        {
            "type": "Feature",
            "id": "pave",
            "geometry": c["parcel"],
            "properties": {"layer": "surface", "class": "pavement"},
        }
    ]
    c["terrain"] = {
        "elevations": [[10 - 0.1 * col - 0.05 * r for col in range(12)] for r in range(10)],
        "cell_size": 1,
        "origin": [0, 10],
        "crs": c["crs"],
        "horizontal_unit": "m",
        "vertical_unit": "m",
        "settings": {"max_flow_paths": 3},
    }
    return c


class CompactResponseTests(unittest.TestCase):
    def test_display_view_keeps_drawn_layers_and_findings_drops_grids(self):
        from drainage_core.engine import analyze, canonical
        from drainage_core.saved import display_analysis

        full = analyze(terrain_case())
        before = canonical(full)
        view = display_analysis(full)
        self.assertEqual(canonical(full), before)
        for key in ("labels", "next_cells", "counts", "outlets"):
            self.assertNotIn(key, view["drainage"])
        self.assertNotIn("rasters", view["research_drainage"].get("primary", {}))
        self.assertEqual(len(view["drainage"]["catchments"]), len(full["drainage"]["catchments"]))
        self.assertIn("geometry", view["drainage"]["catchments"][0])
        self.assertEqual(view["drainage"]["flow_paths"], full["drainage"]["flow_paths"])
        self.assertEqual(view["measurement"], full["measurement"])
        self.assertEqual(view["map_features"], full["map_features"])
        self.assertTrue(view["display_only"])
        self.assertIn("analysis.json", view["omitted_for_display"]["full_result"])

    def test_compact_case_round_trip_and_refusal(self):
        from drainage_core.saved import compact_case, restore_case

        c = terrain_case()
        self.assertIs(compact_case(c, [{"terrain": {"elevations": [[1.0]]}}]), c)
        small = compact_case(c, [deepcopy(c)])
        self.assertNotIn("elevations", small["terrain"])
        self.assertEqual(small["terrain"]["elevations_omitted"]["rows"], 10)
        self.assertEqual(restore_case(small, [deepcopy(c)]), c)
        with self.assertRaisesRegex(ValueError, "not in any saved revision"):
            restore_case(small, [{"terrain": {"elevations": [[1.0]]}}])


class CompactHTTPTests(unittest.TestCase):
    setUpClass = classmethod(baseline_http.HTTPWorkflowTests.setUpClass.__func__)
    tearDownClass = classmethod(baseline_http.HTTPWorkflowTests.tearDownClass.__func__)
    request = baseline_http.HTTPWorkflowTests.request
    json_request = baseline_http.HTTPWorkflowTests.json_request

    def test_saved_and_analysis_responses_are_compact_and_round_trip(self):
        c = terrain_case("compact-http")
        code, _, saved = self.json_request("/api/save", {"case": c})
        self.assertEqual(code, 200, saved)
        self.assertNotIn("labels", saved["drainage"])
        code, _, view = self.json_request("/api/saved/compact-http")
        self.assertEqual(code, 200, view)
        self.assertNotIn("elevations", view["case"]["terrain"])
        self.assertIn("owner_summary", view["analysis"])
        code, _, again = self.json_request("/api/analyze", {"case": view["case"]})
        self.assertEqual(code, 200, again)
        self.assertEqual(again["input_sha256"], saved["input_sha256"])
        code, _, full = self.json_request("/api/saved/compact-http?full=1")
        self.assertEqual(full["case"]["terrain"]["elevations"], c["terrain"]["elevations"])
        code, _, body = self.request("/exports/compact-http/analysis.json")
        self.assertIn("labels", json.loads(body)["drainage"])
        code, _, edited = self.json_request("/api/save", {"case": view["case"], "full": True})
        self.assertEqual(code, 200, edited)
        self.assertIn("labels", edited["drainage"])
        broken = deepcopy(view["case"])
        broken["terrain"]["elevations_omitted"]["sha256"] = "0" * 64
        code, _, error = self.json_request("/api/analyze", {"case": broken})
        self.assertEqual(code, 400)
        self.assertIn("not in any saved revision", error["error"])


# ---------------------------------------------------------------- 5. report + summary


def summary_case():
    c = fixture()
    c["baseline"] = {"published_monthly_total": 3138.21}
    c["features"]["features"] = [
        {
            "type": "Feature",
            "id": "public-system_footprint-1",
            "geometry": mapping(box(1, 0.5, 2, 1.5)),
            "properties": {
                "kind": "system_footprint",
                "layer": "footprint",
                "source_family": "PWD",
                "gsi_system_id": "62571",
                "gsi_system_type": "Rain Garden",
                "project_number": "FY16-JOMA-4143-01",
                "year_installed": 2018,
            },
        },
        {
            "type": "Feature",
            "id": "public-system_footprint-2",
            "geometry": mapping(box(50, 50, 51, 51)),  # off the parcel
            "properties": {"kind": "system_footprint", "gsi_system_id": "999"},
        },
    ]
    return c


def summary_analysis(**extra):
    calc = lambda annual, **row: {"status": "calculated", "gross_annual_reduction": annual, **row}
    return {
        "measurement": {"unknown_sqft": 160070.7},
        "quality_review": {"status": "current"},
        "assessment": {
            "economics": {
                "baseline": {"status": "calculated", "monthly_total": 3138.21},
                "documented": {"status": "blocked", "gross_annual_reduction": None},
                "documented_combined": {"status": "blocked"},
                "modeled": {"status": "blocked"},
            },
            "modeled_integration": {
                "catchment_scenarios": [
                    calc(6666.36, receiver_id="62571", name="coarser_2x"),
                    calc(4540.8, receiver_id="all_unassigned_gsi", name="nominal"),
                    {"status": "blocked", "gross_annual_reduction": None, "receiver_id": "62571"},
                ],
                "permit_scenarios": [calc(2620.32, permit_id="PAD510200")],
                "surface_scenario": {
                    "area_alternatives": [
                        {
                            "status": "calculated",
                            "annual_savings": -1200.0,
                            "name": "unknown_impervious",
                        },
                        {
                            "status": "calculated",
                            "annual_savings": 12686.4,
                            "name": "ia_unknown_assumed_pervious",
                        },
                    ]
                },
            },
            "public_credit_observations": [{"credits_flag": 0, "expired_flag": 1}],
            "categories": [],
            **extra,
        },
    }


class OwnerSummaryTests(unittest.TestCase):
    def test_five_plain_findings_with_identifiers(self):
        from stormwater.owner_summary import owner_summary

        s = owner_summary(summary_case(), summary_analysis())
        self.assertEqual(s["current_bill"]["check"], "matches")
        self.assertIn("$3,138.21 per month", s["current_bill"]["text"])
        self.assertEqual(s["supported"]["annual"], 0.0)
        self.assertTrue(s["supported"]["text"].startswith("$0."))
        h = s["hypothetical"]
        self.assertEqual((h["low"], h["high"], h["label"]), (-1200.0, 12686.4, "Not supported yet"))
        self.assertIn("$1,200 per year increase", h["text"])
        self.assertIn("160,071 sq ft", h["biggest_assumption"])
        steps = [x["text"] for x in s["next_evidence"]]
        self.assertEqual(len(steps), 3)
        self.assertIn("site plan or survey", steps[0])
        self.assertIn("(PCSMP) for project FY16-JOMA-4143-01", steps[1])
        self.assertIn("PAD510200", steps[2])
        self.assertEqual(s["systems"]["count"], 1)  # the off-parcel system is not listed
        self.assertIn("no stormwater credit", s["systems"]["text"])
        self.assertIn("'Expired' credit flag", s["systems"]["text"])

    def test_documented_mismatch_withheld_and_new_fields_are_read_generically(self):
        from stormwater.owner_summary import owner_summary

        a = summary_analysis()
        a["assessment"]["economics"]["documented"] = {
            "status": "calculated",
            "gross_monthly_reduction": 10.0,
            "gross_annual_reduction": 120.0,
        }
        a["assessment"]["economics"]["baseline"]["monthly_total"] = 3200.0
        s = owner_summary(summary_case(), a)
        self.assertEqual(s["supported"]["annual"], 120.0)
        self.assertEqual(s["current_bill"]["check"], "differs")
        self.assertIn("recomputed charge differs", s["next_evidence"][0]["text"])
        self.assertNotIn(120.0, [s["hypothetical"]["low"], s["hypothetical"]["high"]])
        b = summary_analysis(
            systems_without_recorded_credit=[{"gsi_system_id": "77", "gsi_system_type": "Basin"}],
        )
        b["assessment"]["categories"] = [
            {
                "category": "existing_system_management",
                "status": "candidate",
                "missing": ["Approved PCSMP or as-built drawings"],
                "records": [{"status": "calculated", "gross_annual_reduction": 99999.0}],
            }
        ]
        s = owner_summary(summary_case(), b)
        self.assertEqual(s["systems"]["count"], 2)
        self.assertIn("1 of these has no recorded credit", s["systems"]["text"])
        self.assertEqual(s["hypothetical"]["high"], 99999.0)
        self.assertIn("existing mapped systems", s["hypothetical"]["biggest_assumption"])
        outdated = summary_analysis()
        outdated["quality_review"] = {"status": "outdated"}
        s = owner_summary(summary_case(), outdated)
        self.assertEqual(s["supported"]["status"], "withheld")
        self.assertIsNone(s["hypothetical"]["high"])

    def test_policy_fields_from_batch_b1_render_when_present(self):
        from stormwater.owner_summary import owner_summary
        from stormwater.assessment_report import existing_systems_section, modeled_combined_section

        a = summary_analysis(
            existing_system_management={
                "status": "leads",
                "recorded_credit_status": "no_recorded_credit",
                "claim": "Leads, not managed areas.",
                "systems": [
                    {
                        "system_id": "062571",
                        "system_type": "Rain Garden",
                        "project_number": "FY16-JOMA-4143-01",
                        "project_type": "Private - Retrofit",
                        "year_installed": 2018,
                        "on_parcel_footprint_sqft": 742.2,
                        "lead_status": "lead_request_pcsmp",
                        "lead_label": "lead: request PCSMP",
                        "request": "Request from PWD the approved PCSMP for project FY16-JOMA-4143-01",
                        "figure": None,
                    }
                ],
                "systems_without_recorded_credit": [{"system_id": "62571"}],
            },
            systems_without_recorded_credit=[{"system_id": "62571"}],
        )
        a["assessment"]["economics"]["baseline"]["billing_notes"] = ["Minimum applies per account."]
        s = owner_summary(summary_case(), a)
        self.assertEqual(s["systems"]["count"], 1)  # 062571 and 62571 are one system
        self.assertIn("It has no recorded credit.", s["systems"]["text"])
        self.assertIn("Minimum applies per account.", s["current_bill"]["text"])
        html = existing_systems_section(a["assessment"]["existing_system_management"])
        self.assertIn("lead: request PCSMP", html)
        self.assertIn("no recorded credit", html)
        m = a["assessment"]["modeled_integration"]
        m["permit_scenarios"][0].update(
            listing_label="Industrial what-if",
            permit_class="industrial_stormwater",
            site_match="matched",
        )
        m["catchment_scenarios"][0]["storage_check"] = {
            "status": "estimated",
            "storage_range_cuft": [100.0, 200.0],
            "required_treatment_volume_cuft": 400.0,
            "flag": "Terrain-visible storage is below the 1.5-inch volume",
        }
        m["surface_scenario"]["ia_measurement_range"] = {
            "presentation": "Measured-cover range",
            "low_end": {"ia_sqft": 95000.0},
            "high_end": {"ia_sqft": 255000.0},
            "recorded_ia_sqft": 185889.0,
            "recorded_ia_within_range": True,
        }
        m["paved_reference_basis"] = {"status": "not_offered", "label": "developed on 2018 paved"}
        m.update(claim="Modeled alternatives.", status="modeled")
        html = modeled_combined_section(m)
        for text in (
            "Industrial what-if; permit class: industrial stormwater; site match: matched",
            "storage check estimated (terrain-visible 100–200 cu ft vs 400 cu ft required)",
            "recorded IA within the range",
            "developed on 2018 paved",
        ):
            self.assertIn(text, html)

    def test_report_leads_with_summary_and_carries_no_raw_json(self):
        from stormwater.cases import analyze
        from stormwater.report import render_report

        c = summary_case()
        raw = png(np.full((300, 400, 4), 120, dtype="uint8"))
        with tempfile.TemporaryDirectory() as root:
            path = Path(root) / "image"
            path.write_bytes(raw)
            c["imagery"] = {
                "sha256": sha256(raw).hexdigest(),
                "blob_path": str(path),
                "bounds": [0, 0, 4, 2],
            }
            html = render_report(c, analyze(c))
        self.assertLess(html.index("Summary for the owner"), html.index("<svg"))
        self.assertNotIn("<pre>", html)
        self.assertNotIn('"status":', html)
        self.assertIn("data:image/jpeg;base64,", html)
        self.assertIn("FY16-JOMA-4143-01", html)
        self.assertIn("Appendix: sources and technical details", html)

    def test_display_image_is_a_smaller_bounded_jpeg(self):
        from drainage_core.report import display_image

        rng = np.random.default_rng(1)
        raw = png(rng.integers(0, 255, (900, 2400, 4), dtype="uint8"))
        mime, data, width, height = display_image(raw, max_side=1600)
        self.assertEqual(mime, "image/jpeg")
        self.assertEqual((width, height), (1600, 600))
        self.assertLess(len(data), len(raw) / 3)


if __name__ == "__main__":
    unittest.main()
