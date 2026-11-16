"""Free local adaptation of the Villanova/Temple fill/burn/D8/basin workflow.

This additional scenario never changes conservative routing, measured surfaces or
policy facts. ArcGIS-equivalence and empirical accuracy are not asserted.
"""
from collections import deque, Counter
from copy import deepcopy
from hashlib import sha256
import heapq
import json
import math

import numpy as np
from rasterio.features import rasterize, shapes
from rasterio.transform import from_origin
from shapely.geometry import shape, mapping, box
from .geometry import effective_features, union, case_area_sqft
from .drainage import route_grid

METHOD = 'villanova-temple-local-v1'
PAPER = 'https://doi.org/10.2166/wst.2023.072'
METRES = {'m': 1., 'ft': .3048, 'us-ft': 1200 / 3937}
# Table 3, metres; these are algorithmic enforcement offsets, not measured depths.
OFFSETS = {'lidar': {'building': 9.14, 'berm': .061, 'wall': 3.05,
                     'inlet': -1.52, 'gsi': -.91, 'curb_cut': -.91},
           'contour': {'building': 9.14, 'berm': .061,
                       'inlet': -3.05, 'gsi': -2.44, 'curb_cut': -3.05}}
NEIGHBOURS = [(dr, dc) for dr in (-1, 0, 1) for dc in (-1, 0, 1) if dr or dc]
DIRECTIONS = {(0, 1): 1, (1, 1): 2, (1, 0): 4, (1, -1): 8,
              (0, -1): 16, (-1, -1): 32, (-1, 0): 64, (-1, 1): 128}


def digest(value):
    return sha256(json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()).hexdigest()


def fill_dem(elevations):
    """Priority flood to the lowest edge/NoData-adjacent spill elevation, D8.

    Missing terrain is an open, uncertain boundary, never an interpolated surface.
    """
    z = np.asarray(elevations, dtype=float)
    if z.ndim != 2 or not z.size or z.size > 250000 or np.isinf(z).any():
        raise ValueError('Research DEM must be a finite rectangular grid, at most 250,000 cells')
    valid = np.isfinite(z)
    out = z.copy(); seen = ~valid.copy(); queue = []
    rows, cols = z.shape
    for r, c in np.argwhere(valid):
        if r in (0, rows - 1) or c in (0, cols - 1) or any(
                not valid[r + dr, c + dc] for dr, dc in NEIGHBOURS
                if 0 <= r + dr < rows and 0 <= c + dc < cols):
            seen[r, c] = True
            heapq.heappush(queue, (float(z[r, c]), int(r), int(c)))
    while queue:
        height, r, c = heapq.heappop(queue)
        for dr, dc in NEIGHBOURS:
            nr, nc = r + dr, c + dc
            if 0 <= nr < rows and 0 <= nc < cols and not seen[nr, nc]:
                seen[nr, nc] = True
                out[nr, nc] = max(height, z[nr, nc])
                heapq.heappush(queue, (float(out[nr, nc]), nr, nc))
    return out


def _json_grid(array):
    return [[None if not math.isfinite(float(v)) else float(v) for v in row] for row in array]


