"""Repro: enrich_candidates' RGB fallback mixes measurement-image CRS (EPSG:2272) with a case
already moved to native terrain CRS (EPSG:26918) -> vegetation/roof-vegetation reported as 0 sq ft."""
import tempfile, numpy as np
from hashlib import sha256
from pathlib import Path
from rasterio.io import MemoryFile
from shapely.geometry import box, mapping
from drainage_core.geometry import reproject
from stormwater.automatic import enrich_candidates
# parcel in 2272, fully green image
p2272=box(2691200,238600,2691300,238700)
bounds=list(p2272.buffer(100).bounds)
img=np.zeros((3,300,300),'uint8'); img[1]=180; img[0]=60; img[2]=60
with MemoryFile() as m:
    with m.open(driver='PNG',width=300,height=300,count=3,dtype='uint8') as ds: ds.write(img)
    png=m.read()
d=Path(tempfile.mkdtemp()); f=d/'blob'; f.write_bytes(png)
info={'sha256':sha256(png).hexdigest(),'blob_path':str(f),'bounds':bounds,'crs':'EPSG:2272','source_vintage':'2025','acquisition_date':None}
p26918=reproject(p2272,'EPSG:2272','EPSG:26918')
roof={'type':'Feature','id':'r1','geometry':mapping(p26918),'properties':{'layer':'surface','class':'roof'}}
for crs,parcel in (('EPSG:2272',p2272),('EPSG:26918',p26918)):
    feats=[{**roof,'geometry':mapping(parcel)}]
    case={'id':'t','crs':crs,'area_crs':'EPSG:2272','parcel':mapping(parcel),'features':{'type':'FeatureCollection','features':feats},
          'imagery':info,'measurement_imagery':info,'automatic':{},'assessment':{'records':[]}}
    out=enrich_candidates(case)['automatic']
    print(crs,'image_vegetation_candidate_sqft=',out.get('image_vegetation_candidate_sqft'),'roof_vegetation_candidate_sqft=',out.get('roof_vegetation_candidate_sqft'),out.get('warnings'))
