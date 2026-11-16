"""PWD Appendix A worksheet over frozen mapped areas. No routing or awards."""
from copy import deepcopy
from decimal import Decimal
from hashlib import sha256
from math import isfinite
from shapely.geometry import shape, mapping
from drainage_core.geometry import effective_features, union, reproject, case_area_sqft
from drainage_core.sources import canonical, now
from .rules import MANUAL_URL, open_space_factor
from .soil_sources import boundary_hash
from .physical_reuse import normalize_numbers

VERSION='pwd-open-space-cn-2026-09-v1'
# Table A-1, September 2026; columns A, B, C, D, Ub. No soil default.
TABLE={
 'lawn':{'poor':[68,79,86,89,79],'fair':[49,69,79,84,69],'good':[39,61,74,80,61]},
 'meadow':{'na':[30,58,71,78,58]},
 'athletic_field':{'na':[68,79,86,89,79]},
 'porous_turf':{'na':[70,70,79,84,69]},
 'brush':{'poor':[57,73,82,86,73],'fair':[43,65,76,82,65],'good':[32,58,72,79,58]},
 'woods_grass':{'poor':[57,73,82,86,73],'fair':[43,65,76,82,65],'good':[32,58,72,79,58]},
 'woods':{'poor':[45,66,77,83,66],'fair':[36,60,73,79,60],'good':[30,55,70,77,55]},
 'gravel':{'na':[76,85,89,91,89]},'dirt':{'na':[72,82,87,89,87]},
 'water':{'na':[100,100,100,100,100]}}
GROUPS=['A','B','C','D','UB']
EMPTY={'type':'GeometryCollection','geometries':[]}


def soil_groups(properties):
    """All components must account for 100% and agree for an exact mapped HSG.

    Components are not spatially located inside their map unit. Do not assign
    dominant-component percentages to invented sub-parcel polygons.
    """
    parts=properties.get('components',[]);groups=set();total=0.;reasons=[]
    if not parts:return None,[],['Soil component information missing']
    for p in parts:
        try:
            pct=float(p['comppct_r'])
            if isinstance(p['comppct_r'],bool) or not isfinite(pct) or not 0<pct<=100:raise ValueError()
        except (KeyError,TypeError,ValueError):
            reasons.append('Soil component percentage missing or invalid');continue
        total+=pct
        group=str(p.get('hydgrp') or '').strip().upper()
        if group in GROUPS:groups.add(group)
        elif group in ('A/D','B/D','C/D'):
            groups.update(group.split('/'));reasons.append('Dual soil group needs drainage evidence')
        else:reasons.append('Soil hydrologic group missing or unsupported')
    if abs(total-100)>.01:reasons.append('Soil component percentages do not total 100%')
    if len(groups)>1:reasons.append('Soil components do not establish a unique site group')
    # Incomplete groups cannot yield even a reliable candidate range.
    possible=sorted(groups,key=GROUPS.index) if not any('missing' in r or 'percent' in r for r in reasons) else []
    return (possible[0] if len(possible)==1 and not reasons else None),possible,list(dict.fromkeys(reasons))


def review_scope(case):
    # Reviews are conditional on the mapped features and original image lineage.
    # A changed surface/model/boundary must not inherit a previous interpretation.
    return sha256(canonical(normalize_numbers({k:case.get(k) for k in
        ('crs','parcel','features','corrections','imagery_age_policy')}))).hexdigest()


def _cover(properties,override):
    cover=override.get('cover',properties.get('cn_cover'))
    condition=override.get('condition',properties.get('cn_condition'))
    if cover=='lawn' and not condition:
        pct=properties.get('grass_cover_percent')
        if isinstance(pct,(int,float)) and not isinstance(pct,bool) and isfinite(pct) and 0<=pct<=100:
            condition='poor' if pct<50 else 'fair' if pct<=75 else 'good'
    if cover in TABLE and set(TABLE[cover])=={'na'}:condition='na'
    return cover,condition