def feature_inputs(case):
    """Normalize generic features; never invent an inlet over an underground SMP."""
    features = []; omitted = []
    for f in effective_features(case):
        p = f.get('properties', {}); role = p.get('drainage_role')
        if not role:
            if p.get('layer') == 'surface' and p.get('class') == 'roof': role = 'building'
            elif p.get('layer') in ('inlet', 'gsi', 'berm', 'wall', 'curb_cut'): role = p['layer']
            elif p.get('layer') == 'footprint' and p.get('kind') == 'system_footprint':
                kind = str(p.get('gsi_system_type', '')).lower()
                if any(t in kind for t in ('rain garden', 'bioretention', 'vegetated swale', 'stormwater planter')):
                    role = 'gsi'
                else:
                    omitted.append({'id': str(f['id']), 'reason': 'System footprint does not establish a surface receiving feature or inlet'})
        if role:
            from .installation import installation_issues
            as_of=case.get('imagery_age_policy',{}).get('as_of') or case.get('created_at')
            issues=installation_issues(p,as_of) if role=='gsi' else []
            if issues:
                omitted.append({'id':str(f['id']),'reason':'; '.join(issues)});continue
            if role not in OFFSETS['lidar']: raise ValueError('Unsupported drainage_role: ' + str(role))
            features.append({'id': str(f['id']), 'role': role, 'geometry': deepcopy(f['geometry']),
                             'source': deepcopy(p), 'gsi_id': str(p.get('gsi_system_id') or f['id']) if role == 'gsi' else None,
                             'receives_at': p.get('gsi_id'), 'connection_evidence': p.get('connection_evidence', 'unknown')})
    # Extra local surveyed/digitized infrastructure uses exactly the same neutral schema.
    for f in case.get('research_drainage', {}).get('features', []):
        if f.get('role') not in OFFSETS['lidar']: raise ValueError('Unsupported research feature role')
        from .installation import installation_issues
        issues=installation_issues({**f.get('source',{}),**f},case.get('imagery_age_policy',{}).get('as_of') or case.get('created_at')) if f.get('role')=='gsi' else []
        if issues:
            omitted.append({'id':str(f['id']),'reason':'; '.join(issues)});continue
        features.append(deepcopy(f))
    grid=case.get('terrain') or {}
    if grid:
        size=grid['cell_size'];x,y=grid['origin'];ids={f['id'] for f in features}
        for inlet in grid.get('inlets',[]):
            if str(inlet['id']) in ids:continue
            r,c=inlet['cell']
            if not (0<=r<len(grid['elevations']) and 0<=c<len(grid['elevations'][0])):
                raise ValueError('Research inlet outside terrain')
            from shapely.geometry import Point
            features.append({'id':str(inlet['id']),'role':'inlet',
                'geometry':mapping(Point(x+(c+.5)*size,y-(r+.5)*size)),
                'source':{'origin':'supplied terrain inlet cell'}})
        if grid.get('roofs'):
            cells=[]
            for r,c in grid['roofs']:
                if not (0<=r<len(grid['elevations']) and 0<=c<len(grid['elevations'][0])):
                    raise ValueError('Research roof outside terrain')
                cells.append(box(x+c*size,y-(r+1)*size,x+(c+1)*size,y-r*size))
            features.append({'id':'terrain-roof-cells','role':'building','geometry':mapping(union(cells)),
                'source':{'origin':'supplied terrain roof cells'}})
    ids = [f['id'] for f in features]
    if any(not isinstance(i, str) or not i for i in ids) or len(ids) != len(set(ids)):
        raise ValueError('Research feature IDs must be unique nonempty strings')
    return sorted(features, key=lambda f: f['id']), omitted


def _mask(geometry, grid, buffer_m=0., all_touched=False):
    size = grid['cell_size']; factor = METRES[grid['horizontal_unit']]
    geom = shape(geometry)
    if not geom.is_valid or geom.is_empty: raise ValueError('Research infrastructure geometry must be valid and nonempty')
    if buffer_m: geom = geom.buffer(buffer_m / factor)
    return rasterize([(mapping(geom), 1)], out_shape=(len(grid['elevations']), len(grid['elevations'][0])),
                     transform=from_origin(*grid['origin'], size, size), all_touched=all_touched, dtype='uint8').astype(bool)


