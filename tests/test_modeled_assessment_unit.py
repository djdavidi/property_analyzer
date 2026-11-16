"""Unit tests only: invented masks/terrain and pure geometry/policy functions.

No inference, imagery retrieval, server, CLI, browser or real-site replay.
"""
from copy import deepcopy
from datetime import date
import unittest
from shapely.geometry import box,mapping
from drainage_core.engine import new_case,canonical,analyze
from drainage_core.geometry import measure,SQFT_PER_M2
from drainage_core.freshness import age_policy
from drainage_core.model_integration import ai_surfaces,build,composition,ia_bounds
from stormwater.model_assessment import match
from stormwater.assessment_policy import evaluate_assessment


def candidate(name,g,id=None,**extra):
    return {'type':'Feature','id':id or 'ai-'+name,'geometry':mapping(g),'properties':{
        'layer':'canopy_candidate' if name=='canopy' else 'surface_candidate','classification':name,
        'source_kind':'modeled semantic estimate','source_vintage':'2025',
        'source_sha256':'a'*64,'model_sha256':'b'*64,**extra}}


def fixture():
    c=new_case('Invented unit site',crs='EPSG:26918');c['parcel']=mapping(box(0,0,30.48,30.48))
    c['imagery_age_policy']=age_policy('2026-11-15')
    c['automatic']={'landcover':{'settings':{'target_pixel_metres':.5},'prediction_sha256':'c'*64}}
    c['baseline']={'ga_sqft':10000,'ia_sqft':10000,'property_type':'NonRes','bill_date':'2026-11-15'}
    c['assessment']={'records':[]}
    c['features']['features']=[candidate('other_pavement',box(0,0,15.24,30.48)),
                               candidate('grass_shrub',box(15.24,0,30.48,30.48))]
    return c


def record(id='r',category='permeable_pavement',x=0,width=3.048,**extra):
    return {'id':id,'category':category,'decision':'candidate','basis':'public_candidate',
        'facts':{},'footprint_geometry':mapping(box(x,0,x+width,30.48)),
        'evidence_refs':[{'source_url':'https://example.test/invented-only'}],**extra}


def fake_research(c,receivers=('G1',),kind='gsi'):
    """Inject a hand-defined hydrology output; do not exercise providers/workflows."""
    c['research_drainage']={'features':[{'id':'receiver-'+g,'role':'gsi','gsi_id':g,
        'geometry':mapping(box(0,0,3.048,30.48))} for g in receivers]}
    primary={'parameters':{},'grid':{'cell_size':1,'horizontal_unit':'m'},'area_conservation_pass':True,
        'catchments':[],'outlet_catchments':[]}
    for g in receivers:
        primary['catchments' if kind=='gsi' else 'outlet_catchments'].append({
            'gsi_id' if kind=='gsi' else 'outlet_id':g,'geometry':c['parcel'],'off_parcel_area_sqft':0})
    return {'method':'invented-unit-output','primary':primary,'sensitivity':[]}


def frozen_gis(c,research=None):
    observed=measure(c)
    return {'measurement':observed,'modeled_integration':build(c,observed,{},research or {})}


def assess(c,g=None):return evaluate_assessment(c,g or frozen_gis(c),as_of='2026-11-15')


def rec_info(result,id='r'):
    return next(r for r in result['modeled_integration']['records'] if r['record_id']==id)


