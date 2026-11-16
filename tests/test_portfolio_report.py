"""Unit-only invented portfolio inputs; no site acquisition/inference/server."""
from copy import deepcopy
from pathlib import Path
import sys
import unittest
# Sibling test helpers import by module name under both `discover -s tests` and
# `python -m unittest tests.test_portfolio_report`.
sys.path.insert(0,str(Path(__file__).resolve().parent))
from stormwater.portfolio_report import complete_sum,scenario,canopy_compatibility,parcel_view,render_html,CATEGORIES,joint_area_hypotheses,without_geometry,PLAIN_LABELS,_plain_finding
from test_modeled_assessment_unit import fixture,frozen_gis,assess,candidate
from shapely.geometry import box,mapping


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


EMPTY={'type':'GeometryCollection','geometries':[]}


def allocated(c,ia,region,credit):
    """Invented approved management allocation occupying ``region`` (80% credit)."""
    c['baseline'].update(ia_sqft=ia,existing_ga_credit_sqft=credit,existing_ia_credit_sqft=credit,
                         existing_credits_spatially_reconciled=True)
    c['assessment']['existing_credit_allocations']=[{'id':'prior','category':'management','geometry':mapping(region),
        'facts':{'approved_ledger_confirmed':True},'evidence_refs':[{'source_url':'https://example.test/invented-ledger'}],
        'ga_credit_sqft':credit,'ia_credit_sqft':credit,'iar_sqft':0}]
    return {'measurement':{'geometries':{'physical_ia':mapping(region),'pervious':EMPTY}}}


def saved(folder,c,r):
    import json
    folder.mkdir(parents=True);(folder/'case.json').write_text(json.dumps(c));(folder/'analysis.json').write_text(json.dumps(r))


