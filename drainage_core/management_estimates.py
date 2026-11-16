"""Additional physical estimates from frozen geometry, never legal eligibility.

No routing, inference or acquisition takes place here.  Appearance assumptions,
unverified connections and DEM-visible storage remain separate from observations.
"""
from copy import deepcopy
from math import isfinite

import numpy as np
from rasterio.features import shapes
from rasterio.transform import from_origin
from shapely.geometry import Point, box, mapping, shape

from .extent import catchment_extent, geometry_cells
from .geometry import case_area_sqft, effective_features, measure, union
from .installation import installation_issues
from .model_integration import CLASSES, _area_only, _polygon, ai_surfaces
from .research import METRES, digest

VERSION = 'saved-management-geometry-v1'
EMPTY = {'type': 'GeometryCollection', 'geometries': []}


def _frozen(case, gis):
    """Bind the interpretation to exact saved inputs when a hash is supplied."""
    from .engine import ENGINE_VERSION, input_hash, result_hash
    if gis.get('input_sha256') and gis['input_sha256'] != input_hash(case):
        raise ValueError('Frozen GIS input does not match this case')
    if gis.get('analysis_sha256') and gis['analysis_sha256'] != result_hash(gis):
        raise ValueError('Frozen GIS content hash does not match')
    if str(gis.get('engine_version', '')).startswith('gis-engine-'):
        from .quality import artifact_quality
        if gis['engine_version'] != ENGINE_VERSION or artifact_quality(gis)['status'] == 'outdated':
            raise ValueError('Historical or invalidated GIS requires an explicitly updated physical artifact')
    # Re-measure source observations, never historical AI-promoted IA totals.
    observation = measure(case)
    ai = ai_surfaces(case, observation)
    integration = gis.get('modeled_integration', {})
    roof_research = integration.get('ai_roof_drainage')
    research = roof_research or gis.get('research_drainage', {})
    lineage = {'case_sha256': input_hash(case), 'gis_analysis_sha256': gis.get('analysis_sha256'),
        'gis_engine_version': gis.get('engine_version'), 'research_method': research.get('method'),
        'research_branch': 'saved_ai_roof_supplemented' if roof_research else 'saved_source_roofs_only',
        'saved_integration_version': integration.get('version'),
        'interpretation': 'Reinterpreted saved class geometries; historical AI IA totals are not reused',
        'prediction_sha256': ai.get('prediction_sha256'), 'ai_sources': deepcopy(ai['sources'])}
    return observation, ai, research, lineage


def _routing_alternatives(case, gis, system_id, selected_branch):
    """Retain the source-roof branch as a diagnostic, not another money run."""
    if selected_branch != 'saved_ai_roof_supplemented':
        return []
    source = gis.get('research_drainage', {})
    parcel = shape(case['parcel']); alternatives = []
    for name, geometry, run in _runs({}, source, system_id):
        alternatives.append({'name': name, 'research_branch': 'saved_source_roofs_only',
            'geometry': mapping(geometry),
            'contributing_area_sqft': case_area_sqft(geometry, case),
            'on_parcel_area_sqft': case_area_sqft(geometry.intersection(parcel), case),
            'off_parcel_area_sqft': case_area_sqft(geometry.difference(parcel), case),
            'diagnostics': _diagnostics(case, run, geometry),
            'scope': 'Routing diagnostic only; excluded from selected area scenarios and savings',
            'limitations': ['Missing source roof outlines can route actual buildings as ground; this branch is not automatically a plausible upper bound']})
    return alternatives


def _runs(gis, research, system_id):
    full = [('nominal', research['primary'])] if research.get('primary') else []
    full += [(r['name'], r) for r in research.get('sensitivity', [])]
    lookup = dict(full)
    saved = gis.get('modeled_integration', {}).get('runs', [])
    # Integrated geometries can include the explicitly saved AI-roof branch.
    if saved:
        for run in saved:
            parts = [shape(c['geometry']) for c in run.get('catchments', [])
                     if c.get('kind') == 'gsi' and str(c.get('receiver_id')) == system_id]
            if parts:
                yield run['name'], _area_only(union(parts)), lookup.get(run['name'], run)
    else:
        for name, run in full:
            parts = [shape(c['geometry']) for c in run.get('catchments', [])
                     if str(c.get('gsi_id')) == system_id]
            if parts:
                yield name, _area_only(union(parts)), run


