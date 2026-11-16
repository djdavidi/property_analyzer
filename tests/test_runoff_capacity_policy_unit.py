"""Invented static-event budgets and PWD ledger unit tests; no site replay."""
from copy import deepcopy
import unittest
from unittest.mock import patch

from drainage_core.engine import canonical
from stormwater.runoff_capacity import estimate_capacity_management
from tests.test_management_estimates import fixture, rectangle, add_existing, add_weighted_base


def setup():
    case, gis, engineering = fixture()
    engineering['footprint_geometry'] = rectangle(500)
    engineering['runs'][0]['on_parcel_geometry'] = rectangle(3000)
    source = engineering['runs'][0]['area_scenarios'][1]
    source.update(area_sqft=2000, geometry=rectangle(2000))
    capacity = {'system_id': '62571', 'status': 'estimated',
        'surface_storage_volume_cuft': 187.5, 'source_lineage': {},
        'scenarios': [{'name': 'boundary_cell_minimum', 'status': 'estimated', 'volume_cuft': 187.5},
                      {'name': 'bilinear_perimeter', 'status': 'estimated', 'volume_cuft': 500}]}
    return case, gis, engineering, capacity


def run(case, gis, engineering, capacity):
    return estimate_capacity_management(case, gis, engineering, capacity, '2026-11-16')