class ModeledGeometryUnitTests(unittest.TestCase):
    def test_ai_fills_only_modeled_unknowns_and_leaves_source_intact(self):
        c=fixture();before=canonical(c);obs=measure(c);r=build(c,obs,{},{});m=r['measurement']
        self.assertAlmostEqual(m['ia_sqft'],5000);self.assertAlmostEqual(m['pervious_sqft'],5000)
        self.assertEqual(obs['ia_sqft'],0);self.assertAlmostEqual(obs['unknown_sqft'],10000)
        self.assertEqual(canonical(c),before)

    def test_observed_surfaces_win_and_disagreement_is_reported(self):
        c=fixture();c['features']['features'].append({'id':'survey','geometry':mapping(box(0,0,15.24,30.48)),
            'properties':{'layer':'surface','class':'pervious'}})
        r=build(c,measure(c),{},{});self.assertEqual(r['measurement']['ia_sqft'],0)
        self.assertAlmostEqual(r['ai']['observation_disagreement_sqft'],5000)

    def test_overlapping_classes_are_unknown_not_double_counted(self):
        c=fixture();c['features']['features'].append(candidate('bare_soil',box(0,0,15.24,30.48)))
        r=build(c,measure(c),{},{});self.assertAlmostEqual(r['ai']['class_conflict_sqft'],5000)
        self.assertEqual(r['measurement']['ia_sqft'],0);self.assertAlmostEqual(r['measurement']['unknown_sqft'],5000)

    def test_shared_class_boundaries_are_not_conflicting_area(self):
        c=fixture();r=ai_surfaces(c,measure(c))
        from shapely.geometry import shape
        self.assertTrue(shape(r['conflict_geometry']).is_empty)
        self.assertAlmostEqual(shape(r['coverage_geometry']).area,30.48**2)

    def test_rgb_candidate_cannot_become_canopy_or_pavement(self):
        c=fixture()
        for f in c['features']['features']:f['properties']['source_kind']='modeled image candidate'
        r=build(c,measure(c),{},{});self.assertEqual(r['ai']['status'],'unavailable')
        row=composition(c,r['ai'],r['measurement'],c['parcel'])['classes'][0]
        self.assertIsNone(row['area_sqft'])

    def test_stale_future_unknown_date_and_missing_hash_are_excluded(self):
        for patch in ({'source_vintage':'2018'},{'source_vintage':'2030'},{'source_vintage':None},{'model_sha256':None}):
            c=fixture()
            for f in c['features']['features']:f['properties'].update(patch)
            r=ai_surfaces(c,measure(c));self.assertEqual(r['status'],'unavailable');self.assertEqual(len(r['excluded']),2)

    def test_canopy_does_not_fill_hidden_ground(self):
        c=fixture();c['features']['features']=[candidate('canopy',box(0,0,30.48,30.48))]
        r=build(c,measure(c),{},{});self.assertAlmostEqual(r['measurement']['canopy_sqft'],10000)
        self.assertEqual(r['measurement']['ia_sqft'],0);self.assertAlmostEqual(r['measurement']['unknown_sqft'],10000)

    def test_bounds_are_ordered_and_cannot_override_observed_pervious(self):
        c=fixture();c['features']['features'].append({'id':'survey','geometry':mapping(box(15.24,0,30.48,30.48)),
            'properties':{'layer':'surface','class':'pervious'}})
        r=build(c,measure(c),{},{});bs=ia_bounds(c,r,box(0,0,30.48,30.48))
        self.assertLess(bs['lower'].area,bs['nominal'].area);self.assertGreaterEqual(bs['upper'].area,bs['nominal'].area)
        self.assertAlmostEqual(bs['upper'].area,15.24*30.48)

    def test_absent_pixel_size_has_no_invented_boundary_range(self):
        c=fixture();c['automatic']={};r=build(c,measure(c),{},{});comp=composition(c,r['ai'],r['measurement'],c['parcel'])
        self.assertIsNone(comp['classes'][0]['edge_lower_sqft'])

    def test_polygon_parts_of_clipped_geometry_collection_are_retained(self):
        from shapely.geometry import GeometryCollection,LineString
        c=fixture();geom=GeometryCollection([box(0,0,15.24,30.48),LineString([(20,0),(25,0)])])
        c['features']['features']=[candidate('other_pavement',geom)]
        m=build(c,measure(c),{},{});self.assertAlmostEqual(m['measurement']['ia_sqft'],5000)

    def test_malformed_ai_geometry_is_reported_without_breaking_other_classes(self):
        c=fixture();c['features']['features'][0]['geometry']={'type':'InvalidShape','coordinates':[]}
        m=build(c,measure(c),{},{});self.assertEqual(len(m['ai']['excluded']),1)
        self.assertAlmostEqual(m['measurement']['pervious_sqft'],5000)

    def test_ai_roof_supplements_only_additional_draining_view(self):
        c=fixture();c['parcel']=mapping(box(0,0,7,7));roof=box(1,1,2,2)
        c['features']['features']=[candidate('roof',roof),candidate('other_pavement',box(0,0,7,7).difference(roof))]
        c['terrain']={'elevations':[[10-i*.1 for i in range(7)] for _ in range(7)],'origin':[0,7],
            'cell_size':1,'crs':c['crs'],'horizontal_unit':'m','vertical_unit':'m','settings':{'max_flow_paths':0}}
        c['research_drainage']={'sensitivity':False,'features':[{'id':'g','gsi_id':'G1','role':'gsi','geometry':mapping(box(4,3,5,4))}]}
        a=analyze(c);self.assertEqual(a['research_drainage']['primary']['roof_excluded_cells'],0)
        self.assertEqual(a['modeled_integration']['ai_roof_drainage']['primary']['roof_excluded_cells'],1)
        self.assertEqual(a['measurement']['ia_sqft'],0);self.assertAlmostEqual(a['modeled_integration']['roof_supplement_sqft'],SQFT_PER_M2)

    def test_catchment_composition_uses_injected_geometry_and_ai(self):
        c=fixture();research=fake_research(c);r=build(c,measure(c),{},research)
        co=r['runs'][0]['catchments'][0]['composition'];self.assertAlmostEqual(co['modeled_ia_sqft'],5000)
        self.assertEqual(r['drainage_source'],'Existing research scenario')

    def test_explicit_pipe_to_external_outlet_is_not_a_gsi_or_proximity_guess(self):
        from drainage_core.research import run_model,feature_inputs
        from shapely.geometry import Point
        c=fixture();c['parcel']=mapping(box(0,0,7,7))
        c['terrain']={'elevations':[[10-i*.1 for i in range(7)] for _ in range(7)],'origin':[0,7],
            'cell_size':1,'crs':c['crs'],'horizontal_unit':'m','vertical_unit':'m','settings':{'max_flow_paths':0},
            'inlets':[{'id':'inlet','cell':[3,2]}],'connections':[{'from':'inlet','to':'O1','evidence':'scenario'}]}
        r=run_model(c,measure(c),feature_inputs(c)[0])
        self.assertEqual(r['catchments'],[]);self.assertEqual(r['outlet_catchments'][0]['outlet_id'],'O1')
        self.assertTrue(r['area_conservation_pass'])
        c['terrain']['connections'][0]['evidence']='unknown'
        self.assertEqual(run_model(c,measure(c),feature_inputs(c)[0])['outlet_catchments'],[])


