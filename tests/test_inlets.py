"""G3: public PWD inlet ingestion from a frozen public response; no network.

The fixture is a small read-only capture of the City INLETS layer (see the
companion .json for URL, retrieval time and SHA-256). It checks source handling,
lineage and routing robustness, not real-site drainage accuracy.
"""
from copy import deepcopy
from hashlib import sha256
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch

from shapely.geometry import box, mapping, shape

from drainage_core.engine import analyze, new_case
from drainage_core.sources import Cache, SourceError
from stormwater.acquisition import INLETS, acquire_inlets
import network_guard

network_guard.install()

FIXTURES = Path(__file__).resolve().parent/'fixtures'/'inlets'
META = json.loads((FIXTURES/'pwd-inlets-vine-st-2026-11-16.json').read_text())
RAW = (FIXTURES/META['file']).read_bytes()


class _Response(io.BytesIO):
    def __enter__(self): return self
    def __exit__(self, *exc): self.close()


def opener(requests, body=RAW, expect=META['request_url']):
    def open_(request, timeout=None):
        url = getattr(request, 'full_url', request); requests.append(url)
        if expect is not None and url != expect:
            raise OSError('Unexpected request '+url)
        return _Response(body)
    return open_


def offline(request, timeout=None):
    raise OSError('Public sources are offline in tests')


def parcel_case():
    c = new_case('Inlet fixture', crs=META['crs']); c['id'] = 'inlet-fixture'
    c['parcel'] = deepcopy(META['test_parcel'])
    return c


