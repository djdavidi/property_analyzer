"""G1: billed-area reconciliation across saved/cached parcels (offline fixtures).

Expected areas are derived by hand from tariff 2026-09-01 section 4.3(a): billed
area = ceil(final area / 500) x 500; final GA = GA - GA credit; final IA =
statutory IA - IA credit - IAR; under 5,000 sq ft GA statutory IA is 85% of GA
(developed) or 25% (undeveloped).
"""
from hashlib import sha256
import csv
import io
import json
from pathlib import Path
import tempfile
import unittest

from drainage_core.sources import Cache
from stormwater.billing_reconciliation import COLUMNS, main, reconcile, report
import network_guard

network_guard.install()

FIXTURES = Path(__file__).resolve().parent/'fixtures'/'billing'
META = json.loads((FIXTURES/'pwd-201345-details-excerpt.meta.json').read_text())
EXCERPT = (FIXTURES/META['file']).read_bytes()


def refuse(request, timeout=None):
    raise AssertionError('The reconciliation report must not fetch anything')


def baseline(ga, ia, billed_ga, billed_ia, ga_credit=0, ia_credit=0, iar=0, **extra):
    return {'ga_sqft': ga, 'ia_sqft': ia, 'recorded_ga_sqft': ga, 'recorded_ia_sqft': ia,
            'billed_ga_sqft': billed_ga, 'billed_ia_sqft': billed_ia, 'existing_ga_credit_sqft': ga_credit,
            'existing_ia_credit_sqft': ia_credit, 'existing_iar_sqft': iar, 'npdes_fraction': 0,
            'property_type': 'NonRes', 'accounts': [{'allocation': 1, 'discount_factor': 1}], 'undeveloped': None, **extra}


def write_case(root, identifier, base, name='Synthetic reconciliation case'):
    folder = Path(root)/identifier; folder.mkdir(parents=True)
    (folder/'case.json').write_text(json.dumps({'id': identifier, 'name': name, 'baseline': base}))


def tree(root):
    return sorted((str(p.relative_to(root)), sha256(p.read_bytes()).hexdigest() if p.is_file() else None)
                  for p in Path(root).rglob('*'))


class ReconcileTests(unittest.TestCase):
    def test_fixture_excerpt_hash(self):
        self.assertEqual(sha256(EXCERPT).hexdigest(), META['excerpt_sha256'])

    def test_credit_order_mismatch_is_flagged_not_corrected(self):
        # GA 10,000 - 1,000 credit = 9,000 (billed 9,000). IA 8,000 - 2,000 = 6,000.
        rows = reconcile(baseline(10000, 8000, 9000, 8000, ga_credit=1000, ia_credit=2000))
        self.assertEqual(len(rows), 1); r = rows[0]
        self.assertEqual((r['computed_final_ga_sqft'], r['computed_billed_ga_sqft']), (9000, 9000))
        self.assertEqual((r['computed_final_ia_sqft'], r['computed_billed_ia_sqft']), (6000, 6000))
        self.assertEqual((r['ga_match'], r['ia_match'], r['status']), ('matches_billed_area', 'mismatch', 'mismatch'))
        self.assertTrue(any('reconcile recorded credits' in n for n in r['notes']))

    def test_small_parcel_reports_both_status_alternatives(self):
        # GA 4,000: developed 3,400 -> 3,500 billed; undeveloped 1,000 -> 1,000.
        rows = {r['alternative']: r for r in reconcile(baseline(4000, 3900, 4000, 1000))}
        self.assertEqual(set(rows), {'developed', 'undeveloped'})
        self.assertEqual(rows['developed']['computed_billed_ia_sqft'], 3500)
        self.assertEqual(rows['developed']['status'], 'mismatch')
        self.assertEqual(rows['undeveloped']['computed_billed_ia_sqft'], 1000)
        self.assertEqual(rows['undeveloped']['status'], 'consistent')
        self.assertTrue(all(any('Undeveloped status unknown' in n for n in r['notes']) for r in rows.values()))

    def test_final_area_match_and_unknowns_stay_unknown(self):
        r = reconcile(baseline(10000, 6250, 10000, 6250))[0]
        self.assertEqual((r['ga_match'], r['ia_match']), ('matches_billed_area', 'matches_final_area'))
        self.assertEqual(r['status'], 'consistent')
        self.assertEqual(reconcile(baseline(10000, 6000, None, None))[0]['status'], 'not_available')
        missing = reconcile(baseline(None, 6000, 10000, 6000))[0]
        self.assertEqual(missing['status'], 'not_evaluated'); self.assertIsNone(missing['computed_billed_ga_sqft'])
        self.assertEqual(reconcile(baseline(10000, 6000, 10000, 6000, property_type='Res'))[0]['status'], 'not_applicable')
        assumed = reconcile(baseline(10000, 8000, 10000, 7000, ia_credit=1000, iar=None))[0]
        self.assertEqual(assumed['status'], 'consistent')
        self.assertTrue(any('IAR split unknown' in n for n in assumed['notes']))
        self.assertIsNone(assumed['existing_iar_sqft'])
        odd = reconcile(baseline(10000, 6000, 10000, 6000, bill_date='2025-09-01'))[0]
        self.assertTrue(any('outside the verified tariff period' in n for n in odd['notes']))