class RecordJoinUnitTests(unittest.TestCase):
    def test_category_context_is_available_without_inventing_installed_systems(self):
        c=fixture();out=assess(c)
        pavement=next(v for v in out['categories'] if v['category']=='permeable_pavement')
        self.assertAlmostEqual(pavement['modeled_context']['predicted_pavement_sqft'],5000)
        self.assertEqual(pavement['modeled_context']['permeability'],'Unknown')
        self.assertEqual(pavement['records'],[]);self.assertEqual(pavement['status'],'missing_evidence')

    def test_explicit_system_id_links_to_receiver_and_preserves_review_status(self):
        c=fixture();c['assessment']['records']=[record(raw_record={'gsi_system_id':'G1'})]
        r=assess(c,frozen_gis(c,fake_research(c)))
        self.assertEqual(rec_info(r)['runs'][0]['catchment_match']['status'],'linked')
        self.assertEqual(rec_info(r)['runs'][0]['receiver_id'],'G1')
        screened=r['categories'][1]['records'][0]
        self.assertEqual(screened['status'],'candidate');self.assertIsNone(screened['managed_area_sqft'])
        self.assertIn('modeled_context',screened)

    def test_unique_receiver_overlap_is_candidate_link(self):
        c=fixture();c['assessment']['records']=[record()];g=frozen_gis(c,fake_research(c))
        linked=match(c['assessment']['records'][0],c,g['modeled_integration'],g['modeled_integration']['runs'][0])
        self.assertEqual(linked['status'],'linked');self.assertIn('unverified',linked['basis'])

    def test_conflicting_ids_or_overlaps_are_not_silently_chosen(self):
        c=fixture();c['assessment']['records']=[record(gsi_id='G1',raw_record={'gsi_system_id':'G2'})]
        r=assess(c,frozen_gis(c,fake_research(c,('G1','G2'))))
        self.assertEqual(rec_info(r)['runs'][0]['catchment_match']['status'],'ambiguous')
        self.assertEqual(rec_info(r)['runs'][0]['scenarios'][0]['status'],'blocked')
        c['assessment']['records']=[record()]
        r=assess(c,frozen_gis(c,fake_research(c,('G1','G2'))))
        self.assertEqual(rec_info(r)['runs'][0]['catchment_match']['status'],'ambiguous')

    def test_missing_explicit_id_does_not_match_another_receiver(self):
        c=fixture();c['assessment']['records']=[record(gsi_id='missing')]
        r=assess(c,frozen_gis(c,fake_research(c)))
        info=rec_info(r)['runs'][0];self.assertEqual(info['catchment_match']['status'],'missing')
        self.assertNotIn('receiver_id',info);self.assertIn('footprint only',info['area_basis'])

    def test_direct_discharge_requires_explicit_outfall_not_nearby_gsi(self):
        c=fixture();c['assessment']['records']=[record(category='direct_discharge',facts={})]
        r=assess(c,frozen_gis(c,fake_research(c)))
        self.assertEqual(rec_info(r)['runs'][0]['scenarios'][0]['status'],'blocked')
        c['assessment']['records'][0]['facts']['outfall_id']='O1'
        r=assess(c,frozen_gis(c,fake_research(c,('O1',),kind='outlet')))
        self.assertEqual(rec_info(r)['runs'][0]['receiver_id'],'O1')
        self.assertEqual(rec_info(r)['runs'][0]['scenarios'][1]['status'],'calculated')

    def test_rejection_and_npdes_are_not_overridden_by_ai(self):
        c=fixture();c['assessment']['records']=[record(decision='rejected'),record('permit','industrial_npdes')]
        r=assess(c);self.assertEqual(rec_info(r)['status'],'rejected')
        self.assertEqual(rec_info(r,'permit')['status'],'not_applicable')
        self.assertEqual(r['modeled_integration']['combined'],[])

    def test_footprint_fallback_is_explicit_direct_rainfall_scenario(self):
        c=fixture();c['assessment']['records']=[record()];r=assess(c)
        info=rec_info(r)['runs'][0];self.assertIn('upstream contributing area unknown',info['area_basis'])
        nominal=next(s for s in info['scenarios'] if s['bound']=='nominal')
        self.assertAlmostEqual(nominal['area_sqft'],1000);self.assertEqual(nominal['status'],'calculated')
        self.assertEqual(nominal['gross_monthly_reduction'],8.05);self.assertEqual(nominal['gross_annual_reduction'],96.60)
        self.assertIn('material_confirmed',nominal['assumed_prerequisites'])

    def test_source_crs_mismatch_does_not_supply_public_footprint(self):
        c=fixture();r=record();r.pop('footprint_geometry');r['public_geometry']=c['parcel']
        r['public_geometry_role']='system footprint';r['source']={'crs':'EPSG:3857'}
        c['assessment']['records']=[r];info=rec_info(assess(c))
        self.assertIsNone(info['footprint_composition']);self.assertEqual(info['runs'][0]['scenarios'][0]['status'],'blocked')