def condition(grid, features, *, dem_type='lidar', offset_scale=1., inlet_buffer_m=None, all_touched=False):
    """Fill first; rasterize offsets onto the filled DEM without a second fill.

    At overlaps: strongest raise wins over drops, except a mapped curb cut can
    cut a berm/wall. Buildings always win. Competing drops use the deepest one.
    These deterministic overlap rules are local decisions, not specified by Table 3.
    """
    if dem_type not in OFFSETS: raise ValueError('dem_type must be lidar or contour')
    if not math.isfinite(offset_scale) or offset_scale <= 0: raise ValueError('offset_scale must be positive')
    if grid.get('horizontal_unit') not in METRES or grid.get('vertical_unit') not in METRES:
        raise ValueError('Separate verified horizontal and vertical units are required')
    size = grid['cell_size']
    if isinstance(size, bool) or not math.isfinite(size) or size <= 0: raise ValueError('cell_size must be positive')
    raw = np.asarray(grid['elevations'], dtype=float); filled = fill_dem(grid['elevations'])
    factor = METRES[grid['vertical_unit']]; valid = np.isfinite(raw)
    rise = np.zeros(raw.shape); drop = rise.copy(); building = np.zeros(raw.shape, bool); cuts = building.copy()
    masks = {}; audit = []
    default_buffer = min(1.5, max(.305, size * METRES[grid['horizontal_unit']]))
    for f in features:
        role = f['role']
        if role not in OFFSETS[dem_type]: raise ValueError('No published offset for ' + role + ' with ' + dem_type)
        buffer = (.305 if role == 'gsi' else .152 if role == 'curb_cut' else
                  default_buffer if inlet_buffer_m is None else inlet_buffer_m) if role in ('gsi', 'curb_cut', 'inlet', 'wall') else 0.
        if not math.isfinite(buffer) or buffer < 0: raise ValueError('Infrastructure buffer must be nonnegative')
        mask = _mask(f['geometry'], grid, buffer, all_touched) & valid
        masks[f['id']] = mask
        offset = OFFSETS[dem_type][role] * offset_scale / factor
        if offset > 0: rise[mask] = np.maximum(rise[mask], offset)
        else: drop[mask] = np.minimum(drop[mask], offset)
        if role == 'building': building |= mask
        if role == 'curb_cut': cuts |= mask
        audit.append({'id': f['id'], 'role': role, 'raster_cells': int(mask.sum()), 'buffer_m': buffer,
                      'offset_m': offset * factor, 'source': deepcopy(f.get('source', {})),
                      'status': 'scenario' if mask.any() else 'not_represented_on_grid'})
    delta = np.where(rise > 0, rise, drop)
    delta[cuts & ~building] = drop[cuts & ~building]
    adjusted = filled + delta
    return {'filled': filled, 'adjusted': adjusted, 'fill_depth': filled - raw,
            'adjustment': delta, 'building': building, 'masks': masks, 'features': audit}


def accumulate(next_cells, labels):
    """Inclusive upstream counts over an acyclic D8 graph; excluded cells are zero."""
    rows, cols = len(labels), len(labels[0]); incoming = Counter(); active = set(); nxt = {}
    for r in range(rows):
        for c in range(cols):
            if labels[r][c] in ('nodata', 'barrier') or labels[r][c].startswith('unresolved:roof:'): continue
            p = (r, c); active.add(p)
            if next_cells[r][c] is not None:
                n = tuple(next_cells[r][c]); nxt[p] = n; incoming[n] += 1
    counts = {p: 1 for p in active}; queue = deque(sorted(p for p in active if not incoming[p])); visited = 0
    while queue:
        p = queue.popleft(); visited += 1
        if p in nxt:
            n = nxt[p]
            if n not in active: raise ValueError('Flow pointer enters an excluded cell')
            counts[n] += counts[p]; incoming[n] -= 1
            if incoming[n] == 0: queue.append(n)
    if visited != len(active): raise ValueError('Flow direction contains a cycle')
    out = np.zeros((rows, cols), dtype=np.int64)
    for p, value in counts.items(): out[p] = value
    return out


def _recipient(identifier, by_id, links):
    visited = []; current = identifier
    while current not in visited:
        visited.append(current); f = by_id.get(current)
        if f and f['role'] == 'gsi': return ('gsi',str(f.get('gsi_id') or current)), visited, None
        if f is None and len(visited)>1:
            return ('outlet',current),visited,None
        link = links.get(current)
        if not link or link.get('evidence') not in ('documented', 'scenario'):
            return None, visited, 'Downstream connection missing or unknown'
        current = str(link['to'])
    return None, visited, 'Connection cycle'


