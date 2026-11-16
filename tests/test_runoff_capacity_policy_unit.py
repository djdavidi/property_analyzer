"""Invented static-event budgets and PWD ledger unit tests; no site replay.

Hand arithmetic used below (treatment depth 1.5 in = 0.125 ft):

* Bed: 500 sq ft footprint at x=0; candidate ``base`` 2000 sq ft from x=0, so 1500 sq ft
  lies outside the bed. On-parcel route region 3000 sq ft: other ground = 2500 - 1500 = 1000.
* Garden rain: 500 x 0.125 = 62.5 cu ft. Off-parcel area 1000 -> 125 cu ft; other ground
  1000 -> 125 cu ft.
* Cell minimum 187.5 cu ft: 125 left after rain -> 1000 sq ft equivalent with no other
  load, 0 with either extra load. Bilinear 500 cu ft: 437.5 left -> capped at 1500 sq ft
  for every load (437.5 - 250 = 187.5 still holds 1500 x 0.125).
* Prices (GA = IA = 10000, no prior credit; each charge rounded half-up to cents):
  baseline 20 units: GA 20 x 1.003 = 20.06, IA 20 x 7.048 = 140.96.
  1000 sq ft -> 800 sq ft credits -> billed 9200 -> 19 units: GA 19.057 -> 19.06,
  IA 133.912 -> 133.91; saving 1.00 + 7.05 = 8.05/month = 96.60/yr.
  1500 sq ft -> 1200 credits -> 8800 -> 18 units: GA 18.054 -> 18.05, IA 126.864 -> 126.86;
  saving 2.01 + 14.10 = 16.11/month = 193.32/yr.
"""
from copy import deepcopy
import json
import unittest
from unittest.mock import patch

from drainage_core.engine import canonical
from stormwater.runoff_capacity import estimate_capacity_management
from tests.test_management_estimates import fixture, rectangle, add_existing, add_weighted_base, bind


def capacity(case, volumes=(187.5, 500), components=None, **extra):
    """Phase 4a-shaped capacity result (only the fields policy consumes)."""
    components = components or [('component-1', 500, volumes)]
    rows = [{'component_id': cid, 'rain_exposure_area_sqft': rain, 'scenarios': [
        {'name': 'perimeter_cell_minimum', 'status': 'estimated', 'volume_cuft': v[0]},
        {'name': 'perimeter_bilinear', 'status': 'estimated', 'volume_cuft': v[1]}]} for cid, rain, v in components]
    totals = [sum(c[2][i] for c in components) for i in (0, 1)]
    return {'system_id': '62571', 'status': 'estimated', 'reason': None, 'blocking_reasons': [],
        'unavailable_reasons': [], 'review_flags': [], 'storage_range_cuft': [min(totals), max(totals)],
        'volume_range_cuft': [min(totals), max(totals)], 'volume_range_missing_scenarios': [],
        'components': rows, 'component_count': len(rows), 'per_component_budget_required': len(rows) > 1,
        'source_lineage': {}, **extra}


def setup():
    case, gis, engineering = fixture()
    case['features']['features'][0]['geometry'] = rectangle(500)
    engineering['footprint_geometry'] = rectangle(500)
    engineering['runs'][0]['on_parcel_geometry'] = rectangle(3000)
    engineering['runs'][0]['area_scenarios'][1].update(area_sqft=2000, geometry=rectangle(2000))
    return case, gis, engineering, capacity(case)


def run(case, gis, engineering, cap, rebind=True):
    if rebind:
        bind(case, engineering, gis)
        cap['source_lineage'] = dict(engineering['source_lineage'])
    return estimate_capacity_management(case, gis, engineering, cap, '2026-11-16')


def row(result, storage='perimeter_cell_minimum', load='candidate_ia_and_garden_rain', candidate='base',
        split='single', run_name='nominal'):
    rows = next(r for r in result['runs'] if r['name'] == run_name)['scenarios']
    return next(s for s in rows if s['id'] == '/'.join((candidate, storage, split, load)))