def _grid_array(case, run, field):
    grid = run.get('grid', {})
    values = run.get('rasters', {}).get(field)
    if values is None and field == 'filled_elevations':
        terrain = case.get('terrain') or {}
        if all(grid.get(k) == terrain.get(k) for k in ('origin', 'cell_size', 'crs')):
            values = terrain.get('elevations')
    if values is None or not grid.get('origin') or not grid.get('cell_size'):
        return None
    array = np.asarray(values, dtype=float)
    if array.ndim != 2 or not array.size or np.isinf(array).any():
        raise ValueError('Invalid frozen diagnostic raster')
    return array


def _diagnostics(case, run, geometry):
    result = {'extent_sufficient': run.get('extent_sufficient'),
        'invariants': deepcopy(run.get('invariants')),
        'touches_grid_boundary': None, 'touches_window_edge': None, 'touches_nodata': None, 'extent_complete': None,
        'roof_destinations': 'Only saved explicit routes are included; unconnected roofs are not assigned',
        'interpretation': 'An in-window catchment is retained when upstream extent is incomplete'}
    grid = run.get('grid', {})
    array = _grid_array(case, run, 'filled_elevations')
    if array is not None:
        # Same definition as research/integration catchments (drainage_core.extent).
        cells = geometry_cells(geometry, array.shape, grid['origin'], grid['cell_size'])
        contact = catchment_extent(cells, ~np.isfinite(array), (run.get('coverage') or {}).get('terrain_covers_parcel_buffer'))
        result.update(contact, touches_grid_boundary=contact['touches_window_edge'])
    elif run.get('nodata_cells') == 0:
        result['touches_nodata'] = False
    result['input_dem_sha256'] = run.get('input_dem_sha256')
    return result


def _surface_run(case, observation, ai, name, geometry, run, **extra):
    parcel = shape(case['parcel']); region = _area_only(geometry.intersection(parcel))
    observed = _polygon(observation['geometries']['physical_ia'])
    unknown = _polygon(observation['geometries']['unknown'])
    identified = _area_only(observed.union(shape(ai['ai_ia_on_unknown_geometry'])).intersection(region))
    road = _area_only(shape(ai['geometries']['road']).intersection(unknown).intersection(region))
    developed = _area_only(shape(ai['geometries']['developed_space']).intersection(unknown).intersection(region))
    scenarios = [('low', identified, 'Identified observations plus dated modeled roof IA only', []),
        ('base', identified.union(road), 'Road appearance assumed impervious',
         ['All road-appearance pixels in this catchment are impermeable; this is unverified']),
        ('high', identified.union(road).union(developed), 'Road and developed-space appearance assumed impervious',
         ['All road/developed-space pixels in this catchment are impermeable; this is unverified'])]
    sf = lambda g: case_area_sqft(_area_only(g), case)
    return {'name': name, 'geometry': mapping(geometry), 'on_parcel_geometry': mapping(region),
        'contributing_area_sqft': sf(geometry), 'on_parcel_area_sqft': sf(region),
        'off_parcel_area_sqft': sf(geometry.difference(parcel)),
        'identified_ia_sqft': sf(identified),
        'appearance_areas_sqft': {key: sf(shape(ai['geometries'][key]).intersection(region)) for key in CLASSES},
        'unresolved_ground_sqft': sf(unknown.intersection(region)),
        'unclassified_area_sqft': sf(region.difference(shape(ai['coverage_geometry']))),
        'area_scenarios': [{'id': key, 'area_sqft': sf(g), 'geometry': mapping(_area_only(g)),
            'basis': basis, 'assumptions': assumptions,
            'scope': 'On-parcel candidate hard surface routed toward receiver, not established managed area'}
            for key, g, basis, assumptions in scenarios],
        'all_unknown_impervious_ceiling_sqft': sf(identified.union(unknown.intersection(region))),
        'captured_area_sqft': None, 'adequately_treated_area_sqft': None,
        'diagnostics': _diagnostics(case, run, geometry), **extra}


