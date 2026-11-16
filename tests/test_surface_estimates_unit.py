"""Invented image-cover geometry only; no inference, routing or site replay."""
from copy import deepcopy
import unittest

from shapely.affinity import scale
from shapely.geometry import box, mapping, shape

from drainage_core.engine import canonical, input_hash, new_case
from drainage_core.freshness import age_policy
from drainage_core.geometry import SQFT_PER_M2, projected_crs
from drainage_core.surface_estimates import estimate_surfaces


def semantic(name, geometry):
    return {'id': 'semantic-'+name, 'geometry': mapping(geometry), 'properties': {
        'layer': 'canopy_candidate' if name == 'canopy' else 'surface_candidate',
        'classification': name, 'source_kind': 'modeled semantic estimate',
        'source_vintage': '2025', 'source_sha256': 'a'*64, 'model_sha256': 'b'*64}}


def fixture():
    case = new_case('Invented contextual surface cover', crs='EPSG:26918')
    case['parcel'] = mapping(box(0, 0, 30, 30))
    case['imagery_age_policy'] = age_policy('2026-11-15')
    case['features']['features'] = [semantic('canopy', box(10, 10, 20, 20)),
        semantic('road', box(10, 8, 12, 10)),
        semantic('developed_space', box(12, 8, 14, 10)),
        semantic('grass_shrub', box(14, 8, 16, 10))]
    return case, {'engine_version': 'invented-unit-only'}


def observed(id, kind, geometry):
    return {'id': id, 'geometry': mapping(geometry),
        'properties': {'layer': 'surface', 'class': kind}}


