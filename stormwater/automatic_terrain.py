"""Discover a public native USGS window; never infer elevation units from values."""
from hashlib import sha256
import json
import math
import re
from urllib.parse import urlencode,urlparse
from pathlib import Path
import rasterio
from rasterio.windows import from_bounds,Window
from shapely.geometry import shape,box
from drainage_core.geometry import reproject
from drainage_core.projection import project_case,warp_display
from drainage_core.raster import import_dem


def acquire(case,cache,*,case_root=None):
    if case.get('terrain'):return case,{'provider':'Elevation','status':'saved_native_grid','claim':'Saved terrain retained; current grading and private connections unverified'}
    rejected=None
    if case_root is not None:
        from .terrain_reuse import reuse
        reused,rejected=reuse(case,case_root,cache.root)
        if reused.get('terrain'):return reused,rejected
    parcel=shape(case['parcel']);ll=reproject(parcel,case['crs'],'EPSG:4326')
    try:
        index=cache.fetch_json('https://tnmaccess.nationalmap.gov/api/v1/products?'+urlencode({
            'bbox':','.join(map(str,ll.bounds)),'datasets':'Digital Elevation Model (DEM) 1 meter','max':5,'outputFormat':'JSON'}))
    except Exception as exc:
        if rejected:raise ValueError('Saved terrain preference rejected: '+rejected.get('error','unknown')+'; remote discovery unavailable: '+str(exc)) from exc
        raise
    errors=[]
    for item in index['data'].get('items',[]):
        url=item.get('downloadURL','');parsed=urlparse(url)
        if parsed.scheme!='https' or parsed.hostname!='prd-tnm.s3.amazonaws.com' or '/1m/Projects/' not in url:continue
        try:
            project=url.split('/Projects/')[1].split('/')[0];filename=url.rsplit('/',1)[-1]
            metadata_url='https://thor-f5.er.usgs.gov/ngtoc/metadata/waf/elevation/1_meter/geotiff/'+project+'/'+filename[:-4]+'.xml'
            metadata=cache.fetch_bytes(metadata_url)
            from xml.etree import ElementTree as ET
            xml=ET.fromstring(metadata['content']);text=' '.join(xml.itertext())
            if not re.search(r'elevation values are in meters',text,re.I) or 'NAVD88' not in text:
                raise ValueError('Tile metadata does not explicitly establish metre elevations/NAVD88')
            with rasterio.Env(GDAL_DISABLE_READDIR_ON_OPEN='EMPTY_DIR',CPL_VSIL_CURL_ALLOWED_EXTENSIONS='.tif',
                    GDAL_HTTP_CONNECTTIMEOUT='10',GDAL_HTTP_TIMEOUT='20'):
                with rasterio.open(url) as ds:
                    from pyproj import CRS
                    if abs(CRS(ds.crs).axis_info[0].unit_conversion_factor-1)>1e-9:raise ValueError('Automatic native terrain currently requires verified horizontal metres')
                    region=reproject(parcel,case['crs'],ds.crs).buffer(45.72,join_style='mitre')
                    if not box(*ds.bounds).covers(region):raise ValueError('Tile lacks full parcel and routing buffer')
                    win=from_bounds(*region.bounds,transform=ds.transform)
                    left,top=math.floor(win.col_off),math.floor(win.row_off);right,bottom=math.ceil(win.col_off+win.width),math.ceil(win.row_off+win.height)
                    if (right-left)*(bottom-top)>250000:raise ValueError('Native terrain window exceeds250000 cells; no silent downsampling')
                    window=Window(left,top,right-left,bottom-top)
                    with rasterio.io.MemoryFile() as mem:
                        profile=ds.profile.copy();profile.update(driver='GTiff',width=right-left,height=bottom-top,
                            transform=ds.window_transform(window),compress='deflate')
                        with mem.open(**profile) as target:target.write(ds.read(window=window));target.update_tags(**ds.tags())
                        content=mem.read()
                    target_crs=ds.crs.to_string()
            _,provenance=cache._store('derived:usgs-native-window-'+sha256(content).hexdigest(),content,
                {'source_url':url,'metadata_url':metadata_url,'metadata_sha256':metadata['provenance']['sha256'],
                 'crs':target_crs,'horizontal_unit':'m','vertical_unit':'m','vertical_datum':'NAVD88',
                 'window':[left,top,right-left,bottom-top],'processing':'Native HTTP range window; no elevation resampling'})
            path=cache.root/'blobs'/provenance['sha256'];terrain=import_dem(path,vertical_unit='m')
            out=project_case(case,target_crs) if case['crs']!=target_crs else case
            if case['crs']!=target_crs:
                out['imagery']=warp_display(case,target_crs,cache.root)
                if out.get('imagery'):out['sources'].append({'sha256':out['imagery']['sha256'],'url':None,
                    'crs':target_crs,'processing':out['imagery'].get('processing'),'retrieved_at':provenance['retrieved_at']})
            terrain['grid']['settings']={'extent_sufficient':False,'required_buffer_native_units':45.72,'max_flow_paths':30}
            out['terrain']=terrain['grid'];out['sources'].extend([index['provenance'],metadata['provenance'],provenance])
            return out,{'provider':'Elevation','status':'source_model','source_url':url,'sha256':provenance['sha256'],
                'saved_terrain_attempt':rejected,
                'metadata_sha256':metadata['provenance']['sha256'],'vertical_unit':'m','vertical_datum':'NAVD88',
                'claim':'Modeled surface routing; roofs/private connections and sufficient watershed extent remain unresolved. Exact capture date/current grading unverified.'}
        except Exception as exc:errors.append(str(exc))
    raise ValueError('No verified-unit native terrain window available: '+
                     ((rejected.get('error','')+'; ') if rejected else '')+'; '.join(errors))
