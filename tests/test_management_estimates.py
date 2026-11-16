"""Unit-only management price hypotheses; none validates a real installation."""
from copy import deepcopy
import unittest
from unittest.mock import patch

from shapely.geometry import box, mapping

from stormwater.management_estimates import estimate_management


DAY = '2026-11-16'


def rectangle(area, start=0):
    return mapping(box(start, 0, start + area / 100 * .3048, 30.48))


def fixture():
    parcel = rectangle(10000)
    case = {
        'crs': 'EPSG:26918', 'parcel': parcel,
        'features': {'features': [{'type': 'Feature', 'id': 'public-footprint',
                                  'geometry': rectangle(500),
                                  'properties': {'gsi_system_id': '62571', 'year_installed': 2018}}]},
        'baseline': {'ga_sqft': 10000, 'ia_sqft': 10000, 'bill_date': DAY,
                     'existing_ga_credit_sqft': 0, 'existing_ia_credit_sqft': 0,
                     'existing_iar_sqft': 0, 'npdes_fraction': 0,
                     'actual_bill_verified': False},
        'assessment': {'records': [], 'attachments': []},
    }
    # Deliberately incomplete entire-parcel classification and extent. Candidate
    # geometry alone supports a conditional credit illustration at billed IA.
    gis = {'measurement': {'complete': False, 'geometries': {'physical_ia': parcel}},
           'drainage': {'extent_sufficient': False}}
    engineering = {
        'system_id': '62571', 'system_type': 'Rain Garden', 'footprint_area_sqft': 500,
        'status': 'modeled', 'runs': [{
            'name': 'native', 'contributing_area_sqft': 4000, 'on_parcel_area_sqft': 3000,
            'off_parcel_area_sqft': 1000, 'identified_ia_sqft': 500,
            'area_scenarios': [{'id': name, 'area_sqft': area, 'geometry': rectangle(area),
                                'basis': 'Invented unit-test cover assumption',
                                'assumptions': ['Invented routing; not site evidence']}
                               for name, area in [('low', 500), ('base', 1000), ('high', 2000)]],
            'diagnostics': {'extent_sufficient': False},
        }], 'source_lineage': {'input_sha256': 'invented-not-an-empirical-source'},
        'missing_evidence': ['Capacity', 'Bypass'],
    }
    return case, gis, engineering


def run(case, gis, engineering, **kwargs):
    return estimate_management(case, gis, engineering, DAY, **kwargs)


def base(result):
    return result['runs'][0]['scenarios'][1]


def add_existing(case, gis):
    case['baseline'].update(existing_ga_credit_sqft=800, existing_ia_credit_sqft=800,
                            existing_credits_spatially_reconciled=True)
    case['assessment']['existing_credit_allocations'] = [{
        'id': 'prior-award', 'category': 'management', 'geometry': rectangle(1000),
        'facts': {'approved_ledger_confirmed': True},
        'evidence_refs': [{'source_url': 'https://example.test/invented-approved-ledger'}],
        'ga_credit_sqft': 800, 'ia_credit_sqft': 800, 'iar_sqft': 0,
    }]


def add_weighted_base(engineering, start=0):
    scenario = engineering['runs'][0]['area_scenarios'][1]
    scenario.update(geometry=rectangle(3000, start), weighted_components=[
        {'geometry': rectangle(500, start), 'impervious_fraction': 1,
         'basis': 'Invented roof observation'},
        {'geometry': rectangle(2500, start + 1.524), 'impervious_fraction': .2,
         'basis': 'Invented whole-property-billing-compatible ground fraction; not validation'},
    ])
    return scenario


