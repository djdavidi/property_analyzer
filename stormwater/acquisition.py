"""Reproducible free-public-data acquisition. Cache replay never refreshes a source."""
from __future__ import annotations
import hashlib
import json
import math
import os
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlencode, urlparse
from urllib.request import Request, urlopen

from drainage_core.sources import Cache,SourceError,now,canonical,quality_checks
from drainage_core.sources import arcgis_features as _generic_arcgis_features


def arcgis_features(layer, cache, params=None, refresh=False, page_size=1000, max_pages=100):
    """Philadelphia adapter: preserve the existing EPSG:2272 query default."""
    return _generic_arcgis_features(layer,cache,{'outSR':'2272',**(params or {})},
                                    refresh,page_size,max_pages)

PWD = 'https://stormwater.phila.gov/PwdWebApi/api/v1/parcel'
ARCGIS = 'https://services.arcgis.com/fLeGjb7u4uXqeF9q/ArcGIS/rest/services'
BUILDINGS = ARCGIS + '/LI_BUILDING_FOOTPRINTS/FeatureServer/0'
SYSTEMS = ARCGIS + '/GSI_SMP_TYPES/FeatureServer/0'


def normalize_billing(data):
    """Accept raw public details or the workspace's sanitized saved snapshot."""
    parcel = data.get('parcel', data.get('Parcel',{}))
    raw_accounts = data.get('accounts', data.get('ChargeSummary',{}).get('ParcelAccounts', data.get('Accounts',[])))
    accounts = []
    rows = []
    for account in raw_accounts or []:
        rows.extend(account.get('current', [r for r in account.get('YearlyAccountCharges',[]) if r.get('RateSchedule',{}).get('IsCurrent')]))
        allocation = account.get('allocation', account.get('AccountPercentOfCharge', account.get('Allocation')))
        if allocation is None:
            allocation = 1/len(raw_accounts)
        accounts.append({'allocation':allocation,'discount_factor':1.0,'discount_verified':False})
    def number(key):
        value = parcel.get(key)
        return float(value) if value is not None else None
    npdes = number('NPDESCredit')
    # Public API stores NPDESCredit as boolean/0.07 depending on response version.
    if npdes == 1:
        npdes = .07
    return {'ga_sqft':number('GrossArea'),'ia_sqft':number('ImpervArea'),
            'recorded_ga_sqft':number('GrossArea'),'recorded_ia_sqft':number('ImpervArea'),
            'billed_ga_sqft':number('FinalGross'),'billed_ia_sqft':number('FinalImperv'),
            'existing_ga_credit_sqft':data.get('ChargeSummary',{}).get('GrossCreditSqFt',number('GrossCredit')),
            'existing_ia_credit_sqft':data.get('ChargeSummary',{}).get('ImpervCreditSqFt',number('ImpervCredit')),
            'existing_iar_sqft':0 if number('GrossCredit') == 0 and number('ImpervCredit') == 0 else None,
            'npdes_fraction':npdes,'accounts':accounts,'property_type':parcel.get('BldgType'),
            'undeveloped':False, 'undeveloped_verified':False,'bill_date':rows[0]['RateSchedule']['StartDate'][:10] if rows and rows[0].get('RateSchedule') else None,
            'published_monthly_total':sum(float(row['TotalWeightedCharge']) for row in rows) if rows else number('WeightedCharge'),
            'existing_credits_spatially_reconciled':False,
            'actual_bill_verified':False,'source_total_kind':'public calculation, not actual invoice'}


