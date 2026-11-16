import sys; sys.path.insert(0,'tests')
from stormwater.renewals import credit_renewals
src={'source_url':'https://example.test/x'}
for ev in ({'id':'a','status':'terminated','effective_from':'2024-01-01','terminated_on':'2027-03-01',**src},
           {'id':'b','status':'expired','effective_from':'2021-01-01','expires_on':'2025-01-01',**src},
           {'id':'c','status':'awarded','effective_from':'2024-01-01',**src}):
    r=credit_renewals([ev],as_of='2026-11-15')[0]; print(ev['status'],'->',r['status'],r['missing'],r['warnings'])
from test_assessment_policy import fixture, record, run
c,g=fixture(); r=record('industrial_npdes'); r['facts']['compliance_through']='2026-09-30'; c['assessment']['records']=[r]
out=run(c,g); e=out['categories'][3]['records'][0]; print('NPDES with last DMR period ending 2026-09-30, as_of 2026-11-15:',e['status'],'failed=',e['failed'])
print('economics documented:',out['economics']['documented']['status'],out['economics']['documented'].get('reasons'))
