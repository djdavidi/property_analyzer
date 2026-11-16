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


def _modeled_catchments(research, modeled):
    """Research/integration catchments keyed by (model, run, kind, receiver_id)."""
    found = {}
    primary = (research or {}).get('primary')
    if primary:
        for run in [('nominal', primary)] + [(v.get('name'), v) for v in (research or {}).get('sensitivity', [])]:
            for kind, key, idkey in (('gsi', 'catchments', 'gsi_id'), ('outlet', 'outlet_catchments', 'outlet_id')):
                for c in run[1].get(key, []):
                    found[('research', run[0], kind, str(c[idkey]))] = c['geometry']
    for run in (modeled or {}).get('runs', []):
        for c in run.get('catchments', []):
            found[('integration', run['name'], c['kind'], str(c['receiver_id']))] = c['geometry']
    return found


def _reference_target(r, conservative, modeled):
    """A conservative terminal label, or a modeled receiver catchment by ID (C8).

    Explicit: receiver_id with optional model (research|integration, default
    research), run (default nominal) and receiver_kind (gsi|outlet). An ``outlet``
    that is not a conservative terminal label is read as a receiver ID, with an
    optional ``gsi:``/``outlet:`` kind prefix. Ambiguous matches stay unmeasured.
    """
    if not r.get('receiver_id') and r.get('outlet') in conservative:
        return conservative[r['outlet']], {'model': 'conservative', 'terminal': r['outlet']}, None
    identifier = r.get('receiver_id'); kind = r.get('receiver_kind')
    if not identifier and r.get('outlet'):
        identifier = str(r['outlet'])
        for prefix in ('gsi', 'outlet'):
            if identifier.startswith(prefix + ':'):
                kind = kind or prefix; identifier = identifier[len(prefix) + 1:]
    if not identifier:
        return None, None, 'No reconstructed catchment for reference outlet'
    model = r.get('model', 'research'); run = r.get('run', 'nominal')
    matches = [(k, g) for k, g in modeled.items() if k[0] == model and k[1] == run and k[3] == str(identifier)
               and (kind is None or k[2] == kind)]
    if len(matches) > 1:
        return None, None, 'Reference receiver ID matches more than one modeled catchment; set receiver_kind'
    if not matches:
        return None, None, 'No reconstructed catchment for reference outlet'
    (model, run, kind, identifier), geometry = matches[0]
    return geometry, {'model': model, 'run': run, 'receiver_kind': kind, 'receiver_id': identifier}, None


def validate_case(case, measurement, drainage_geometries=None, *, research=None, modeled=None):
    refs = case.get('references', [])
    modeled_catchments = _modeled_catchments(research, modeled)
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
                target = {'model': 'measurement'}
            else:
                predicted, target, blocker = _reference_target(r, drainage_geometries or {}, modeled_catchments)
                if not predicted:
                    blockers.append(blocker); continue
            accepted.append({'reference_id':r['id'],'holdout':r.get('holdout',False),'target':target,
                             'metrics':compare_geometry(predicted,r['geometry'],case['crs'],case.get('area_crs')),
                             'source_url':r['source_url'], 'acquisition_date':r.get('acquisition_date'),
                             'routing_disagreements':r.get('routing_disagreements','Not independently reviewed'),
                             'resolution_sensitivity':r.get('resolution_sensitivity','Not evaluated')})
        if not candidates:
            blockers.append('No independent '+kind+' reference supplied')
        result[kind]={'status':'measured' if accepted else 'incomplete','results':accepted,'blockers':blockers,
                      'accuracy_target':None}
    return result
