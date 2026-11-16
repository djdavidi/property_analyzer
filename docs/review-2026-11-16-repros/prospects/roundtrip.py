import json, subprocess
import stormwater.assessment_sources as src, stormwater.soil_sources as soil
from stormwater import assessment_workflow as wf
from stormwater.acquisition import normalize_billing
old={'Parcel':{'GrossArea':10000,'ImpervArea':8000,'BldgType':'NonRes'},'ChargeSummary':{'GrossCreditSqFt':0,'ImpervCreditSqFt':0}}
new={'Parcel':{'GrossArea':10000,'ImpervArea':7500,'BldgType':'NonRes'},'ChargeSummary':{'GrossCreditSqFt':0,'ImpervCreditSqFt':0}}
src.discover=lambda case,cache,refresh=True:{'records':[],'observations':[{'provider':'PWD account/credit public record','raw_record':new}],'source_status':[],'sources':[]}
soil.acquire=lambda case,cache,refresh=False:case
case={'id':'pwd-1','baseline':normalize_billing(old)}       # as built server-side by acquired_case()/case.json
print('baseline ga_sqft repr:',repr(case['baseline']['ga_sqft']))
c=wf.gather(case,None)                                      # e.g. /api/property/assess on a stored case
wire=json.dumps(c)                                          # server response
browser=subprocess.run(['node','-e','process.stdout.write(JSON.stringify(JSON.parse(require("fs").readFileSync(0,"utf8"))))'],input=wire,capture_output=True,text=True).stdout
try:wf.reconcile_baseline(json.loads(browser),'reviewed invoice',True);print('reconcile ok')
except ValueError as e:print('reconcile after browser round-trip ->',e)
wf.reconcile_baseline(json.loads(wire),'reviewed invoice',True);print('same payload without JS number normalisation -> ok')
