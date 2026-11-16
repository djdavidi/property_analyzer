"""Location-neutral physical GIS analysis. No tariffs, credits or city providers."""
from copy import deepcopy
from datetime import datetime,timezone
from hashlib import sha256
import json
import re
import time
import uuid
from shapely.geometry import shape,box,Point,mapping
from .geometry import measure,effective_features,area_sqft,case_area_sqft,union,projected_crs
from .validation import validate_case

ENGINE_VERSION='gis-engine-v5'

def canonical(value):
    return json.dumps(value,sort_keys=True,separators=(',',':'),allow_nan=False)


def input_hash(case):
    return sha256(canonical(case).encode()).hexdigest()


def new_case(name='New GIS project', *, crs):
    return {'schema_version':1,'id':str(uuid.uuid4()),'name':name,'crs':crs,
            'parcel':None,'features':{'type':'FeatureCollection','features':[]},
            'sources':[],'corrections':[],'references':[],
            'terrain':None,'assumptions':[], 'manual_review_minutes':None,
            'created_at':datetime.now(timezone.utc).isoformat()}


def validate_input(case):
    if case.get('schema_version') != 1:
        raise ValueError('Unsupported case schema version')
    if not re.fullmatch(r'[A-Za-z0-9_-]{1,80}',case.get('id','')):
        raise ValueError('Invalid case ID')
    if len(case.get('features',{}).get('features',[])) > 20000:
        raise ValueError('Property case exceeds 20,000 feature limit')
    canonical(case)
    projected_crs(case['crs'])
    if not case.get('parcel'):
        raise ValueError('A parcel polygon is required')