class StoreReportTests(unittest.TestCase):
    def test_public_excerpt_matches_by_hand_and_stores_are_read_only(self):
        url = 'https://stormwater.phila.gov/PwdWebApi/api/v1/parcel/201345/details'
        with tempfile.TemporaryDirectory() as root:
            data = Path(root)/'data'
            cache = Cache(data/'public', opener=refuse)
            cache._store(url, EXCERPT, retrieved_at=META['retrieved_at'])
            # A newer capture whose body reports service errors is evidence, not data.
            cache._store(url, json.dumps({'ChargeSummary': {'Errors': ['Service down']}}).encode(),
                         retrieved_at='2026-11-17T00:00:00+00:00')
            write_case(data/'cases', 'pwd-77', baseline(10000, 8000, 9000, 8000, ga_credit=1000, ia_credit=2000))
            write_case(data/'cases', 'manual-no-baseline', None)
            before = tree(data)
            result = report([data])
            self.assertEqual(tree(data), before, 'Report must not write to the stores')
        rows = {(r['source'], r['source_ref']): r for r in result['rows']}
        public = rows[('cache', url)]
        # 190,627 -> ceil(381.254) x 500 = 191,000; 177,257 -> ceil(354.514) x 500 = 177,500.
        self.assertEqual(public['parcel_id'], 201345)
        self.assertEqual((public['computed_billed_ga_sqft'], public['computed_billed_ia_sqft']), (191000, 177500))
        self.assertEqual((public['pwd_billed_ga_sqft'], public['pwd_billed_ia_sqft']), (191000, 177500))
        self.assertEqual((public['ga_match'], public['ia_match'], public['status']),
                         ('matches_billed_area', 'matches_billed_area', 'consistent'))
        self.assertEqual(public['retrieved_at'], META['retrieved_at'])
        self.assertEqual(public['record_sha256'], META['excerpt_sha256'])
        self.assertEqual(rows[('case', 'pwd-77')]['status'], 'mismatch')
        self.assertEqual(rows[('case', 'manual-no-baseline')]['status'], 'source_error')
        self.assertEqual(result['summary']['parcels_with_mismatch'], [77])
        self.assertEqual(result['summary']['parcels_consistent_only'], [201345])
        self.assertIn('not a refund', result['claim'])
        self.assertEqual({s['kind'] for s in result['stores']}, {'cache', 'cases'})

    def test_error_only_capture_is_a_source_error_not_a_zero(self):
        url = 'https://stormwater.phila.gov/PwdWebApi/api/v1/parcel/5/details'
        with tempfile.TemporaryDirectory() as root:
            Cache(root, opener=refuse)._store(url, json.dumps({'ChargeSummary': {'Errors': ['x']}}).encode())
            result = report([root])
        self.assertEqual(len(result['rows']), 1)
        row = result['rows'][0]
        self.assertEqual((row['parcel_id'], row['status']), (5, 'source_error'))
        self.assertIn('errors', row['notes'][0])
        self.assertIsNone(row.get('computed_billed_ga_sqft'))

    def test_cli_writes_json_and_csv(self):
        with tempfile.TemporaryDirectory() as root:
            store = Path(root)/'cases'
            write_case(store, 'pwd-9', baseline(4000, 3900, 4000, 1000))
            out, table = Path(root)/'report.json', Path(root)/'report.csv'
            self.assertEqual(main(['--store', str(store), '--output', str(out), '--csv', str(table)]), 0)
            result = json.loads(out.read_text()); text = table.read_text()
        self.assertEqual(result['summary']['records'], 2)
        reader = list(csv.DictReader(io.StringIO(text)))
        self.assertEqual(tuple(reader[0].keys()), COLUMNS)
        self.assertEqual({r['alternative'] for r in reader}, {'developed', 'undeveloped'})
        self.assertEqual({r['alternative']: r['status'] for r in reader},
                         {'developed': 'mismatch', 'undeveloped': 'consistent'})


if __name__ == '__main__':
    unittest.main()