def acquire_property(parcel_id, cache, refresh=False):
    """Parcel/billing + nearby public building/system geometry, all source failures explicit.

    Land cover, elevation, canopy and private connectivity are never inferred from
    billed IA or the outline of a mapped stormwater system.
    """
    from shapely import wkt
    from shapely.geometry import mapping
    from shapely.ops import transform
    from pyproj import Transformer
    parcel_id = int(parcel_id)
    if parcel_id <= 0:
        raise ValueError('Positive PWD parcel ID required')
    warnings, sources = [], []
    item = cache.fetch_json(f'{PWD}/{parcel_id}',refresh, {'crs':'EPSG:4326','horizontal_unit':'degree'})
    sources.append(item['provenance'])
    raw = item['data']; observed = raw.get('Parcel',raw.get('parcel',{}))
    if not observed.get('Shape'):
        raise SourceError('PWD response has no parcel boundary geometry')
    ll = wkt.loads(observed['Shape'])
    projected = transform(Transformer.from_crs(4326,2272,always_xy=True).transform,ll)
    if projected.is_empty or not projected.is_valid:
        raise SourceError('PWD parcel boundary is invalid')
    try:
        details = cache.fetch_json(f'{PWD}/{parcel_id}/details',refresh)
        sources.append(details['provenance'])
        baseline = normalize_billing(details['data'])
        pending = details['data'].get('Pending', details['data'].get('pending'))
    except SourceError as exc:
        warnings.append(str(exc)); baseline = normalize_billing(raw); pending = None
    features=[]
    minx,miny,maxx,maxy = projected.buffer(150).bounds
    query = {'geometry':','.join(map(str,(minx,miny,maxx,maxy))),
             'geometryType':'esriGeometryEnvelope','inSR':'2272',
             'spatialRel':'esriSpatialRelIntersects'}
    for name, layer in [('roof',BUILDINGS),('system_footprint',SYSTEMS)]:
        try:
            response = arcgis_features(layer,cache,query,refresh)
            sources.extend(response['sources'])
            for feature in response['features']:
                props = feature.setdefault('properties',{})
                feature['id'] = 'public-'+name+'-'+str(feature.get('id',props.get('objectid',len(features))))
                props.update({'kind':name,'layer':'surface' if name=='roof' else 'footprint', 'class':'roof' if name=='roof' else None,'source_family':'City buildings' if name=='roof' else 'PWD','source_dependency':name=='roof','source_kind':'observation','source_url':layer,
                              'acquisition_date':None,'reviewed':False})
                features.append(feature)
        except SourceError as exc:
            warnings.append(f'{name}: {exc}')
    warnings.extend(['PWD boundary recomputation tests consistency, not legal boundary accuracy.',
                     'Public building footprints have unknown acquisition dates; manual review required.',
                     'Independent pavement/ground surfaces, canopy-understory, elevation, soils, inlets and private pipe/roof connections are incomplete.',
                     'Mapped system footprints are not confirmed inlets or contributing drainage boundaries.',
                     'Account discounts, current bills and undeveloped status are unverified.'])
    return {'parcel_id':parcel_id,'address':observed.get('Address'),'parcel':mapping(projected),
            'crs':'EPSG:2272','baseline':baseline,'pending':pending,'sources':sources,
            'features':{'type':'FeatureCollection','features':features},'warnings':warnings,
            'boundary_source':sources[0], 'independent_ia_validation':'incomplete',
            'independent_drainage_validation':'incomplete'}


def acquire_imagery(parcel, cache, *, crs='EPSG:2272', refresh=False, size=1024):
    """Cache a bounded public aerial PNG; disclose fallback and unknown capture dates.

    Service vintage is not the exact acquisition date. No raster classifier is
    silently applied to RGB values; trees/green roofs cannot prove perviousness.
    """
    from shapely.geometry import shape
    bounds=list(shape(parcel).buffer(100).bounds)
    width=int(size); height=max(1,round(width*(bounds[3]-bounds[1])/(bounds[2]-bounds[0])))
    height=min(height,2048)
    services=[('https://services.pasda.psu.edu/arcgis/rest/services/pasda/PhiladelphiaImagery2025/MapServer','2025'),
              ('https://services.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer',None)]
    params={'f':'json','bbox':','.join(map(str,bounds)), 'bboxSR':crs.split(':')[-1],
            'imageSR':crs.split(':')[-1], 'size':f'{width},{height}', 'format':'png','transparent':'false'}
    warnings=[]
    for service,vintage in services:
        try:
            source=cache.fetch_json(service+'/export?'+urlencode(params),refresh,
                                    {'crs':crs,'horizontal_unit':'us-ft' if crs=='EPSG:2272' else None,
                                     'service_vintage':vintage,'acquisition_date':None})
            data=source['data']
            if not data.get('href'):
                raise SourceError('Imagery export lacks image URL')
            href=data['href']
            # ArcGIS may publish an HTTP href from an HTTPS request; require TLS.
            if href.startswith('http://'):
                href='https://'+href[len('http://'):]
            image=cache.fetch_bytes(href,refresh,{'crs':crs,'acquisition_date':None,
                                 'service_vintage':vintage,'bounds':data.get('extent'),
                                 'resolution':[(bounds[2]-bounds[0])/width,(bounds[3]-bounds[1])/height]})
            extent=data.get('extent',{})
            actual=[extent.get(k,bounds[i]) for i,k in enumerate(['xmin','ymin','xmax','ymax'])]
            return {'sha256':image['provenance']['sha256'],'blob_path':str(cache.root/'blobs'/image['provenance']['sha256']),
                    'bounds':actual,'crs':crs,'width':width,'height':height,'media_type':'image/png',
                    'sources':[source['provenance'],image['provenance']],
                    'attribution':'PASDA / Philadelphia' if vintage else 'Esri World Imagery and contributors',
                    'warnings':warnings+['Aerial capture date and season remain unverified; service vintage: '+str(vintage)]}
        except SourceError as exc:
            warnings.append(str(exc))
    try:
        image=acquire_tile_imagery(parcel,cache,crs=crs,size=size,refresh=refresh)
        image['warnings']=warnings+image['warnings']
        return image
    except SourceError as exc:
        raise SourceError('All public imagery sources unavailable: '+'; '.join(warnings)+'; '+str(exc)) from exc