def run_model(case, measurement, features, *, offset_scale=1., inlet_buffer_m=None, all_touched=False, grid=None):
    grid = deepcopy(grid or case['terrain']); options = case.get('research_drainage', {})
    conditioned = condition(grid, features, dem_type=options.get('dem_type', 'lidar'), offset_scale=offset_scale,
                            inlet_buffer_m=inlet_buffer_m, all_touched=all_touched)
    routed_grid = deepcopy(grid); routed_grid['elevations'] = _json_grid(conditioned['adjusted'])
    # Collection is determined by the burned DEM, not by forcing every footprint pixel to collect.
    routed_grid['inlets'] = []; routed_grid['connections'] = []; routed_grid['roof_connections'] = []
    roof = conditioned['building'].copy()
    for cell in grid.get('roofs', []): roof[tuple(cell)] = True
    barrier = {tuple(c) for c in grid.get('barriers', [])}
    # Retain existing hard barriers when no surveyed/paper infrastructure role
    # was supplied. Their unknown height is not silently treated as zero.
    for f in effective_features(case):
        p=f.get('properties',{})
        if p.get('layer')=='barrier' and not p.get('drainage_role'):
            barrier.update(map(tuple,np.argwhere(_mask(f['geometry'],grid,all_touched=True))))
    barrier={p for p in barrier if np.isfinite(conditioned['adjusted'][p])}
    routed_grid['barriers']=[[int(r),int(c)] for r,c in sorted(barrier)]
    roof &= np.isfinite(conditioned['adjusted'])
    for cell in barrier: roof[cell] = False
    routed_grid['roofs'] = np.argwhere(roof).tolist()
    routed_grid.setdefault('settings', {})['max_flow_paths'] = 25
    flow = route_grid(routed_grid)
    accumulation = accumulate(flow['next_cells'], flow['labels'])
    by_id = {f['id']: f for f in features}
    links = {str(l['from']): l for l in grid.get('connections', [])}
    for f in effective_features(case):
        p = f.get('properties', {})
        if p.get('layer') == 'connection': links[str(p['from'])] = p
    for f in features:
        if f.get('receives_at'):
            target = str(f['receives_at'])
            target = next((x['id'] for x in features if str(x.get('gsi_id')) == target), target)
            links[f['id']] = {'to': target, 'evidence': f.get('connection_evidence', 'unknown')}
    # Integer basin raster polygonizes all terminal regions in one pass.
    names = sorted(set(label for row in flow['labels'] for label in row
                       if label not in ('nodata', 'barrier') and not label.startswith('unresolved:roof:')))
    codes = {label: i + 1 for i, label in enumerate(names)}
    basins = np.array([[codes.get(label, 0) for label in row] for row in flow['labels']], dtype=np.int32)
    transform = from_origin(*grid['origin'], grid['cell_size'], grid['cell_size'])
    geometries = {}
    for geom, value in shapes(basins, mask=basins > 0, transform=transform):
        geometries.setdefault(int(value), []).append(shape(geom))
    terminals = {}
    for r, c in np.argwhere(basins > 0):
        if flow['next_cells'][r][c] is None: terminals[flow['labels'][r][c]] = (int(r), int(c))
    parcel = shape(case['parcel']); ia = shape(measurement['geometries']['physical_ia'])
    building_geometry = union([shape(f['geometry']) for f in features if f['role'] == 'building'])
    unknown = shape(measurement['geometries']['unknown']); groups = {}; outlet_groups={}; basin_rows = []
    for name in names:
        code = codes[name]; root = terminals[name]
        recipients = set(); traces = []; unresolved = []
        for f in features:
            if f['role'] in ('gsi', 'inlet', 'curb_cut') and conditioned['masks'][f['id']][root]:
                target, path, reason = _recipient(f['id'], by_id, links)
                if target: recipients.add(target)
                traces.append(path)
                if reason: unresolved.append(reason)
        # Competing receiver identities and any unresolved overlapping collection
        # feature remain ambiguous; do not award the entire basin to both.
        target = next(iter(recipients)) if len(recipients) == 1 and not unresolved else None
        if target:
            (groups if target[0]=='gsi' else outlet_groups).setdefault(target[1],[]).extend(geometries[code])
        basin_rows.append({'id': code, 'terminal': name, 'sink_cell': list(root),
                           'cells': flow['counts'][name], 'gsi_id': target[1] if target and target[0]=='gsi' else None,
                           'outlet_id':target[1] if target and target[0]=='outlet' else None,'upstream_trace': traces,
                           'candidate_gsi_ids': sorted(t[1] for t in recipients if t[0]=='gsi'),
                           'reason': '; '.join(unresolved) or ('Ambiguous receivers' if len(recipients) > 1 else
                                     'No known receiving feature' if not target else 'Modeled connection, not verified treatment')})
    catchments = [];outlet_catchments=[]
    for kind,target,parts in [('gsi',k,v) for k,v in sorted(groups.items())]+[('outlet',k,v) for k,v in sorted(outlet_groups.items())]:
        # Center-cell rasterization must not count slivers of excluded roofs as
        # managed ground IA when vector boundaries cross a raster cell.
        geom = union(parts).difference(building_geometry)
        on = geom.intersection(parcel); known = on.intersection(ia); hidden = on.intersection(unknown)
        # Remove numerical overlay dust, not a minimum reportable physical area.
        if case_area_sqft(known,case)<.000001: known=union([])
        (catchments if kind=='gsi' else outlet_catchments).append({('gsi_id' if kind=='gsi' else 'outlet_id'): target,
                           'geometry': mapping(geom), 'known_ia_geometry': mapping(known),
                           'contributing_area_sqft': case_area_sqft(geom, case),
                           'on_parcel_area_sqft': case_area_sqft(on, case),
                           'off_parcel_area_sqft': case_area_sqft(geom.difference(parcel), case),
                           'on_parcel_known_ia_sqft': case_area_sqft(known, case),
                           'on_parcel_unknown_surface_sqft': case_area_sqft(hidden, case),
                           'potential_ia_upper_sqft': case_area_sqft(known.union(hidden), case),
                           'basis': 'modeled scenario', 'eligibility': 'Not established'})
    managed = union([shape(c['known_ia_geometry']) for c in catchments])
    unknown_managed=union([shape(c['geometry']).intersection(parcel).intersection(unknown) for c in catchments])
    fill_depth = conditioned['fill_depth']; valid = np.isfinite(fill_depth)
    directions = [[None if flow['labels'][r][c] == 'nodata' else
                   DIRECTIONS[(n[0] - r, n[1] - c)] if (n := flow['next_cells'][r][c]) is not None else 0
                   for c in range(flow['cols'])] for r in range(flow['rows'])]
    terminal_sum = sum(int(accumulation[p]) for p in terminals.values())
    rasters = {'filled_elevations': _json_grid(conditioned['filled']), 'fill_depth': _json_grid(fill_depth),
               'conditioned_elevations': _json_grid(conditioned['adjusted']),
               'infrastructure_adjustment': _json_grid(np.where(valid, conditioned['adjustment'], np.nan)),
               'direction_d8': directions, 'accumulation_including_self': accumulation.tolist(), 'micro_basins': basins.tolist()}
    return {'status': 'modeled' if catchments else 'partial', 'basis': 'modeled scenario',
            'grid': {k: deepcopy(grid[k]) for k in ('origin', 'cell_size', 'crs', 'horizontal_unit', 'vertical_unit')},
            'parameters': {'dem_type': options.get('dem_type', 'lidar'), 'offset_scale': offset_scale,
                           'inlet_buffer_m': inlet_buffer_m, 'all_touched': all_touched},
            'feature_audit': conditioned['features'], 'micro_basins': basin_rows,
            'catchments': catchments, 'outlet_catchments':outlet_catchments,'flow_paths': flow['flow_paths'],
            'known_ia_union_geometry': mapping(managed), 'known_ia_union_sqft': case_area_sqft(managed, case),
            'unknown_ground_union_geometry':mapping(unknown_managed),
            'unknown_ground_union_sqft':case_area_sqft(unknown_managed,case),
            'filled_cells': int((fill_depth[valid] > 0).sum()),
            'max_fill_depth_vertical_units': float(fill_depth[valid].max()) if valid.any() else None,
            'roof_excluded_cells': int(roof.sum()), 'nodata_cells': flow['nodata_cells'],
            'routed_ground_cells': int((basins > 0).sum()), 'terminal_accumulation_cells': terminal_sum,
            'area_conservation_pass': terminal_sum == int((basins > 0).sum()),
            'boundary_basins': sum(r['terminal'].startswith(('edge:', 'unresolved:nodata:')) for r in basin_rows),
            'extent_sufficient': bool(grid.get('settings', {}).get('extent_sufficient', False)),
            'input_dem_sha256': digest(grid['elevations']), 'rasters': rasters,
            'raster_sha256': {k: digest(v) for k, v in rasters.items()}}


