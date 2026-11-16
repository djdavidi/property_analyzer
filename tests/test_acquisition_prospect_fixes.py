"""Phase 5 regressions: acquisition (review D3-D6, R16) and prospects (E1-E3, E5).

Converted from docs/review-2026-11-16-repros/imagery/*.py (except r7) and
prospects/{poison,owners,seed_only,dup_and_retry,stale_drop,cancel_race}.py.
Every source is an injected stub; nothing is fetched and nothing under data/ is written.
"""
from copy import deepcopy
import datetime as dt
from hashlib import sha256
import io
import json
from pathlib import Path
import subprocess
import tempfile
from threading import Event
import unittest
from unittest.mock import Mock, patch
from urllib.parse import parse_qs, urlparse

import numpy as np
from shapely.geometry import Point, box, mapping, shape

import network_guard
from drainage_core.freshness import age_policy
from drainage_core.sources import Cache, SourceError, arcgis_features, crs_from_declaration
from stormwater import prospects as p
from stormwater.assessment_sources import _Fallback
from stormwater.record_cache import SharedCache
from test_automatic_site import fixture, png

network_guard.install()


class Response(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False


def body(value):
    return Response(value if isinstance(value, bytes) else json.dumps(value).encode())


# --- D3: HTTP-200 error bodies ---------------------------------------------------

class ErrorBodyTests(unittest.TestCase):
    URL = 'https://example.test/FeatureServer/0/query?f=geojson'
    GOOD = {'features': [{'id': 1, 'properties': {}}]}
    ERROR = {'error': {'code': 500, 'message': 'Unable to complete operation.'}}

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.mode = {'value': 'good'}
        self.cache = Cache(self.temp.name, opener=lambda request, timeout=None:
                           body(self.GOOD if self.mode['value'] == 'good' else self.ERROR))

    def test_error_body_is_history_only_and_outage_falls_back_to_last_good(self):
        good = self.cache.fetch_json(self.URL, refresh=True)
        self.mode['value'] = 'error'
        with self.assertRaisesRegex(SourceError, 'Invalid source response'):
            self.cache.fetch_json(self.URL, refresh=True)
        # The manifest still points at the good capture; the error is kept as history.
        self.assertEqual(self.cache._read(self.URL)[1], good['provenance'])
        history = [json.loads(path.read_text()) for path in (Path(self.temp.name)/'history').glob('*.json')]
        self.assertEqual(sum(bool(h.get('invalid_response')) for h in history), 1)
        proxy = _Fallback(self.cache)
        reused = proxy.fetch_json(self.URL, refresh=True)
        self.assertEqual(reused['data'], self.GOOD); self.assertTrue(reused['provenance']['cache_reused_after_failure'])
        self.mode['value'] = 'good'
        self.assertEqual(self.cache.fetch_json(self.URL)['data'], self.GOOD)

    def test_legacy_poisoned_manifest_is_skipped_for_last_good_capture(self):
        self.cache._store(self.URL, json.dumps(self.GOOD).encode(), retrieved_at='2026-01-01T00:00:00+00:00')
        self.cache._store(self.URL, json.dumps(self.ERROR).encode(), retrieved_at='2026-02-01T00:00:00+00:00')  # pre-fix write
        saved = self.cache._read_usable(self.URL)
        self.assertEqual(json.loads(saved[0]), self.GOOD); self.assertEqual(saved[1]['retrieved_at'], '2026-01-01T00:00:00+00:00')
        self.cache.opener = network_guard.offline_opener
        reused = _Fallback(self.cache).fetch_json(self.URL, refresh=True)
        self.assertEqual(reused['provenance']['retrieved_at'], '2026-01-01T00:00:00+00:00')

    def test_soil_query_error_body_reuses_dated_good_response(self):
        url = 'https://sda.example.test/Tabular/post.rest'
        first = self.cache.post_json(url, {'query': 'q'}, refresh=True)
        self.mode['value'] = 'error'
        again = self.cache.post_json(url, {'query': 'q'}, refresh=True)
        self.assertEqual(again['data'], self.GOOD); self.assertTrue(again['provenance']['cache_reused_after_failure'])
        self.mode['value'] = 'good'
        self.assertEqual(self.cache.post_json(url, {'query': 'q'})['provenance']['sha256'], first['provenance']['sha256'])

    def test_pwd_charge_summary_errors_are_invalid_records(self):
        url = p.BILLING+'/2/details'
        errored = {'Parcel': {'ParcelID': 2}, 'ChargeSummary': {'Errors': ['temporarily unavailable']}}
        with tempfile.TemporaryDirectory() as root:
            cache = SharedCache(root, fallback_roots=[], opener=lambda *a, **k: body(errored))
            with self.assertRaisesRegex(SourceError, 'billing service reported errors'):
                cache.fetch_json(url)
            self.assertIsNone(cache._read(url))


# --- D4: pagination ----------------------------------------------------------------

def paged_opener(total, cap):
    def opener(request, timeout=None):
        query = parse_qs(urlparse(request.full_url).query)
        offset = int(query['resultOffset'][0]); count = min(int(query['resultRecordCount'][0]), cap)
        ids = list(range(1, total+1))[offset:offset+count]
        data = {'type': 'FeatureCollection', 'features': [{'type': 'Feature', 'id': i, 'properties': {'objectid': i}, 'geometry': None} for i in ids]}
        if offset+count < total:
            data['properties'] = {'exceededTransferLimit': True}
        return body(data)
    return opener


class PaginationTests(unittest.TestCase):
    def test_service_page_cap_below_requested_size_returns_every_record(self):
        for cap, page_size in ((1000, 2000), (500, 1000), (400, 1000)):
            with self.subTest(cap=cap), tempfile.TemporaryDirectory() as root:
                result = arcgis_features('https://example.test/FeatureServer/0', Cache(root, opener=paged_opener(2500, cap)),
                                         {'outSR': '4326'}, page_size=page_size)
                self.assertEqual(sorted(f['id'] for f in result['features']), list(range(1, 2501)))

    def test_truncated_page_without_progress_fails_loudly(self):
        cache = Mock(); cache.fetch_json.return_value = {'data': {'features': [], 'exceededTransferLimit': True}, 'provenance': {}}
        with self.assertRaisesRegex(SourceError, 'no pagination progress'):
            arcgis_features('https://example.test/0', cache)


# --- D6(b): undeclared or ESRI-only CRS --------------------------------------------

class SourceCRSTests(unittest.TestCase):
    def fetch(self, data, params):
        cache = Mock(); cache.fetch_json.return_value = {'data': data, 'provenance': {}}
        return arcgis_features('https://example.test/FS/0', cache, params)

    def test_rfc7946_lonlat_body_is_not_relabelled_as_requested_crs(self):
        lonlat = {'type': 'FeatureCollection', 'features': [{'type': 'Feature', 'id': 1, 'properties': {},
                  'geometry': {'type': 'Point', 'coordinates': [-75.17, 39.96]}}]}
        with self.assertRaisesRegex(SourceError, 'no CRS member'):
            self.fetch(lonlat, {'outSR': '2272'})
        envelope = {'geometry': '2691000,238000,2692000,239000', 'geometryType': 'esriGeometryEnvelope', 'inSR': '2272', 'outSR': '2272'}
        with self.assertRaisesRegex(SourceError, 'misses'):
            self.fetch(lonlat, envelope)
        projected = {'features': [{'id': 1, 'geometry': {'type': 'Point', 'coordinates': [2691500, 238500]}}]}
        self.assertEqual(self.fetch(projected, envelope)['crs'], 'EPSG:2272')

    def test_esri_only_wkid_is_resolved_or_rejected_as_source_error(self):
        self.assertTrue(crs_from_declaration(102729).equals(crs_from_declaration('EPSG:2272')))
        self.assertEqual(self.fetch({'spatialReference': {'wkid': 102729}, 'features': []}, {'outSR': '2272', 'f': 'json'})['crs'], 'EPSG:2272')
        with self.assertRaisesRegex(SourceError, 'CRS'):
            self.fetch({'spatialReference': {'wkid': 999999}, 'features': []}, {'outSR': '2272', 'f': 'json'})


# --- D6(a): record age limit --------------------------------------------------------

class RecordAgeTests(unittest.TestCase):
    URL = 'https://stormwater.phila.gov/PwdWebApi/api/v1/parcel/12345'

    def cache(self, root, opener, reuse):
        cache = SharedCache(Path(root), fallback_roots=[], reuse_recent_records=reuse, opener=opener)
        cache._store(self.URL, b'{"Parcel":{"Shape":"OLD-2023"}}', retrieved_at='2023-01-01T00:00:00+00:00')
        return cache

    def test_expired_record_is_refetched_without_explicit_refresh(self):
        calls = []
        with tempfile.TemporaryDirectory() as root:
            cache = self.cache(root, lambda request, timeout=None: calls.append(1) or body({'Parcel': {'Shape': 'NEW'}}), True)
            self.assertEqual(cache.fetch_json(self.URL)['data'], {'Parcel': {'Shape': 'NEW'}})
        self.assertEqual(len(calls), 1)

    def test_failed_refetch_reuses_expired_record_only_with_an_explicit_event(self):
        with tempfile.TemporaryDirectory() as root:
            cache = self.cache(root, network_guard.offline_opener, True)
            item = cache.fetch_json(self.URL)
            self.assertEqual(item['data'], {'Parcel': {'Shape': 'OLD-2023'}})
            self.assertTrue(item['provenance']['record_age_limit_exceeded'])
            self.assertEqual(cache.reuse_events[-1]['status'], 'reused_expired_record_after_failure')
            proxy = _Fallback(cache); proxy.fetch_json(self.URL)
            self.assertTrue(proxy.used_cache)
        with tempfile.TemporaryDirectory() as root:
            cache = self.cache(root, lambda *a, **k: self.fail('No request when the record policy is inactive'), False)
            cache.fetch_json(self.URL)
            self.assertEqual(cache.reuse_events[-1]['status'], 'reused_expired_record')


# --- E1: owner screen (D8) -----------------------------------------------------------

class OwnerScreenTests(unittest.TestCase):
    def test_private_lookalikes_public_bodies_and_prefix_review(self):
        expected = {
            'nongovernment_record': ['COMMONWEALTH PLAZA ASSOCIATES LLC', 'COMMONWEALTH HOSPITALITY LP', 'PHILADELPHIA WATERFRONT PARTNERS LP',
                                     'THE PHILADELPHIA SCHOOL', 'PHILADELPHIA SCHOOL OF CIRCUS ARTS', 'PHILADELPHIA AUTHENTIC FOODS INC',
                                     'PA STATE EMPLOYEES CREDIT UNION', 'PENNSYLVANIA STATE EDUCATION ASSN', 'U S AIRWAYS INC',
                                     'PHILADELPHIA HOUSING PARTNERS LP', 'PHILADELPHIA PARKING ASSOCIATES LLC', 'PHILADELPHIA COUNTY DENTAL SOCIETY',
                                     'PHILADELPHIA ZOO', 'U S STEEL CORP'],
            'government': ['PHILADELPHIA GAS WORKS', 'PHILA GAS WORKS', 'PHILADELPHIA LAND BANK', 'NATIONAL RAILROAD PASSENGER CORP',
                           'PHILADELPHIA INDUSTRIAL DEVELOPMENT CORP', 'BOARD OF CITY TRUSTS', 'PHILADELPHIA AUTHORITY FOR INDUSTRIAL DEVELOPMENT',
                           'REDEVELOPMENT AUTHORITY OF THE CITY OF PHILADELPHIA', 'CITY OF PHILADELPHIA', 'CITY & COUNTY OF PHILADELPHIA',
                           'COMMONWEALTH OF PA DEPT OF GENERAL SERVICES', 'AMTRAK'],
            'review': ['PENNSYLVANIA STATE UNIVERSITY', 'PENNSYLVANIA STATE UNIV', 'TEMPLE UNIVERSITY-OF THE COMMONWEALTH',
                       'CITY OF PHILADELPHIA HOUSING PARTNERS', 'PHILADELPHIA HOUSING AUTHORITY DEVELOPMENT FUND LLC'],
        }
        for status, names in expected.items():
            for name in names:
                with self.subTest(name=name):
                    self.assertEqual(p.owner_status(name)['status'], status)


# --- Prospect scans (synthetic offline world) ----------------------------------------

def sysf(sid, bounds, project):
    return {'type': 'Feature', 'id': int(sid), 'geometry': mapping(box(*bounds)), 'properties': {'objectid': int(sid), 'gsi_system_id': sid,
            'project_type': 'Private - Retrofit', 'year_installed': 2018, 'status': 'Complete', 'gsi_system_type': 'Rain Garden', 'project_number': project}}


def parf(pid, bounds):
    return {'type': 'Feature', 'id': int(pid), 'geometry': mapping(box(*bounds)), 'properties': {'objectid': int(pid), 'parcelid': int(pid),
            'address': f'{pid} TEST ST', 'owner1': 'PRIVATE HOLDINGS LLC', 'owner2': None, 'gross_area': (bounds[2]-bounds[0])*(bounds[3]-bounds[1])}}


def bill(pid, charge=1000):
    return {'Parcel': {'ParcelID': int(pid), 'Owner1': 'PRIVATE HOLDINGS LLC', 'Owner2': None, 'Address': f'{pid} TEST ST', 'GrossArea': 100000,
            'ImpervArea': 80000, 'NPDESCredit': 0, 'BldgType': 'NonRes'},
            'ChargeSummary': {'GrossCreditSqFt': 0, 'ImpervCreditSqFt': 0, 'Errors': [], 'ParcelTotals': [{'TotalStormwaterCharge': charge,
            'RateSchedule': {'IsCurrent': True, 'StartDate': '2026-07-01T00:00:00', 'EndDate': '2027-06-30T00:00:00'}}]}, 'Pending': {'Expired': 0, 'Credits': 0}}


class World:
    """Offline City/PWD services that declare their CRS like the real ArcGIS layers."""
    def __init__(self, systems, parcels, bills, parcel_errors=0, fail_parcel_calls=()):
        self.systems, self.parcels, self.bills = systems, parcels, bills
        self.parcel_errors, self.fail_parcel_calls, self.calls = parcel_errors, set(fail_parcel_calls), []

    def opener(self, request, timeout=None):
        url = request.full_url; self.calls.append(url)
        query = {k: v[0] for k, v in parse_qs(urlparse(url).query).items()}
        crs = {'type': 'name', 'properties': {'name': 'EPSG:2272'}}
        if 'GSI_SMP_TYPES' in url:
            return body({'type': 'FeatureCollection', 'crs': crs, 'features': self.systems})
        if 'PWD_PARCELS' in url:
            number = sum('PWD_PARCELS' in c for c in self.calls)
            if number in self.fail_parcel_calls:
                raise OSError('parcel service timeout')
            if self.parcel_errors:
                self.parcel_errors -= 1
                return body({'error': {'code': 500, 'message': 'Unable to complete operation (transient)'}})
            points = json.loads(query['geometry'])['points']
            hits = [f for f in self.parcels if any(shape(f['geometry']).intersects(Point(*pt)) for pt in points)]
            return body({'type': 'FeatureCollection', 'crs': crs, 'features': hits})
        if '/PwdWebApi/' in url:
            return body(self.bills[url.rstrip('/').split('/')[-2]])
        raise AssertionError(url)


class ProspectScanTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup); self.root = self.temp.name

    def cache(self, world):
        return SharedCache(self.root+'/public', fallback_roots=[], opener=world.opener)

    def test_transient_error_body_is_refetched_by_the_next_scan(self):
        world = World([sysf('1', (10, 10, 90, 90), 'P1')], [parf('1', (0, 0, 100, 100))], {'1': bill('1')}, parcel_errors=1)
        cache = self.cache(world)
        with self.assertRaisesRegex(SourceError, 'smoke check'):
            p.run_scan(self.root, cache=cache)
        before = len(world.calls)
        result = p.run_scan(self.root, cache=cache, refresh_stale=True)
        self.assertEqual(result['status'], 'complete'); self.assertEqual([s['parcel_ids'] for s in result['top']], [['1']])
        self.assertTrue(any('PWD_PARCELS' in c for c in world.calls[before:]))
        self.assertFalse(any('GSI_SMP' in c for c in world.calls[before:]))  # inventory reused, not re-downloaded

    def test_cached_legacy_error_entry_counts_as_missing(self):
        url = p.BILLING+'/1/details'
        source = Mock(); source._read_usable.return_value = (json.dumps({'error': 'old'}).encode(), {'retrieved_at': '2026-11-15T00:00:00Z'})
        source._problem.return_value = 'source reported an error'; source.fetch_json.return_value = {'data': bill('1'), 'provenance': {}}
        capped = p.CappedCache(source, max_requests=1)
        self.assertEqual(capped.fetch_json(url)['data'], bill('1')); self.assertEqual(capped.requests, 1)

    def test_every_selected_system_is_located_not_just_the_project_seed(self):
        world = World([sysf('1', (10, 10, 90, 90), 'P1'), sysf('2', (210, 10, 240, 40), 'P1')],
                      [parf('1', (0, 0, 100, 100)), parf('2', (200, 0, 300, 100))], {'1': bill('1', 1000), '2': bill('2', 5000)})
        result = p.run_scan(self.root, cache=self.cache(world))
        self.assertEqual(result['counts']['matched_parcels'], 2); self.assertEqual(result['ambiguous_matches'], [])
        self.assertEqual(result['top'][0]['parcel_ids'], ['1', '2'])

    def test_unqueried_parcels_are_labelled_distinctly(self):
        world = World([sysf('1', (10, 10, 90, 90), 'P1'), sysf('2', (210, 10, 240, 40), 'P1')],
                      [parf('1', (0, 0, 100, 100)), parf('2', (200, 0, 300, 100))], {'1': bill('1'), '2': bill('2')}, fail_parcel_calls={2})
        result = p.run_scan(self.root, cache=self.cache(world))
        held = result['ambiguous_matches']
        self.assertEqual([(h['system_id'], h['reason_code']) for h in held], [('2', 'parcel_not_queried')])
        self.assertEqual(result['counts']['ambiguous_systems'], 0); self.assertEqual(result['counts']['parcel_not_queried_systems'], 1)
        self.assertEqual(result['status'], 'partial')

    def test_failed_billing_can_be_retried_and_geometry_is_stored_once(self):
        errored = bill('2', 5000); errored['ChargeSummary']['Errors'] = ['temporarily unavailable']
        parcels = [parf('1', (0, 0, 100, 100)), parf('2', (400, 0, 500, 100))]
        world = World([sysf('1', (10, 10, 90, 90), 'P1'), sysf('2', (410, 10, 490, 90), 'P2')], parcels, {'1': bill('1'), '2': errored})
        cache = self.cache(world)
        first = p.run_scan(self.root, cache=cache)
        self.assertEqual(first['retry_parcel_ids'], ['2']); self.assertEqual([f['parcel_id'] for f in first['failures']], ['2'])
        raw = (Path(self.root)/'runs'/first['id']/'results.json').read_text()
        self.assertEqual(raw.count(json.dumps(parcels[0]['geometry']['coordinates'], separators=(',', ':'))), 1)
        self.assertEqual(p.canonical(p.load_result(self.root)), p.canonical(first))
        world.bills['2'] = bill('2', 5000)  # source recovers
        retried = p.update_selected(self.root, ['2'], cache=cache)
        self.assertEqual(retried['retry_parcel_ids'], []); self.assertEqual(retried['failures'], [])
        self.assertEqual(sorted(r['parcel_id'] for r in retried['parcel_rows']), ['1', '2']); self.assertEqual(retried['status'], 'complete')
        self.assertFalse(list(Path(self.root).glob('latest.tmp')))

    def test_failed_refresh_of_stale_bills_keeps_flagged_copies(self):
        systems = [sysf(str(i), (i*200+10, 10, i*200+90, 90), f'P{i}') for i in range(1, 4)]
        parcels = [parf(str(i), (i*200, 0, i*200+100, 100)) for i in range(1, 4)]
        world = World(systems, parcels, {str(i): bill(str(i), 1000*i) for i in range(1, 4)})
        cache = self.cache(world)
        first = p.run_scan(self.root, cache=cache)

        class Later(dt.datetime):
            @classmethod
            def now(cls, tz=None):
                return dt.datetime.now(tz)+dt.timedelta(days=45)
        cache.opener = network_guard.offline_opener
        with patch.object(p, 'datetime', Later):
            later = p.run_scan(self.root, cache=cache, refresh_stale=True)
        self.assertEqual([s['parcel_ids'] for s in later['top']], [['1', '2', '3']])
        self.assertEqual(len(later['stale_records_kept']), 3); self.assertTrue(later['top'][0]['needs_record_review'])
        self.assertEqual(later['status'], 'partial'); self.assertTrue(later['promoted'])
        self.assertEqual(p.load_result(self.root)['id'], later['id']); self.assertNotEqual(first['id'], later['id'])

    def test_degraded_run_does_not_replace_latest_shortlist(self):
        world = World([sysf('1', (10, 10, 90, 90), 'P1'), sysf('2', (410, 10, 490, 90), 'P2')],
                      [parf('1', (0, 0, 100, 100)), parf('2', (400, 0, 500, 100))], {'1': bill('1'), '2': bill('2')})
        cache = self.cache(world)
        good = p.run_scan(self.root, cache=cache)
        world.bills['2'] = deepcopy(world.bills['2']); world.bills['2']['ChargeSummary']['Errors'] = ['down']
        worse = p.run_scan(self.root, cache=cache, refresh=True)
        self.assertFalse(worse['promoted']); self.assertIn('remains the latest', worse['not_promoted_reason'])
        self.assertEqual(p.load_result(self.root)['id'], good['id'])
        self.assertEqual(p.load_result(self.root, worse['id'])['id'], worse['id'])

    def test_cancel_during_save_reports_the_saved_result(self):
        world = World([sysf('1', (10, 10, 90, 90), 'P1')], [parf('1', (0, 0, 100, 100))], {'1': bill('1')})
        stop = Event(); original = p.save_result
        def slow_save(root, result, **kw):
            original(root, result, **kw); stop.set()
        with patch.object(p, 'save_result', side_effect=slow_save):
            result = p.run_scan(self.root, cache=self.cache(world), cancel=stop)
        self.assertEqual(p.load_result(self.root)['id'], result['id'])

    def test_selected_update_keeps_the_saved_limit(self):
        world = World([sysf('1', (10, 10, 90, 90), 'P1'), sysf('2', (410, 10, 490, 90), 'P2')],
                      [parf('1', (0, 0, 100, 100)), parf('2', (400, 0, 500, 100))], {'1': bill('1'), '2': bill('2')})
        cache = self.cache(world)
        first = p.run_scan(self.root, cache=cache, limit=1)
        self.assertEqual(len(first['top']), 1)
        after = p.update_selected(self.root, ['1'], cache=cache)
        self.assertEqual(len(after['top']), 1); self.assertEqual(p.rerank_saved(self.root)['limit'], 1)

    def test_job_refresh_flag_is_applied_or_rejected(self):
        from stormwater.prospect_jobs import ProspectJobs
        jobs = ProspectJobs(self.root)
        with self.assertRaisesRegex(ValueError, 'cannot refresh'):
            jobs.start(refresh=True)
        done = Event()
        def scan(root, **kw):
            done.set(); scan.kw = kw; return {'id': 'fixture'}
        with patch('stormwater.prospect_jobs.run_scan', side_effect=scan):
            jobs.start(refresh=True, mode='update'); self.assertTrue(done.wait(2))
        self.assertTrue(scan.kw['refresh'])


