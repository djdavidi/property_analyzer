import stormwater.assessment_sources as src, stormwater.soil_sources as soil
from stormwater import assessment_workflow as wf
from stormwater.acquisition import normalize_billing
raw={'Parcel':{'GrossArea':10000,'ImpervArea':8000,'BldgType':'NonRes'},'ChargeSummary':{'GrossCreditSqFt':0,'ImpervCreditSqFt':0}}
URL='https://example/records'
REC={'id':'r1','category':'green_roof','decision':'candidate','basis':'public_candidate','facts':{'a':1},'source':{'url':URL}}
state={'records':[REC]}
def fake_discover(case,cache,refresh=True):
    return {'records':[dict(r) for r in state['records']],'observations':[{'provider':'PWD account/credit public record','raw_record':raw}],
            'source_status':[{'url':URL,'status':'retrieved'}],'sources':[]}
src.discover=fake_discover; soil.acquire=lambda case,cache,refresh=False: case
case={'id':'x','baseline':{**normalize_billing(raw),'ia_sqft':7000.0,'actual_bill_verified':True}}
c1=wf.gather(case,None)
print('run1 baseline_refresh:',c1['assessment']['baseline_refresh']['status'],c1['assessment']['baseline_refresh']['fields_changed'])
c2=wf.reconcile_baseline(c1,'Invoice verified; keep 7000 sqft',False)
print('after review:',c2['assessment']['baseline_refresh']['status'])
c3=wf.gather(c2,None)
print('run2 (identical public data) baseline_refresh:',c3['assessment']['baseline_refresh']['status'])
# Disappearance then reappearance
state['records']=[]
c4=wf.gather(c3,None)
print('record after omission:',c4['assessment']['records'][0].get('source_update',{}).get('status'))
state['records']=[REC]
c5=wf.gather(c4,None)
print('record after unchanged reappearance:',c5['assessment']['records'][0].get('source_update',{}).get('status'), '|', c5['assessment']['records'][0].get('source_update',{}).get('reason'))
