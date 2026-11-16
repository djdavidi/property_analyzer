import sys, tempfile, json, datetime as dt
sys.path.insert(0,__import__('os').path.dirname(__import__('os').path.abspath(__file__)))
from harness import *
from stormwater.record_cache import SharedCache
systems=[sysf(str(i),(i*200+10,10,i*200+90,90),f'P{i}') for i in range(1,4)]
parcels=[parf(str(i),(i*200,0,i*200+100,100)) for i in range(1,4)]
w=World(systems,parcels,{str(i):bill(str(i),1000*i) for i in range(1,4)})
class Later(dt.datetime):
    @classmethod
    def now(cls,tz=None):return dt.datetime.now(tz)+dt.timedelta(days=45)
with tempfile.TemporaryDirectory() as root:
    cache=SharedCache(root+'/public',fallback_roots=[],opener=w.opener)
    r=p.run_scan(root,cache=cache);print('day 0 ranked:',[s['parcel_ids'] for s in r['top']])
    p.datetime=Later                                    # 45 days later: bills are stale (>30d), inventory/parcels fresh (<90d)
    def down(req,timeout=None):raise OSError('PWD API timeout')
    cache.opener=down
    r=p.run_scan(root,cache=cache,refresh_stale=True)   # what the UI 'update' / CLI --update-stale does
    print('day 45 update-stale with outage: ranked',[s['parcel_ids'] for s in r['top']],'failures',len(r['failures']))
    r=p.run_scan(root,cache=cache,max_requests=1,refresh_stale=False)
    print('day 45 plain scan (no refresh): ranked',[s['parcel_ids'] for s in r['top']],'needs_review',[s['needs_record_review'] for s in r['top']])