# --- D5/D6(c): PASDA imagery -------------------------------------------------------

PARCEL = mapping(box(2691146, 238552, 2691528, 239087))


def metadata_xml(**dates):
    period = ''.join(f'<{k}>{v}</{k}>' for k, v in dates.items())
    wrap = f'<rngdates>{period}</rngdates>' if 'begdate' in dates else f'<sngdate>{period}</sngdate>'
    return f'<metadata><idinfo><timeperd><timeinfo>{wrap}</timeinfo></timeperd></idinfo></metadata>'.encode()


class Pasda:
    def __init__(self, years, *, alpha=255, metadata=None, export_down=False, catalog_down=False):
        self.years, self.alpha, self.metadata = years, alpha, metadata or {}
        self.export_down, self.catalog_down, self.calls = export_down, catalog_down, []

    def opener(self, request, timeout=None):
        url = request.full_url; self.calls.append(url)
        if url.startswith('https://services.pasda.psu.edu/arcgis/rest/services/pasda?'):
            if self.catalog_down:
                raise OSError('PASDA catalog timeout')
            return body({'services': [{'name': f'pasda/PhiladelphiaImagery{y}', 'type': 'MapServer'} for y in self.years]
                         + [{'name': 'pasda/PhiladelphiaImagery2011_leafon', 'type': 'MapServer'}]})
        if url.startswith('https://www.pasda.psu.edu/metadata/'):
            name = url.rsplit('/', 1)[-1][:-4]
            if name not in self.metadata:
                raise OSError('metadata missing')
            return body(self.metadata[name])
        if '/export?' in url:
            if self.export_down:
                raise OSError('PASDA export timeout')
            query = {k: v[0] for k, v in parse_qs(urlparse(url).query).items()}
            xmin, ymin, xmax, ymax = map(float, query['bbox'].split(','))
            return body({'href': 'http://services.pasda.psu.edu/out/'+url.split('/MapServer')[0].rsplit('/', 1)[-1]+'.png',
                         'extent': {'xmin': xmin, 'ymin': ymin, 'xmax': xmax, 'ymax': ymax, 'spatialReference': {'wkid': 102729}}})
        if url.startswith('https://services.pasda.psu.edu/out/'):
            return body(png([[[30, 130, 30, 255], [30, 130, 30, self.alpha]]]*2))
        raise AssertionError(url)


class ImageryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)

    def acquire(self, service, as_of='2026-11-15', root=None, **kw):
        from stormwater.acquisition import acquire_imagery
        return acquire_imagery(PARCEL, Cache(root or self.temp.name, opener=service.opener), freshness_policy=age_policy(as_of), **kw)

    def test_newest_eligible_vintage_png32_alpha_and_capture_metadata(self):
        service = Pasda(['2023', '2024', '2025', '2026'],
                        metadata={'PhiladelphiaImagery2026': metadata_xml(begdate='20260412', enddate='20260520')}, alpha=0)
        image = self.acquire(service, as_of='2028-03-01')
        self.assertEqual(image['service'], 'pasda/PhiladelphiaImagery2026')
        self.assertEqual(image['acquisition_date'], '2026-04-12'); self.assertEqual(image['capture_date_precision'], 'day')
        export = next(u for u in service.calls if '/export?' in u)
        self.assertIn('format=png32', export); self.assertIn('transparent=true', export)
        self.assertEqual(image['coverage_fraction'], .5); self.assertTrue(any('outside' in w for w in image['warnings']))
        self.assertFalse(any('arcgisonline' in u for u in service.calls))

    def test_year_only_metadata_keeps_january_bound_and_too_new_rule_uses_newest_listed(self):
        service = Pasda(['2024', '2025'], metadata={'PhiladelphiaImagery2025': metadata_xml(caldate='2025')})
        image = self.acquire(service)
        self.assertEqual((image['source_vintage'], image['acquisition_date']), ('2025', None))
        self.assertEqual(image['available_vintages'], ['2025', '2024'])
        with tempfile.TemporaryDirectory() as other, self.assertRaisesRegex(SourceError, 'three-year age limit'):
            self.acquire(Pasda(['2022', '2023']), as_of='2026-11-15', root=other)

    def test_outages_are_reported_as_outages(self):
        for service in (Pasda(['2025'], catalog_down=True), Pasda(['2025'], export_down=True)):
            with tempfile.TemporaryDirectory() as root, self.assertRaisesRegex(SourceError, 'outage'):
                self.acquire(service, root=root)

    def test_catalog_outage_uses_last_dated_catalog(self):
        self.acquire(Pasda(['2025']))
        from stormwater.acquisition import imagery_vintages
        warnings = []
        found, provenance = imagery_vintages(Cache(self.temp.name, opener=Pasda(['2025'], catalog_down=True).opener), True, warnings)
        self.assertEqual([v['year'] for v in found], ['2025']); self.assertTrue(provenance['cache_reused_after_failure'])
        self.assertIn('catalog refresh failed', warnings[0])

    def test_palette_blobs_from_old_caches_still_decode(self):
        from stormwater.acquisition import _coverage_fraction
        from rasterio.io import MemoryFile
        with MemoryFile() as mem:
            with mem.open(driver='PNG', width=2, height=1, count=1, dtype='uint8') as ds:
                ds.write(np.array([[[0, 1]]], dtype='uint8')); ds.write_colormap(1, {0: (0, 0, 0, 255), 1: (30, 130, 30, 255)})
            content = mem.read()
        self.assertEqual(_coverage_fraction(content), 1.0)