class InletProviderTests(unittest.TestCase):
    def test_fixture_hash_matches_recorded_provenance(self):
        self.assertEqual(sha256(RAW).hexdigest(), META['sha256'])
        self.assertEqual(len(RAW), META['bytes'])
        self.assertTrue(META['request_url'].startswith(META['layer']+'/query?'))

    def test_frozen_response_normalizes_to_inlets_with_unknown_connections(self):
        with tempfile.TemporaryDirectory() as root:
            requests = []
            cache = Cache(root, opener=opener(requests))
            found = acquire_inlets(META['test_parcel'], META['crs'], cache)
        self.assertEqual(requests, [META['request_url']], 'Provider request must be reproducible')
        self.assertEqual(len(found['features']), META['feature_count'])
        self.assertEqual(found['excluded'], []); self.assertEqual(found['outside_buffer'], 0)
        self.assertEqual(found['sources'][0]['sha256'], META['sha256'])
        self.assertEqual(found['source_url'], INLETS)
        region = shape(META['test_parcel']).buffer(150, join_style=2)
        for f in found['features']:
            p = f['properties']
            self.assertTrue(f['id'].startswith('public-inlet-'))
            self.assertEqual((p['layer'], p['drainage_role'], p['kind']), ('inlet', 'inlet', 'inlet'))
            self.assertEqual((p['connection_evidence'], p['downstream_connection']), ('unknown', 'unknown'))
            self.assertEqual(p['source_url'], INLETS); self.assertEqual(p['source_family'], 'PWD inlets')
            self.assertFalse(p['reviewed']); self.assertNotIn('gsi_id', p)
            self.assertTrue(region.covers(shape(f['geometry'])))
            # 9999 is the layer's placeholder year; it is kept as recorded, never as a date.
            self.assertIsNone(p['year_installed']); self.assertEqual(p['year_installed_recorded'], 9999)
            self.assertTrue(any('placeholder' in n for n in p['notes']))
        systems = {f['properties']['recorded_sewer_system'] for f in found['features']}
        self.assertEqual(systems, {'STORM', 'COMBINED'})

    def test_non_inlet_symbols_and_points_outside_the_buffer_are_not_inlets(self):
        data = json.loads(RAW)
        data['features'][0]['properties']['symbolgroup'] = 'Manhole'
        data['features'][1]['properties']['symbolgroup'] = None
        far = deepcopy(data['features'][2]); far['id'] = far['properties']['objectid'] = 999999
        far['geometry']['coordinates'] = [2691741.0, 238762.0]  # north-east corner of the query envelope
        data['features'].append(far)
        with tempfile.TemporaryDirectory() as root:
            cache = Cache(root, opener=opener([], json.dumps(data).encode(), None))
            found = acquire_inlets(META['test_parcel'], META['crs'], cache)
        ids = {f['id'] for f in found['features']}
        self.assertNotIn('public-inlet-%s' % data['features'][0]['id'], ids)
        self.assertIn({'object_id': data['features'][0]['id'], 'reason': "symbol group 'Manhole' is not an inlet"}, found['excluded'])
        unrecorded = next(f for f in found['features'] if f['id'] == 'public-inlet-%s' % data['features'][1]['id'])
        self.assertIn('Symbol group unrecorded', ' '.join(unrecorded['properties']['notes']))
        # A mitred buffer of a square is its envelope, so the corner point is kept;
        # a point beyond the envelope is not requested at all.
        self.assertIn('public-inlet-999999', ids)

    def test_round_parcel_buffer_drops_envelope_corner_points(self):
        data = json.loads(RAW)
        circle = shape(META['test_parcel']).centroid.buffer(30)
        with tempfile.TemporaryDirectory() as root:
            cache = Cache(root, opener=opener([], RAW, None))
            found = acquire_inlets(mapping(circle), META['crs'], cache)
        region = circle.buffer(150, join_style=2)
        self.assertEqual(len(found['features'])+found['outside_buffer'], len(data['features']))
        self.assertGreater(found['outside_buffer'], 0)
        self.assertTrue(all(region.covers(shape(f['geometry'])) for f in found['features']))

    def test_source_failures_raise_instead_of_returning_zero_inlets(self):
        with tempfile.TemporaryDirectory() as root:
            with self.assertRaises(SourceError):
                acquire_inlets(META['test_parcel'], META['crs'], Cache(root, opener=offline))
            wrong = json.loads(RAW); wrong['crs']['properties']['name'] = 'EPSG:4326'
            with self.assertRaisesRegex(SourceError, 'CRS'):
                acquire_inlets(META['test_parcel'], META['crs'], Cache(root+'/b', opener=opener([], json.dumps(wrong).encode(), None)))
            error = json.dumps({'error': {'code': 400, 'message': 'Invalid query'}}).encode()
            with self.assertRaises(SourceError):
                acquire_inlets(META['test_parcel'], META['crs'], Cache(root+'/c', opener=opener([], error, None)))


