"""Invented unit inputs only: no real-site replay, requests or browser checks."""
from copy import deepcopy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from shapely.geometry import box, mapping

from drainage_core.engine import canonical
from drainage_core.surface_estimates import estimate_surfaces
from stormwater.management_pilot import (_ground_constraint, _weighted_engineering,
    estimate_property, run_saved)
from tests.test_management_geometry_unit import fixture, candidate


def pilot_fixture():
    case, gis = fixture('62571')
    case['id'] = 'pwd-98627'
    case['baseline'] = {'ga_sqft': 10000, 'ia_sqft': 5000,
        'bill_date': '2026-11-16', 'existing_ga_credit_sqft': 0,
        'existing_ia_credit_sqft': 0, 'existing_iar_sqft': 0,
        'accounts': [{'allocation': 1, 'discount_factor': 1}],
        'actual_bill_verified': False, 'npdes_fraction': 0}
    # Replace an area of developed appearance with canopy (disjoint classes).
    case['features']['features'][2] = candidate('developed_space', box(12.192, 0, 18.288, 30.48))
    case['features']['features'].append(candidate('canopy', box(9.144, 0, 12.192, 30.48)))
    return case, gis


class ManagementPilotUnitTests(unittest.TestCase):
    def test_billing_constraint_is_explicit_and_not_an_appeal_measurement(self):
        case, gis = pilot_fixture()
        result = estimate_property(case, gis, ['62571'])
        self.assertTrue(result['ground_constraint']['compatible_with_recorded_ia'])
        self.assertEqual(result['impervious_area']['annual_savings_estimate'], 0)
        self.assertEqual(result['impervious_area']['status'], 'no_supported_reduction_identified')
        self.assertFalse(result['impervious_area']['actual_available_savings_verified'])
        self.assertEqual(result['canopy']['uncertainty']['status'], 'not_calibrated')
        self.assertNotIn('confidence', result['canopy'])
        self.assertNotIn('complete', result['impervious_area'])

    def test_known_pilot_properties_no_longer_receive_invented_percentages(self):
        def assert_no_numeric_confidence(value):
            if isinstance(value, dict):
                for key, item in value.items():
                    if key in ('confidence_pct', 'confidence_percentage', 'percentage'):
                        self.assertIsNone(item)
                    assert_no_numeric_confidence(item)
            elif isinstance(value, list):
                for item in value:
                    assert_no_numeric_confidence(item)
        for identifier in ('pwd-98627', 'pwd-538963'):
            with self.subTest(identifier=identifier):
                case, gis = pilot_fixture()
                case['id'] = identifier
                result = estimate_property(case, gis, ['62571'])
                assert_no_numeric_confidence(result)
                self.assertNotIn('confidence', result['canopy'])
                self.assertNotIn('confidence', result['impervious_area'])
                self.assertNotIn('confidence', result['systems'][0]['policy'])
                self.assertEqual(result['systems'][0]['policy']['uncertainty']['status'], 'not_calibrated')

    def test_weighted_whole_parcel_matches_prior_and_keeps_physical_original(self):
        case, gis = pilot_fixture()
        result = estimate_property(case, gis, ['62571'])
        system = result['systems'][0]
        estimate = system['policy']['current_estimate']
        self.assertAlmostEqual(estimate['candidate_ia_sqft'], case['baseline']['ia_sqft'], places=5)
        self.assertTrue(estimate['fractional_ia_is_assumed'])
        self.assertFalse(any('weighted_components' in s for s in system['physical']['runs'][0]['area_scenarios']))
        self.assertIsNone(system['policy']['captured_ia_sqft'])
        self.assertTrue(result['do_not_sum'])

    def test_inputs_immutable_and_policy_does_not_route_infer_or_acquire(self):
        case, gis = pilot_fixture()
        before = canonical([case, gis])
        with (patch('drainage_core.engine.analyze', side_effect=AssertionError('no routing')),
              patch('urllib.request.urlopen', side_effect=AssertionError('no network'))):
            result = estimate_property(case, gis, ['62571'])
        self.assertEqual(before, canonical([case, gis]))
        self.assertIsNotNone(result['canopy']['annual_savings_estimate'])

    def test_incompatible_prior_does_not_silently_price_clipped_best_canopy(self):
        case, gis = pilot_fixture()
        case['baseline']['ia_sqft'] = 500
        result = estimate_property(case, gis, ['62571'])
        self.assertFalse(result['ground_constraint']['compatible_with_recorded_ia'])
        self.assertIsNone(result['canopy']['annual_savings_estimate'])
        self.assertIsNone(result['ground_constraint']['canopy_ground_ia_estimate_sqft'])

    def test_missing_semantics_cannot_become_zero_canopy(self):
        case, gis = pilot_fixture()
        case['features']['features'] = [f for f in case['features']['features'] if not f['id'].startswith('ai-')]
        with self.assertRaisesRegex(ValueError, 'missing imagery is not zero canopy'):
            estimate_property(case, gis, ['62571'])

    def test_invalid_historical_gis_is_not_reused(self):
        case, gis = pilot_fixture()
        gis['engine_version'] = 'gis-engine-v4'
        with self.assertRaisesRegex(ValueError, 'Historical or invalidated GIS'):
            estimate_property(case, gis, ['62571'])

    def test_known_failed_canopy_prerequisite_cannot_be_assumed_away(self):
        case, gis = pilot_fixture()
        case['assessment'] = {'records': [{'category': 'canopy', 'facts': {'ground_impervious_overlap_confirmed': False}}]}
        result = estimate_property(case, gis, ['62571'])
        self.assertIsNone(result['canopy']['annual_savings_estimate'])

    def test_saved_adapter_reads_and_preserves_exact_bytes(self):
        case, gis = pilot_fixture()
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / 'input'
            root.mkdir()
            for name, value in [('case', case), ('gis-analysis', gis)]:
                (root / (name + '.json')).write_text(json.dumps(value, indent=2))
            before = {p.name: p.read_bytes() for p in root.iterdir()}
            result = run_saved([(root, ['62571'])], Path(temporary) / 'output')
            self.assertEqual(before, {p.name: p.read_bytes() for p in root.iterdir()})
            self.assertEqual(len(result['input_manifest']), 2)
            self.assertEqual(result['properties'][0]['systems'][0]['policy']['system_id'], '62571')
            self.assertEqual(result['version'], 'saved-three-system-pilot-v3')
            self.assertNotIn('confidence_meaning', result)

    def test_01073_primary_savings_follow_storage_not_the_old_full_area_price(self):
        case, gis = pilot_fixture()
        for f in case['features']['features']:
            if f['properties'].get('kind') == 'system_footprint':
                f['properties']['gsi_system_id'] = '01073'
        gis['research_drainage']['primary']['catchments'][0]['gsi_id'] = '01073'
        capacity = {'system_id': '01073', 'status': 'estimated',
            'surface_storage_volume_cuft': 10, 'source_lineage': {},
            'scenarios': [{'name': 'boundary_cell_minimum', 'status': 'estimated', 'volume_cuft': 10}]}
        with patch('drainage_core.runoff_capacity.estimate_capacity', return_value=capacity):
            system = estimate_property(case, gis, ['01073'])['systems'][0]
        self.assertEqual(system['policy']['current_estimate']['annual_savings'], 0)
        self.assertGreater(system['full_area_management_scenario']['current_estimate']['annual_savings'], 0)
        self.assertFalse(system['full_area_management_scenario']['usable_for_current_savings'])
        self.assertEqual(system['policy']['basis'], 'storage_limited_management_estimate')
        self.assertIsNone(system['managed_runoff']['verified_managed_area_sqft'])

    def test_01073_unknown_capacity_withholds_primary_price(self):
        case, gis = pilot_fixture()
        for f in case['features']['features']:
            if f['properties'].get('kind') == 'system_footprint':
                f['properties']['gsi_system_id'] = '01073'
        gis['research_drainage']['primary']['catchments'][0]['gsi_id'] = '01073'
        with patch('drainage_core.runoff_capacity.estimate_capacity', return_value={
                'system_id': '01073', 'status': 'unavailable', 'surface_storage_volume_cuft': None}):
            system = estimate_property(case, gis, ['01073'])['systems'][0]
        self.assertIsNone(system['policy']['current_estimate'])
        self.assertIsNotNone(system['full_area_management_scenario']['current_estimate'])


if __name__ == '__main__':
    unittest.main()