def analyze_research(case, measurement, conservative):
    """Default additive analysis, independently disableable for historical replay."""
    options = case.get('research_drainage', {})
    if options.get('enabled') is False: return {'status': 'disabled', 'method': METHOD}
    if not case.get('terrain'): return {'status': 'unavailable', 'method': METHOD, 'reason': 'No suitable DEM supplied'}
    features, omitted = feature_inputs(case)
    primary = run_model(case, measurement, features)
    variants = []
    if options.get('sensitivity', True):
        for name, scale, buffer, touched in [('low_offsets', .5, .305, False), ('high_offsets', 1.5, 1.5, True)]:
            run = run_model(case, measurement, features, offset_scale=scale, inlet_buffer_m=buffer, all_touched=touched)
            run.pop('rasters'); run.pop('flow_paths'); run.pop('micro_basins'); run['name'] = name; variants.append(run)
        # Strict 2x block means; incomplete/NoData blocks stay missing. No invented finer DEM.
        grid = deepcopy(case['terrain']); source = np.array(grid['elevations'], dtype=float)
        rows, cols = source.shape; coarse = np.full(((rows + 1) // 2, (cols + 1) // 2), np.nan)
        for r in range(0, rows - 1, 2):
            for c in range(0, cols - 1, 2):
                block = source[r:r + 2, c:c + 2]
                if np.isfinite(block).all(): coarse[r // 2, c // 2] = block.mean()
        grid['elevations'] = _json_grid(coarse); grid['cell_size'] *= 2
        for key in ('roofs', 'barriers', 'storage'):
            grid[key] = sorted({(r // 2, c // 2) for r, c in grid.get(key, []) if np.isfinite(coarse[r // 2, c // 2])})
        grid.pop('parcel_mask', None)
        run = run_model(case, measurement, features, grid=grid)
        run.pop('rasters'); run.pop('flow_paths'); run.pop('micro_basins')
        run.update(name='coarser_2x', resampling='Strict complete-block mean; incomplete border blocks become NoData',
                   original_valid_area_m2=float(np.isfinite(source).sum()) * (case['terrain']['cell_size'] * METRES[grid['horizontal_unit']]) ** 2)
        variants.append(run)
    warnings = ['Additional modeled evidence only; current drainage and physical areas remain unchanged.',
                'Known feature locations with paper elevation offsets are assumptions, not surveyed infrastructure elevations.',
                'Roofs are excluded under the paper sewer-drainage assumption; actual roof connections remain unverified.',
                'No inlet bypass, capacity, rainfall/runoff calibration or hydraulic performance is established.',
                'Native and coarser sensitivity ranges are not confidence intervals; resampling does not create finer measured terrain detail.']
    if omitted: warnings.append('Some system footprints were excluded because they do not establish surface entries.')
    if not primary['extent_sufficient']: warnings.append('Surrounding watershed extent remains unverified.')
    if primary['nodata_cells'] or primary['boundary_basins']: warnings.append('Missing terrain or boundary outlets can change contributing areas.')
    if not any(f['role'] == 'inlet' for f in features): warnings.append('No mapped inlets supplied; missing storm drains may substantially change modeled GSI catchments.')
    values = [r['known_ia_union_sqft'] for r in [primary] + variants]
    comparisons=[]
    for c in primary['catchments']:
        region=shape(c['geometry']); breakdown=[]
        for old in conservative.get('catchments',[]):
            overlap=region.intersection(shape(old['geometry']))
            if not overlap.is_empty:
                breakdown.append({'previous_terminal':old['outlet'],'overlap_area_sqft':case_area_sqft(overlap,case)})
        comparisons.append({'gsi_id':c['gsi_id'],'previous_terminal_breakdown':breakdown,
                            'meaning':'Where the additional modeled catchment lies within current terminal regions; not proof the new route is correct'})
    return {'method': METHOD, 'status': primary['status'], 'source': {'url': PAPER, 'section': 'Drainage area delineation; Table 3'},
            'implementation_decisions':{
                'fill':'D8 priority flood, open raster edge and NoData-adjacent boundaries',
                'overlaps':'Maximum raise beats deepest drop; curb cuts cut berms/walls; buildings win',
                'routing':'Shared deterministic steepest-D8 and shortest-flat paths; no diagonal corner crossing; untyped existing barriers stay hard barriers',
                'basins':'Terminal micro-basins; upstream collection-to-GSI traces require supplied documented/scenario links',
                'offset_sensitivity':'0.5x/1.5x offsets are analyst stress tests, not published confidence bounds',
                'buffer_sensitivity':'Small/large published inlet-wall buffers; high case also tests touched-cell rasterization',
                'equivalence':'ArcGIS/ArcHydro equivalence has not been established'},
            'primary': primary, 'sensitivity': variants, 'omitted_features': omitted,
            'sensitivity_known_ia_sqft': {'min': min(values), 'max': max(values), 'meaning': 'Tested assumption/grid envelope, not statistical confidence'},
            'comparison': {'conservative_model': conservative.get('model'),
                           'conservative_unresolved_area_sqft': conservative.get('unresolved_area_sqft'),
                           'by_gsi':comparisons,
                           'interpretation': 'Additional evidence; no replacement, averaging or automatic verified allocation'},
            'validation': {'status': 'incomplete', 'missing': ['Independent same-vintage drainage boundaries',
                'Surveyed inlets, curb cuts, berms and private conveyance', 'Verified roof destinations',
                'Current grading and construction state', 'Rainfall and inlet/GSI inflow observations',
                'Finer native DEM resolution comparison', 'ArcGIS/ArcHydro output equivalence benchmark']},
            'warnings': warnings}


def write_diagnostic_rasters(directory, research):
    """Optional local GeoTIFF export; original input remains in the frozen case."""
    from pathlib import Path
    import rasterio
    p=research['primary']; grid=p['grid']; root=Path(directory);root.mkdir(parents=True,exist_ok=True)
    outputs=[];valid=np.isfinite(np.array(p['rasters']['filled_elevations'],dtype=float))
    for name,values in p['rasters'].items():
        data=np.asarray(values,dtype='float64');data[~valid]=-999999.
        path=root/(name+'.tif')
        with rasterio.open(path,'w',driver='GTiff',height=data.shape[0],width=data.shape[1],count=1,
                           dtype='float64',crs=grid['crs'],transform=from_origin(*grid['origin'],grid['cell_size'],grid['cell_size']),
                           nodata=-999999.,compress='deflate') as dst:
            dst.write(data,1);dst.update_tags(method=METHOD,vertical_unit=grid['vertical_unit'],
                value_semantics='inclusive cell counts' if name=='accumulation_including_self' else name,
                source_array_sha256=p['raster_sha256'][name],basis='modeled scenario')
        outputs.append({'name':path.name,'sha256':sha256(path.read_bytes()).hexdigest()})
    return outputs
