"""Location-neutral local GIS/drainage commands; no jurisdiction or billing imports."""
from __future__ import annotations

import argparse
from copy import deepcopy
from datetime import datetime, timezone, date
from hashlib import sha256
import json
import math
from pathlib import Path
import shutil

from pyproj import CRS
from pyproj.exceptions import CRSError
from shapely.geometry import shape, mapping, box, Point, LineString
from shapely.ops import unary_union

from .geometry import projected_crs, reproject, polygon


def _write(path, value):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(value,separators=(',',':'),allow_nan=False)+'\n')


def _declared_crs(data):
    declaration=data.get('crs')
    if isinstance(declaration,str):return declaration
    if isinstance(declaration,dict):return declaration.get('properties',{}).get('name')
    return None


def _read_geojson(path, explicit_crs=None):
    path=Path(path);data=json.loads(path.read_text())
    embedded=_declared_crs(data)
    if explicit_crs and embedded and CRS(explicit_crs)!=CRS(embedded):
        raise ValueError(f'{path.name}: declared CRS conflicts with the explicit CRS')
    source=CRS(explicit_crs or embedded or 'EPSG:4326')
    if data.get('type')=='FeatureCollection':features=data.get('features',[])
    elif data.get('type')=='Feature':features=[data]
    elif data.get('type') in ('Polygon','MultiPolygon','Point','MultiPoint','LineString','MultiLineString','GeometryCollection'):
        features=[{'type':'Feature','geometry':data,'properties':{}}]
    else:raise ValueError(f'{path.name}: expected GeoJSON geometry, Feature or FeatureCollection')
    if not features:raise ValueError(f'{path.name}: GeoJSON contains no features')
    for feature in features:
        if feature.get('properties') is None:feature['properties']={}
        if not isinstance(feature.get('properties',{}),dict):raise ValueError(f'{path.name}: feature properties must be an object')
        if not feature.get('geometry'):raise ValueError(f'{path.name}: empty geometry is not usable evidence')
        geom=shape(feature['geometry'])
        if geom.is_empty or not geom.is_valid:raise ValueError(f'{path.name}: invalid or empty geometry; repair it explicitly')
        if not all(math.isfinite(v) for v in geom.bounds):raise ValueError('Geometry coordinates must be finite')
        if source.is_geographic:
            lonlat=reproject(geom,source,'EPSG:4326') if source!=CRS('EPSG:4326') else geom
            xmin,ymin,xmax,ymax=lonlat.bounds
            if not (-180<=xmin<=xmax<=180 and -90<=ymin<=ymax<=90):
                raise ValueError(f'{path.name}: coordinates are outside longitude/latitude bounds; supply the correct input CRS')
    return deepcopy(features),source


def _automatic_utm(boundary, source):
    center=reproject(boundary,source,'EPSG:4326').centroid
    if not (-80<=center.y<=84):
        raise ValueError('Automatic UTM selection supports latitudes 80°S–84°N; provide an appropriate projected --crs for this location')
    zone=max(1,min(60,int(math.floor((center.x+180)/6))+1))
    return CRS.from_epsg((32600 if center.y>=0 else 32700)+zone)


def _source(path,crs,role, *, acquisition_date=None,crs_assumed=False):
    p=Path(path)
    return {'path':str(p.resolve()),'url':p.resolve().as_uri(),'sha256':sha256(p.read_bytes()).hexdigest(),
            'retrieved_at':datetime.now(timezone.utc).isoformat(),'acquisition_date':acquisition_date,
            'crs':CRS(crs).to_string(),'horizontal_unit':CRS(crs).axis_info[0].unit_name,
            'role':role,'input_crs_basis':'RFC 7946 longitude/latitude default' if crs_assumed else 'explicit or embedded CRS'}