class ManagementEstimateTests(unittest.TestCase):
    def test_estimate_lineage_cannot_be_applied_to_a_different_property(self):
        c, g, e = fixture()
        e['source_lineage']['case_sha256'] = '0'*64
        result = run(c, g, e)
        self.assertEqual(result['status'], 'blocked')
        self.assertIsNone(base(result)['annual_savings'])
        self.assertIn('Engineering estimate belongs to different case inputs', result['reasons'])

    def test_estimate_must_match_exact_frozen_artifact(self):
        c, g, e = fixture()
        e['source_lineage']['gis_analysis_sha256'] = '0'*64
        result = run(c, g, e)
        self.assertEqual(result['status'], 'blocked')
        self.assertIsNone(base(result)['annual_savings'])

    def test_known_bill_difference_and_required_volume(self):
        c, g, e = fixture()
        result = run(c, g, e)
        estimate = base(result)
        # 1000 managed sqft adds 800 sqft credits on both GA and IA. At500-sqft
        # ceilings the billed areas each fall by500: 1.003+7.048 =8.05/month.
        self.assertEqual(estimate['monthly_savings'], 8.05)
        self.assertEqual(estimate['annual_savings'], 96.60)
        self.assertEqual(estimate['required_runoff_volume_cuft_at_1_5in'], 125)
        self.assertEqual(estimate['ledger']['new_ga_credit_sqft'], 800)
        self.assertEqual(estimate['ledger']['new_ia_credit_sqft'], 800)
        self.assertEqual(result['current_estimate']['candidate_ia_sqft'], 1000)

    def test_incomplete_extent_and_full_parcel_ia_do_not_block_conditional_price(self):
        c, g, e = fixture()
        result = run(c, g, e)
        self.assertEqual(result['status'], 'conditional_estimate')
        self.assertEqual(base(result)['status'], 'calculated')
        self.assertFalse(g['measurement']['complete'])
        self.assertFalse(g['drainage']['extent_sufficient'])

    def test_upstream_footprint_capture_and_verified_managed_are_distinct(self):
        c, g, e = fixture()
        result = run(c, g, e)
        self.assertEqual(result['footprint_area_sqft'], 500)
        self.assertEqual(result['runs'][0]['contributing_area_sqft'], 4000)
        self.assertEqual(base(result)['candidate_ia_sqft'], 1000)
        self.assertIsNone(base(result)['captured_ia_sqft'])
        self.assertIsNone(base(result)['verified_managed_area_sqft'])
        self.assertIsNone(result['treatment_capacity_cuft'])
        self.assertIsNone(result['capture_fraction'])
        self.assertEqual(result['eligibility']['status'], 'unverified')
        self.assertIsNone(result['confidence']['percentage'])
        self.assertTrue(result['do_not_sum'])
        self.assertIn('Actual account bill', result['warnings'][0])

    def test_no_acquisition_or_rerouting_and_no_mutation(self):
        c, g, e = fixture()
        before = deepcopy((c, g, e))
        with patch('socket.socket', side_effect=AssertionError('Network forbidden')), \
             patch('drainage_core.engine.analyze', side_effect=AssertionError('Reroute forbidden')):
            result = run(c, g, e)
        self.assertEqual(base(result)['status'], 'calculated')
        self.assertEqual((c, g, e), before)
        self.assertNotIn('routing_confirmed', c['assessment'])

    def test_missing_capacity_still_shows_conditional_money(self):
        c, g, e = fixture()
        result = run(c, g, e)
        self.assertIsNotNone(base(result)['annual_savings'])
        self.assertIn('capacity', ' '.join(base(result)['assumptions']).lower())
        self.assertEqual(result['missing_evidence'], ['Capacity', 'Bypass'])

    def test_missing_basin_connection_has_unit_examples_not_site_estimate(self):
        c, g, e = fixture()
        e.update(system_type='Subsurface Basin', runs=[])
        result = run(c, g, e)
        self.assertEqual(result['status'], 'unit_sensitivities_only')
        self.assertEqual([s['candidate_ia_sqft'] for s in result['sensitivity_examples']], [1000, 5000, 10000])
        self.assertIsNone(result['current_estimate'])
        self.assertIsNone(result['range'])
        for item in result['sensitivity_examples']:
            self.assertFalse(item['is_site_area_estimate'])
            self.assertEqual(item['area_kind'], 'illustrative_managed_ia_sensitivity')
            self.assertNotIn(item['id'], ['low', 'base', 'high'])
        self.assertEqual(result['sensitivity_examples'][0]['annual_savings'], 96.60)

    def test_explicit_noninstallation_and_proposed_flags_block(self):
        for properties in [{'installed': False}, {'existing_installation': False}, {'status': 'Proposed'},
                           {'proposed_only': True}, {'year_installed': 2027}]:
            with self.subTest(properties=properties):
                c, g, e = fixture()
                c['features']['features'][0]['properties'].update(properties)
                result = run(c, g, e)
                self.assertEqual(base(result)['status'], 'blocked')
                self.assertIsNone(base(result)['annual_savings'])
                self.assertEqual(result['eligibility']['status'], 'requirements_failed')

    def test_matching_record_false_prerequisite_or_rejection_cannot_be_assumed_away(self):
        for change in [{'facts': {'routing_confirmed': False}}, {'decision': 'rejected'},
                       {'facts': {'treatment_depth_inches': 1}}]:
            with self.subTest(change=change):
                c, g, e = fixture()
                c['assessment']['records'] = [{'id': 'record', 'source': {'gsi_system_id': '062571'}, **change}]
                self.assertEqual(base(run(c, g, e))['status'], 'blocked')

    def test_unrelated_system_failure_does_not_block(self):
        c, g, e = fixture()
        c['assessment']['records'] = [{'id': 'other', 'system_id': 'other', 'facts': {'routing_confirmed': False}}]
        self.assertEqual(base(run(c, g, e))['status'], 'calculated')

    def test_changed_matching_evidence_requires_review(self):
        c, g, e = fixture()
        c['assessment']['records'] = [{'system_id': '62571', 'source_update': {'status': 'pending_review'}}]
        result = base(run(c, g, e))
        self.assertEqual(result['status'], 'blocked')
        self.assertIn('Changed system evidence requires source-update review', result['reasons'])

    def test_current_ia_budget_does_not_use_larger_image_area(self):
        c, g, e = fixture()
        c['baseline']['ia_sqft'] = 750
        result = run(c, g, e)
        self.assertEqual(result['runs'][0]['scenarios'][0]['status'], 'calculated')
        self.assertEqual(base(result)['status'], 'blocked')
        self.assertIsNone(base(result)['annual_savings'])
        self.assertIn('billed physical IA', ' '.join(base(result)['reasons']))

    def test_geometry_cannot_credit_off_parcel_or_false_scalar(self):
        for scenario in [{'geometry': rectangle(1000, start=-1)}, {'area_sqft': 1001.1}]:
            with self.subTest(scenario=scenario):
                c, g, e = fixture()
                e['runs'][0]['area_scenarios'][1].update(scenario)
                self.assertEqual(base(run(c, g, e))['status'], 'blocked')

    def test_existing_credit_totals_without_ledger_block(self):
        c, g, e = fixture()
        c['baseline'].update(existing_ga_credit_sqft=800, existing_ia_credit_sqft=800,
                            existing_credits_spatially_reconciled=True)
        result = base(run(c, g, e))
        self.assertEqual(result['status'], 'blocked')
        self.assertIn('Detailed existing credit allocation ledger missing', result['reasons'])

    def test_existing_full_area_occupied_not_just_credit_amount(self):
        c, g, e = fixture()
        add_existing(c, g)
        c['baseline']['ia_sqft'] = 1900
        e['runs'][0]['area_scenarios'][1]['geometry'] = rectangle(1000, start=3.048)
        result = base(run(c, g, e))
        self.assertEqual(result['status'], 'blocked')
        self.assertIn('Candidate and existing allocations exceed available billed physical IA', result['reasons'])

    def test_existing_overlap_blocks_and_disjoint_allocation_keeps_prior_credits(self):
        c, g, e = fixture()
        add_existing(c, g)
        self.assertEqual(base(run(c, g, e))['status'], 'blocked')
        e['runs'][0]['area_scenarios'][1]['geometry'] = rectangle(1000, start=3.048)
        result = base(run(c, g, e))
        self.assertEqual(result['status'], 'calculated')
        self.assertEqual(result['ledger']['existing_ia_credit_sqft'], 800)
        self.assertEqual(result['bill']['final_ia_sqft'], 8400)

    def test_invalid_approved_allocation_totals_are_not_accepted(self):
        c, g, e = fixture()
        add_existing(c, g)
        c['assessment']['existing_credit_allocations'][0]['ia_credit_sqft'] = 799
        e['runs'][0]['area_scenarios'][1]['geometry'] = rectangle(1000, start=3.048)
        self.assertEqual(base(run(c, g, e))['status'], 'blocked')

    def test_unlocated_unit_example_cannot_ignore_existing_occupancy(self):
        c, g, e = fixture()
        add_existing(c, g)
        e['runs'] = []
        result = run(c, g, e)
        self.assertEqual(result['sensitivity_examples'][0]['status'], 'blocked')
        self.assertIn('Unlocated area', ' '.join(result['sensitivity_examples'][0]['reasons']))

    def test_all_blocked_unit_examples_are_not_presented_as_available_estimates(self):
        c, g, e = fixture()
        e['runs'] = []
        c['baseline']['ia_sqft'] = 500
        result = run(c, g, e)
        self.assertEqual(result['status'], 'blocked')
        self.assertTrue(result['reasons'])

    def test_existing_npdes_combination_remains_blocked(self):
        c, g, e = fixture()
        c['baseline']['npdes_fraction'] = .07
        result = base(run(c, g, e))
        self.assertEqual(result['status'], 'blocked')
        self.assertIn('NPDES', ' '.join(result['reasons']))

    def test_pending_baseline_refresh_blocks_stale_prices(self):
        c, g, e = fixture()
        c['assessment']['baseline_refresh'] = {'status': 'pending_review'}
        self.assertEqual(base(run(c, g, e))['status'], 'blocked')

    def test_unknown_or_invalid_numeric_inputs_remain_unknown_not_zero(self):
        for area in [None, True, float('nan'), float('inf'), -1, 'invalid']:
            with self.subTest(area=area):
                c, g, e = fixture()
                e['runs'][0]['area_scenarios'][1]['area_sqft'] = area
                estimate = base(run(c, g, e))
                self.assertEqual(estimate['status'], 'blocked')
                self.assertIsNone(estimate['annual_savings'])
                self.assertIsNone(estimate['candidate_ia_sqft'])
        c, g, e = fixture()
        c['baseline']['existing_ia_credit_sqft'] = None
        self.assertEqual(base(run(c, g, e))['status'], 'blocked')

    def test_zero_lower_scenario_is_not_verified_no_opportunity(self):
        c, g, e = fixture()
        e['runs'][0]['area_scenarios'][0].update(area_sqft=0, geometry=None)
        result = run(c, g, e)
        low = result['runs'][0]['scenarios'][0]
        self.assertEqual(low['annual_savings'], 0)
        self.assertIsNone(low['verified_managed_area_sqft'])
        self.assertIn('remains unknown', low['note'])
        self.assertEqual(result['range']['annual_savings'][0], 0)

    def test_empty_zero_geometry_preserves_existing_multiaccount_minimum(self):
        c, g, e = fixture()
        c['baseline'].update(ga_sqft=100, ia_sqft=0, accounts=[{'allocation': .5}, {'allocation': .5}])
        e['runs'][0]['area_scenarios'] = [{'id': 'base', 'area_sqft': 0,
                                          'geometry': {'type': 'GeometryCollection', 'geometries': []}}]
        result = run(c, g, e)
        zero = result['runs'][0]['scenarios'][0]
        self.assertEqual(zero['status'], 'calculated')
        self.assertEqual(zero['monthly_savings'], 0)
        self.assertEqual(zero['bill']['monthly_total'], result['baseline']['monthly_total'])
        self.assertEqual(zero['bill']['minimum_mode'], 'per_account')

    def test_weighted_components_price_fractional_assumption_not_whole_polygon(self):
        c, g, e = fixture()
        add_weighted_base(e)
        before = deepcopy((c, g, e))
        estimate = base(run(c, g, e))
        self.assertEqual(estimate['status'], 'calculated')
        self.assertEqual(estimate['candidate_ia_sqft'], 1000)
        self.assertEqual(estimate['annual_savings'], 96.6)
        self.assertTrue(estimate['fractional_ia_is_assumed'])
        self.assertEqual(estimate['area_kind'], 'modeled_fractional_on_parcel_contributing_ia')
        self.assertIsNone(estimate['verified_managed_area_sqft'])
        self.assertEqual((c, g, e), before)

    def test_weighted_components_reject_invalid_fraction_and_missing_basis(self):
        for fraction in [None, True, -0.1, 1.01, float('nan'), 'invalid']:
            with self.subTest(fraction=fraction):
                c, g, e = fixture()
                scenario = add_weighted_base(e)
                scenario['weighted_components'][1]['impervious_fraction'] = fraction
                self.assertEqual(base(run(c, g, e))['status'], 'blocked')
        c, g, e = fixture()
        add_weighted_base(e)['weighted_components'][1]['basis'] = ''
        self.assertEqual(base(run(c, g, e))['status'], 'blocked')

    def test_weighted_components_reject_overlap_scalar_mismatch_and_incomplete_union(self):
        for defect in ('overlap', 'scalar', 'union', 'missing'):
            with self.subTest(defect=defect):
                c, g, e = fixture()
                scenario = add_weighted_base(e)
                if defect == 'overlap':
                    scenario['weighted_components'][1]['geometry'] = rectangle(2500, 1)
                elif defect == 'scalar':
                    scenario['area_sqft'] = 1100
                elif defect == 'union':
                    scenario['geometry'] = rectangle(1000)
                else:
                    scenario['weighted_components'] = []
                self.assertEqual(base(run(c, g, e))['status'], 'blocked')

    def test_weighted_possible_geometry_still_respects_existing_ledger(self):
        c, g, e = fixture()
        add_existing(c, g)
        # Even if little imperviousness is assumed, the whole possible geometry
        # must be disjoint from an existing credit allocation.
        add_weighted_base(e)
        self.assertEqual(base(run(c, g, e))['status'], 'blocked')
        add_weighted_base(e, start=3.048)
        estimate = base(run(c, g, e))
        self.assertEqual(estimate['status'], 'calculated')
        self.assertEqual(estimate['ledger']['existing_ia_credit_sqft'], 800)
        self.assertEqual(estimate['bill']['final_ia_sqft'], 8400)

    def test_hypothetical_connection_evidence_and_assumptions_survive_pricing(self):
        c, g, e = fixture()
        e['runs'][0].update(kind='connection_hypothesis',
                            connection_scope='Only terminals inside basin footprint',
                            candidate_collection_points=[{'id': 'terminal-31'}],
                            evidence=[{'terminal_id': 'terminal-31'}],
                            assumptions=['Terminal31 is hypothesized to enter the basin; no saved pipe link.'])
        result = run(c, g, e)
        self.assertEqual(result['runs'][0]['kind'], 'connection_hypothesis')
        self.assertEqual(result['runs'][0]['evidence'], [{'terminal_id': 'terminal-31'}])
        self.assertEqual(result['runs'][0]['candidate_collection_points'], [{'id': 'terminal-31'}])
        self.assertIn('Terminal31 is hypothesized', ' '.join(base(result)['assumptions']))

    def test_missing_base_is_not_replaced_with_an_invented_best_estimate(self):
        c, g, e = fixture()
        del e['runs'][0]['area_scenarios'][1]
        result = run(c, g, e)
        self.assertIsNone(result['current_estimate'])
        self.assertIsNotNone(result['range'])

    def test_rule_and_tariff_effective_periods_remain_enforced(self):
        c, g, e = fixture()
        result = estimate_management(c, g, e, '2028-01-01')
        self.assertEqual(base(result)['status'], 'blocked')
        self.assertIn('Assessment date outside verified rule period', base(result)['reasons'])


if __name__ == '__main__':
    unittest.main()
