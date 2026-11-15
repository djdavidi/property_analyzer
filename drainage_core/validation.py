"""Independent-reference metrics, deliberately separate for IA and catchments."""
from shapely.geometry import shape
from .geometry import area_sqft,reproject


def compare_geometry(predicted, reference, crs, area_crs=None):
    p, r = shape(predicted), shape(reference)
    if not p.is_valid or not r.is_valid or r.is_empty or r.area <= 0 or r.geom_type not in ('Polygon','MultiPolygon'):
        raise ValueError('Reference and predicted geometries must be valid; reference nonempty')
    intersection = p.intersection(r)
    union = p.union(r)
    area_crs=area_crs or crs
    sf = lambda g: area_sqft(reproject(g,crs,area_crs) if crs!=area_crs else g,area_crs)
    pa, ra = sf(p), sf(r)
    return {'predicted_sqft':pa,'reference_sqft':ra,'signed_error_sqft':pa-ra,
            'absolute_error_percent':100*abs(pa-ra)/ra,
            'intersection_over_union':sf(intersection)/sf(union) if union.area else 0,
            'precision':sf(intersection)/pa if pa else 0,
            'recall':sf(intersection)/ra,'area_crs':area_crs,
            'false_positive_sqft':sf(p.difference(r)),
            'false_negative_sqft':sf(r.difference(p)),
            'boundary_hausdorff_native_units':p.boundary.hausdorff_distance(r.boundary) if not p.is_empty else None}


def validate_case(case, measurement, drainage_geometries=None):
    refs = case.get('references', [])
    result = {}
    for kind in ('ia','drainage'):
        candidates=[r for r in refs if r.get('kind') == kind]
        accepted=[]; blockers=[]
        for r in candidates:
            if case.get('synthetic_case') or r.get('synthetic') or r.get('source_kind')=='synthetic' or str(r.get('source_url','')).startswith('synthetic:'):
                blockers.append('Synthetic fixtures are excluded from independent real-site validation')
                continue
            if not r.get('independent') or not r.get('source_url') or not r.get('stable_site_verified'):
                blockers.append('Reference needs independent source, source URL and verified stable site vintage')
                continue
            if r.get('crs') != case['crs']:
                blockers.append('Reference CRS must match case; reproject explicitly')
                continue
            if kind == 'ia':
                if not measurement['complete']:
                    blockers.append('IA surface coverage is incomplete'); continue
                predicted=measurement['geometries']['physical_ia']
            else:
                predicted=(drainage_geometries or {}).get(r.get('outlet'))
                if not predicted:
                    blockers.append('No reconstructed catchment for reference outlet'); continue
            accepted.append({'reference_id':r['id'],'holdout':r.get('holdout',False),
                             'metrics':compare_geometry(predicted,r['geometry'],case['crs'],case.get('area_crs')),
                             'source_url':r['source_url'], 'acquisition_date':r.get('acquisition_date'),
                             'routing_disagreements':r.get('routing_disagreements','Not independently reviewed'),
                             'resolution_sensitivity':r.get('resolution_sensitivity','Not evaluated')})
        if not candidates:
            blockers.append('No independent '+kind+' reference supplied')
        result[kind]={'status':'measured' if accepted else 'incomplete','results':accepted,'blockers':blockers,
                      'accuracy_target':None}
    return result