# --- R16 and D6(d)/(e): semantic model limit, fallback reason, RGB CRS, cache ------

class ModelLimitTests(unittest.TestCase):
    def test_large_analysis_box_coarsens_within_limit_before_request(self):
        from drainage_core.semantic_cover import analysis_resolution
        from stormwater.automatic import imagery_plan
        self.assertEqual(analysis_resolution([0, 0, 300, 300], 'EPSG:26918'), .5)
        target = analysis_resolution([0, 0, 600, 600], 'EPSG:26918')  # 36 ha: 0.5 m would be 1.44M cells
        self.assertGreater(target, .5); self.assertLessEqual(target, 1)
        self.assertLessEqual(-(-600//target)**2, 1_000_000)
        plan = imagery_plan(mapping(box(0, 0, 3000, 20)), 'EPSG:26918')  # long, thin: needs a larger image
        self.assertTrue(plan['model_within_limit']); self.assertGreater(plan['image_size'], 2048)
        too_big = imagery_plan(mapping(box(0, 0, 1500, 1500)), 'EPSG:26918')
        self.assertFalse(too_big['model_within_limit']); self.assertIn('at most 1 m', too_big['reason'])

    def test_semantic_model_runs_for_a_box_over_25_hectares(self):
        from drainage_core.semantic_cover import semantic_cover
        c = fixture(); c['parcel'] = mapping(box(0, 0, 520, 520))  # 27 ha
        raw = png(np.full((1100, 1100, 3), 100, 'uint8'))
        with tempfile.TemporaryDirectory() as folder:
            weights = Path(folder)/'w'; weights.write_bytes(b'w'); runtime = Path(folder)/'python'; runtime.touch()
            def infer(command, **kw):
                np.save(command[-1], np.full(np.load(command[-2]).shape[:2], 8, 'uint8')); return subprocess.CompletedProcess(command, 0, '', '')
            with patch('drainage_core.semantic_cover.MODEL_SHA256', sha256(b'w').hexdigest()), \
                 patch('drainage_core.semantic_cover.subprocess.run', side_effect=infer):
                result = semantic_cover(raw, [0, 0, 520, 520], c, {'sha256': 'a'*64}, runtime=runtime, weights=weights)
        width, height = result['settings']['pixel_dimensions']
        self.assertLessEqual(width*height, 1_000_000); self.assertGreater(result['settings']['target_pixel_metres'], .5)

    def test_transparent_nodata_does_not_bleed_into_valid_model_input(self):
        from drainage_core.semantic_cover import semantic_cover
        pixels = np.zeros((300, 300, 4), 'uint8'); pixels[:, 120:] = (200, 200, 200, 255)  # left 40% transparent black
        raw = png(pixels); c = fixture(); c['parcel'] = mapping(box(0, 0, 30, 30)); seen = {}
        with tempfile.TemporaryDirectory() as folder:
            weights = Path(folder)/'w'; weights.write_bytes(b'w'); runtime = Path(folder)/'python'; runtime.touch()
            def infer(command, **kw):
                seen['input'] = np.load(command[-2]); np.save(command[-1], np.full(seen['input'].shape[:2], 8, 'uint8'))
                return subprocess.CompletedProcess(command, 0, '', '')
            with patch('drainage_core.semantic_cover.MODEL_SHA256', sha256(b'w').hexdigest()), \
                 patch('drainage_core.semantic_cover.subprocess.run', side_effect=infer):
                semantic_cover(raw, [0, 0, 30, 30], c, {'sha256': 'a'*64}, runtime=runtime, weights=weights)
        valid_columns = seen['input'][:, 24:, :].astype(int)  # source columns >= 120 are fully opaque
        self.assertTrue(np.all(np.abs(valid_columns-200) <= 1), valid_columns[0, :3].tolist())

    def test_rgb_fallback_reason_is_recorded_next_to_results(self):
        from stormwater.automatic import landcover
        c = fixture(); c['imagery_age_policy'] = age_policy('2026-11-15')
        raw = png([[[30, 130, 30], [100, 100, 100]]]*2)
        with tempfile.TemporaryDirectory() as root:
            path = Path(root)/'image'; path.write_bytes(raw)
            c['measurement_imagery'] = {'source_vintage': '2025', 'sha256': sha256(raw).hexdigest(), 'blob_path': str(path),
                                        'bounds': [0, 0, 4, 2], 'crs': c['crs'], 'sources': []}
            with patch('drainage_core.semantic_cover.semantic_cover', side_effect=RuntimeError('worker crashed')):
                result = landcover(c, Mock(), False)
        self.assertIn('RuntimeError: worker crashed', result['fallback']['message'])
        self.assertEqual(result['model_unavailable'], 'RuntimeError: worker crashed')

    def test_rgb_fallback_measures_in_image_crs_after_terrain_reprojection(self):
        from drainage_core.geometry import reproject
        from stormwater.automatic import enrich_candidates
        p2272 = box(2691200, 238600, 2691300, 238700)
        raw = png([[[60, 180, 60]]*30]*30)
        with tempfile.TemporaryDirectory() as root:
            blob = Path(root)/'blob'; blob.write_bytes(raw)
            info = {'sha256': sha256(raw).hexdigest(), 'blob_path': str(blob), 'bounds': list(p2272.buffer(100).bounds),
                    'crs': 'EPSG:2272', 'source_vintage': '2025', 'acquisition_date': None}
            moved = reproject(p2272, 'EPSG:2272', 'EPSG:26918')
            case = {'id': 't', 'crs': 'EPSG:26918', 'area_crs': 'EPSG:2272', 'parcel': mapping(moved),
                    'features': {'type': 'FeatureCollection', 'features': []}, 'imagery': info, 'measurement_imagery': info,
                    'automatic': {}, 'assessment': {'records': []}}
            out = enrich_candidates(case)['automatic']
        self.assertAlmostEqual(out['image_vegetation_candidate_sqft'], 10000, delta=50)

    def test_interrupted_semantic_cache_write_is_a_miss(self):
        import drainage_core.semantic_cover as sc
        c = {'crs': 'EPSG:2272', 'parcel': mapping(box(50, 50, 150, 150))}
        raw = png(np.full((200, 200, 3), 120, 'uint8'))
        calls = []
        def ok(command, **kw):
            calls.append(1); np.save(command[4], np.full(np.load(command[3]).shape[:2], 8, 'uint8')); return subprocess.CompletedProcess(command, 0, '', '')
        with tempfile.TemporaryDirectory() as folder:
            folder = Path(folder); weights = folder/'w.pth'; weights.write_bytes(b'fake'); runtime = folder/'python'; runtime.touch()
            with patch.object(sc, 'MODEL_SHA256', sha256(b'fake').hexdigest()), patch.object(sc.subprocess, 'run', side_effect=ok):
                sc.semantic_cover(raw, [0, 0, 200, 200], c, {'sha256': 'a'*64}, runtime=runtime, weights=weights, cache=folder/'semantic')
                next((folder/'semantic').glob('*.sha256')).unlink()
                sc.semantic_cover(raw, [0, 0, 200, 200], c, {'sha256': 'a'*64}, runtime=runtime, weights=weights, cache=folder/'semantic')
                self.assertEqual(len(calls), 2); self.assertEqual(len(list((folder/'semantic').glob('*.sha256'))), 1)
                self.assertFalse(list((folder/'semantic').glob('*.tmp')))


# --- D6(f)/(g): soils and terrain discovery ---------------------------------------

class SoilAndTerrainTests(unittest.TestCase):
    def test_sda_geometry_collection_keeps_polygonal_parts(self):
        from stormwater.soil_sources import COLUMNS, parse
        wkt = 'GEOMETRYCOLLECTION (POLYGON ((0 0, 1 0, 1 1, 0 1, 0 0)), LINESTRING (1 1, 2 2), POINT (3 3))'
        features = parse({'Table': [COLUMNS, ['1', '10', wkt, 'Urban land', 'c1', 'Urban', 90, 'D']]})
        self.assertEqual(len(features), 1); self.assertEqual(shape(features[0]['geometry']).area, 1)

    def test_newest_usgs_product_is_tried_first_and_datum_spellings_match(self):
        from xml.etree import ElementTree
        from stormwater import automatic_terrain as terrain
        facts = terrain.metadata_facts(ElementTree.fromstring(
            '<m><idinfo><timeperd><timeinfo><rngdates><begdate>20240414</begdate><enddate>20250402</enddate></rngdates></timeinfo></timeperd></idinfo>'
            '<spref><vertdef><altsys><altdatum>NAVD 88</altdatum><altunits>meters</altunits></altsys></vertdef></spref></m>'))
        self.assertEqual((facts['metres'], facts['vertical_datum'], facts['capture_start']), (True, 'NAVD88', '2024-04-14'))
        self.assertIsNone(terrain.metadata_facts(ElementTree.fromstring('<m>elevation values are in meters NGVD 29</m>'))['vertical_datum'])
        old = {'downloadURL': 'https://prd-tnm.s3.amazonaws.com/StagedProducts/Elevation/1m/Projects/OLD_2015/TIFF/old.tif', 'publicationDate': '2020-03-30'}
        new = {'downloadURL': 'https://prd-tnm.s3.amazonaws.com/StagedProducts/Elevation/1m/Projects/NEW_D24/TIFF/new.tif', 'publicationDate': '2026-10-23'}
        cache = Mock(); cache.fetch_json.return_value = {'data': {'items': [old, new]}, 'provenance': {}}
        cache.fetch_bytes.side_effect = OSError('stop after metadata order is known')
        case = {'crs': 'EPSG:2272', 'parcel': mapping(box(2691146, 238552, 2691528, 239087))}
        with self.assertRaises(ValueError):
            terrain.acquire(case, cache)
        self.assertIn('NEW_D24', cache.fetch_bytes.call_args_list[0].args[0])


if __name__ == '__main__':
    unittest.main()