def worksheet(case,gis):
    measurement=gis['measurement'];parcel=shape(case['parcel']);area=lambda g:case_area_sqft(g,case)
    physical=shape(measurement['geometries']['pervious']);unknown=shape(measurement['geometries']['unknown'])
    a=case.get('assessment',{});snapshot=a.get('soil_snapshot') or {};issues=[]
    usable=snapshot.get('status') in ('retrieved','cached_after_failure')
    if snapshot.get('boundary_sha256')!=boundary_hash(case):usable=False;issues.append('Soil snapshot missing or does not match current parcel boundary')
    if snapshot.get('snapshot_sha256') and snapshot['snapshot_sha256']!=sha256(canonical({k:v for k,v in snapshot.items() if k!='snapshot_sha256'})).hexdigest():
        usable=False;issues.append('Soil snapshot content hash mismatch')
    soils=[]
    if usable:
        for f in snapshot.get('features',[]):
            g=reproject(shape(f['geometry']),snapshot['crs'],case['crs']).intersection(parcel)
            if not g.is_empty and g.area>0:soils.append((f,g))
    else:issues.append(snapshot.get('error') or 'Public soil data have not been acquired successfully')
    soil_conflicts=union([g.intersection(h) for i,(_,g) in enumerate(soils) for _,h in soils[i+1:]])
    soil_conflicts=_area_only(soil_conflicts)
    soil_union=union([g for _,g in soils]);patches=[]
    for f in effective_features(case):
        p=f.get('properties',{})
        if p.get('layer')=='surface' and p.get('class')=='pervious':
            g=_area_only(shape(f['geometry']).intersection(physical))
            if not g.is_empty:patches.append((str(f['id']),g,p,'mapped_open_space'))
    # Conservative observations take precedence over modeled grass/soil candidates.
    ai=gis.get('modeled_integration',{}).get('ai',{})
    if ai.get('status')=='modeled':
        for cls in ('grass_shrub','bare_soil'):
            g=_area_only(shape(ai.get('geometries',{}).get(cls,EMPTY)).intersection(unknown))
            if not g.is_empty:patches.append(('image-'+cls,g,{'image_class':cls},'image_candidate'))
    patch_conflicts=_area_only(union([g.intersection(h) for i,(_,g,_,_) in enumerate(patches) for _,h,_,_ in patches[i+1:]]))
    rows=[]
    def add(fid,g,p,basis,soil=None,extra=None):
        if g.is_empty or area(g)<.001:return
        saved_override=a.get('open_space_inputs',{}).get(fid,{})
        stale=bool(saved_override and saved_override.get('scope_sha256')!=review_scope(case))
        override={} if stale else saved_override
        cover,condition=_cover(p,override);missing=list(extra or [])
        if stale:missing.append('Previous cover review is stale after mapped-input change')
        group=None;possible=[]
        if soil:
            group,possible,reasons=soil_groups(soil['properties']);missing+=reasons
        else:missing.append('Soil group unknown')
        if cover not in TABLE:missing.append('PWD cover type unknown')
        elif condition not in TABLE[cover]:missing.append('Cover condition unknown')
        values=[]
        covers=[cover] if cover in TABLE else ['lawn','brush'] if p.get('image_class')=='grass_shrub' else ['dirt'] if p.get('image_class')=='bare_soil' else []
        for c in covers:
            conditions=[condition] if condition in TABLE[c] else list(TABLE[c])
            for cond in conditions:
                values.extend(TABLE[c][cond][GROUPS.index(s)] for s in possible)
        exact=TABLE[cover][condition][GROUPS.index(group)] if group and cover in TABLE and condition in TABLE[cover] and not extra else None
        sqft=area(g)
        rows.append({'feature_id':fid,'basis':basis,'input_basis':'manual review' if override else 'mapped attributes',
            'area_sqft':sqft,'geometry':mapping(g),'cover':cover,'condition':condition,'image_class':p.get('image_class'),
            'soil_group':group,'possible_soil_groups':possible,'mapunit_key':soil['properties'].get('mukey') if soil else None,
            'mapunit_name':soil['properties'].get('mapunit_name') if soil else None,'soil_polygon_id':soil.get('id') if soil else None,
            'soil_components':deepcopy(soil['properties'].get('components',[])) if soil else [],
            'curve_number':exact,'area_times_cn':sqft*exact if exact is not None else None,
            'candidate_cn_min':min(values) if values and not extra else None,'candidate_cn_max':max(values) if values and not extra else None,
            'status':'calculated_conditional' if exact is not None else 'unknown_inputs',
            'missing':list(dict.fromkeys(missing)),'cover_source':{k:deepcopy(p[k]) for k in ('source_family','source_url','source_sha256','model_sha256','acquisition_date','source_vintage') if k in p},
            'review':deepcopy(saved_override),'review_stale':stale})
    for fid,g,p,basis in patches:
        conflict=g.intersection(patch_conflicts)
        clean=g.difference(patch_conflicts)
        # Emit each conflicting area once; no arbitrary first-feature preference.
        if not conflict.is_empty:
            patches_conflict_seen=union([shape(r['geometry']) for r in rows if r['feature_id']=='conflicting-open-space'])
            add('conflicting-open-space',conflict.difference(patches_conflict_seen),{},basis,extra=['Overlapping open-space cover inputs'])
        add(fid,clean.intersection(soil_conflicts),p,basis,extra=['Overlapping soil polygons; unique soil assignment unknown'])
        clean=clean.difference(soil_conflicts)
        for soil,sg in soils:add(fid,clean.intersection(sg),p,basis,soil)
        add(fid,clean.difference(soil_union),p,basis,extra=['Soil polygon coverage missing'])
    # Frozen pervious geometry may be supplied without detailed feature records.
    mapped_union=union([g for _,g,_,basis in patches if basis=='mapped_open_space'])
    add('unattributed-open-space',physical.difference(mapped_union),{},'mapped_open_space',extra=['Mapped open space has no cover feature'])
    mapped=[r for r in rows if r['basis']=='mapped_open_space'];candidates=[r for r in rows if r['basis']=='image_candidate']
    # Appendix A steps 3-5: sum(area x CN) / sum(area). Summed in Decimal so a
    # uniform CN61 split into strips averages to exactly 61 (review B4).
    d_total=sum((_dec(r['area_sqft']) for r in mapped),Decimal(0))
    d_known=sum((_dec(r['area_sqft']) for r in mapped if r['curve_number'] is not None),Decimal(0))
    d_product=sum((_dec(r['area_sqft'])*Decimal(r['curve_number']) for r in mapped if r['curve_number'] is not None),Decimal(0))
    total=float(d_total);known=float(d_known);product=float(d_product)
    complete=total>.000001 and total-known<.001
    d_average=d_product/d_total if complete else None
    average=float(d_average) if d_average is not None else None
    unresolved=area(unknown)
    # A complete mapped subset still cannot establish all open space on an
    # incompletely mapped parcel. Keep that average separate from property CN.
    property_cn=average if average is not None and unresolved<.001 else None
    d_property_cn=d_average if property_cn is not None else None
    if unresolved>=.001:issues.append('Unresolved ground may contain additional open space; property-wide CN unknown')
    if not total:issues.append('No confirmed mapped open-space area; absence is not established')
    if total-known>=.001:issues.append('Open-space rows have unresolved cover, condition or soil inputs')
    output={'version':VERSION,'status':'calculated_conditional' if property_cn is not None else 'incomplete',
        'average_cn':property_cn,'mapped_open_space_average_cn':average,'known_portion_average_cn':float(d_product/d_known) if d_known else None,
        'mapped_open_space_sqft':total if total else None,'known_cn_area_sqft':known if total else None,
        'unknown_cn_area_sqft':float(d_total-d_known) if total else None,'image_candidate_area_sqft':sum(r['area_sqft'] for r in candidates) if ai.get('status')=='modeled' else None,
        'unresolved_ground_sqft':unresolved,'total_area_times_cn':product if complete else None,
        'credit_factor':open_space_factor(d_property_cn) if d_property_cn is not None else None,
        'rows':rows,'issues':list(dict.fromkeys(issues)),
        'area_tolerance_sqft':.001,
        'formula':'Average CN = sum(area × CN) / total open-space area; impervious areas excluded',
        'lookup_sha256':sha256(canonical(TABLE)).hexdigest(),
        'rule_source':{'url':MANUAL_URL,'sha256':'5c7b6e87ae442731625b91e278ccdd160a21e960b3460886e8349aa42f8ffb49','version':'September 2026','sections':'Appendix A Tables A-1 and A-2',
                       'verified_from':'2026-09-01','verified_through':'2027-08-31'},
        'soil_status':snapshot.get('status','not_acquired'),'soil_snapshot_sha256':snapshot.get('snapshot_sha256'),
        'soil_sources':deepcopy(snapshot.get('sources',[])),
        'gis_analysis_sha256':gis.get('analysis_sha256'),'gis_input_sha256':gis.get('input_sha256'),
        'claim':'Conditional mapped-soil estimate, not verified site soil, permeability, eligibility or an award. Image candidates are separate. No benefits or manual CN facts are changed.',
        'rounding':'Average summed in Decimal; credit counts whole CN steps below 75 (manual 4.3.3.1), so a fractional average uses the next whole CN upward. PWD has not confirmed fractional handling. No automatic bill savings allocation.'}
    output['worksheet_sha256']=sha256(canonical(output)).hexdigest()
    return output