def build_project(args):
    """Create a generic case from portable local evidence without a data vendor."""
    from .engine import new_case
    from .terrain import prepare_terrain
    boundary_features,boundary_crs=_read_geojson(args.boundary,args.boundary_crs)
    boundary=unary_union([polygon(f['geometry']) for f in boundary_features])
    target=CRS(args.crs) if args.crs else None
    if args.dem:
        import rasterio
        with rasterio.open(args.dem) as dem:
            if not dem.crs:raise ValueError('DEM coordinate system is missing')
            native=CRS(dem.crs)
        projected_crs(native)
        if target and target!=native:
            raise ValueError('--crs must match the DEM native projected CRS; align the raster explicitly before importing')
        target=native
        if not args.vertical_unit:raise ValueError('--vertical-unit is required when --dem is supplied')
        if args.unit_status=='verified' and (not args.unit_evidence or not args.unit_explanation):
            raise ValueError('Reviewed unit evidence requires both --unit-evidence URL and --unit-explanation text')
    target=target or _automatic_utm(boundary,boundary_crs)
    projected_crs(target)
    if not math.isfinite(args.buffer) or args.buffer<0:raise ValueError('--buffer must be finite and nonnegative')
    if args.acquisition_date:date.fromisoformat(args.acquisition_date)
    area_crs=CRS(args.area_crs) if args.area_crs else target
    projected_crs(area_crs)
    case=new_case(args.name or Path(args.boundary).stem,crs=target.to_string())
    case['area_crs']=area_crs.to_string()
    case['parcel']=mapping(reproject(boundary,boundary_crs,target))
    case['sources']=[_source(args.boundary,boundary_crs,'analysis boundary',
                            crs_assumed=not args.boundary_crs and not _declared_crs(json.loads(Path(args.boundary).read_text())))]
    case['processing_history']=[{'operation':'Vector coordinate transformation','source_crs':boundary_crs.to_string(),
                                 'target_crs':target.to_string(),'method':'pyproj always_xy; no terrain resampling'}]
    if args.features:
        features,source_crs=_read_geojson(args.features,args.features_crs)
        used=set()
        for index,feature in enumerate(features):
            properties=feature.setdefault('properties',{})
            if not properties.get('layer'):
                if properties.get('class') in ('roof','pavement','pervious','unknown'):properties['layer']='surface'
                else:raise ValueError('Each input feature needs properties.layer; surfaces also need class roof/pavement/pervious/unknown')
            if properties['layer']=='surface' and properties.get('class') not in ('roof','pavement','pervious','unknown'):
                raise ValueError('Surface class must be roof, pavement, pervious or unknown')
            identifier=str(feature.get('id','input-'+str(index)))
            if identifier in used:raise ValueError('Input feature IDs must be unique')
            used.add(identifier);feature['id']=identifier
            feature['geometry']=mapping(reproject(shape(feature['geometry']),source_crs,target))
            properties.setdefault('source_kind','observation')
            properties.setdefault('source_family','local input')
        case['features']={'type':'FeatureCollection','features':features}
        case['sources'].append(_source(args.features,source_crs,'surface/construction/drainage features',
                             crs_assumed=not args.features_crs and not _declared_crs(json.loads(Path(args.features).read_text()))))
        case['processing_history'].append({'operation':'Feature coordinate transformation','source_crs':source_crs.to_string(),
                                           'target_crs':target.to_string(),'method':'pyproj always_xy'})
    output=Path(args.output);inputs=output/'inputs';inputs.mkdir(parents=True,exist_ok=True)
    for name,path in [('boundary.geojson',args.boundary),('features.geojson',args.features)]:
        if path:
            digest=sha256(Path(path).read_bytes()).hexdigest()
            destination=inputs/(Path(name).stem+'-'+digest+Path(name).suffix)
            if destination.exists() and sha256(destination.read_bytes()).hexdigest()!=digest:
                raise ValueError('Frozen input snapshot hash mismatch')
            if not destination.exists():shutil.copyfile(path,destination)
            for source in case['sources']:
                if source.get('sha256')==digest:source['snapshot_path']='inputs/'+destination.name
    if args.dem:
        evidence={'status':args.unit_status,'source_url':args.unit_evidence or Path(args.dem).resolve().as_uri(),
                  'explanation':args.unit_explanation or 'Caller specified vertical units for this scenario; source units have not been independently verified'}
        item=prepare_terrain(args.dem,case['parcel'],inputs/('terrain-'+case['id']+'.tif'),crs=case['crs'],
                             vertical_unit=args.vertical_unit,unit_evidence=evidence,
                             acquisition_date=args.acquisition_date,
                             buffer_native_units=args.buffer/target.axis_info[0].unit_conversion_factor)
        case['terrain']=item['grid'];case['sources'].append(item['provenance'])
        case['warnings']=item['warnings']
        case['assumptions'].append('Geometric crop buffer '+str(args.buffer)+' metres; hydrologic sufficiency remains unverified')
        case['assumptions'].append(evidence['explanation'])
    else:
        case['warnings']=['No DEM supplied; area measurement is available but drainage routing is unavailable']
    return case


