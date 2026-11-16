"""Known-answer conditioning, topology, integration and conditional-ledger checks."""
from copy import deepcopy
from datetime import date
import json
import unittest
import numpy as np
from shapely.geometry import mapping, box, Point

from drainage_core.engine import new_case, analyze, canonical, result_hash
from drainage_core.geometry import measure
from drainage_core.research import fill_dem, condition, accumulate, run_model, feature_inputs, analyze_research


def fixture():
    c=new_case('Invented research check',crs='EPSG:32618')
    c['parcel']=mapping(box(0,0,7,7))
    c['features']['features']=[{'type':'Feature','id':'paving','geometry':c['parcel'],
                              'properties':{'layer':'surface','class':'pavement'}}]
    c['terrain']={'elevations':[[10-c*.1 for c in range(7)] for r in range(7)],
                  'cell_size':1,'origin':[0,7],'crs':c['crs'],'horizontal_unit':'m','vertical_unit':'m',
                  'settings':{'extent_sufficient':False,'max_flow_paths':0}}
    c['research_drainage']={'sensitivity':False,'features':[
        {'id':'garden','role':'gsi','gsi_id':'G1','geometry':mapping(box(3,3,4,4))}]}
    return c


def model(c):
    return run_model(c,measure(c),feature_inputs(c)[0])


