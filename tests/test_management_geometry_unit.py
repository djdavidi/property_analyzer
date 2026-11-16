"""Invented frozen geometry/raster tests; no providers, inference or site replay."""
from copy import deepcopy
import unittest

from shapely.geometry import box, mapping, shape

from drainage_core.engine import canonical, input_hash, new_case
from drainage_core.freshness import age_policy
from drainage_core.geometry import SQFT_PER_M2
from drainage_core.management_estimates import estimate_canopy, estimate_system
from drainage_core.research import digest


def candidate(name, geometry, **properties):
    return {'id': 'ai-'+name, 'geometry': mapping(geometry), 'properties': {
        'layer': 'canopy_candidate' if name == 'canopy' else 'surface_candidate',
        'classification': name, 'source_kind': 'modeled semantic estimate',
        'source_vintage': '2025', 'source_sha256': 'a'*64, 'model_sha256': 'b'*64,
        **properties}}


def fixture(system_id='G1', system_type='Rain Garden'):
    case = new_case('Invented physical pilot', crs='EPSG:26918')
    case['parcel'] = mapping(box(0, 0, 30.48, 30.48))
    case['imagery_age_policy'] = age_policy('2026-11-15')
    case['automatic'] = {'landcover': {'prediction_sha256': 'c'*64,
        'settings': {'target_pixel_metres': .5}}}
    case['features']['features'] = [
        {'id': 'observed', 'geometry': mapping(box(0, 0, 3.048, 30.48)),
         'properties': {'layer': 'surface', 'class': 'pavement'}},
        candidate('road', box(3.048, 0, 9.144, 30.48)),
        candidate('developed_space', box(9.144, 0, 18.288, 30.48)),
        candidate('grass_shrub', box(18.288, 0, 30.48, 30.48)),
        {'id': 'footprint', 'geometry': mapping(box(0, 0, 3.048, 3.048)),
         'properties': {'layer': 'footprint', 'kind': 'system_footprint',
             'gsi_system_id': system_id, 'gsi_system_type': system_type}}]
    run = {'grid': {}, 'catchments': [{'gsi_id': system_id, 'geometry': case['parcel']}],
        'extent_sufficient': False, 'area_conservation_pass': True}
    gis = {'engine_version': 'invented-unit-output',
        'research_drainage': {'method': 'invented-frozen', 'primary': run, 'sensitivity': []}}
    return case, gis


def scenarios(result):
    return {row['id']: row for row in result['runs'][0]['area_scenarios']}


