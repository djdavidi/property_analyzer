"""Invented local-spill storage units; no site replay, providers or routing."""
from copy import deepcopy
import unittest
from unittest.mock import patch

import numpy as np
from shapely.affinity import scale
from shapely.geometry import box, mapping

from drainage_core.engine import canonical, input_hash
from drainage_core.geometry import SQFT_PER_M2, projected_crs
from drainage_core.runoff_capacity import estimate_capacity


CUFT_PER_M3 = SQFT_PER_M2 / .3048


def fixture():
    elevations = [[10.]*7 for _ in range(7)]
    for row in range(2, 5):
        for col in range(2, 5):
            elevations[row][col] = 0.
    case = {'id': 'invented-capacity', 'crs': 'EPSG:26918', 'parcel': mapping(box(0, 0, 7, 7)),
        'imagery_age_policy': {'as_of': '2026-11-16'},
        'features': {'features': [{'id': 'garden', 'geometry': mapping(box(1, 1, 6, 6)),
            'properties': {'kind': 'system_footprint', 'gsi_system_id': '01073',
                           'gsi_system_type': 'Rain Garden', 'year_installed': 2024}}]},
        'terrain': {'origin': [0, 7], 'cell_size': 1., 'horizontal_unit': 'm',
            'vertical_unit': 'm', 'crs': 'EPSG:26918', 'elevations': elevations}}
    return case, {}