def _terminal_hypotheses(case, research, footprint):
    """A saved unassigned terminal inside a basin can nominate a pipe hypothesis.

    It is not an inlet observation.  Its precise upstream raster basin is used;
    no distance allocation or footprint-to-served-area multiplier is applied.
    """
    run = research.get('primary') or {}; grid = run.get('grid', {})
    raster = run.get('rasters', {}).get('micro_basins')
    if raster is None or not grid.get('origin') or not grid.get('cell_size'):
        return
    x, y = grid['origin']; size = grid['cell_size']; array = np.asarray(raster, dtype=np.int32)
    roofs = [shape(f['geometry']) for f in effective_features(case)
             if f.get('properties', {}).get('layer') == 'surface' and f['properties'].get('class') == 'roof']
    for basin in run.get('micro_basins', []):
        if basin.get('gsi_id') or basin.get('outlet_id') or not str(basin.get('terminal', '')).startswith(('unresolved:flat:', 'unresolved:depression:')):
            continue
        r, c = basin['sink_cell']; point = Point(x+(c+.5)*size, y-(r+.5)*size)
        if not footprint.covers(point):
            continue
        mask = array == basin['id']
        geometry = _area_only(union([shape(g) for g, _ in shapes(array, mask=mask,
            transform=from_origin(x, y, size, size))]).difference(union(roofs)))
        if not geometry.is_empty:
            yield 'hypothetical-terminal-'+str(basin['id']), geometry, run, {
                'kind': 'connection_hypothesis', 'terminal': deepcopy(basin),
                'collection_point': mapping(point),
                'assumptions': ['An unobserved collection point exists at this saved terminal and connects to the underground basin'],
                'evidence': 'Saved unassigned terrain terminal lies inside mapped basin footprint; no inlet or pipe is documented'}


def _conservative_terminal_hypothesis(case, gis, footprint):
    """Retain original depression catchments as a separate connection hypothesis."""
    run = gis.get('drainage', {}); origin = run.get('origin'); size = run.get('cell_size')
    if not origin or not size:
        return
    x, y = origin; parts = []; points = []
    for catchment in run.get('catchments', []):
        label = str(catchment.get('outlet', ''))
        if not label.startswith('unresolved:depression:'):
            continue
        try:
            r, c = map(int, label.rsplit(':', 2)[-2:])
        except ValueError:
            continue
        point = Point(x+(c+.5)*size, y-(r+.5)*size)
        if not footprint.covers(point):
            continue
        geometry = _polygon(catchment['geometry'])
        if not geometry.covers(point):
            raise ValueError('Saved terminal point is not in its catchment')
        parts.append(geometry)
        points.append({'terminal': label, 'collection_point': mapping(point),
            'upstream_geometry': mapping(geometry),
            'upstream_area_sqft': case_area_sqft(geometry, case)})
    if parts:
        adapted = {**run, 'grid': {k: run.get(k) for k in
            ('origin', 'cell_size', 'crs', 'horizontal_unit', 'vertical_unit')}}
        yield 'hypothetical-conservative-depression-collection', _area_only(union(parts)), adapted, {
            'kind': 'connection_hypothesis', 'candidate_collection_points': points,
            'connection_hypothesis_count': len(points),
            'assumptions': ['Each named in-footprint depression terminal has an unobserved collection point connected to this basin'],
            'evidence': 'Exact original conservative depression terminals and their upstream catchments; no observed inlet/pipe',
            'connection_scope': 'Union of named hypothetical connections; any subset, including none, may actually connect'}