class SurfaceEstimatesUnitTests(unittest.TestCase):
    def test_unclassified_ring_stays_in_denominator(self):
        case, gis = fixture(); result = estimate_surfaces(case, gis, (2,))
        context = result['canopy']['contexts'][0]
        crown = box(10, 10, 20, 20); ring = crown.buffer(2).difference(crown)
        self.assertAlmostEqual(context['visible_context_coverage_fraction'], 12/ring.area)
        self.assertAlmostEqual(context['road_context_under_canopy_sqft'], 100*4/ring.area*SQFT_PER_M2)
        self.assertAlmostEqual(context['developed_context_under_canopy_sqft'], 100*4/ring.area*SQFT_PER_M2)
        self.assertAlmostEqual(context['unclassified_context_under_canopy_sqft'],
            100*(1-12/ring.area)*SQFT_PER_M2)
        self.assertLess(context['visible_context_coverage_fraction'], .15)
        self.assertGreater(context['unclassified_context_under_canopy_sqft'], 80*SQFT_PER_M2)

    def test_known_roof_and_known_ground_ia_not_counted_as_hidden_canopy_ground(self):
        case, gis = fixture(); case['parcel'] = mapping(box(0, 0, 10, 10))
        case['features']['features'] = [
            observed('roof', 'roof', box(0, 0, 2, 10)),
            observed('pavement', 'pavement', box(2, 0, 3, 10)),
            semantic('canopy', box(0, 0, 5, 10)),
            semantic('road', box(5, 0, 6, 10)),
            semantic('developed_space', box(6, 0, 8, 10)),
            semantic('grass_shrub', box(8, 0, 10, 10))]
        result = estimate_surfaces(case, gis, (2,)); canopy = result['canopy']
        self.assertAlmostEqual(result['roof_and_observed_ia_sqft'], 30*SQFT_PER_M2)
        self.assertAlmostEqual(canopy['observed_ground_ia_overlap_sqft'], 10*SQFT_PER_M2)
        self.assertAlmostEqual(canopy['hidden_ground_sqft'], 20*SQFT_PER_M2)
        self.assertAlmostEqual(canopy['range_sqft'][0], 10*SQFT_PER_M2)
        self.assertAlmostEqual(canopy['range_sqft'][1], 30*SQFT_PER_M2)
        self.assertAlmostEqual(shape(canopy['geometry']).intersection(box(0, 0, 2, 10)).area, 0)
        self.assertAlmostEqual(sum(result[k] for k in ('roof_and_observed_ia_sqft',
            'road_appearance_sqft', 'developed_appearance_sqft', 'soft_appearance_sqft',
            'unclassified_ground_sqft'))+canopy['hidden_ground_sqft'], result['parcel_area_sqft'])

    def test_known_pervious_under_canopy_remains_in_disjoint_area_accounting(self):
        case, gis = fixture(); case['parcel'] = mapping(box(0, 0, 10, 10))
        case['features']['features'] = [
            observed('pervious', 'pervious', box(0, 0, 2, 10)),
            semantic('canopy', box(0, 0, 4, 10)),
            semantic('road', box(4, 0, 6, 10)),
            semantic('developed_space', box(6, 0, 8, 10)),
            semantic('grass_shrub', box(8, 0, 10, 10))]
        result = estimate_surfaces(case, gis, (2,))
        self.assertAlmostEqual(result['canopy']['hidden_ground_sqft'], 20*SQFT_PER_M2)
        self.assertAlmostEqual(result['observed_pervious_sqft'], 20*SQFT_PER_M2)
        self.assertAlmostEqual(sum(result[k] for k in ('roof_and_observed_ia_sqft',
            'observed_pervious_sqft', 'road_appearance_sqft', 'developed_appearance_sqft',
            'soft_appearance_sqft', 'unclassified_ground_sqft'))+result['canopy']['hidden_ground_sqft'],
            result['parcel_area_sqft'])

    def test_buffer_distances_are_metres_in_both_native_unit_systems(self):
        case, gis = fixture(); feet = deepcopy(case); feet['crs'] = 'EPSG:2272'
        factor = projected_crs(feet['crs']).axis_info[0].unit_conversion_factor
        feet['parcel'] = mapping(scale(shape(feet['parcel']), xfact=1/factor, yfact=1/factor, origin=(0, 0)))
        for feature in feet['features']['features']:
            feature['geometry'] = mapping(scale(shape(feature['geometry']),
                xfact=1/factor, yfact=1/factor, origin=(0, 0)))
        metres = estimate_surfaces(case, gis, (2, 5, 10))
        converted = estimate_surfaces(feet, gis, (2, 5, 10))
        self.assertAlmostEqual(metres['canopy']['hidden_ground_sqft'], converted['canopy']['hidden_ground_sqft'])
        for first, second in zip(metres['canopy']['contexts'], converted['canopy']['contexts']):
            for key in ('road_context_under_canopy_sqft', 'developed_context_under_canopy_sqft',
                'unclassified_context_under_canopy_sqft', 'visible_context_coverage_fraction'):
                self.assertAlmostEqual(first[key], second[key])

    def test_distances_are_sensitivity_not_new_impervious_observations(self):
        case, gis = fixture(); result = estimate_surfaces(case, gis, (1, 2, 5))
        contexts = result['canopy']['contexts']
        self.assertEqual([c['distance_metres'] for c in contexts], [1, 2, 5])
        self.assertNotAlmostEqual(contexts[0]['road_context_under_canopy_sqft'],
            contexts[-1]['road_context_under_canopy_sqft'])
        self.assertEqual(result['roof_and_observed_ia_sqft'], 0)
        self.assertEqual(result['canopy']['observed_ground_ia_overlap_sqft'], 0)
        self.assertIsNone(result['confidence']['percentage'])

    def test_invalid_distances_are_rejected(self):
        case, gis = fixture()
        for value in (True, False, 0, -1, float('inf'), float('-inf'), float('nan'), '2', None):
            with self.subTest(value=value):
                with self.assertRaisesRegex(ValueError, 'finite positive metres'):
                    estimate_surfaces(case, gis, (value,))

    def test_no_visible_ring_keeps_all_hidden_area_unsupported(self):
        case, gis = fixture(); case['parcel'] = mapping(box(10, 10, 20, 20))
        case['features']['features'] = [semantic('canopy', box(10, 10, 20, 20))]
        context = estimate_surfaces(case, gis, (5,))['canopy']['contexts'][0]
        self.assertEqual(context['visible_context_coverage_fraction'], 0)
        self.assertAlmostEqual(context['no_visible_ground_context_sqft'], 100*SQFT_PER_M2)
        self.assertAlmostEqual(context['unclassified_context_under_canopy_sqft'], 100*SQFT_PER_M2)
        self.assertEqual(context['road_context_under_canopy_sqft'], 0)

    def test_stale_semantic_cover_not_used_and_source_inputs_immutable(self):
        case, gis = fixture()
        for feature in case['features']['features']:
            feature['properties']['source_vintage'] = '2010'
        gis['input_sha256'] = input_hash(case)
        before = canonical({'case': case, 'gis': gis})
        with self.assertRaisesRegex(ValueError, 'missing imagery is not zero canopy'):
            estimate_surfaces(case, gis)
        self.assertEqual(before, canonical({'case': case, 'gis': gis}))

    def test_observed_pavement_remains_available_as_visible_ring_evidence(self):
        case, gis = fixture()
        case['features']['features'] = [semantic('canopy', box(10, 10, 20, 20)),
            observed('pavement', 'pavement', box(10, 8, 12, 10))]
        context = estimate_surfaces(case, gis, (2,))['canopy']['contexts'][0]
        ring_area = box(10, 10, 20, 20).buffer(2).difference(box(10, 10, 20, 20)).area
        self.assertAlmostEqual(context['visible_context_coverage_fraction'], 4/ring_area)
        self.assertAlmostEqual(context['road_context_under_canopy_sqft'], 100*4/ring_area*SQFT_PER_M2)

    def test_context_shares_reconcile_to_hidden_crown_area_including_soft_share(self):
        # Review r6: the 2 m ring holds 4 m2 each of road, developed and grass.
        case, gis = fixture(); result = estimate_surfaces(case, gis, (2, 5))
        ring_area = box(10, 10, 20, 20).buffer(2).difference(box(10, 10, 20, 20)).area
        context = result['canopy']['contexts'][0]
        self.assertAlmostEqual(context['soft_context_under_canopy_sqft'], 100*4/ring_area*SQFT_PER_M2)
        for context in result['canopy']['contexts']:
            with self.subTest(distance=context['distance_metres']):
                self.assertAlmostEqual(sum(context[k] for k in ('road_context_under_canopy_sqft',
                    'developed_context_under_canopy_sqft', 'soft_context_under_canopy_sqft',
                    'unclassified_context_under_canopy_sqft')), result['canopy']['hidden_ground_sqft'])

    def test_observed_canopy_is_included_and_reported_separately_from_model(self):
        # Observed crown box(0, 20, 10, 30) over ground the image left unclassified
        # conceals it (100 m2). The part over modeled road (box(10, 8, 12, 10)) was
        # visible ground in the image and is not hidden (4 m2).
        case, gis = fixture()
        before = estimate_surfaces(case, gis, (2,))
        case['features']['features'].append({'id': 'observed-canopy', 'geometry': mapping(box(0, 20, 10, 30)),
            'properties': {'layer': 'canopy'}})
        case['features']['features'].append({'id': 'observed-canopy-road', 'geometry': mapping(box(10, 8, 12, 10)),
            'properties': {'layer': 'canopy'}})
        result = estimate_surfaces(case, gis, (2,)); canopy = result['canopy']
        self.assertAlmostEqual(canopy['observed_crown_sqft'], 104*SQFT_PER_M2)
        self.assertAlmostEqual(canopy['model_crown_sqft'], 100*SQFT_PER_M2)
        self.assertAlmostEqual(canopy['visible_crown_sqft'], 204*SQFT_PER_M2)
        self.assertAlmostEqual(canopy['observed_only_crown_sqft'], 104*SQFT_PER_M2)
        self.assertAlmostEqual(canopy['observed_crown_over_visible_ground_sqft'], 4*SQFT_PER_M2)
        self.assertAlmostEqual(canopy['hidden_ground_sqft'], before['canopy']['hidden_ground_sqft'] + 100*SQFT_PER_M2)
        self.assertAlmostEqual(result['road_appearance_sqft'], before['road_appearance_sqft'])
        self.assertAlmostEqual(sum(result[k] for k in ('roof_and_observed_ia_sqft', 'observed_pervious_sqft',
            'road_appearance_sqft', 'developed_appearance_sqft', 'soft_appearance_sqft', 'unclassified_ground_sqft'))
            + canopy['hidden_ground_sqft'], result['parcel_area_sqft'])
        for context in canopy['contexts']:
            self.assertAlmostEqual(sum(context[k] for k in ('road_context_under_canopy_sqft',
                'developed_context_under_canopy_sqft', 'soft_context_under_canopy_sqft',
                'unclassified_context_under_canopy_sqft')), canopy['hidden_ground_sqft'])

    def test_observed_pervious_overrides_ai_roof_in_context(self):
        case, gis = fixture()
        case['features']['features'] = [semantic('canopy', box(10, 10, 20, 20)),
            semantic('roof', box(10, 8, 14, 10)),
            observed('pervious', 'pervious', box(10, 8, 14, 10))]
        context = estimate_surfaces(case, gis, (2,))['canopy']['contexts'][0]
        ring_area = box(10, 10, 20, 20).buffer(2).difference(box(10, 10, 20, 20)).area
        self.assertAlmostEqual(context['visible_context_coverage_fraction'], 8/ring_area)
        self.assertAlmostEqual(context['unclassified_context_under_canopy_sqft'], 100*(1-8/ring_area)*SQFT_PER_M2)


if __name__ == '__main__':
    unittest.main()