class AutomaticInletWorkflowTests(unittest.TestCase):
    def acquire(self, case, cache):
        from stormwater.automatic import acquire
        with patch('stormwater.automatic.buildings', side_effect=SourceError('offline buildings')), \
             patch('stormwater.acquisition.acquire_imagery', side_effect=SourceError('offline imagery')), \
             patch('stormwater.automatic.landcover', side_effect=SourceError('offline landcover')), \
             patch('stormwater.automatic_terrain.acquire', side_effect=SourceError('offline terrain')):
            return acquire(case, cache)

    @staticmethod
    def status(out):
        return next(s for s in out['automatic']['source_status'] if s['provider'] == 'Storm inlets')

    def test_inlets_are_an_explicit_recorded_source_and_reruns_replace_not_duplicate(self):
        c = parcel_case()
        with tempfile.TemporaryDirectory() as root:
            cache = Cache(root, opener=opener([]))
            out = self.acquire(c, cache)
            s = self.status(out)
            self.assertEqual(s['status'], 'source_observation'); self.assertEqual(s['mapped_inlets'], 12)
            self.assertEqual(s['source_url'], INLETS)
            inlets = [f for f in out['features']['features'] if f['properties'].get('layer') == 'inlet']
            self.assertEqual(len(inlets), 12)
            self.assertIn(META['sha256'], {x.get('sha256') for x in out['sources']})
            # A manual edit referencing one inlet survives a rerun in which it vanished.
            target = inlets[0]['id']
            out['corrections'] = [{'id': 'r', 'at': '2026-11-16', 'reason': 'Field note: grate verified', 'action': 'delete',
                                   'target': target}]
            fewer = json.loads(RAW); fewer['features'] = [f for f in fewer['features'] if 'public-inlet-%s' % f['id'] != target]
            again = self.acquire(out, Cache(root+'/second', opener=opener([], json.dumps(fewer).encode(), None)))
        ids = [f['id'] for f in again['features']['features'] if f['properties'].get('layer') == 'inlet']
        self.assertEqual(len(ids), len(set(ids)))
        self.assertEqual(len(ids), 12); self.assertIn(target, ids)
        self.assertEqual(self.status(again)['mapped_inlets'], 11)

    def test_outage_is_recorded_and_never_removes_or_zeroes_inlets(self):
        c = parcel_case()
        with tempfile.TemporaryDirectory() as root:
            out = self.acquire(c, Cache(root, opener=offline))
            s = self.status(out)
            self.assertEqual(s['status'], 'unavailable'); self.assertIn('unavailable', s['error'])
            self.assertNotIn('mapped_inlets', s)
            self.assertFalse(any(f['properties'].get('layer') == 'inlet' for f in out['features']['features']))
            saved = self.acquire(c, Cache(root+'/ok', opener=opener([])))
            # Fresh cache, total outage: saved inlets stay as a dated snapshot.
            again = self.acquire(saved, Cache(root+'/down', opener=offline))
            self.assertEqual(self.status(again)['status'], 'dated_saved_snapshot')
            self.assertEqual(sum(f['properties'].get('layer') == 'inlet' for f in again['features']['features']), 12)
            # Same cache, refresh fails: the last good capture is reused and labelled.
            cache = Cache(root+'/ok', opener=offline)
            reused = self.acquire(saved, cache)
            self.assertEqual(self.status(reused)['status'], 'cached_after_failure')
            self.assertEqual(self.status(reused)['mapped_inlets'], 12)

    def test_mock_cache_outage_is_recorded(self):
        out = self.acquire(parcel_case(), Mock())
        self.assertEqual(self.status(out)['status'], 'unavailable')


class InletRoutingTests(unittest.TestCase):
    """Phase 3 robustness with real inlet points: no crash, no erased catchments."""

    def test_public_inlets_route_or_are_recorded_as_unrepresented(self):
        with tempfile.TemporaryDirectory() as root:
            found = acquire_inlets(META['test_parcel'], META['crs'], Cache(root, opener=opener([])))
        c = parcel_case()
        x0, y0, x1, y1 = shape(c['parcel']).buffer(100).bounds
        n = 26; size = 10
        c['terrain'] = {'crs': META['crs'], 'origin': [x0, y1], 'cell_size': size, 'horizontal_unit': 'us-ft',
                        'vertical_unit': 'ft', 'settings': {'extent_sufficient': False, 'max_flow_paths': 5},
                        'elevations': [[40-.2*r-.1*col for col in range(n)] for r in range(n)]}
        c['features']['features'] = found['features']
        result = analyze(c)
        rows = [r for r in result['drainage']['feature_representation'] if r['layer'] == 'inlet']
        self.assertEqual(len(rows), 12)
        grid = box(x0, y1-n*size, x0+n*size, y1)
        for f in found['features']:
            row = next(r for r in rows if r['id'] == f['id'])
            inside = grid.contains(shape(f['geometry']))
            if not inside:
                self.assertEqual(row['status'], 'not_represented_on_grid')
        represented = [r['id'] for r in rows if r['status'] == 'represented']
        self.assertTrue(represented)
        counts = result['drainage']['counts']
        self.assertTrue(any(k.startswith('inlet:public-inlet-') for k in counts))
        # Inlets never invent a downstream link.
        self.assertFalse(any(str(k).startswith('outlet:') for k in counts))


if __name__ == '__main__':
    unittest.main()