def demo_case():
    """Invented Sydney UTM 56S site: no jurisdiction, source vendor or credits."""
    from .engine import new_case
    x,y=334000,6251000;crs='EPSG:32756'
    case=new_case('Sydney synthetic GIS example',crs=crs)
    case.update(id='generic-demo-sydney',created_at='2026-01-01T00:00:00Z',synthetic_case=True)
    case['parcel']=mapping(box(x+10,y-40,x+40,y-10))
    def feature(id,g,layer,cls=None,**props):
        p={'layer':layer,'source_kind':'synthetic',**props}
        if cls:p['class']=cls
        return {'type':'Feature','id':id,'geometry':mapping(g),'properties':p}
    case['features']={'type':'FeatureCollection','features':[
        feature('roof',box(x+10,y-20,x+20,y-10),'surface','roof'),
        feature('paving',box(x+20,y-40,x+40,y-10),'surface','pavement'),
        feature('lawn',box(x+10,y-40,x+20,y-20),'surface','pervious'),
        feature('canopy',box(x+15,y-25,x+25,y-15),'canopy'),
        feature('inlet-A',Point(x+37,y-37),'inlet',evidence='documented'),
        feature('pipe-A',LineString([(x+37,y-37),(x+46,y-45)]),'connection',
                **{'from':'inlet-A','to':'external-outlet-A','evidence':'documented'})]}
    case['terrain']={'crs':crs,'origin':[x,y],'cell_size':2,'horizontal_unit':'m','vertical_unit':'m',
                     'elevations':[[20-r*.1-c*.2 for c in range(25)] for r in range(25)],
                     'settings':{'extent_sufficient':False,'required_buffer_native_units':0,'flat_tolerance':0,'max_flow_paths':20}}
    case['sources']=[{'url':'synthetic://generic-gis/sydney-known-answer','source_kind':'synthetic',
                      'retrieved_at':'2026-01-01T00:00:00Z','acquisition_date':None,'crs':crs,
                      'horizontal_unit':'m','vertical_unit':'m','resolution':2}]
    case['assumptions']=['All geometry, elevations and connections are invented.',
                         'The evidence labels describe the synthetic fixture, not a real survey.',
                         'Roof routing and hydrologic extent remain unresolved; synthetic correctness is not empirical accuracy.']
    case['warnings']=['SYNTHETIC EXAMPLE: no real property or independently validated drainage is represented']
    return case


def _summary(case,result,output):
    m=result['measurement'];factor=.3048**2
    return {'case_id':case['id'],'input_sha256':result['input_sha256'],'crs':case['crs'],
            'gross_area_m2':m['ga_sqft']*factor,'known_impervious_area_m2':m['ia_sqft']*factor,
            'unknown_surface_area_m2':m['unknown_sqft']*factor,
            'gross_area_sqft':m['ga_sqft'],'known_impervious_area_sqft':m['ia_sqft'],
            'drainage_status':result['drainage']['status'],'processing_seconds':result['processing_seconds'],
            'warnings':result['warnings'],'output':str(Path(output).resolve()),
            'report':str(Path(output).resolve()/'report.html')}


def parser():
    p=argparse.ArgumentParser(description=__doc__)
    commands=p.add_subparsers(dest='command',required=True)
    demo=commands.add_parser('demo',help='Run an invented metric Sydney example without input downloads')
    demo.add_argument('--output',type=Path,default=Path('gis-demo'))
    run=commands.add_parser('run',help='Measure and route local evidence for any location')
    run.add_argument('--boundary',type=Path,required=True,help='GeoJSON polygon boundary')
    run.add_argument('--boundary-crs',help='Override default RFC 7946 WGS84 longitude/latitude interpretation')
    run.add_argument('--features',type=Path,help='GeoJSON surfaces, construction features, inlets and connections')
    run.add_argument('--features-crs',help='Feature input CRS, default RFC 7946 WGS84')
    run.add_argument('--dem',type=Path,help='North-up projected square-cell elevation GeoTIFF')
    run.add_argument('--vertical-unit',choices=['m','ft','us-ft'],help='Required with DEM; independent of horizontal units')
    run.add_argument('--unit-status',choices=['assumed','verified'],default='assumed')
    run.add_argument('--unit-evidence',help='Source URL for reviewed vertical-unit evidence')
    run.add_argument('--unit-explanation',help='Evidence interpretation; required when --unit-status verified')
    run.add_argument('--acquisition-date',help='Known DEM acquisition day, YYYY-MM-DD; omit if unknown')
    run.add_argument('--crs',help='Projected analysis CRS; defaults to native DEM CRS or boundary-centroid UTM')
    run.add_argument('--area-crs',help='Optional projected area-accounting CRS; defaults to analysis CRS')
    run.add_argument('--buffer',type=float,default=50,help='Geometric crop buffer in metres, default 50; does not establish watershed completeness')
    run.add_argument('--name',help='Project display name')
    run.add_argument('--output',type=Path,required=True)
    saved=commands.add_parser('analyze',help='Rerun a frozen generic case with no source refresh')
    saved.add_argument('case',type=Path);saved.add_argument('--output',type=Path,required=True)
    serve=commands.add_parser('serve',help='Open the local map/editor server for a saved project')
    serve.add_argument('--workspace',type=Path,required=True);serve.add_argument('--port',type=int,default=8766)
    return p


def main(argv=None):
    args=parser().parse_args(argv)
    try:
        if args.command=='serve':
            if not 1<=args.port<=65535:raise ValueError('Port must be 1–65535')
            from .server import serve
            serve(port=args.port,workspace=args.workspace)
            return 0
        from .workspace import ProjectStore
        if args.command=='demo':case=demo_case()
        elif args.command=='run':case=build_project(args)
        else:case=json.loads(args.case.read_text())
        result=ProjectStore(args.output).save(case)
        print(json.dumps(_summary(case,result,args.output),indent=2,allow_nan=False));return 0
    except (ValueError,KeyError,FileNotFoundError,TypeError,OSError,CRSError) as exc:
        print(json.dumps({'error':str(exc)}));return 1


if __name__=='__main__':raise SystemExit(main())