class ModeledSavingsUnitTests(unittest.TestCase):
    def test_incomplete_model_still_reports_explicit_appeal_assumptions(self):
        c=fixture();c['features']['features']=[candidate('canopy',box(0,0,30.48,30.48))]
        s=assess(c)['modeled_integration']['surface_scenario']
        self.assertEqual(s['measurement_only']['status'],'blocked')
        self.assertEqual(len(s['area_alternatives']),3)
        self.assertEqual(s['area_alternatives'][0]['monthly_savings'],0)
        self.assertEqual(s['area_alternatives'][1]['ia_sqft'],0)
        self.assertAlmostEqual(s['area_alternatives'][2]['ia_sqft'],10000)
        self.assertEqual(measure(c)['ia_sqft'],0)

    def test_modeled_ia_increase_is_negative_appeal_savings(self):
        c=fixture();c['baseline']['ia_sqft']=1000
        v=assess(c)['modeled_integration']['surface_scenario']['area_alternatives'][1]
        self.assertLess(v['monthly_savings'],0)

    def test_untyped_existing_gsi_has_its_own_ai_informed_alternative(self):
        c=fixture();r=assess(c,frozen_gis(c,fake_research(c)))
        values=r['modeled_integration']['catchment_scenarios']
        v=next(v for v in values if v['receiver_id']=='G1' and v['bound']=='nominal')
        self.assertAlmostEqual(v['area_sqft'],5000)
        self.assertEqual(v['status'],'calculated');self.assertAlmostEqual(v['ledger']['new_ia_credit_sqft'],4000)
        total=next(v for v in values if v['receiver_id']=='all_unassigned_gsi' and v['bound']=='nominal')
        self.assertEqual(total['gross_monthly_reduction'],v['gross_monthly_reduction'])

    def test_gsi_already_linked_to_individual_record_is_not_recounted(self):
        c=fixture();c['assessment']['records']=[record(gsi_id='G1')]
        r=assess(c,frozen_gis(c,fake_research(c)))
        self.assertEqual(r['modeled_integration']['catchment_scenarios'],[])

    def test_permit_what_if_does_not_change_candidate_or_documented_economics(self):
        c=fixture();c['assessment']['records']=[record('permit','industrial_npdes',facts={'permit_id':'SYNTHETIC-ONLY'})]
        r=assess(c);s=r['modeled_integration']['permit_scenarios'][0]
        self.assertEqual(s['status'],'calculated');self.assertGreater(s['gross_monthly_reduction'],0)
        self.assertEqual(r['categories'][3]['records'][0]['status'],'candidate')
        self.assertEqual(r['economics']['documented']['status'],'blocked')

    def test_inactive_or_construction_permit_what_if_is_blocked(self):
        for facts in ({'active':False},{'permit_type':'construction'}):
            c=fixture();c['assessment']['records']=[record('permit','industrial_npdes',facts=facts)]
            self.assertEqual(assess(c)['modeled_integration']['permit_scenarios'][0]['status'],'blocked')

    def test_unit_source_and_existing_findings_are_unchanged(self):
        c=fixture();c['assessment']['records']=[record()];g=frozen_gis(c);before=canonical(c);old=canonical(g)
        out=assess(c,g);self.assertEqual(canonical(c),before);self.assertEqual(canonical(g),old)
        self.assertEqual(out['economics']['modeled']['status'],'blocked')
        self.assertEqual(out['categories'][1]['records'][0]['status'],'candidate')

    def test_per_record_linked_area_uses_catchment_not_footprint(self):
        c=fixture();c['assessment']['records']=[record(gsi_id='G1')]
        r=assess(c,frozen_gis(c,fake_research(c)))
        nominal=rec_info(r)['runs'][0]['scenarios'][1]
        self.assertAlmostEqual(nominal['area_sqft'],5000)
        self.assertAlmostEqual(nominal['ledger']['new_ia_credit_sqft'],4000)

    def test_known_failed_or_proposed_prerequisites_block_estimates(self):
        for facts in ({'material_confirmed':False},{'proposed_only':True},{'installed':False},{'treatment_depth_inches':.5}):
            c=fixture();c['assessment']['records']=[record(facts=facts)]
            info=rec_info(assess(c));self.assertTrue(info['known_failed_prerequisites'])
            self.assertTrue(all(s['status']=='blocked' for s in info['runs'][0]['scenarios']))

    def test_overlapping_candidates_block_combined_but_keep_alternatives(self):
        c=fixture();c['assessment']['records']=[record('a'),record('b')]
        r=assess(c);combined=next(v for v in r['modeled_integration']['combined'] if v['bound']=='nominal')
        self.assertEqual(combined['status'],'blocked');self.assertTrue(any('Overlapping' in x for x in combined['reasons']))
        self.assertEqual(rec_info(r,'a')['runs'][0]['scenarios'][1]['status'],'calculated')

    def test_disjoint_records_share_one_ledger(self):
        c=fixture();c['assessment']['records']=[record('a'),record('b',x=3.048)]
        r=assess(c);v=next(v for v in r['modeled_integration']['combined'] if v['bound']=='nominal')
        self.assertEqual(v['status'],'calculated');self.assertEqual(set(v['record_areas_sqft']),{'a','b'})
        self.assertAlmostEqual(v['ledger']['new_ia_credit_sqft'],1600)
        self.assertAlmostEqual(v['gross_annual_reduction'],v['gross_monthly_reduction']*12)

    def test_existing_unreconciled_credits_still_block(self):
        c=fixture();c['assessment']['records']=[record()]
        c['baseline'].update(existing_ia_credit_sqft=500,existing_credits_spatially_reconciled=False)
        s=rec_info(assess(c))['runs'][0]['scenarios'][1]
        self.assertEqual(s['status'],'blocked');self.assertTrue(any('reconciliation' in x for x in s['reasons']))

    def test_ai_surface_correction_is_conditional_and_separate(self):
        c=fixture();r=assess(c);s=r['modeled_integration']['surface_scenario']
        self.assertEqual(s['measurement_only']['status'],'calculated')
        self.assertAlmostEqual(s['measurement_only']['physical_ia_sqft'],5000)
        self.assertEqual(r['economics']['measurement_only']['status'],'blocked')

    def test_canopy_known_and_hidden_ground_assumptions_are_separate(self):
        c=fixture();c['features']['features']=[candidate('canopy',box(0,0,30.48,30.48))]
        r=assess(c);scenarios=r['modeled_integration']['canopy_scenarios']
        self.assertEqual(scenarios[0]['status'],'blocked');self.assertEqual(scenarios[1]['status'],'calculated')
        self.assertAlmostEqual(scenarios[1]['area_sqft'],10000)
        self.assertAlmostEqual(scenarios[1]['bill']['ledger']['new_iar_sqft'],5000)

    def test_known_pervious_cannot_be_reassigned_by_upper_record_bound(self):
        c=fixture();c['features']['features'].append({'id':'known-lawn','geometry':mapping(box(0,0,3.048,30.48)),
            'properties':{'layer':'surface','class':'pervious'}})
        c['assessment']['records']=[record()];s=rec_info(assess(c))['runs'][0]['scenarios']
        self.assertTrue(all(v['status']=='blocked' for v in s))

    def test_model_savings_respect_verified_rule_and_tariff_period(self):
        c=fixture();c['features']['features']=[candidate('canopy',box(0,0,30.48,30.48))]
        out=evaluate_assessment(c,frozen_gis(c),as_of='2029-01-01')['modeled_integration']
        self.assertEqual(out['surface_scenario']['status'],'blocked')
        self.assertTrue(all(v['status']=='blocked' for v in out['canopy_scenarios']))