class ManagementGeometryTests(unittest.TestCase):
    def test_explicit_surface_hypotheses_never_assume_vegetation_pavement(self):
        case, gis = fixture(); result = estimate_system(case, gis, 'G1'); rows = scenarios(result)
        for key, value in [('low', 1000), ('base', 3000), ('high', 6000)]:
            self.assertAlmostEqual(rows[key]['area_sqft'], value)
        self.assertAlmostEqual(result['runs'][0]['unresolved_ground_sqft'], 9000)
        self.assertIsNone(result['runs'][0]['adequately_treated_area_sqft'])
        self.assertIsNone(result['confidence']['percentage'])

    def test_saved_semantic_ia_total_is_ignored_and_legacy_label_reinterpreted(self):
        case, gis = fixture()
        case['features']['features'][2]['properties']['classification'] = 'other_pavement'
        gis['modeled_integration'] = {'version': 'ai-drainage-integration-v1',
            'measurement': {'ia_sqft': 10000}}
        result = estimate_system(case, gis, 'G1')
        self.assertAlmostEqual(scenarios(result)['base']['area_sqft'], 3000)
        self.assertAlmostEqual(scenarios(result)['high']['area_sqft'], 6000)

    def test_pervious_observation_overrides_road_appearance(self):
        case, gis = fixture()
        case['features']['features'].append({'id': 'pervious',
            'geometry': mapping(box(3.048, 0, 9.144, 30.48)),
            'properties': {'layer': 'surface', 'class': 'pervious'}})
        rows = scenarios(estimate_system(case, gis, 'G1'))
        self.assertAlmostEqual(rows['base']['area_sqft'], 1000)
        self.assertAlmostEqual(rows['high']['area_sqft'], 4000)

    def test_stale_classes_do_not_fill_unknown_ground(self):
        case, gis = fixture()
        for f in case['features']['features']:
            if f['id'].startswith('ai-'): f['properties']['source_vintage'] = '2010'
        result = estimate_system(case, gis, 'G1')
        self.assertEqual(len(result['ai_exclusions']), 3)
        for row in scenarios(result).values(): self.assertAlmostEqual(row['area_sqft'], 1000)

    def test_off_parcel_catchment_not_counted_in_candidate_ia(self):
        case, gis = fixture()
        gis['research_drainage']['primary']['catchments'][0]['geometry'] = mapping(box(-3.048, 0, 30.48, 30.48))
        run = estimate_system(case, gis, 'G1')['runs'][0]
        self.assertAlmostEqual(run['on_parcel_area_sqft'], 10000)
        self.assertAlmostEqual(run['off_parcel_area_sqft'], 1000)
        for row in run['area_scenarios']:
            self.assertTrue(shape(case['parcel']).covers(shape(row['geometry'])))

    def test_extent_warning_retains_in_window_estimate(self):
        case, gis = fixture(); result = estimate_system(case, gis, 'G1')
        self.assertFalse(result['runs'][0]['diagnostics']['extent_sufficient'])
        self.assertAlmostEqual(scenarios(result)['high']['area_sqft'], 6000)

    def test_exact_grid_edge_and_nodata_contact_reported(self):
        case, gis = fixture()
        grid = {'origin': [0, 30.48], 'cell_size': 3.048, 'crs': case['crs'],
            'horizontal_unit': 'm', 'vertical_unit': 'm'}
        array = [[1.]*10 for _ in range(10)]; array[5][5] = None
        gis['research_drainage']['primary'].update(grid=grid, rasters={'filled_elevations': array})
        d = estimate_system(case, gis, 'G1')['runs'][0]['diagnostics']
        self.assertTrue(d['touches_grid_boundary']); self.assertTrue(d['touches_nodata'])

    def test_basin_footprint_is_not_an_inlet_or_contributing_area(self):
        case, gis = fixture('01074', 'Subsurface Basin')
        gis['research_drainage']['primary']['catchments'] = []
        result = estimate_system(case, gis, '01074')
        self.assertEqual(result['status'], 'connection_unknown'); self.assertEqual(result['runs'], [])
        self.assertAlmostEqual(result['footprint_area_sqft'], 100)
        self.assertIsNone(result['surface_storage_diagnostic']['volume_cuft'])

    def test_only_exact_in_footprint_terminal_nominates_connection(self):
        case, gis = fixture('01074', 'Subsurface Basin')
        gis['research_drainage']['primary']['catchments'] = []
        inside = mapping(box(0, 0, 9.144, 30.48)); outside = mapping(box(20, 0, 30.48, 30.48))
        gis['drainage'] = {'origin': [0, 30.48], 'cell_size': 3.048, 'crs': case['crs'],
            'horizontal_unit': 'm', 'vertical_unit': 'm', 'catchments': [
                {'outlet': 'unresolved:depression:9:0', 'geometry': inside},
                {'outlet': 'unresolved:depression:9:8', 'geometry': outside}]}
        result = estimate_system(case, gis, '01074'); run = result['runs'][0]
        self.assertEqual(result['status'], 'connection_hypothesis')
        self.assertEqual(run['connection_hypothesis_count'], 1)
        self.assertAlmostEqual(run['on_parcel_area_sqft'], 3000)
        self.assertAlmostEqual(run['within_system_footprint_sqft'], 100)
        self.assertAlmostEqual(run['outside_system_footprint_sqft'], 2900)
        self.assertAlmostEqual(scenarios(result)['base']['area_sqft'], 3000)
        self.assertIsNone(run['captured_area_sqft'])

    def test_proposed_or_false_installation_cannot_receive_an_estimate(self):
        for patch in ({'installed': False}, {'status': 'proposed'}, {'year_installed': 2030}):
            case, gis = fixture(); case['features']['features'][-1]['properties'].update(patch)
            result = estimate_system(case, gis, 'G1')
            self.assertEqual(result['status'], 'excluded'); self.assertEqual(result['runs'], [])

    def test_source_fill_depth_used_instead_of_burned_offset(self):
        case, gis = fixture()
        case['features']['features'][-1]['geometry'] = mapping(box(1, 1, 2, 2))
        raw = [[1., 1., 1.], [1., 0., 1.], [1., 1., 1.]]
        grid = {'origin': [0, 3], 'cell_size': 1, 'crs': case['crs'],
            'horizontal_unit': 'm', 'vertical_unit': 'm'}
        case['terrain'] = {**grid, 'elevations': raw}
        run = gis['research_drainage']['primary']
        run.update(grid=grid, input_dem_sha256=digest(raw), rasters={
            'fill_depth': [[0., 0., 0.], [0., 1., 0.], [0., 0., 0.]],
            'filled_elevations': [[1.]*3 for _ in range(3)],
            'conditioned_elevations': [[1., 1., 1.], [1., -90., 1.], [1., 1., 1.]]})
        storage = estimate_system(case, gis, 'G1')['surface_storage_diagnostic']
        self.assertAlmostEqual(storage['volume_cuft'], SQFT_PER_M2/.3048)
        self.assertEqual(storage['status'], 'modeled')
        self.assertIn('before burn offsets', storage['basis'])

    def test_unbound_storage_raster_does_not_establish_volume(self):
        case, gis = fixture()
        gis['research_drainage']['primary']['rasters'] = {'fill_depth': [[1.]]}
        gis['research_drainage']['primary']['grid'] = {'origin': [0, 1], 'cell_size': 1}
        storage = estimate_system(case, gis, 'G1')['surface_storage_diagnostic']
        self.assertIsNone(storage['volume_cuft'])

    def test_exact_system_id_preserves_leading_zeros(self):
        case, gis = fixture('01073')
        with self.assertRaises(ValueError): estimate_system(case, gis, '1073')

    def test_hash_mismatch_rejected_and_source_inputs_unchanged(self):
        case, gis = fixture(); gis['input_sha256'] = input_hash(case)
        before = canonical({'case': case, 'gis': gis})
        estimate_system(case, gis, 'G1')
        self.assertEqual(before, canonical({'case': case, 'gis': gis}))
        changed = deepcopy(case); changed['name'] = 'Different saved input'
        with self.assertRaisesRegex(ValueError, 'input does not match'):
            estimate_system(changed, gis, 'G1')

    def test_canopy_hidden_ground_is_only_an_explicit_upper_hypothesis(self):
        case, gis = fixture()
        case['features']['features'] = [case['features']['features'][0],
            candidate('canopy', box(0, 0, 30.48, 30.48)), case['features']['features'][-1]]
        result = estimate_canopy(case, gis)
        rows = {r['id']: r for r in result['area_scenarios']}
        self.assertAlmostEqual(result['canopy_area_sqft'], 10000)
        self.assertAlmostEqual(rows['low']['area_sqft'], 1000)
        self.assertAlmostEqual(rows['base']['area_sqft'], 1000)
        self.assertAlmostEqual(rows['high']['area_sqft'], 10000)

    def test_overlapping_class_predictions_cannot_be_counted_twice(self):
        case, gis = fixture()
        case['features']['features'].append(candidate('bare_soil', box(3.048, 0, 9.144, 30.48)))
        rows = scenarios(estimate_system(case, gis, 'G1'))
        self.assertAlmostEqual(rows['base']['area_sqft'], 1000)
        self.assertAlmostEqual(rows['high']['area_sqft'], 4000)

    def test_absent_canopy_evidence_does_not_become_zero_canopy(self):
        case, gis = fixture()
        case['features']['features'] = [case['features']['features'][0], case['features']['features'][-1]]
        result = estimate_canopy(case, gis)
        self.assertEqual(result['status'], 'unavailable')
        self.assertIsNone(result['canopy_area_sqft'])
        self.assertEqual(result['area_scenarios'], [])

    def test_original_and_ai_roof_routing_branches_remain_distinct(self):
        case, gis = fixture()
        original = deepcopy(gis['research_drainage']['primary'])
        original['name'] = 'coarser_2x'
        original['catchments'][0]['geometry'] = mapping(box(0, 0, 27.432, 30.48))
        gis['research_drainage']['sensitivity'] = [original]
        selected = deepcopy(gis['research_drainage'])
        selected['primary']['catchments'][0]['geometry'] = mapping(box(0, 0, 15.24, 30.48))
        selected['sensitivity'] = []
        gis['modeled_integration'] = {'ai_roof_drainage': selected,
            'runs': [{'name': 'nominal', 'catchments': [{'kind': 'gsi', 'receiver_id': 'G1',
                'geometry': mapping(box(0, 0, 15.24, 30.48))}]}]}
        before = canonical(gis); result = estimate_system(case, gis, 'G1')
        self.assertEqual(result['source_lineage']['research_branch'], 'saved_ai_roof_supplemented')
        self.assertEqual(len(result['runs']), 1)
        self.assertAlmostEqual(result['runs'][0]['on_parcel_area_sqft'], 5000)
        diagnostics = result['alternative_routing']
        self.assertEqual([r['name'] for r in diagnostics], ['nominal', 'coarser_2x'])
        self.assertAlmostEqual(diagnostics[0]['on_parcel_area_sqft'], 10000)
        self.assertAlmostEqual(diagnostics[1]['on_parcel_area_sqft'], 9000)
        self.assertTrue(all(r['research_branch'] == 'saved_source_roofs_only' for r in diagnostics))
        self.assertTrue(all('area_scenarios' not in r for r in diagnostics))
        self.assertEqual(before, canonical(gis))

    def test_source_only_branch_is_identified_without_duplicate_diagnostic(self):
        case, gis = fixture(); result = estimate_system(case, gis, 'G1')
        self.assertEqual(result['source_lineage']['research_branch'], 'saved_source_roofs_only')
        self.assertEqual(result['alternative_routing'], [])


if __name__ == '__main__':
    unittest.main()
