"""Repro: an HTTP-200 ArcGIS/SDA error body overwrites the last-good manifest, so
(a) the outage fallback (_Fallback / post_json) can no longer reach the good snapshot and
(b) the error is replayed forever on non-refresh reads."""
import io, json, tempfile
from drainage_core.sources import Cache, SourceError
from stormwater.assessment_sources import _Fallback
class R(io.BytesIO):
    def __enter__(s): return s
    def __exit__(s,*a): pass
mode={'v':'good'}
def opener(req, timeout=None):
    if mode['v']=='good': return R(json.dumps({'features':[{'id':1,'properties':{}}]}).encode())
    return R(json.dumps({'error':{'code':500,'message':'Unable to complete operation.'}}).encode())
url='https://example.test/FeatureServer/0/query?f=geojson'
with tempfile.TemporaryDirectory() as d:
    c=Cache(d,opener=opener)
    print('1 good fetch:',c.fetch_json(url,refresh=True)['data'])
    mode['v']='transient-error'
    p=_Fallback(c)
    try: p.fetch_json(url,refresh=True)
    except SourceError as e: print('2 refresh during transient error -> fallback FAILED:',e)
    mode['v']='good'
    try: print(c.fetch_json(url,refresh=False)['data'])
    except SourceError as e: print('3 later non-refresh read after service recovered -> still error:',str(e)[:90])
    # post_json (Soil Data Access) path
    mode['v']='good'; sda='https://sda.example.test/Tabular/post.rest'
    print('4 SDA good:',c.post_json(sda,{'query':'q'},refresh=True)['data'])
    mode['v']='transient-error'
    try: c.post_json(sda,{'query':'q'},refresh=True)
    except SourceError as e: print('5 SDA refresh error, no reuse of dated good response:',str(e)[:80])
    mode['v']='good'
    try: c.post_json(sda,{'query':'q'},refresh=False)
    except SourceError as e: print('6 SDA non-refresh after recovery -> sticky error:',str(e)[:80])
