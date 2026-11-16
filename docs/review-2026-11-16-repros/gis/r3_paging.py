# Repro: arcgis_features advances resultOffset by page_size, not by records received.
# A service whose maxRecordCount (here 400) is below page_size (1000) returns
# 400 rows + exceededTransferLimit=true; the next request starts at 1000, so
# rows 400-999, 1400-1999 ... are silently skipped and the result is "complete".
import io, json, tempfile
from urllib.parse import urlparse, parse_qs
from drainage_core.sources import Cache, arcgis_features
TOTAL=2500; MAXREC=400
class Resp(io.BytesIO):
    def __enter__(self): return self
    def __exit__(self,*a): return False
def opener(req,timeout=None):
    q=parse_qs(urlparse(req.full_url).query)
    off=int(q['resultOffset'][0]); n=min(int(q['resultRecordCount'][0]),MAXREC)
    rows=list(range(off,min(off+n,TOTAL)))
    body={'type':'FeatureCollection','features':[{'type':'Feature','id':i+1,'properties':{'objectid':i+1},
           'geometry':{'type':'Point','coordinates':[-75.1,39.9]}} for i in rows]}
    if off+n<TOTAL: body['properties']={'exceededTransferLimit':True}
    return Resp(json.dumps(body).encode())
with tempfile.TemporaryDirectory() as d:
    fc=arcgis_features('https://example.invalid/arcgis/rest/services/x/FeatureServer/0',Cache(d,opener=opener))
    ids=sorted(f['id'] for f in fc['features'])
    print('service rows:',TOTAL,' returned:',len(ids),' pages:',len(fc['sources']),' first gap after id',next(i for a,i in zip(ids,ids[1:]) if i!=a+1)-1 if len(ids)>1 else None,' no error raised')
