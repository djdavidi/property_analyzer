import sys, tempfile, json
sys.path.insert(0,__import__('os').path.dirname(__import__('os').path.abspath(__file__)))
from harness import *
from pathlib import Path
from stormwater.record_cache import SharedCache
from stormwater.prospect_jobs import ProspectJobs
# Two projects on two parcels; parcel 2's billing returns a public error.
systems=[sysf('1',(10,10,90,90),'P1'),sysf('2',(210,10,290,90),'P2')]
parcels=[parf('1',(0,0,100,100)),parf('2',(200,0,300,100))]
b2=bill('2',5000);b2['ChargeSummary']['Errors']=['temporarily unavailable']
w=World(systems,parcels,{'1':bill('1',1000),'2':b2})
with tempfile.TemporaryDirectory() as root:
    cache=SharedCache(root+'/public',fallback_roots=[],opener=w.opener)
    r=p.run_scan(root,cache=cache)
    raw=(Path(root)/'runs'/r['id']/'results.json').read_text()
    g=json.dumps(parcels[0]['geometry']['coordinates'],separators=(',',':'))
    print('failures:',[(f['parcel_id'],f['error'][:40]) for f in r['failures']])
    print('copies of parcel 1 geometry in results.json:',raw.count(g))
    try:p.update_selected(root,['2'],cache=cache);print('retry ok')
    except ValueError as e:print('selected retry of failed parcel 2 ->',e)
    w.bills['2']=bill('2',5000)  # source recovers
    jobs=ProspectJobs(root)
    try:jobs.start(mode='update');print('full rescan via UI job allowed')
    except ValueError as e:print('UI full rescan ->',e)
