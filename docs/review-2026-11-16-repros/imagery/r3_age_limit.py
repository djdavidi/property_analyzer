"""Repro: SharedCache's 30/90-day record age limit is bypassed when refresh=False
(server /api/property/assess calls lookup() and acquire_property() with refresh=False)."""
import io, json, tempfile
from pathlib import Path
from stormwater.record_cache import SharedCache
calls=[]
class R(io.BytesIO):
    def __enter__(s): return s
    def __exit__(s,*a): pass
def opener(req, timeout=None):
    calls.append(req.full_url); return R(b'{"Parcel":{"Shape":"NEW"}}')
url='https://stormwater.phila.gov/PwdWebApi/api/v1/parcel/12345'
with tempfile.TemporaryDirectory() as d:
    c=SharedCache(Path(d),fallback_roots=[],reuse_recent_records=True,opener=opener)
    c._store(url,b'{"Parcel":{"Shape":"OLD-2023"}}',retrieved_at='2023-01-01T00:00:00+00:00')
    r=c.fetch_json(url,refresh=False)
    print('refresh=False ->',r['data'],'| retrieved_at',r['provenance']['retrieved_at'],'| network calls',len(calls),'| reuse_events',c.reuse_events)
    r=c.fetch_json(url,refresh=True)
    print('refresh=True  ->',r['data'],'| network calls',len(calls))