def _surface_storage(case, research, footprint, underground=False):
    limits = ['Surface depression volume only; excludes media, infiltration, pipes and hidden storage',
        'DEM age/resolution, grading and actual rim/outlet elevations require site verification',
        'Neither effective treatment capacity nor captured runoff is established']
    if underground:
        return {'status': 'unavailable', 'volume_cuft': None,
            'reason': 'Surface DEM cannot measure underground storage', 'limitations': limits}
    run = research.get('primary') or {}; grid = run.get('grid', {})
    depth = _grid_array(case, run, 'fill_depth')
    if depth is None:
        return {'status': 'unavailable', 'volume_cuft': None,
            'reason': 'Frozen pre-infrastructure depression-fill raster is unavailable', 'limitations': limits}
    # This raster is filled DEM minus source DEM, before any paper burn offsets.
    terrain = case.get('terrain') or {}
    source_hash = run.get('input_dem_sha256')
    if not source_hash or source_hash != digest(terrain.get('elevations')):
        return {'status': 'unavailable', 'volume_cuft': None,
            'reason': 'Pre-burn fill raster cannot be bound to the saved source elevation grid', 'limitations': limits}
    factor = METRES.get(grid.get('vertical_unit'))
    if factor is None or any(grid.get(k) != terrain.get(k) for k in ('origin', 'cell_size', 'crs')):
        return {'status': 'unavailable', 'volume_cuft': None,
            'reason': 'Pre-burn fill grid units/alignment are not established', 'limitations': limits}
    if depth.shape != np.asarray(terrain['elevations'], dtype=float).shape or (depth[np.isfinite(depth)] < -1e-9).any():
        raise ValueError('Invalid frozen pre-burn fill-depth grid')
    region = _area_only(footprint.intersection(shape(case['parcel'])))
    x, y = grid['origin']; size = grid['cell_size']; volume = 0.; valid_parts = []; missing_parts = []
    minx, miny, maxx, maxy = region.bounds if not region.is_empty else (0, 0, 0, 0)
    r0 = max(0, int(np.floor((y-maxy)/size))); r1 = min(depth.shape[0], int(np.ceil((y-miny)/size)))
    c0 = max(0, int(np.floor((minx-x)/size))); c1 = min(depth.shape[1], int(np.ceil((maxx-x)/size)))
    for r in range(r0, r1):
        for c in range(c0, c1):
            part = _area_only(box(x+c*size, y-(r+1)*size, x+(c+1)*size, y-r*size).intersection(region))
            if part.is_empty: continue
            if isfinite(depth[r, c]):
                valid_parts.append(part)
                volume += case_area_sqft(part, case)*max(0., float(depth[r, c]))*factor/.3048
            else:
                missing_parts.append(part)
    covered = union(valid_parts); missing = _area_only(region.difference(covered))
    return {'status': 'partial' if not missing.is_empty else 'modeled', 'volume_cuft': volume,
        'covered_footprint_sqft': case_area_sqft(covered, case),
        'uncovered_or_nodata_footprint_sqft': case_area_sqft(missing, case),
        'basis': 'Cell depth × polygon-intersection area from saved filled-minus-source DEM, before burn offsets',
        'input_dem_sha256': source_hash, 'fill_depth_sha256': digest(run['rasters']['fill_depth']),
        'limitations': limits}


def estimate_system(case, frozen_gis, system_id):
    """Return additional per-system area scenarios without changing saved results."""
    system_id = str(system_id)
    observation, ai, research, lineage = _frozen(case, frozen_gis)
    features = [f for f in effective_features(case)
        if str(f.get('properties', {}).get('gsi_system_id')) == system_id
        and f.get('properties', {}).get('kind') == 'system_footprint']
    if not features:
        raise ValueError('Mapped system footprint not found: '+system_id)
    footprint = _area_only(union([_polygon(f['geometry']) for f in features]))
    types = sorted({str(f.get('properties', {}).get('gsi_system_type', 'Unknown')) for f in features})
    if len(types) != 1:
        raise ValueError('Conflicting mapped system types: '+system_id)
    underground = any(s in types[0].lower() for s in ('subsurface', 'underground'))
    issues = list(dict.fromkeys(issue for f in features for issue in installation_issues(
        f.get('properties', {}), case.get('imagery_age_policy', {}).get('as_of') or case.get('created_at'))))
    result = {'version': VERSION, 'system_id': system_id, 'system_type': types[0],
        'footprint_geometry': mapping(footprint), 'footprint_area_sqft': case_area_sqft(footprint, case),
        'on_parcel_footprint_sqft': case_area_sqft(footprint.intersection(shape(case['parcel'])), case),
        'source_features': deepcopy(features), 'source_lineage': lineage, 'runs': [],
        'alternative_routing': _routing_alternatives(case, frozen_gis, system_id, lineage['research_branch']),
        'confidence': {'status': 'not_calibrated', 'percentage': None},
        'missing_evidence': ['Actual inlet/pipe/roof routes and bypasses', 'Storage, infiltration and adequate treatment',
            'Locally checked surface classes and current installation/condition'],
        'ai_exclusions': deepcopy(ai['excluded']), 'installation_issues': issues}
    if issues:
        result.update(status='excluded', surface_storage_diagnostic={'status': 'excluded', 'volume_cuft': None})
        return result
    for name, geometry, run in _runs(frozen_gis, research, system_id):
        result['runs'].append(_surface_run(case, observation, ai, name, geometry, run,
            kind='saved_surface_route', route_basis='Frozen modeled receiver catchment'))
    if underground and not result['runs']:
        for name, geometry, run, evidence in _terminal_hypotheses(case, research, footprint):
            result['runs'].append(_surface_run(case, observation, ai, name, geometry, run, **evidence))
        for name, geometry, run, evidence in _conservative_terminal_hypothesis(case, frozen_gis, footprint):
            result['runs'].append(_surface_run(case, observation, ai, name, geometry, run, **evidence))
    for run in result['runs']:
        on = shape(run['on_parcel_geometry'])
        run['within_system_footprint_sqft'] = case_area_sqft(on.intersection(footprint), case)
        run['outside_system_footprint_sqft'] = case_area_sqft(on.difference(footprint), case)
    result['status'] = ('connection_hypothesis' if underground else 'modeled') if result['runs'] else 'connection_unknown'
    if not result['runs']:
        result['missing_evidence'].append('No saved upstream catchment is connected to this footprint; footprint is not served area')
    result['surface_storage_diagnostic'] = _surface_storage(case, research, footprint, underground)
    result['range_basis'] = 'Explicit surface/connection hypotheses and DEM sensitivity; not a confidence interval'
    result['scenario_envelope_sqft'] = {key: {
        'minimum': min((s['area_sqft'] for r in result['runs'] for s in r['area_scenarios'] if s['id'] == key), default=None),
        'maximum': max((s['area_sqft'] for r in result['runs'] for s in r['area_scenarios'] if s['id'] == key), default=None)}
        for key in ('low', 'base', 'high')}
    return result