class RunoffCapacityUnitTests(unittest.TestCase):
    def test_known_bowl_volume_uses_local_spill_and_explicit_rain_area(self):
        case, gis = fixture()
        result = estimate_capacity(case, gis, '01073')
        self.assertEqual(result['status'], 'estimated')
        self.assertAlmostEqual(result['surface_storage_volume_cuft'], 90*CUFT_PER_M3)
        self.assertAlmostEqual(result['wetted_area_sqft'], 9*SQFT_PER_M2)
        self.assertAlmostEqual(result['rain_exposure_area_sqft'], 25*SQFT_PER_M2)
        self.assertEqual(result['scenarios'][0]['component_spill_elevations_m'], [10.])
        self.assertTrue(all(row['rain_exposure_area_sqft'] == result['footprint_area_sqft'] for row in result['scenarios']))
        self.assertNotIn('managed_area_sqft', result)

    def test_frozen_burn_or_regional_fill_does_not_set_storage_depth(self):
        case, gis = fixture()
        gis['research_drainage'] = {'primary': {'rasters': {'fill_depth': [[1000]*7]*7,
            'conditioned_elevations': [[-1000]*7]*7}}}
        result = estimate_capacity(case, gis, '01073')
        self.assertAlmostEqual(result['surface_storage_volume_cuft'], 90*CUFT_PER_M3)

    def test_low_spill_lowers_capacity_without_quantile_or_median_substitution(self):
        case, gis = fixture()
        case['terrain']['elevations'][1][3] = 2.
        result = estimate_capacity(case, gis, '01073')
        self.assertEqual(result['scenarios'][0]['component_spill_elevations_m'], [2.])
        self.assertAlmostEqual(result['surface_storage_volume_cuft'], 18*CUFT_PER_M3)

    def test_flat_covered_terrain_is_zero_modeled_surface_storage_not_missing(self):
        case, gis = fixture()
        case['terrain']['elevations'] = [[10.]*7 for _ in range(7)]
        result = estimate_capacity(case, gis, '01073')
        self.assertEqual(result['status'], 'estimated')
        self.assertEqual(result['surface_storage_volume_cuft'], 0.)

    def test_nodata_inside_facility_does_not_become_zero_capacity(self):
        case, gis = fixture()
        case['terrain']['elevations'][3][3] = None
        result = estimate_capacity(case, gis, '01073')
        self.assertEqual(result['status'], 'unavailable')
        self.assertIsNone(result['surface_storage_volume_cuft'])

    def test_footprint_beyond_grid_has_unknown_capacity(self):
        case, gis = fixture()
        case['features']['features'][0]['geometry'] = mapping(box(-1, 1, 6, 6))
        result = estimate_capacity(case, gis, '01073')
        self.assertEqual(result['status'], 'unavailable')
        self.assertIsNone(result['surface_storage_volume_cuft'])

    def test_missing_or_unverified_vertical_units_are_unknown(self):
        case, gis = fixture()
        case['terrain']['vertical_unit'] = None
        self.assertIsNone(estimate_capacity(case, gis, '01073')['surface_storage_volume_cuft'])
        case.pop('terrain')
        self.assertIsNone(estimate_capacity(case, gis, '01073')['surface_storage_volume_cuft'])

    def test_vertical_foot_values_equal_metre_volume(self):
        case, gis = fixture()
        feet = deepcopy(case)
        feet['terrain']['vertical_unit'] = 'ft'
        feet['terrain']['elevations'] = (np.asarray(feet['terrain']['elevations'])/.3048).tolist()
        self.assertAlmostEqual(estimate_capacity(case, gis, '01073')['surface_storage_volume_cuft'],
            estimate_capacity(feet, gis, '01073')['surface_storage_volume_cuft'])

    def test_native_horizontal_feet_match_metre_geometry_and_volume(self):
        case, gis = fixture()
        feet = deepcopy(case)
        factor = projected_crs('EPSG:2272').axis_info[0].unit_conversion_factor
        feet['crs'] = feet['terrain']['crs'] = 'EPSG:2272'
        feet['terrain'].update(horizontal_unit='us-ft', cell_size=1/factor, origin=[0, 7/factor])
        feet['parcel'] = mapping(scale(box(0, 0, 7, 7), xfact=1/factor, yfact=1/factor, origin=(0, 0)))
        feet['features']['features'][0]['geometry'] = mapping(scale(box(1, 1, 6, 6), xfact=1/factor, yfact=1/factor, origin=(0, 0)))
        first = estimate_capacity(case, gis, '01073')
        second = estimate_capacity(feet, gis, '01073')
        self.assertAlmostEqual(first['surface_storage_volume_cuft'], second['surface_storage_volume_cuft'])
        self.assertAlmostEqual(first['footprint_area_sqft'], second['footprint_area_sqft'])

    def test_conflicting_horizontal_units_cannot_produce_a_volume(self):
        case, gis = fixture()
        case['terrain']['horizontal_unit'] = 'ft'
        result = estimate_capacity(case, gis, '01073')
        self.assertEqual(result['status'], 'unavailable')
        self.assertIsNone(result['surface_storage_volume_cuft'])

    def test_disconnected_components_have_distinct_local_spills_not_global_minimum(self):
        case, gis = fixture()
        array = np.full((7, 13), 10.)
        array[:, 7:] = 20.
        array[2:5, 2:5] = 0.
        array[2:5, 8:11] = 0.
        case['terrain']['elevations'] = array.tolist()
        case['parcel'] = mapping(box(0, 0, 13, 7))
        case['features']['features'][0]['geometry'] = mapping(box(1, 1, 6, 6).union(box(7, 1, 12, 6)))
        result = estimate_capacity(case, gis, '01073')
        self.assertEqual(len(result['components']), 2)
        self.assertEqual(sorted(result['scenarios'][0]['component_spill_elevations_m']), [10., 20.])
        self.assertAlmostEqual(result['surface_storage_volume_cuft'], 270*CUFT_PER_M3)

    def test_overlapping_duplicate_footprints_not_double_counted(self):
        case, gis = fixture()
        duplicate = deepcopy(case['features']['features'][0]); duplicate['id'] = 'duplicate'
        case['features']['features'].append(duplicate)
        result = estimate_capacity(case, gis, '01073')
        self.assertAlmostEqual(result['surface_storage_volume_cuft'], 90*CUFT_PER_M3)

    def test_underground_or_proposed_record_is_not_surface_storage_estimate(self):
        case, gis = fixture()
        case['features']['features'][0]['properties']['gsi_system_type'] = 'Subsurface Basin'
        self.assertIsNone(estimate_capacity(case, gis, '01073')['surface_storage_volume_cuft'])
        case['features']['features'][0]['properties'].update(gsi_system_type='Rain Garden', status='proposed')
        self.assertEqual(estimate_capacity(case, gis, '01073')['status'], 'excluded')

    def test_invalid_grid_parameters_rejected(self):
        for value in (0, -1, True, float('nan'), float('inf')):
            case, gis = fixture(); case['terrain']['cell_size'] = value
            with self.subTest(value=value), self.assertRaises(ValueError):
                estimate_capacity(case, gis, '01073')

    def test_inputs_immutable_and_no_acquisition_or_rerouting(self):
        case, gis = fixture(); gis['input_sha256'] = input_hash(case)
        before = canonical([case, gis])
        with (patch('drainage_core.engine.analyze', side_effect=AssertionError('no routing')),
              patch('urllib.request.urlopen', side_effect=AssertionError('no network'))):
            result = estimate_capacity(case, gis, '01073')
        self.assertEqual(result['status'], 'estimated')
        self.assertEqual(canonical([case, gis]), before)
        gis['input_sha256'] = '0'*64
        with self.assertRaisesRegex(ValueError, 'does not match'):
            estimate_capacity(case, gis, '01073')


if __name__ == '__main__':
    unittest.main()