def routing(case, measurement):
    from .drainage import route_grid
    if not case.get('terrain'):
        return {'status':'unavailable','warnings':['No suitable elevation grid supplied; no drainage reconstruction performed']}, {}
    grid=deepcopy(case['terrain'])
    if grid.get('crs') != case['crs']:
        raise ValueError('Terrain and case CRS differ; align explicitly before routing')
    heights=grid['elevations']; rows=len(heights); cols=len(heights[0])
    if rows*cols > 250000:
        raise ValueError('Terrain exceeds 250,000-cell property limit; crop before import')
    size=grid['cell_size']; x,y=grid['origin']
    terrain_envelope=box(x,y-rows*size,x+cols*size,y)
    parcel=shape(case['parcel'])
    buffer_size=grid.get('settings',{}).get('required_buffer_native_units',0)
    if buffer_size < 0: raise ValueError('Routing buffer must be nonnegative')
    coverage_warnings=[]
    if not terrain_envelope.covers(parcel.buffer(buffer_size)):
        grid.setdefault('settings',{})['extent_sufficient']=False
        coverage_warnings.append('Partial routing extent: terrain does not cover the parcel and requested buffer')
    expected_unit = projected_crs(case['crs']).axis_info[0].unit_conversion_factor
    unit_scale={'m':1.,'ft':.3048,'us-ft':1200/3937}.get(grid.get('horizontal_unit'))
    if unit_scale is None or abs(expected_unit-unit_scale)>1e-9:
        raise ValueError('Terrain horizontal unit does not match CRS')
    features=effective_features(case); parcel=shape(case['parcel'])
    barriers=[shape(f['geometry']) for f in features if f['properties'].get('layer') == 'barrier']
    roofs=[shape(f['geometry']) for f in features if f['properties'].get('class') == 'roof' and f['properties'].get('layer') == 'surface']
    barrier=union(barriers); roof=union(roofs)
    grid.setdefault('barriers',[]); grid.setdefault('roofs',[]); grid.setdefault('inlets',[])
    grid['parcel_mask']=[]
    for r in range(rows):
        mask=[]
        for c in range(cols):
            center=Point(x+(c+.5)*size,y-(r+.5)*size)
            mask.append(parcel.covers(center))
            if not barrier.is_empty and barrier.intersects(box(x+c*size,y-(r+1)*size,x+(c+1)*size,y-r*size)):
                grid['barriers'].append([r,c])
            if not roof.is_empty and roof.covers(center): grid['roofs'].append([r,c])
        grid['parcel_mask'].append(mask)
    for f in features:
        p=f['properties']
        if p.get('layer') == 'inlet':
            pt=shape(f['geometry']); r=int((y-pt.y)//size); c=int((pt.x-x)//size)
            if 0<=r<rows and 0<=c<cols:
                grid['inlets']=[i for i in grid['inlets'] if i['id']!=f['id']]
                grid['inlets'].append({'id':f['id'],'cell':[r,c]})
            else: raise ValueError('Inlet falls outside terrain extent')
        if p.get('layer') == 'connection':
            grid.setdefault('connections',[]).append({'from':p['from'],'to':p['to'],'evidence':p.get('evidence','unknown')})
    output=route_grid(grid)
    output['warnings'].extend(coverage_warnings)
    output['status']='modeled' if output['coverage_complete'] and output['extent_sufficient'] else 'partial'
    grouped={}
    for r,row in enumerate(output['labels']):
        for c,label in enumerate(row):
            if label is not None and label not in ('barrier','nodata'):
                # Unknown roof pixels are not individual collection outlets.
                # Keep detailed labels in the grid, aggregate their display union.
                display_label='unresolved:roof' if label.startswith('unresolved:roof:') else label
                grouped.setdefault(display_label,[]).append(box(x+c*size,y-(r+1)*size,x+(c+1)*size,y-r*size))
    physical=shape(measurement['geometries']['physical_ia'])
    geoms={key:mapping(union(v)) for key,v in grouped.items()}
    output['catchments']=[{'outlet':key,'geometry':geom,
                          'contributing_area_sqft':case_area_sqft(shape(geom),case),
                          'on_parcel_area_sqft':case_area_sqft(shape(geom).intersection(parcel),case),
                          'on_parcel_physical_ia_sqft':case_area_sqft(shape(geom).intersection(physical),case),
                          'off_parcel_physical_ia_sqft':None,
                          'eligibility':'Not established by routing'} for key,geom in geoms.items()]
    for catchment in output['catchments']:
        for key,value in list(catchment.items()):
            if key.endswith('_sqft'):
                catchment[key[:-5]+'_m2']=None if value is None else value*.09290304
    output['origin']=grid['origin']; output['cell_size']=size; output['crs']=case['crs']
    output['display_grouping']='Unconnected roof cells grouped as unresolved:roof; per-cell routing labels retained separately'
    output['area_accounting_crs']=case.get('area_crs',case['crs'])
    output['grid_area_basis']='outlets/counts use native grid-cell areas; catchment geometry areas use area_accounting_crs'
    return output, geoms


def result_hash(result):
    """Deterministic content digest; elapsed processing time is observational."""
    return sha256(canonical({k:v for k,v in result.items() if k not in ('analysis_sha256','processing_seconds')}).encode()).hexdigest()


def analyze(case, *, source_dependencies=None):
    """Measure/reroute a frozen GIS case without importing jurisdiction code.

    source_dependencies is an explicit legacy-data interpretation option; it is
    recorded in the artifact and never changes source observations or geometry.
    New providers should mark source_dependency=True on dependent observations.
    """
    from .sources import quality_checks
    start=time.perf_counter();validate_input(case)
    view=case if source_dependencies is None else {**case,'dependent_source_families':list(source_dependencies)}
    measurement=measure(view)
    quality=quality_checks([s for s in case.get('sources',[]) if s.get('crs') or s.get('resolution')],
                           construction_completed=case.get('construction_completed'))
    drainage,geometries=routing(case,measurement)
    from .research import analyze_research
    research=analyze_research(case,measurement,drainage)
    from .model_integration import build as integrate_models
    modeled=integrate_models(case,measurement,drainage,research)
    warnings=list(case.get('warnings',[]))+measurement['warnings']+drainage.get('warnings',[])
    if quality:warnings.append('Source metadata quality has unresolved dates, units, coverage or temporal checks; see source_quality_issues')
    validation=validate_case(case,measurement,geometries)
    for kind,v in validation.items():
        if v['status']=='incomplete':warnings.append(kind.upper()+' independent validation incomplete: '+'; '.join(v['blockers']))
    result={'schema_version':1,'result_type':'gis-analysis','engine_version':ENGINE_VERSION,
            'input_sha256':input_hash(case),'measurement':measurement,'drainage':drainage,
            'research_drainage':research,
            'modeled_integration':modeled,
            'map_features':effective_features(case),'source_quality_issues':quality,
            'validation':validation,'warnings':list(dict.fromkeys(warnings)),
            'processing_settings':{'dependent_source_families':list(view.get('dependent_source_families',[]))},
            'processing_seconds':round(time.perf_counter()-start,6),
            'manual_review_minutes':case.get('manual_review_minutes'),
            'claim':'Physical GIS screening; source suitability, site conditions and independent validation remain explicit'}
    if case.get('imagery_age_policy'):
        result['processing_settings']['imagery_age_policy']=deepcopy(case['imagery_age_policy'])
    if case.get('terrain_reuse'):
        result['processing_settings']['terrain_reuse']=deepcopy(case['terrain_reuse'])
    from .quality import processing_fingerprint
    result['processing_fingerprint']=processing_fingerprint()
    result['analysis_sha256']=result_hash(result)
    return result