def estimate_canopy(case, frozen_gis):
    """Bound pavement beneath canopy separately from canopy's visible footprint."""
    observation, ai, _, lineage = _frozen(case, frozen_gis)
    parcel = shape(case['parcel'])
    canopy = _area_only(union([shape(observation['geometries']['canopy']),
        shape(ai['geometries']['canopy'])]).intersection(parcel))
    roofs = union([shape(f['geometry']) for f in effective_features(case)
        if f.get('properties', {}).get('layer') == 'surface' and f['properties'].get('class') == 'roof']
        + [shape(ai['geometries']['roof'])])
    ground = _area_only(canopy.difference(roofs))
    known = _area_only(ground.intersection(shape(observation['geometries']['physical_ia'])))
    hidden = _area_only(ground.intersection(shape(observation['geometries']['unknown'])))
    road = _area_only(hidden.intersection(shape(ai['geometries']['road'])))
    complete = observation.get('canopy_status') == 'complete' or (
        ai['status'] == 'modeled' and case_area_sqft(
            _area_only(parcel.difference(shape(ai['coverage_geometry']))), case) < .001)
    available = complete or not canopy.is_empty
    scenarios = [('low', known, 'Observed ground IA beneath mapped canopy'),
        ('base', known.union(road), 'Observed ground IA plus road appearance assumed impervious beneath canopy'),
        ('high', known.union(hidden), 'All unresolved ground beneath canopy assumed impervious')]
    return {'version': VERSION, 'status': 'modeled' if complete else 'partial' if available else 'unavailable',
        'canopy_geometry': mapping(canopy),
        'canopy_area_sqft': case_area_sqft(canopy, case) if available else None,
        'mapped_canopy_extent_sqft': case_area_sqft(canopy, case),
        'canopy_coverage_complete': complete,
        'known_ground_ia_beneath_canopy_sqft': case_area_sqft(known, case),
        'unresolved_ground_beneath_canopy_sqft': case_area_sqft(hidden, case),
        'roof_overlap_excluded_sqft': case_area_sqft(canopy.intersection(roofs), case),
        'area_scenarios': [{'id': key, 'area_sqft': case_area_sqft(g, case), 'geometry': mapping(_area_only(g)),
            'basis': basis, 'assumptions': [] if key == 'low' else [basis],
            'scope': 'Underlying ground IA hypothesis only, not a credit award'} for key, g, basis in scenarios] if available else [],
        'source_lineage': lineage, 'ai_exclusions': deepcopy(ai['excluded']),
        'confidence': {'status': 'not_calibrated', 'percentage': None},
        'missing_evidence': ['Pavement/permeability beneath obscuring canopy',
            'Current canopy outline and eligibility measurements']}
