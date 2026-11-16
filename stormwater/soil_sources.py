"""Bounded read-only USDA SSURGO queries; no inferred drainage or soil default."""
from copy import deepcopy
from hashlib import sha256
from math import isfinite
from shapely import wkt
from shapely.geometry import shape, mapping, box
from drainage_core.geometry import reproject, polygon
from drainage_core.sources import SourceError, canonical, now

URL='https://sdmdataaccess.sc.egov.usda.gov/Tabular/post.rest'
MAX_ROWS=1000
COLUMNS=['mupolygonkey','mukey','wkt','muname','cokey','compname','comppct_r','hydgrp']


def boundary_hash(case):
    return sha256(canonical({'crs':case['crs'],'parcel':mapping(polygon(case['parcel']))})).hexdigest()


def query(case):
    parcel=reproject(polygon(case['parcel']),case['crs'],'EPSG:4326')
    a,b,c,d=parcel.bounds
    if not all(isfinite(v) for v in (a,b,c,d)) or not (-180<=a<c<=180 and -90<=b<d<=90):
        raise SourceError('Invalid WGS84 parcel extent')
    if c-a>.1 or d-b>.1:raise SourceError('Soil query exceeds bounded property extent (0.1 degree)')
    # Bounding envelope limits query complexity; exact clipping happens locally.
    bounds=wkt.dumps(box(a,b,c,d),rounding_precision=9)
    geom="geometry::STGeomFromText('"+bounds+"',4326)"
    return (f'SELECT TOP {MAX_ROWS+1} p.mupolygonkey, p.mukey, '
        f'p.mupolygongeo.STIntersection({geom}).STAsText() AS wkt, '
        'm.muname, c.cokey, c.compname, c.comppct_r, c.hydgrp '
        'FROM mupolygon p INNER JOIN mapunit m ON m.mukey=p.mukey '
        'LEFT JOIN component c ON c.mukey=p.mukey '
        f'WHERE p.mupolygongeo.STIntersects({geom})=1 ORDER BY p.mupolygonkey,c.cokey')


def polygonal_parts(geometry):
    """Polygon/MultiPolygon made of a collection's areal members (zero-area parts dropped)."""
    from shapely.geometry import MultiPolygon
    polygons=[]
    for part in getattr(geometry,'geoms',[geometry]):
        if part.geom_type=='Polygon' and not part.is_empty and part.area>0:polygons.append(part)
        elif part.geom_type=='MultiPolygon':polygons.extend(p for p in part.geoms if not p.is_empty and p.area>0)
        elif part.geom_type=='GeometryCollection':
            nested=polygonal_parts(part);polygons.extend(getattr(nested,'geoms',[nested]) if not nested.is_empty else [])
    if not polygons:return MultiPolygon()
    if len(polygons)==1:return polygons[0]
    combined=MultiPolygon(polygons)
    if combined.is_valid:return combined
    from shapely.ops import unary_union
    return unary_union(polygons)


def parse(data):
    table=data.get('Table')
    if table is None and data=={}:return []  # SDA represents no rows as {}.
    if not isinstance(table,list) or not table or table[0]!=COLUMNS:
        raise SourceError('USDA soil response columns missing or unexpected')
    if len(table)-1>MAX_ROWS:raise SourceError('USDA soil row limit reached; completeness unknown')
    polys={}
    for values in table[1:]:
        if not isinstance(values,list) or len(values)!=len(COLUMNS):raise SourceError('Malformed USDA soil row')
        row=dict(zip(COLUMNS,values));key=str(row['mupolygonkey'])
        try:g=wkt.loads(row['wkt'])
        except Exception as exc:raise SourceError('Invalid USDA soil geometry') from exc
        if g.geom_type=='GeometryCollection':
            # STIntersection may return touching lines/points beside the polygons;
            # those have no area. Keep the polygonal parts only.
            g=polygonal_parts(g)
        if not g.is_valid:raise SourceError('Invalid USDA soil polygon')
        if g.is_empty or g.area==0:continue
        if g.geom_type not in ('Polygon','MultiPolygon'):raise SourceError('USDA soil geometry must be polygonal')
        if key not in polys:
            polys[key]={'id':key,'type':'Feature','geometry':mapping(g),
                'properties':{'mukey':str(row['mukey']),'mapunit_name':row['muname'],'components':[]}}
        elif shape(polys[key]['geometry'])!=g:raise SourceError('Inconsistent geometry for USDA soil polygon')
        components=polys[key]['properties']['components']
        component={k:row[k] for k in ('cokey','compname','comppct_r','hydgrp')}
        if component not in components:components.append(component)
    return list(polys.values())


def acquire(case,cache,refresh=False):
    """Assessment-only metadata; leave physical inputs/source hashes unchanged."""
    result=deepcopy(case);a=result.setdefault('assessment',{});previous=a.get('soil_snapshot')
    snapshot={'provider':'USDA NRCS SSURGO / Soil Data Access','boundary_sha256':boundary_hash(case),
        'attempted_at':now(),'crs':'EPSG:4326','features':[],'sources':[],
        'claim':'Mapped survey components, not a site soil test. Fill, compaction and drainage may differ.'}
    try:
        response=cache.post_json(URL,{'query':query(case),'format':'JSON+COLUMNNAME'},refresh,
                                 {'crs':'EPSG:4326','acquisition_date':None,'processing':'SSURGO component join; no dominant-group substitution'})
        snapshot['sources']=[response['provenance']]
        snapshot['features']=parse(response['data'])
        snapshot['status']='cached_after_failure' if response['provenance'].get('cache_reused_after_failure') else 'retrieved'
    except Exception as exc:
        snapshot.update(status='unavailable',error=str(exc))
        # The last saved interpretation is preserved as history, not silently used
        # for a different boundary or after a failed/malformed new response.
    if previous:a.setdefault('soil_history',[]).append(deepcopy(previous))
    snapshot['snapshot_sha256']=sha256(canonical(snapshot)).hexdigest()
    a['soil_snapshot']=snapshot
    a.setdefault('source_status',[]).append({k:deepcopy(snapshot[k]) for k in ('provider','status','attempted_at','claim')}
        | {'error':snapshot.get('error'),'source_sha256':[s['sha256'] for s in snapshot['sources']]})
    return result
