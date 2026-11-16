"""Repro: server maxRecordCount < requested page_size -> offset pagination skips records."""
import io, json, tempfile
from urllib.parse import urlparse, parse_qs
from drainage_core.sources import Cache, arcgis_features
TOTAL=2500; MAXREC=1000   # e.g. a layer with maxRecordCount=1000 (common ArcGIS default)
def opener(req, timeout=None):
    q=parse_qs(urlparse(req.full_url).query)
    off=int(q['resultOffset'][0]); n=min(int(q['resultRecordCount'][0]),MAXREC)
    ids=list(range(1,TOTAL+1))[off:off+n]
    body={'type':'FeatureCollection','features':[{'type':'Feature','id':i,'properties':{'objectid':i},'geometry':None} for i in ids]}
    if off+n<TOTAL: body['properties']={'exceededTransferLimit':True}
    class R(io.BytesIO):
        def __enter__(s): return s
        def __exit__(s,*a): pass
    return R(json.dumps(body).encode())
with tempfile.TemporaryDirectory() as d:
    c=Cache(d,opener=opener)
    # caller asks for 2000/page (e.g. a future/other caller); server caps to 1000
    r=arcgis_features('https://example.test/FeatureServer/0',c,{'outSR':'4326'},page_size=2000)
    got=sorted(f['id'] for f in r['features'])
    print('pages',len(r['sources']),'returned',len(got),'of',TOTAL,'missing e.g.',[i for i in range(1,TOTAL+1) if i not in set(got)][:3],'...')
    # Same with the code's own page_size=1000 but a 500-record server (many hosted layers / services)
    MAXREC=500
with tempfile.TemporaryDirectory() as d:
    MAXREC=500
    c=Cache(d,opener=opener)
    r=arcgis_features('https://example.test/FeatureServer/0',c,{'outSR':'4326'},page_size=1000)
    got=set(f['id'] for f in r['features'])
    print('maxRecordCount=500, page_size=1000: returned',len(got),'of',TOTAL,'; no error raised')
