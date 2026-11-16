"""Check fix #27: undeclared GeoJSON CRS accepted as requested; ESRI-only wkid raises non-SourceError."""
import io, json, tempfile
from drainage_core.sources import Cache, arcgis_features, SourceError
from pyproj import CRS
class R(io.BytesIO):
    def __enter__(s): return s
    def __exit__(s,*a): pass
bodies={}
def opener(req, timeout=None): return R(json.dumps(bodies['b']).encode())
lonlat={'type':'FeatureCollection','features':[{'type':'Feature','id':1,'properties':{},
   'geometry':{'type':'Point','coordinates':[-75.17,39.96]}}]}
with tempfile.TemporaryDirectory() as d:
    bodies['b']=lonlat
    r=arcgis_features('https://x.test/FS/0',Cache(d,opener=opener),{'outSR':'2272'})
    print('RFC7946 lon/lat body with no crs member, requested 2272 -> labelled',r['crs'],r['features'][0]['geometry']['coordinates'])
with tempfile.TemporaryDirectory() as d:
    bodies['b']={'spatialReference':{'wkid':102729},'features':[]}
    try:
        arcgis_features('https://x.test/FS/0',Cache(d,opener=opener),{'outSR':'2272','f':'json'})
        print('wkid 102729 accepted')
    except SourceError as e: print('SourceError',e)
    except Exception as e: print('NON-SourceError escapes:',type(e).__mro__[:3],str(e)[:80])