class PortfolioLedgerAndGateTests(unittest.TestCase):
    """Review H3/H4/H6/H10 (repros new-policy/r2_portfolio.py, r3_pilot.py R4b, r5, r6)."""

    def test_canopy_cap_respects_existing_occupied_area_h4(self):
        # Recorded IA 6000; an approved allocation occupies 5000 sq ft (4000 credit at 80%).
        # Cap = min(9000, 6000 - 4000) = 2000; occupied 5000 + 2000 > 6000 -> blocked.
        c=fixture();g=allocated(c,6000,box(0,0,15.24,30.48),4000)
        v=canopy_compatibility(c['baseline'],4000,9000,case=c,gis=g,as_of='2026-11-15',region=mapping(box(15.24,0,30.48,30.48)))
        self.assertEqual(v['status'],'blocked');self.assertIsNone(v['annual_change'])
        self.assertIn('Allocations exceed available physical impervious area',v['reasons'])
        # Baseline only (no itemized ledger): existing credits cannot be reconciled.
        b=deepcopy(c['baseline']);b.pop('existing_credits_spatially_reconciled')
        self.assertEqual(canopy_compatibility(b,4000,9000)['status'],'blocked')

    def test_canopy_cap_cannot_stack_on_ground_under_an_existing_award_r4b(self):
        c=fixture();region=box(0,0,6.096,30.48);g=allocated(c,10000,region,1600)
        v=canopy_compatibility(c['baseline'],6000,9000,known_overlap=2000,case=c,gis=g,as_of='2026-11-15',region=mapping(region))
        self.assertEqual(v['status'],'blocked')
        self.assertTrue(any('Overlapping physical allocations' in r for r in v['reasons']))

    def test_canopy_cap_honours_baseline_refresh_and_one_money_path_r6(self):
        from unittest.mock import patch
        c=fixture();c['features']['features']=[candidate('canopy',box(0,0,30.48,30.48))]
        g=frozen_gis(c);a=assess(c,g)
        with patch('stormwater.billing.calculate_scenarios',side_effect=AssertionError('one money path (D7)')):
            m=parcel_view(c,{**g,'assessment':a,'billing':{'baseline':{'annualized_total':1200}}},{'parcel_id':'1','address':'Invented','systems':[]})
        cap=next(x for x in m['categories'] if x['category']=='canopy')['scenarios'][0]
        self.assertEqual(cap['status'],'calculated');self.assertEqual(cap['priced_by'][:24],'assessment_policy._econo')
        c['assessment']['baseline_refresh']={'status':'pending_review'};c['baseline'].pop('bill_date')
        a=assess(c,g);m=parcel_view(c,{**g,'assessment':a,'billing':{'baseline':{}}},{'parcel_id':'1','address':'Invented','systems':[]})
        cap=next(x for x in m['categories'] if x['category']=='canopy')['scenarios'][0]
        self.assertEqual(cap['status'],'blocked');self.assertIsNone(cap['annual_change'])
        self.assertEqual(a['economics']['modeled']['status'],'blocked')

    def test_management_status_and_amount_follow_the_rows_h10(self):
        from test_modeled_assessment_unit import fake_research
        from stormwater.billing import monthly_bill
        c=fixture();g=frozen_gis(c,fake_research(c));a=assess(c,g)
        m=parcel_view(c,{**g,'assessment':a,'billing':{'baseline':{}}},{'parcel_id':'1','address':'Invented','systems':[{'system_id':'G1'}]})
        cat=next(x for x in m['categories'] if x['category']=='management')
        self.assertEqual(cat['status'],'conditional')
        upper=[s['annual_change'] for s in cat['scenarios'] if s['bound']=='upper']
        self.assertTrue(upper and upper[0]>0)
        self.assertIn('/year lower',_plain_finding(cat,m)[2])
        self.assertEqual(m['catchment_route_states'],['complete_in_window']);self.assertTrue(m['watershed_extent_verified'])

    def test_build_portfolio_refuses_mismatched_inputs_and_labels_outdated_h3(self):
        import tempfile
        from drainage_core.engine import input_hash
        from stormwater.portfolio_report import build_portfolio
        c=fixture();c['features']['features']=[candidate('canopy',box(0,0,30.48,30.48))]
        g=frozen_gis(c);a=assess(c,g)
        selection={'source_run':'invented','sites':[{'parcel_id':'1','address':'Invented','systems':[]}]}
        base={**g,'assessment':a,'billing':{'baseline':{'annualized_total':1200,'monthly_total':100}}}
        with tempfile.TemporaryDirectory() as tmp:
            saved(Path(tmp)/'cases'/'pwd-1',c,base)
            with self.assertRaisesRegex(ValueError,'does not match current case inputs'):build_portfolio(selection,tmp)
        with tempfile.TemporaryDirectory() as tmp:
            saved(Path(tmp)/'cases'/'pwd-1',c,{**base,'input_sha256':input_hash(c)})
            current=build_portfolio(selection,tmp)
        self.assertEqual(current['as_of'],'2026-11-15');self.assertEqual(current['sites'][0]['input_status'],'current')
        cap=next(x for x in current['sites'][0]['members'][0]['categories'] if x['category']=='canopy')['scenarios'][0]
        self.assertIsNotNone(cap['annual_change'])
        with tempfile.TemporaryDirectory() as tmp:
            saved(Path(tmp)/'cases'/'pwd-1',c,{**base,'input_sha256':input_hash(c),'policy_processing_fingerprint':'older-billing-code'})
            old=build_portfolio(selection,tmp)
        member=old['sites'][0]['members'][0]
        self.assertEqual(member['input_status'],'outdated');self.assertEqual(old['sites'][0]['input_status'],'outdated')
        cap=next(x for x in member['categories'] if x['category']=='canopy')['scenarios'][0]
        self.assertIsNone(cap['annual_change']);self.assertEqual(cap['status'],'outdated')
        self.assertIn('withheld',render_html(old))

    def test_published_charge_is_the_public_record_and_labels_follow_data_h6(self):
        c=fixture();c['features']['features']=[candidate('canopy',box(0,0,30.48,30.48))]
        c['baseline']['published_monthly_total']=10.00
        g=frozen_gis(c);a=assess(c,g)
        from stormwater.assessment_policy import _economics
        from datetime import date
        bill=_economics(c,g,[],date(2026,11,15),None)['baseline']
        m=parcel_view(c,{**g,'assessment':a,'billing':{'baseline':bill}},{'parcel_id':'1','address':'Invented','systems':[]})
        self.assertEqual(m['current_annual_public_charge'],120.0);self.assertEqual(m['charge_basis'],'published')
        self.assertEqual(m['computed_monthly_charge'],163.83);self.assertEqual(m['computed_minus_published_monthly'],153.83)
        m['supported_additional_annual_change']=500.0
        site={'rank':1,'address':'Site','owner':None,'parcel_count':1,'parcel_ids':['1'],'members':[m],
              'current_annual_public_charge':m['current_annual_public_charge'],'computed_annual_charge':m['computed_annual_charge']}
        html=render_html({'as_of':'2026-11-15','sites':[site]})
        self.assertIn('$120 (public record)',html);self.assertNotIn('$1,966/year in public records',html)
        self.assertIn('$153.83 per month',html)
        self.assertIn('documented credit computed at about $500/year',html)
        self.assertNotIn('New credits confirmed: none established',html)
        self.assertIn('<p>Unknown owner</p>',html);self.assertNotIn('<p>None</p>',html)
        computed_only={**site,'current_annual_public_charge':None,'computed_annual_charge':1965.96}
        self.assertIn('(computed from recorded areas; not a public record)',render_html({'as_of':None,'sites':[computed_only]}))


if __name__=='__main__':unittest.main()
