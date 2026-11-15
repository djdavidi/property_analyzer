"""Projected physical-area accounting; observations never inherit billing totals."""
from copy import deepcopy
from math import isfinite
from pyproj import CRS, Transformer
from shapely.geometry import shape, mapping, GeometryCollection
from shapely.ops import unary_union, transform

SQFT_PER_M2 = (1 / 0.3048) ** 2


def projected_crs(crs):
    c = CRS.from_user_input(crs)
    if not c.is_projected or not c.axis_info:
        raise ValueError("Area calculations require an explicit projected CRS")
    return c


def area_m2(geometry, crs):
    """Projected geometry area expressed in square metres, regardless of native units."""
    c = projected_crs(crs)
    return geometry.area * c.axis_info[0].unit_conversion_factor ** 2


def area_sqft(geometry, crs):
    return area_m2(geometry,crs) * SQFT_PER_M2


def polygon(value):
    g = shape(value)
    if g.geom_type not in ('Polygon', 'MultiPolygon') or not g.is_valid or g.is_empty:
        raise ValueError("Expected a nonempty valid Polygon or MultiPolygon; repair explicitly")
    if not all(isfinite(v) for v in g.bounds):
        raise ValueError("Geometry coordinates must be finite")
    return g


def reproject(geometry, source, target):
    return transform(Transformer.from_crs(source, target, always_xy=True).transform, geometry)


def case_area_m2(geometry, case):
    """Keep area accounting in a designated local CRS when terrain CRS changes."""
    target=case.get('area_crs',case['crs'])
    projected_crs(target)
    g=reproject(geometry,case['crs'],target) if target != case['crs'] else geometry
    return area_m2(g,target)


def case_area_sqft(geometry, case):
    return case_area_m2(geometry,case) * SQFT_PER_M2


def union(items):
    return unary_union(items) if items else GeometryCollection()


def effective_features(case):
    """Apply append-only edits without altering source observations.

    Surface corrections occlude earlier surfaces within their geometry. Removing
    an edit replays the original observations rather than destructively erasing them.
    """
    features = deepcopy(case.get('features', {}).get('features', []))
    features.extend({'type':'Feature','id':b['id'],'geometry':deepcopy(b['geometry']),
                     'properties':{'layer':'benefit','benefit':deepcopy(b)}}
                    for b in case.get('benefits',[]) if b.get('geometry'))
    by_id = {f['id']: f for f in features}
    if len(by_id) != len(features):
        raise ValueError('Feature IDs must be unique')
    for edit in case.get('corrections', []):
        if not edit.get('reason') or not edit.get('at'):
            raise ValueError('Corrections need a reason and timestamp')
        action = edit['action']
        if action == 'delete':
            if edit['target'] not in by_id:
                raise ValueError('Correction target does not exist')
            del by_id[edit['target']]
        elif action in ('add', 'replace'):
            f = deepcopy(edit['feature'])
            if action == 'replace' and edit['target'] not in by_id:
                raise ValueError('Correction target does not exist')
            if action == 'replace':
                del by_id[edit['target']]
            if f['id'] in by_id:
                raise ValueError('Correction feature ID already exists')
            f.setdefault('properties', {})['correction_id'] = edit['id']
            f['properties']['evidence'] = 'manual_correction'
            if f['properties'].get('layer') == 'surface':
                mask = polygon(f['geometry'])
                for old in list(by_id.values()):
                    if old['properties'].get('layer') == 'surface':
                        remaining = shape(old['geometry']).difference(mask)
                        if remaining.is_empty:
                            del by_id[old['id']]
                        else:
                            old['geometry'] = mapping(remaining)
            by_id[f['id']] = f
        else:
            raise ValueError('Unknown correction action')
    return list(by_id.values())


def measure(case):
    crs = case['crs']
    projected_crs(crs)
    parcel = polygon(case['parcel'])
    classes = {key: [] for key in ('roof', 'pavement', 'pervious', 'unknown', 'canopy')}
    warnings = []
    for f in effective_features(case):
        p = f.get('properties', {})
        key = 'canopy' if p.get('layer') == 'canopy' else p.get('class') if p.get('layer') == 'surface' else None
        if key:
            if key not in classes:
                raise ValueError('Unsupported surface class: ' + key)
            classes[key].append(polygon(f['geometry']).intersection(parcel))
    geom = {key: union(v) for key, v in classes.items()}
    raw_ia = geom['roof'].union(geom['pavement'])
    conflicts = raw_ia.intersection(geom['pervious'])
    ambiguous = geom['unknown'].union(conflicts)
    ia = raw_ia.difference(ambiguous)
    pervious = geom['pervious'].difference(raw_ia).difference(ambiguous)
    unknown = parcel.difference(ia.union(pervious))
    ground = geom['pavement'].difference(geom['roof']).difference(ambiguous)
    canopy_ground = ground.intersection(geom['canopy'])
    if conflicts.area > 1e-8:
        warnings.append('Conflicting impervious/pervious observations are unknown until corrected')
    if unknown.area > 1e-8:
        warnings.append('Unknown surface area prevents a complete physical IA measurement')
    dependence = sorted({str(f.get('properties', {}).get('source_family') or f.get('properties', {}).get('source_url') or 'Unidentified declared dependency') for f in effective_features(case)
                         if f.get('properties', {}).get('layer') == 'surface'
                         and (f.get('properties', {}).get('source_dependency') is True
                              or f.get('properties', {}).get('source_family') in case.get('dependent_source_families', []))})
    if dependence:
        warnings.append('Surface measurement depends on declared source datasets; agreement with those same datasets is not independent validation')
    sf = lambda g: case_area_sqft(g, case)
    result = {
        'ga_sqft': sf(parcel), 'ia_sqft': sf(ia), 'ia_min_sqft': sf(ia),
        'ia_max_sqft': sf(ia.union(unknown)), 'unknown_sqft': sf(unknown),
        'pervious_sqft': sf(pervious), 'roof_sqft': sf(geom['roof'].intersection(ia)),
        'ground_ia_sqft': sf(ground), 'canopy_ground_ia_sqft': sf(canopy_ground),
        'complete': sf(unknown) < .001, 'boundary_claim': 'Source-polygon consistency only; legal boundary unverified',
        'area_crs':case.get('area_crs',crs),
        'source_dependence': dependence, 'warnings': warnings,
        'geometries': {key: mapping(g) for key, g in {'physical_ia': ia, 'unknown': unknown,
                         'pervious': pervious, 'canopy_ground_ia': canopy_ground}.items()},
    }
    result.update({name[:-5]+'_m2':value/SQFT_PER_M2
                   for name,value in list(result.items()) if name.endswith('_sqft')})
    return result