def acquire_tile_imagery(parcel, cache, *, crs='EPSG:2272', zoom=18, size=1024, refresh=False):
    """Bounded free public aerial tile mosaic, reprojected locally into the case CRS."""
    import io
    import numpy as np
    from rasterio.io import MemoryFile
    from pyproj import Transformer
    from shapely.geometry import shape
    from shapely.ops import transform
    from rasterio.transform import from_bounds
    from rasterio.warp import reproject,Resampling
    from concurrent.futures import ThreadPoolExecutor
    bounds=list(shape(parcel).buffer(100).bounds)
    merc=transform(Transformer.from_crs(crs,3857,always_xy=True).transform,shape(parcel).buffer(100))
    xmin,ymin,xmax,ymax=merc.bounds
    world=math.pi*6378137; span=2*world/(2**zoom)
    tx0=int((xmin+world)//span);tx1=int((xmax+world)//span)
    ty0=int((world-ymax)//span);ty1=int((world-ymin)//span)
    tiles=[(x,y) for y in range(ty0,ty1+1) for x in range(tx0,tx1+1)]
    if len(tiles)>36:raise SourceError('Aerial tile window exceeds bounded property acquisition limit')
    template='https://services.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}'
    def fetch(tile):
        x,y=tile
        item=cache.fetch_bytes(template.format(z=zoom,y=y,x=x),refresh,
                              {'crs':'EPSG:3857','acquisition_date':None,'horizontal_unit':'m',
                               'resolution':[span/256,span/256],'tile':[zoom,x,y]})
        with MemoryFile(item['content']) as mem:
            with mem.open() as image:
                array=np.moveaxis(image.read([1,2,3]),0,-1)
        if array.shape!=(256,256,3):raise SourceError('Unexpected aerial tile size')
        return tile,array,item['provenance']
    canvas=np.zeros(((ty1-ty0+1)*256,(tx1-tx0+1)*256,3),dtype=np.uint8)
    sources=[]
    with ThreadPoolExecutor(max_workers=4) as executor:
        for (x,y),array,source in executor.map(fetch,tiles):
            canvas[(y-ty0)*256:(y-ty0+1)*256,(x-tx0)*256:(x-tx0+1)*256]=array
            sources.append(source)
    source_bounds=[tx0*span-world,world-(ty1+1)*span,(tx1+1)*span-world,world-ty0*span]
    width=int(size);height=max(1,round(width*(bounds[3]-bounds[1])/(bounds[2]-bounds[0])))
    destination=np.zeros((height,width,3),dtype=np.uint8)
    for band in range(3):
        reproject(canvas[:,:,band],destination[:,:,band],src_transform=from_bounds(*source_bounds,canvas.shape[1],canvas.shape[0]),
                  src_crs='EPSG:3857',dst_transform=from_bounds(*bounds,width,height),dst_crs=crs,resampling=Resampling.bilinear)
    with MemoryFile() as mem:
        with mem.open(driver='PNG',width=width,height=height,count=3,dtype='uint8') as image:
            image.write(np.moveaxis(destination,-1,0))
        encoded=mem.read()
    metadata={'crs':crs,'bounds':bounds,'acquisition_date':None,'horizontal_unit':'us-ft' if crs=='EPSG:2272' else None,
              'resolution':[(bounds[2]-bounds[0])/width,(bounds[3]-bounds[1])/height],
              'processing':{'method':'tile mosaic; EPSG:3857 to case CRS; bilinear display-only warp','zoom':zoom,
                            'source_sha256':[s['sha256'] for s in sources]}}
    _,derived=cache._store('derived:world-imagery-'+hashlib.sha256(canonical(metadata)).hexdigest(),encoded,metadata)
    return {'sha256':derived['sha256'],'blob_path':str(cache.root/'blobs'/derived['sha256']),
            'bounds':bounds,'crs':crs,'width':width,'height':height,'media_type':'image/png',
            'attribution':'Esri World Imagery and contributors','sources':sources+[derived],
            'warnings':['Aerial capture date/season unverified; free Esri World Imagery tiles used as display-only fallback.',
                        'Display reprojection does not increase underlying imagery resolution.']}
