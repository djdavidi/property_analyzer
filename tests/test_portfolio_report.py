"""Unit-only invented portfolio inputs; no site acquisition/inference/server."""
from copy import deepcopy
import unittest
from stormwater.portfolio_report import complete_sum,scenario,canopy_compatibility,parcel_view,render_html,CATEGORIES,joint_area_hypotheses,without_geometry,PLAIN_LABELS,_plain_finding
from test_modeled_assessment_unit import fixture,frozen_gis,assess,candidate
from shapely.geometry import box


class PortfolioReportTests(unittest.TestCase):
    def test_missing_member_is_unknown_and_explicit_zero_is_not_missing(self):
        self.assertIsNone(complete_sum([1,None]));self.assertIsNone(complete_sum([]))
        self.assertIsNone(complete_sum([True]));self.assertIsNone(complete_sum([float('nan')]))
        self.assertEqual(complete_sum([0,0]),0);self.assertEqual(complete_sum([10,20]),30)

    def test_blocked_or_invalidated_scenario_does_not_expose_savings_as_available(self):
        for status in ('blocked','invalidated','unknown'):
            self.assertIsNone(scenario({'status':status,'gross_annual_reduction':100})['annual_change'])

    def test_signed_calculated_change_keeps_increase(self):
        self.assertEqual(scenario({'status':'calculated','annual_savings':-25})['annual_change'],-25)

    def test_canopy_cap_is_joint_assumption_and_does_not_mutate_baseline(self):
        b=fixture()['baseline'];b['ia_sqft']=6000;before=deepcopy(b)
        v=canopy_compatibility(b,4000,9000)
        self.assertEqual(v['area_sqft'],2000);self.assertFalse(v['raw_all_hidden_consistent'])
        self.assertEqual(v['status'],'calculated');self.assertGreater(v['annual_change'],0)
        self.assertIn('not expected savings',' '.join(v['assumptions']));self.assertEqual(b,before)

    def test_negative_residual_is_contradiction_not_zero_canopy_savings(self):
        b=fixture()['baseline'];b['ia_sqft']=1000;v=canopy_compatibility(b,2000,9000)
        self.assertEqual(v['status'],'contradictory');self.assertIsNone(v['annual_change']);self.assertNotIn('area_sqft',v)

    def test_unknown_and_zero_overlap_do_not_become_zero_opportunity(self):
        b=fixture()['baseline']
        self.assertEqual(canopy_compatibility(b,None,1)['status'],'unknown')
        self.assertEqual(canopy_compatibility(b,0,None)['status'],'unknown')
        self.assertEqual(canopy_compatibility(b,10000,1000)['status'],'blocked')

    def test_existing_unreconciled_credit_still_blocks_cap(self):
        b=fixture()['baseline'];b['existing_ia_credit_sqft']=500
        self.assertEqual(canopy_compatibility(b,1000,1000)['status'],'blocked')

    def test_joint_area_extreme_uses_coherent_ga_and_keeps_bill_increase(self):
        b=fixture()['baseline'];b['ia_sqft']=1000
        m={'ga_sqft':10000.1,'ia_sqft':2000,'pervious_sqft':0,'unknown_sqft':8000.1}
        rows=joint_area_hypotheses(b,m)
        self.assertTrue(all(s['status']=='calculated' for s in rows))
        self.assertEqual(rows[1]['ia_sqft'],rows[1]['ga_sqft'])
        self.assertLess(rows[1]['annual_change'],0)
        self.assertIn('not a supported appeal',rows[1]['basis'])

    def test_geometry_omission_keeps_source_and_area_evidence_without_mutation(self):
        raw={'rows':[{'geometry':{'coordinates':[1,2]},'area_sqft':200,'source_url':'https://example.test'}]}
        out=without_geometry(raw);self.assertNotIn('geometry',out['rows'][0])
        self.assertIn('geometry',raw['rows'][0]);self.assertEqual(out['rows'][0]['area_sqft'],200)

    def test_complete_category_coverage_and_source_input_preservation(self):
        c=fixture();c['features']['features']=[candidate('canopy',box(0,0,30.48,30.48))]
        g=frozen_gis(c);a=assess(c,g);r={**g,'assessment':a,'billing':{'baseline':{'annualized_total':1200}},'quality_review':{'status':'not_independently_validated'}}
        before=deepcopy((c,r));view=parcel_view(c,r,{'parcel_id':'1','address':'Invented','systems':[]})
        self.assertEqual({v['category'] for v in view['categories']},{k for k,_ in CATEGORIES})
        self.assertEqual(len(view['categories']),12);self.assertIsNone(view['net_annual_change'])
        self.assertIn('Not a catchment',view['categories'][0]['drainage_linkage'])
        self.assertEqual((c,r),before)
        self.assertIn('area_correction',view['bill_ladder']);self.assertIn('existing_credits',view['bill_ladder'])

    def test_html_escapes_owner_and_keeps_unknowns_and_all_categories(self):
        c=fixture();g=frozen_gis(c);r={**g,'assessment':assess(c,g),'billing':{'baseline':{'annualized_total':1200}}}
        m=parcel_view(c,r,{'parcel_id':'1','address':'Invented','systems':[]})
        s={k:None for k in ('recorded_ga_sqft','recorded_ia_sqft','identified_ia_sqft','unresolved_ground_sqft','visible_canopy_sqft','net_annual_change')}
        s.update(rank=1,address='<script>bad</script>',owner='<img onerror=bad>',parcel_count=1,parcel_ids=['1'],members=[m],current_annual_public_charge=1200,evidence_status='Unknown',next_action='Review')
        html=render_html({'as_of':'2026-11-15','claim':'Not additive','sites':[s]})
        self.assertNotIn('<script>bad',html);self.assertIn('&lt;script&gt;',html)
        self.assertIn('Cannot estimate yet',html);self.assertIn('Final bill and total saving',html)
        for key,_ in CATEGORIES:
            self.assertIn('data-category="'+key+'"',html);self.assertIn(PLAIN_LABELS[key],html)

    def test_plain_overview_has_four_columns_and_no_visible_machine_labels(self):
        c=fixture();g=frozen_gis(c);r={**g,'assessment':assess(c,g),'billing':{'baseline':{'annualized_total':1200}}}
        m=parcel_view(c,r,{'parcel_id':'1','address':'Invented','systems':[]})
        s={'rank':1,'address':'Site','owner':'Owner','parcel_count':1,'parcel_ids':['1'],'members':[m],'current_annual_public_charge':1200}
        before=deepcopy(m);html=render_html({'as_of':'2026-11-15','sites':[s]})
        self.assertEqual(html.split('</thead>',1)[0].count('<th>'),4)
        self.assertNotIn('recorded_total_compatible_canopy_cap',html)
        self.assertNotIn('Joint GA/IA',html);self.assertNotIn('<pre>',html)
        self.assertIn('not a prediction',html);self.assertEqual(m,before)

    def test_bill_increase_is_explained_as_higher_and_examples_are_not_totals(self):
        m={'primary_run':'no_terrain'}
        c={'category':'ga_adjustment','scenarios':[{'status':'calculated','annual_change':-11.52}]}
        _,_,amount,_=_plain_finding(c,m);self.assertIn('higher',amount);self.assertIn('$12',amount)
        c={'category':'permeable_pavement','records':[{}],'scenarios':[{'status':'calculated','annual_change':100}]}
        self.assertIn('not a site total',_plain_finding(c,m)[2])


if __name__=='__main__':unittest.main()