class ModeledPresentationUnitTests(unittest.TestCase):
    def test_report_helpers_show_record_link_and_escape_source_text(self):
        from stormwater.assessment_report import modeled_record_section,modeled_combined_section
        c=fixture();c['assessment']['records']=[record()]
        info=rec_info(assess(c));info['basis']='<script>bad</script>'
        html=modeled_record_section(info)
        self.assertIn('AI and drainage estimates for this record',html)
        self.assertIn('upstream contributing area unknown',html)
        self.assertNotIn('<script>bad</script>',html);self.assertIn('&lt;script&gt;',html)
        self.assertIn('not statistical confidence',modeled_combined_section(assess(c)['modeled_integration']))

    def test_derived_record_and_ai_catchments_are_exported_with_model_status(self):
        from stormwater.report import export_geojson
        from drainage_core.engine import result_hash
        c=fixture();c['assessment']['records']=[record(gsi_id='G1')]
        # Inject the hydrology unit fixture into an otherwise complete frozen GIS result.
        g=analyze(c);g['modeled_integration']=build(c,g['measurement'],g['drainage'],fake_research(c))
        a=assess(c,g);data=export_geojson(c,{**g,'assessment':a})
        layers={f['properties'].get('layer') for f in data['features']}
        self.assertIn('ai_informed_catchment',layers);self.assertIn('modeled_assessment',layers)
        row=next(f for f in data['features'] if f['properties'].get('layer')=='modeled_assessment')
        self.assertEqual(row['properties']['record_id'],'r')
        self.assertEqual(row['properties']['receiver_id'],'G1')
        self.assertEqual(row['properties']['basis'],'modeled estimate; eligibility unverified')

    def test_engine_artifact_replays_and_policy_consumes_without_routing(self):
        from unittest.mock import patch
        from stormwater.jurisdictions.philadelphia import apply
        c=fixture();c['assessment']['records']=[record()];before=canonical(c)
        a=analyze(c);b=analyze(c)
        self.assertEqual(a['analysis_sha256'],b['analysis_sha256'])
        frozen=canonical(a)
        with patch('drainage_core.engine.routing',side_effect=AssertionError('Policy rerouted GIS')):
            out=apply(c,a)
        self.assertIn('modeled_integration',out['assessment'])
        self.assertEqual(canonical(a),frozen);self.assertEqual(canonical(c),before)


if __name__=='__main__':unittest.main()