def _dec(value):
    """Area as Decimal from its shortest float repr (no binary expansion)."""
    return Decimal(str(value))


def _area_only(g):
    if g.geom_type in ('Polygon','MultiPolygon'):return g
    return union([_area_only(p) for p in getattr(g,'geoms',[])])


def review_inputs(case,feature_id,cover,condition,reason):
    if not isinstance(reason,str) or not reason.strip():raise ValueError('A review reason is required')
    if cover not in TABLE and cover not in (None,''):raise ValueError('Unsupported PWD cover type')
    if cover in TABLE:
        if set(TABLE[cover])=={'na'}:condition='na'
        elif condition not in TABLE[cover] and condition not in (None,''):raise ValueError('Unsupported cover condition')
    from drainage_core.geometry import effective_features
    ids={str(f['id']) for f in effective_features(case) if f.get('properties',{}).get('layer')=='surface' and f['properties'].get('class')=='pervious'}
    ids.update(('image-grass_shrub','image-bare_soil'))
    if not isinstance(feature_id,str) or feature_id not in ids:raise ValueError('Choose a mapped open-space feature')
    result=deepcopy(case);a=result.setdefault('assessment',{});inputs=a.setdefault('open_space_inputs',{})
    before=deepcopy(inputs.get(feature_id));entry={'cover':cover or None,'condition':condition or None,'reason':reason.strip(),'at':now(),'basis':'manual','scope_sha256':review_scope(case)}
    inputs[feature_id]=entry
    a.setdefault('open_space_reviews',[]).append({'feature_id':feature_id,'before':before,'after':deepcopy(entry),
        'before_sha256':sha256(canonical(before)).hexdigest(),'after_sha256':sha256(canonical(entry)).hexdigest()})
    return result