class ResearchDrainageTests(unittest.TestCase):
    def test_fill_known_bowl_and_preserve_original(self):
        z=[[10]*5,[10,5,5,5,10],[10,5,1,5,10],[10,5,5,5,10],[10]*5]; frozen=deepcopy(z)
        np.testing.assert_array_equal(fill_dem(z),np.full((5,5),10))
        self.assertEqual(z,frozen)

    def test_fill_uses_lowest_spill_not_highest_boundary(self):
        z=[[10,10,4,10,10],[10,2,2,2,10],[10,2,1,2,10],[10]*5]
        self.assertEqual(fill_dem(z)[2,2],4)

    def test_nodata_is_open_unknown_not_filled(self):
        z=[[10]*5,[10,2,2,2,10],[10,2,None,2,10],[10]*5]
        out=fill_dem(z)
        self.assertTrue(np.isnan(out[2,2]));self.assertEqual(out[1,1],2)

    def test_invalid_terrain_and_units_rejected(self):
        for z in ([],[[float('inf')]],[[1],[2,3]]):
            with self.assertRaises(ValueError):fill_dem(z)
        c=fixture();c['terrain']['vertical_unit']='unknown'
        with self.assertRaises(ValueError):model(c)

    def test_paper_offsets_fill_then_burn_no_second_fill(self):
        c=fixture();c['terrain']['elevations']=[[10]*7 for _ in range(7)]
        c['terrain']['elevations'][3][3]=1
        out=condition(c['terrain'],feature_inputs(c)[0])
        self.assertEqual(out['filled'][3,3],10)
        self.assertAlmostEqual(out['adjusted'][3,3],9.09)
        self.assertEqual(out['fill_depth'][3,3],9)

    def test_independent_vertical_units_convert_offsets(self):
        c=fixture();features=feature_inputs(c)[0]
        m=condition(c['terrain'],features)['adjusted']
        c['terrain']['vertical_unit']='ft'
        c['terrain']['elevations']=(np.array(c['terrain']['elevations'])/.3048).tolist()
        np.testing.assert_allclose(condition(c['terrain'],features)['adjusted']*.3048,m)

    def test_contour_and_lidar_parameters_are_distinct(self):
        c=fixture();f=feature_inputs(c)[0]
        a=condition(c['terrain'],f);b=condition(c['terrain'],f,dem_type='contour')
        self.assertAlmostEqual(a['features'][0]['offset_m'],-.91)
        self.assertAlmostEqual(b['features'][0]['offset_m'],-2.44)

    def test_building_wins_overlap_and_roof_is_excluded(self):
        c=fixture();c['research_drainage']['features'].append({'id':'building','role':'building','geometry':mapping(box(3,3,4,4))})
        out=condition(c['terrain'],feature_inputs(c)[0])
        self.assertAlmostEqual(out['adjusted'][3,3]-out['filled'][3,3],9.14)
        r=model(c);self.assertEqual(r['roof_excluded_cells'],1)
        self.assertEqual(r['routed_ground_cells'],48)
        self.assertTrue(r['invariants']['terminal_accumulation_equals_routed_cells'])

    def test_curb_cut_opens_berm_but_not_building(self):
        c=fixture();g=mapping(box(3,3,4,4))
        fs=[{'id':'berm','role':'berm','geometry':g},{'id':'cut','role':'curb_cut','geometry':g}]
        out=condition(c['terrain'],fs);self.assertAlmostEqual(out['adjustment'][3,3],-.91)
        fs.append({'id':'roof','role':'building','geometry':g})
        self.assertAlmostEqual(condition(c['terrain'],fs)['adjustment'][3,3],9.14)

    def test_existing_untyped_vector_barrier_is_not_dropped(self):
        c=fixture();c['features']['features'].append({'id':'curb','geometry':mapping(box(.95,0,1.05,7)),
            'properties':{'layer':'barrier'}})
        r=model(c)
        self.assertEqual(r['routed_ground_cells'],35)
        self.assertTrue(r['invariants']['terminal_accumulation_equals_routed_cells'])

    def test_narrow_feature_loss_is_reported_and_touching_can_test_it(self):
        c=fixture();fs=[{'id':'thin','role':'berm','geometry':mapping(box(3.01,2,3.05,5))}]
        self.assertEqual(condition(c['terrain'],fs)['features'][0]['raster_cells'],0)
        self.assertGreater(condition(c['terrain'],fs,all_touched=True)['features'][0]['raster_cells'],0)

    def test_accumulation_hand_calculated_branch_and_cycle(self):
        nexts=[[[1,1],[1,1]],[[1,1],None]]
        counts=accumulate(nexts,[['sink']*2 for _ in range(2)])
        self.assertEqual(counts.tolist(),[[1,1],[1,4]])
        with self.assertRaises(ValueError):accumulate([[[0,1],[0,0]]],[['x','x']])

    def test_direct_gsi_basin_area_and_mass_balance(self):
        c=fixture();r=model(c)
        self.assertEqual(len(r['catchments']),1)
        self.assertGreater(r['known_ia_union_sqft'],0)
        self.assertEqual(r['terminal_accumulation_cells'],49)
        self.assertEqual(r['routed_ground_cells'],49)
        self.assertTrue(r['invariants']['terminal_accumulation_equals_routed_cells'])
        self.assertEqual(r['catchments'][0]['off_parcel_area_sqft'],0)

    def test_inlet_upstream_connection_aggregates_only_when_supplied(self):
        c=fixture();c['research_drainage']['features'].append({'id':'drain','role':'inlet',
            'geometry':mapping(Point(1.5,3.5)),'receives_at':'G1','connection_evidence':'unknown'})
        before=model(c)
        c['research_drainage']['features'][-1]['connection_evidence']='scenario'
        after=model(c)
        self.assertGreater(after['known_ia_union_sqft'],before['known_ia_union_sqft'])
        self.assertTrue(any(b['gsi_id']=='G1' and ['drain','garden'] in b['upstream_trace'] for b in after['micro_basins']))

    def test_connection_cycle_stays_unassigned(self):
        c=fixture();g=mapping(Point(1.5,3.5))
        c['research_drainage']['features'].extend([
            {'id':'A','role':'inlet','geometry':g,'receives_at':'B','connection_evidence':'scenario'},
            {'id':'B','role':'inlet','geometry':g,'receives_at':'A','connection_evidence':'scenario'}])
        self.assertTrue(any('cycle' in b['reason'] for b in model(c)['micro_basins']))

    def test_existing_grid_inlet_and_pipe_link_inform_research(self):
        c=fixture();c['terrain']['inlets']=[{'id':'drain','cell':[3,1]}]
        c['terrain']['connections']=[{'from':'drain','to':'garden','evidence':'documented'}]
        r=model(c)
        self.assertTrue(any(['drain','garden'] in b['upstream_trace'] for b in r['micro_basins']))

    def test_research_vectors_follow_case_projection(self):
        from drainage_core.projection import project_case
        c=fixture();before=canonical(c);out=project_case(c,'EPSG:3857')
        self.assertNotEqual(out['research_drainage']['features'][0]['geometry'],c['research_drainage']['features'][0]['geometry'])
        self.assertEqual(canonical(c),before)

    def test_overlapping_receivers_not_double_counted(self):
        c=fixture();f=deepcopy(c['research_drainage']['features'][0]);f.update(id='second',gsi_id='G2')
        c['research_drainage']['features'].append(f)
        r=model(c);self.assertEqual(r['catchments'],[])
        self.assertTrue(any('Ambiguous' in b['reason'] for b in r['micro_basins']))

    def test_offparcel_contributions_are_retained(self):
        c=fixture();c['parcel']=mapping(box(3,3,4,4));r=model(c)
        self.assertGreater(r['catchments'][0]['off_parcel_area_sqft'],0)
        self.assertLessEqual(r['known_ia_union_sqft'],1/.09290304+.00001)

    def test_underground_footprint_never_becomes_inlet(self):
        c=fixture();c['research_drainage']['features']=[]
        c['features']['features'].append({'id':'underground','geometry':mapping(box(3,3,4,4)),
            'properties':{'layer':'footprint','kind':'system_footprint','gsi_system_type':'Subsurface Basin'}})
        fs,omitted=feature_inputs(c);self.assertEqual(fs,[]);self.assertEqual(len(omitted),1)
        self.assertEqual(model(c)['catchments'],[])

    def test_unknown_ground_is_not_known_managed_ia(self):
        c=fixture();c['features']['features']=[];r=model(c)
        self.assertEqual(r['known_ia_union_sqft'],0)
        self.assertGreater(r['catchments'][0]['potential_ia_upper_sqft'],0)

    def test_sensitivity_and_hashes_replay_without_mutation(self):
        c=fixture();c['research_drainage']['sensitivity']=True;before=canonical(c)
        a=analyze(c);b=analyze(c);r=a['research_drainage']
        self.assertEqual(len(r['sensitivity']),3)
        self.assertEqual(r,b['research_drainage']);self.assertEqual(before,canonical(c))
        self.assertEqual(a['analysis_sha256'],result_hash(a))
        self.assertTrue(all(v['invariants']['terminal_accumulation_equals_routed_cells'] for v in [r['primary']]+r['sensitivity']))
        self.assertTrue(r['sensitivity'][-1]['nodata_cells']>0)
        self.assertEqual(r['validation']['status'],'incomplete')

    def test_addition_does_not_change_current_method_or_measurement(self):
        c=fixture();old=deepcopy(c);old['research_drainage']['enabled']=False
        a=analyze(c);b=analyze(old)
        self.assertEqual(a['drainage'],b['drainage']);self.assertEqual(a['measurement'],b['measurement'])

    def test_subpixel_roof_sliver_cannot_be_counted_as_managed_ground(self):
        c=fixture();c['features']['features']=[{'id':'roof','geometry':mapping(box(3.01,3.01,3.1,3.1)),
            'properties':{'layer':'surface','class':'roof'}}]
        r=model(c)
        self.assertEqual(r['known_ia_union_sqft'],0)
        self.assertGreater(sum(v['potential_ia_upper_sqft'] for v in r['catchments']),0)

    def test_diagnostic_geotiffs_preserve_grid_units_and_array_hashes(self):
        import tempfile
        from pathlib import Path
        import rasterio
        from drainage_core.research import write_diagnostic_rasters
        c=fixture();c['terrain']['elevations'][0][0]=None
        r=analyze(c)['research_drainage']
        with tempfile.TemporaryDirectory() as d:
            files=write_diagnostic_rasters(d,r);self.assertEqual(len(files),7)
            with rasterio.open(Path(d)/'filled_elevations.tif') as src:
                self.assertEqual(src.crs.to_string(),c['crs'])
                self.assertEqual(src.tags()['vertical_unit'],'m')
                self.assertEqual(src.tags()['source_array_sha256'],r['primary']['raster_sha256']['filled_elevations'])
                self.assertTrue(src.read(1,masked=True).mask[0,0])
                self.assertEqual(src.transform.c,0);self.assertEqual(src.transform.f,7)

    def test_report_export_include_both_methods(self):
        from drainage_core.report import render_report,export_geojson
        c=fixture();a=analyze(c)
        self.assertIn('Villanova/Temple additional analysis',render_report(c,a))
        data=export_geojson(c,a)
        self.assertTrue(any(f['properties'].get('layer')=='research_catchment' for f in data['features']))

    def test_conditional_bill_scenarios_preserve_baseline_and_evidence(self):
        from stormwater.assessment_policy import evaluate_assessment
        c=fixture();c['baseline']={'ga_sqft':6000,'ia_sqft':5001,'bill_date':'2026-09-01','property_type':'NonRes'}
        c['terrain']['settings']['extent_sufficient']=True  # Explicit invented extent for arithmetic unit only.
        original=canonical(c);gis=analyze(c);a=evaluate_assessment(c,gis,as_of='2026-11-15')
        research=a['research_drainage_scenarios']['scenarios'][0]
        self.assertEqual(research['status'],'calculated')
        self.assertEqual(research['gross_monthly_reduction'],7.05)
        self.assertEqual(research['gross_annual_reduction'],84.60)
        self.assertEqual(original,canonical(c))
        self.assertEqual(a['economics']['modeled']['status'],'blocked')
        self.assertFalse(any(cat['status']=='screen_pass' for cat in a['categories']))

    def test_unreconciled_existing_credit_still_blocks_research_savings(self):
        from stormwater.assessment_policy import evaluate_assessment
        c=fixture();c['baseline']={'ga_sqft':6000,'ia_sqft':5000,'bill_date':'2026-09-01',
                                 'existing_ia_credit_sqft':500,'existing_credits_spatially_reconciled':False}
        c['terrain']['settings']['extent_sufficient']=True
        a=evaluate_assessment(c,analyze(c),as_of='2026-11-15')
        s=a['research_drainage_scenarios']['scenarios'][0]
        self.assertEqual(s['status'],'blocked');self.assertIsNone(s['gross_monthly_reduction'])
        self.assertTrue(any('reconciliation' in v for v in s['reasons']))

    def test_missing_known_surface_does_not_generate_zero_savings_claim(self):
        from stormwater.assessment_policy import evaluate_assessment
        c=fixture();c['features']['features']=[];c['baseline']={'ga_sqft':6000,'ia_sqft':5000}
        s=evaluate_assessment(c,analyze(c),as_of='2026-11-15')['research_drainage_scenarios']['scenarios'][0]
        self.assertEqual(s['status'],'blocked');self.assertIsNone(s['gross_annual_reduction'])

    def test_unknown_ground_upper_scenario_is_explicit_and_does_not_change_measurement(self):
        from stormwater.assessment_policy import evaluate_assessment
        c=fixture();c['features']['features']=[];c['baseline']={'ga_sqft':6000,'ia_sqft':5001}
        c['terrain']['settings']['extent_sufficient']=True
        gis=analyze(c);before=canonical(gis)
        variants=evaluate_assessment(c,gis,as_of='2026-11-15')['research_drainage_scenarios']['scenarios']
        self.assertEqual(variants[0]['status'],'blocked')
        self.assertEqual(variants[1]['surface_assumption'],'unknown_ground_assumed_impervious')
        self.assertTrue(variants[1]['assumed_prerequisites']['all_unclassified_catchment_ground_is_impervious'])
        self.assertEqual(variants[1]['status'],'calculated');self.assertGreater(variants[1]['gross_annual_reduction'],0)
        self.assertEqual(canonical(gis),before);self.assertEqual(gis['measurement']['ia_sqft'],0)


if __name__=='__main__':unittest.main()
