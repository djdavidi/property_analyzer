import sys, tempfile, json
sys.path.insert(0,__import__('os').path.dirname(__import__('os').path.abspath(__file__)))
from harness import *
from stormwater.record_cache import SharedCache
# Project P1: big system on parcel 1 (seed) + a second system wholly on parcel 2.
systems=[sysf('1',(10,10,90,90),'P1'),sysf('2',(210,10,240,40),'P1')]
parcels=[parf('1',(0,0,100,100)),parf('2',(200,0,300,100))]
bills={'1':bill('1',1000),'2':bill('2',5000)}
w=World(systems,parcels,bills)
with tempfile.TemporaryDirectory() as root:
    cache=SharedCache(root+'/public',fallback_roots=[],opener=w.opener)
    r=p.run_scan(root,cache=cache,max_requests=80)
    print('matched parcels:',r['counts']['matched_parcels'],'ranked:',[s['parcel_ids'] for s in r['top']])
    print('ambiguous:',json.dumps(r['ambiguous_matches']))
    print('parcel queries:',sum('PWD_PARCELS' in c for c in w.calls))
