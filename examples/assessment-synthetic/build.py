"""Build an invented, offline existing-site workflow; no real eligible benefit."""
import json
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT))
from shapely.geometry import box,mapping
from stormwater.cases import new_case,CaseStore
from stormwater.assessment_workflow import ensure_assessment


def build():
    case=new_case('Existing-site assessment — entirely invented systems and records')
    case.update(id='existing-site-synthetic',crs='EPSG:26918',synthetic_case=True,
                created_at='2026-11-15T00:00:00Z',parcel=mapping(box(0,0,30.48,30.48)))
    def region(start,width=3.048):return mapping(box(start,0,start+width,30.48))
    case['features']['features']=[
        {'type':'Feature','id':'roof','geometry':region(0,6.096),'properties':{'layer':'surface','class':'roof'}},
        {'type':'Feature','id':'paving','geometry':region(6.096,18.288),'properties':{'layer':'surface','class':'pavement'}},
        {'type':'Feature','id':'lawn','geometry':region(24.384,6.096),'properties':{'layer':'surface','class':'pervious'}}]
    case['baseline']={'ga_sqft':10000,'ia_sqft':8000,'actual_bill_verified':False,'bill_date':'2026-11-15',
                      'source':'Invented billing baseline, not an invoice','published_monthly_total':130}
    common={key:True for key in ('existing_installation','account_current','physical_area_confirmed',
        'parcel_allocation_confirmed','routing_confirmed','approved_record_drawings','current_condition_confirmed',
        'maintenance_documented','professional_reviewed')}
    a=ensure_assessment(case)
    for category,start in [('green_roof',0),('permeable_pavement',6.096),('direct_discharge',12.192)]:
        facts={**common,'treatment_depth_inches':1.5}
        if category=='permeable_pavement':facts.update({key:True for key in ('material_confirmed','construction_documented',
            'storage_documented','infiltration_or_underdrain_documented')})
        if category=='direct_discharge':
            facts.update({key:True for key in ('catchment_confirmed','route_confirmed','outfall_confirmed',
                'destination_confirmed','no_city_infrastructure','ownership_confirmed','no_erosion_or_detriment',
                'site_plan_documented','photographs_current','private_connections_resolved')})
            facts.update(waterway_name='Invented waterway',outfall_id='invented-outfall',upstream_smp_present=False)
        a['records'].append({'id':category+'-modeled','category':category,'decision':'confirmed','basis':'modeled',
            'geometry':region(start),'footprint_geometry':region(start,1.524),'facts':facts,
            'evidence_refs':[{'source_url':'https://example.test/entirely-invented-evidence','page':1}]})
    facts={key:True for key in ('account_current','site_match','operator_match','industrial_stormwater','active',
        'compliance_previous_12_months','permit_documented','discharge_monitoring_reports_previous_12_months')}
    facts.update(permit_id='SYNTHETIC-NOT-A-PERMIT',effective_from='2023-03-24',expires_on='2028-03-23',
                 compliance_from='2025-11-15',compliance_through='2026-11-15')
    a['records'].append({'id':'industrial-modeled','category':'industrial_npdes','decision':'confirmed',
        'basis':'modeled','facts':facts,'evidence_refs':[{'source_url':'https://example.test/not-a-real-permit','page':2}]})
    a['credit_history']=[{'id':'unexplained-flag','credit_id':'unexplained-flag','category':'unknown','status':'expired',
        'notes':'Invented unexplained flag. No award, lapse date or refund is inferred.'},
        {'id':'old-illustrative-award','credit_id':'prior-roof','category':'green_roof','status':'awarded',
         'effective_from':'2020-01-01','expires_on':'2024-01-01','credited_area_sqft':500,
         'source_url':'https://example.test/invented-historical-letter'},
        {'id':'illustrative-renewal','credit_id':'prior-roof','supersedes':'old-illustrative-award','category':'green_roof',
         'status':'renewed','effective_from':'2024-01-01','expires_on':'2026-12-31','credited_area_sqft':500,
         'source_url':'https://example.test/invented-renewal'}]
    case['warnings']=['SYNTHETIC: all geometry, facts, permits, invoices and history are invented. No approval, installed real system, award or real savings is established.']
    case['assumptions']=['All new category prerequisites are conditional modeled inputs, not document-verified facts.',
        'Illustrative historical credit quantities are not presumed current received benefits; baseline is separate.',
        'No terrain or independent measurement references supplied. No empirical IA/drainage validation.']
    return case

if __name__=='__main__':
    case=build()
    if '--fixture' in sys.argv:
        (Path(__file__).parent/'case.json').write_text(json.dumps(case,indent=2)+'\n')
    else:
        result=CaseStore().save(case)
        print('Saved data/cases/'+case['id']+'; open this saved case in the local Philadelphia app.')
        print(json.dumps({'categories':[{k:r[k] for k in ('category','status')} for r in result['assessment']['categories']],
                          'modeled':result['assessment']['economics']['modeled'],'limitations':case['warnings']},indent=2))