class RunoffCapacityPolicyUnitTests(unittest.TestCase):
    def test_reserve_rain_exclude_system_bed_and_price_only_managed_equivalent(self):
        case, gis, e, cap = setup()
        result = run(case, gis, e, cap); best = result['current_estimate']
        self.assertEqual(result['status'], 'storage_limited_estimate')
        self.assertAlmostEqual(best['garden_ia_excluded_sqft'], 500)
        self.assertAlmostEqual(best['external_contributing_ia_sqft'], 1500)
        self.assertAlmostEqual(best['direct_garden_rainfall_cuft'], 62.5)
        self.assertAlmostEqual(best['available_storage_for_external_runoff_cuft'], 125)
        self.assertAlmostEqual(best['estimated_managed_ia_equivalent_sqft'], 1000)
        self.assertAlmostEqual(best['estimated_managed_runoff_volume_cuft'], 125)
        self.assertAlmostEqual(best['unaccommodated_external_ia_runoff_cuft'], 62.5)
        self.assertEqual(best['annual_savings'], 96.60)
        self.assertIsNone(result['verified_managed_area_sqft'])

    def test_cannot_allocate_more_than_external_contribution(self):
        case, gis, e, cap = setup(); cap['surface_storage_volume_cuft'] = 100000
        cap['scenarios'][0]['volume_cuft'] = 100000
        best = run(case, gis, e, cap)['current_estimate']
        self.assertAlmostEqual(best['estimated_managed_ia_equivalent_sqft'], 1500)
        self.assertAlmostEqual(best['estimated_managed_runoff_volume_cuft'], 187.5)

    def test_known_zero_residual_storage_is_a_zero_scenario(self):
        case, gis, e, cap = setup(); cap['surface_storage_volume_cuft'] = 50
        cap['scenarios'][0]['volume_cuft'] = 50
        best = run(case, gis, e, cap)['current_estimate']
        self.assertEqual(best['status'], 'calculated')
        self.assertEqual(best['estimated_managed_ia_equivalent_sqft'], 0)
        self.assertEqual(best['annual_savings'], 0)

    def test_missing_capacity_does_not_fall_back_to_unlimited_credit_or_zero(self):
        case, gis, e, cap = setup(); cap.update(status='unavailable', surface_storage_volume_cuft=None)
        result = run(case, gis, e, cap)
        self.assertEqual(result['status'], 'unavailable')
        self.assertIsNone(result['current_estimate'])
        self.assertIsNone(result['range'])

    def test_other_ground_runoff_load_sensitivity_is_distinct_from_best(self):
        case, gis, e, cap = setup()
        result = run(case, gis, e, cap)
        rows = result['runs'][0]['scenarios']
        best, wet = rows[0], rows[1]
        self.assertAlmostEqual(best['other_ground_area_sqft'], 1000)
        self.assertAlmostEqual(wet['other_ground_runoff_cuft'], 125)
        self.assertAlmostEqual(wet['estimated_managed_ia_equivalent_sqft'], 0)
        self.assertEqual(result['current_estimate']['additional_soft_ground_runoff_fraction'], 0)
        self.assertIn('not a confidence interval', result['range']['basis'])

    def test_fractional_candidate_scaled_without_fabricating_a_specific_subarea(self):
        case, gis, e, cap = setup(); add_weighted_base(e)
        e['runs'][0]['area_scenarios'][1]['area_sqft'] = 1000
        cap['surface_storage_volume_cuft'] = 100; cap['scenarios'][0]['volume_cuft'] = 100
        result = run(case, gis, e, cap); best = result['current_estimate']
        self.assertAlmostEqual(best['external_contributing_ia_sqft'], 500)
        self.assertAlmostEqual(best['estimated_managed_ia_equivalent_sqft'], 300)
        components = best['priced']['weighted_components']
        self.assertEqual(len(components), 1)
        self.assertAlmostEqual(components[0]['impervious_fraction'], .12)
        self.assertTrue(best['priced']['fractional_ia_is_assumed'])

    def test_existing_allocations_overlap_possible_geometry_still_blocks(self):
        case, gis, e, cap = setup(); add_existing(case, gis)
        result = run(case, gis, e, cap)
        self.assertEqual(result['status'], 'blocked')
        self.assertIsNone(result['current_estimate']['annual_savings'])
        self.assertTrue(any('overlap' in reason.lower() for reason in result['reasons']))

    def test_bad_original_scalar_not_hidden_by_area_recomputation(self):
        case, gis, e, cap = setup(); e['runs'][0]['area_scenarios'][1]['area_sqft'] = 9999
        result = run(case, gis, e, cap)
        self.assertEqual(result['status'], 'blocked')
        self.assertIsNone(result['current_estimate'])

    def test_known_failed_treatment_not_assumed_true_by_capacity(self):
        case, gis, e, cap = setup()
        case['assessment']['records'] = [{'id': 'failed', 'system_id': '62571',
            'facts': {'treatment_depth_inches': .5}}]
        result = run(case, gis, e, cap)
        self.assertEqual(result['status'], 'blocked')
        self.assertIsNone(result['current_estimate']['annual_savings'])

    def test_capacity_system_and_input_lineage_must_match(self):
        for changes in ({'system_id': 'other'}, {'source_lineage': {'case_sha256': 'bad'}},
                        {'source_lineage': {'gis_analysis_sha256': 'bad'}}):
            with self.subTest(changes=changes):
                case, gis, e, cap = setup(); cap.update(changes)
                self.assertEqual(run(case, gis, e, cap)['status'], 'blocked')

    def test_invalid_volume_does_not_become_positive_money(self):
        for value in (-1, True, float('nan'), float('inf')):
            with self.subTest(value=value):
                case, gis, e, cap = setup(); cap['scenarios'][0]['volume_cuft'] = value
                self.assertEqual(run(case, gis, e, cap)['status'], 'blocked')

    def test_cross_parcel_storage_not_assigned_to_one_billing_parcel(self):
        case, gis, e, cap = setup()
        e['footprint_geometry'] = rectangle(11000)
        result = run(case, gis, e, cap)
        self.assertEqual(result['status'], 'blocked')
        self.assertIsNone(result['current_estimate'])

    def test_capacity_rainfall_exposure_must_match_garden_geometry(self):
        case, gis, e, cap = setup(); cap['rain_exposure_area_sqft'] = 1000
        result = run(case, gis, e, cap)
        self.assertEqual(result['status'], 'blocked')
        self.assertIn('rainfall exposure', result['reasons'][0])

    def test_primary_storage_mismatch_not_silently_ignored(self):
        case, gis, e, cap = setup(); cap['surface_storage_volume_cuft'] = 1000
        self.assertEqual(run(case, gis, e, cap)['status'], 'blocked')

    def test_unit_operation_immutable_no_network_or_routing(self):
        case, gis, e, cap = setup(); before = canonical([case, gis, e, cap])
        with (patch('drainage_core.engine.analyze', side_effect=AssertionError('no routing')),
              patch('urllib.request.urlopen', side_effect=AssertionError('no network'))):
            result = run(case, gis, e, cap)
        self.assertEqual(before, canonical([case, gis, e, cap]))
        self.assertEqual(result['status'], 'storage_limited_estimate')


if __name__ == '__main__':
    unittest.main()