class RunoffCapacityPolicyUnitTests(unittest.TestCase):
    def test_range_first_across_storage_methods_and_loads(self):
        case, gis, e, cap = setup()
        result = run(case, gis, e, cap)
        self.assertEqual(result['status'], 'storage_limited_range')
        head = result['headline']
        self.assertEqual(head['run'], 'nominal')
        self.assertEqual(head['storage_range_cuft'], [187.5, 500])
        self.assertEqual(head['annual_savings_range'], [0.0, 193.32])
        self.assertEqual(head['status'], 'range')
        self.assertEqual(head['storage_methods'], ['perimeter_cell_minimum', 'perimeter_bilinear'])
        self.assertIn('not a confidence interval', head['basis'])
        self.assertIsNone(head['qualifying_managed_area_sqft'])

    def test_bed_reserved_and_candidate_rows_known_answers(self):
        case, gis, e, cap = setup()
        result = run(case, gis, e, cap)
        best = row(result)
        self.assertAlmostEqual(best['system_bed_ia_excluded_sqft'], 500)
        self.assertAlmostEqual(best['candidate_ia_outside_bed_sqft'], 1500)
        self.assertAlmostEqual(best['direct_garden_rainfall_cuft'], 62.5)
        self.assertAlmostEqual(best['available_storage_for_candidate_runoff_cuft'], 125)
        self.assertAlmostEqual(best['volume_equivalent_managed_ia_sqft'], 1000)
        self.assertAlmostEqual(best['unaccommodated_candidate_runoff_cuft'], 62.5)
        self.assertEqual(best['annual_savings'], 96.60)
        self.assertTrue(best['volume_equivalent_is_hypothetical'])
        self.assertEqual(row(result, 'perimeter_bilinear')['annual_savings'], 193.32)
        self.assertIsNone(result['verified_managed_area_sqft'])

    def test_supplied_captured_stored_treated_and_qualifying_are_separate(self):
        case, gis, e, cap = setup()
        q = row(run(case, gis, e, cap))['quantities']
        self.assertAlmostEqual(q['runoff_supplied_cuft'], 250)   # 62.5 rain + 1500 x 0.125
        self.assertAlmostEqual(q['runoff_stored_cuft'], 187.5)   # 62.5 rain + 125 of candidate runoff
        for key in ('runoff_captured_cuft', 'runoff_treated_cuft', 'qualifying_managed_area_sqft'):
            self.assertIsNone(q[key])

    def test_off_parcel_area_consumes_storage_r6(self):
        case, gis, e, cap = setup()
        small = run(case, gis, e, deepcopy(cap))
        self.assertEqual(row(small, 'perimeter_bilinear', 'plus_off_parcel_runoff')['annual_savings'], 193.32)
        self.assertEqual(row(small, load='plus_off_parcel_runoff')['annual_savings'], 0)
        e['runs'][0]['off_parcel_area_sqft'] = 1000000
        large = run(case, gis, e, deepcopy(cap))
        # 437.5 cu ft left after rain cannot hold 125,000 cu ft of off-parcel runoff.
        self.assertEqual(row(large, 'perimeter_bilinear', 'plus_off_parcel_runoff')['volume_equivalent_managed_ia_sqft'], 0)
        self.assertEqual(row(large, 'perimeter_bilinear', 'plus_off_parcel_runoff')['annual_savings'], 0)

    def test_unknown_off_parcel_area_withholds_lower_end_and_reference(self):
        case, gis, e, cap = setup()
        e['runs'][0]['off_parcel_area_sqft'] = None
        result = run(case, gis, e, cap)
        self.assertEqual(row(result, load='plus_off_parcel_runoff')['status'], 'unavailable')
        self.assertEqual(result['headline']['annual_savings_range'][0], None)
        self.assertEqual(result['headline']['status'], 'partial_range')
        self.assertIsNone(result['current_estimate'])
        self.assertIn('unbounded', result['current_estimate_withheld_reason'])
        self.assertTrue(any(f['code'] == 'off_parcel_load_unbounded' for f in result['review_flags']))

    def test_bounded_reference_row_is_one_row_not_the_headline(self):
        case, gis, e, cap = setup()
        result = run(case, gis, e, cap)
        current = result['current_estimate']
        self.assertEqual(current['id'], 'base/perimeter_cell_minimum/single/plus_off_parcel_runoff')
        self.assertEqual(current['annual_savings'], 0)
        self.assertIn('not a bound', current['role'])

    def test_no_conservative_label_anywhere(self):
        case, gis, e, cap = setup()
        result = run(case, gis, e, cap)
        def keys(value):
            if isinstance(value, dict):
                for k, v in value.items():
                    yield k
                    yield from keys(v)
            elif isinstance(value, list):
                for v in value:
                    yield from keys(v)
        self.assertFalse(any('conservative' in str(k) for k in keys(result)))
        text = json.dumps(result)
        self.assertNotIn('conservative estimate', text.lower())

    def test_disconnected_components_budgeted_separately(self):
        # Two 250 sq ft parts: cell storage 100 and 50 cu ft, each reserves 31.25 for rain.
        # Remaining 68.75 and 18.75: pooled 87.5 -> 700 sq ft (560 credit -> 19 units, 96.60/yr);
        # all inflow to the least component 18.75 -> 150 sq ft (120 credit -> still 20 units, $0).
        case, gis, e, cap = setup()
        cap = capacity(case, components=[('component-1', 250, (100, 200)), ('component-2', 250, (50, 300))])
        result = run(case, gis, e, cap)
        pooled, least = row(result, split='pooled'), row(result, split='all_to_least')
        self.assertAlmostEqual(pooled['volume_equivalent_managed_ia_sqft'], 700)
        self.assertAlmostEqual(least['volume_equivalent_managed_ia_sqft'], 150)
        self.assertEqual(pooled['annual_savings'], 96.60)
        self.assertEqual(least['annual_savings'], 0)
        self.assertTrue(any(f['code'] == 'disconnected_components' for f in result['review_flags']))

    def test_capacity_status_blocked_unavailable_excluded_are_distinct(self):
        for status, field, reason in (('blocked', 'blocking_reasons', 'Terrain predates system'),
                                      ('unavailable', 'unavailable_reasons', 'A source DEM aligned to the case CRS is required'),
                                      ('excluded', 'reason', 'Installation year is after observation date')):
            with self.subTest(status=status):
                case, gis, e, cap = setup()
                cap.update(status=status, storage_range_cuft=None, components=[])
                cap[field] = [reason] if field.endswith('reasons') else reason
                result = run(case, gis, e, cap)
                self.assertEqual(result['status'], status)
                self.assertIn(reason, result['reasons'])
                self.assertIsNone(result['headline'])

    def test_review_flags_are_carried_through(self):
        case, gis, e, cap = setup()
        cap['review_flags'] = [{'code': 'dem_date_unknown', 'message': 'DEM capture date unknown'}]
        self.assertIn('dem_date_unknown', [f['code'] for f in run(case, gis, e, cap)['review_flags']])

    def test_partial_route_labels_rows_and_withholds_reference(self):
        case, gis, e, cap = setup()
        e['runs'][0].update(route_state='partial_upstream_unknown', route_state_reason='Touches window edge')
        result = run(case, gis, e, cap)
        self.assertEqual(result['headline']['status'], 'partial_range')
        self.assertEqual(result['headline']['partial_label'], 'partial: true value may be higher')
        self.assertEqual(row(result)['partial_label'], 'partial: true value may be higher')
        self.assertEqual(result['headline']['in_window_annual_savings_range'], [0.0, 193.32])
        self.assertIsNone(result['current_estimate'])

    def test_missing_terrain_or_failed_invariant_blocks(self):
        for state in ('missing_terrain', 'invariant_failed'):
            with self.subTest(state=state):
                case, gis, e, cap = setup()
                e['runs'][0]['route_state'] = state
                result = run(case, gis, e, cap)
                self.assertEqual(result['status'], 'blocked')
                self.assertIsNone(result['headline'])

    def test_nominal_blocked_is_not_replaced_by_a_sensitivity_run_h2(self):
        # Review H2 (repro new-policy/r9_cap_select.py).
        case, gis, e, cap = setup(); add_existing(case, gis)
        nominal = deepcopy(e['runs'][0]); sensitivity = deepcopy(e['runs'][0]); sensitivity['name'] = 'sens'
        for s in sensitivity['area_scenarios']:
            s['geometry'] = rectangle(s['area_sqft'], start=3.048)
        e['runs'] = [sensitivity, nominal]
        result = run(case, gis, e, cap)
        self.assertEqual(result['status'], 'blocked')
        self.assertIsNone(result['current_estimate'])
        self.assertIsNone(result['headline'])
        self.assertEqual(row(result, run_name='sens', candidate='base')['status'], 'calculated')
        self.assertTrue(any('Overlapping physical allocations' in r for r in result['reasons']))

    def test_fractional_candidate_scaled_without_fabricating_a_specific_subarea(self):
        # Weighted base: 500 sq ft at fraction 1 (entirely the bed) + 2500 at 0.2 = 500 outside.
        # Storage 100 - 62.5 rain = 37.5 cu ft -> 300 sq ft equivalent -> fraction 0.2 x 300/500 = 0.12.
        case, gis, e, cap = setup(); add_weighted_base(e)
        e['runs'][0]['area_scenarios'][1]['area_sqft'] = 1000
        cap = capacity(case, volumes=(100, 100))
        best = row(run(case, gis, e, cap))
        self.assertAlmostEqual(best['candidate_ia_outside_bed_sqft'], 500)
        self.assertAlmostEqual(best['volume_equivalent_managed_ia_sqft'], 300)
        components = best['priced']['weighted_components']
        self.assertEqual(len(components), 1)
        self.assertAlmostEqual(components[0]['impervious_fraction'], .12)
        self.assertTrue(best['priced']['fractional_ia_is_assumed'])

    def test_bad_original_scalar_not_hidden_by_area_recomputation(self):
        case, gis, e, cap = setup(); e['runs'][0]['area_scenarios'][1]['area_sqft'] = 9999
        result = run(case, gis, e, cap)
        self.assertEqual(result['status'], 'blocked')
        self.assertIsNone(result['current_estimate'])

    def test_known_failed_treatment_not_assumed_true_by_capacity(self):
        case, gis, e, cap = setup()
        case['assessment']['records'] = [{'id': 'failed', 'system_id': '62571', 'facts': {'treatment_depth_inches': .5}}]
        result = run(case, gis, e, cap)
        self.assertEqual(result['status'], 'blocked')
        self.assertIsNone(result['current_estimate'])

    def test_capacity_system_and_input_lineage_must_match(self):
        for changes in ({'system_id': 'other'}, {'source_lineage': {'case_sha256': 'bad', 'gis_analysis_sha256': None}},
                        {'source_lineage': {'gis_analysis_sha256': 'bad'}}, {'source_lineage': {}}):
            with self.subTest(changes=changes):
                case, gis, e, cap = setup(); bind(case, e, gis); cap.update(changes)
                self.assertEqual(run(case, gis, e, cap, rebind=False)['status'], 'blocked')

    def test_invalid_volume_does_not_become_positive_money(self):
        for value in (-1, True, float('nan'), float('inf')):
            with self.subTest(value=value):
                case, gis, e, cap = setup(); cap['components'][0]['scenarios'][0]['volume_cuft'] = value
                cap['storage_range_cuft'] = None
                self.assertEqual(run(case, gis, e, cap)['status'], 'blocked')

    def test_cross_parcel_storage_not_assigned_to_one_billing_parcel(self):
        case, gis, e, cap = setup()
        e['footprint_geometry'] = rectangle(11000)
        result = run(case, gis, e, cap)
        self.assertEqual(result['status'], 'blocked')
        self.assertIsNone(result['current_estimate'])

    def test_capacity_rainfall_exposure_must_match_garden_geometry(self):
        case, gis, e, cap = setup(); cap['components'][0]['rain_exposure_area_sqft'] = 1000
        result = run(case, gis, e, cap)
        self.assertEqual(result['status'], 'blocked')
        self.assertIn('rainfall exposure', result['reasons'][0])

    def test_storage_range_mismatch_not_silently_ignored(self):
        case, gis, e, cap = setup(); cap['storage_range_cuft'] = [1000, 2000]
        self.assertEqual(run(case, gis, e, cap)['status'], 'blocked')

    def test_capacity_without_perimeter_range_is_unavailable_not_zero(self):
        case, gis, e, cap = setup()
        cap.pop('components'); cap['storage_range_cuft'] = None
        cap['scenarios'] = [{'name': 'boundary_cell_minimum', 'status': 'estimated', 'volume_cuft': 10}]
        result = run(case, gis, e, cap)
        self.assertEqual(result['status'], 'unavailable')
        self.assertIsNone(result['current_estimate'])

    def test_unit_operation_immutable_no_network_or_routing(self):
        case, gis, e, cap = setup(); bind(case, e, gis); cap['source_lineage'] = dict(e['source_lineage'])
        before = canonical([case, gis, e, cap])
        with (patch('drainage_core.engine.analyze', side_effect=AssertionError('no routing')),
              patch('urllib.request.urlopen', side_effect=AssertionError('no network')),
              patch('stormwater.billing.calculate_scenarios', side_effect=AssertionError('one money path (D7)'))):
            result = run(case, gis, e, cap, rebind=False)
        self.assertEqual(before, canonical([case, gis, e, cap]))
        self.assertEqual(result['status'], 'storage_limited_range')


if __name__ == '__main__':
    unittest.main()
