import sys, tempfile, json
sys.path.insert(0,__import__('os').path.dirname(__import__('os').path.abspath(__file__)))
from harness import *
from stormwater.record_cache import SharedCache
systems=[sysf('1',(10,10,90,90),'P1')]
parcels=[parf('1',(0,0,100,100))]
w=World(systems,parcels,{'1':bill('1',1000)},parcel_error='Unable to complete operation (transient)')
with tempfile.TemporaryDirectory() as root:
    cache=SharedCache(root+'/public',fallback_roots=[],opener=w.opener)
    for attempt,kw in enumerate([{},{'refresh_stale':True},{'refresh_stale':True}],1):
        n=len(w.calls)
        try:p.run_scan(root,cache=cache,**kw);print(attempt,'ok')
        except Exception as e:print('attempt',attempt,kw,'->',type(e).__name__,str(e)[:70],'| new network calls:',len(w.calls)-n)
    n=len(w.calls);r=p.run_scan(root,cache=cache,refresh=True);print('--refresh ->',r['status'],'new calls',len(w.calls)-n, '(inventory re-downloaded:',any('GSI_SMP' in c for c in w.calls[n:]),')')
