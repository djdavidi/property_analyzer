"""Surface storage below a mapped facility's local terrain spill elevation.

This is an empty-at-start geometric event-storage estimate, not a hydraulic,
infiltration, drawdown or treatment-compliance finding. Only the saved, unburned
source DEM is used. No jurisdiction rainfall depth or credit rule belongs here.
"""
from copy import deepcopy
from math import ceil, floor, isclose, isfinite

import numpy as np
from shapely.geometry import box, shape

from .engine import input_hash, result_hash
from .geometry import case_area_sqft, effective_features, projected_crs, union
from .installation import installation_issues
from .model_integration import _area_only
from .research import METRES, digest

VERSION = 'local-perimeter-storage-v1'


def _number(value, name):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not isfinite(value):
        raise ValueError(name + ' must be a finite number')
    return float(value)


def _bilinear(array, origin, size, point):
    """Cell-centre elevations interpolated only where four valid samples exist."""
    x, y = origin
    col = (point.x - x) / size - .5
    row = (y - point.y) / size - .5
    r, c = floor(row), floor(col)
    if r < 0 or c < 0 or r + 1 >= array.shape[0] or c + 1 >= array.shape[1]:
        return None
    values = array[r:r+2, c:c+2]
    if not np.isfinite(values).all():
        return None
    dr, dc = row-r, col-c
    return float(values[0, 0]*(1-dr)*(1-dc) + values[1, 0]*dr*(1-dc)
                 + values[0, 1]*(1-dr)*dc + values[1, 1]*dr*dc)


def _sample_perimeter(array, origin, size, polygon, offset):
    adjusted = polygon.buffer(offset) if offset else polygon
    if adjusted.is_empty:
        return None
    pieces = list(adjusted.geoms) if adjusted.geom_type == 'MultiPolygon' else [adjusted]
    levels = []
    for part in pieces:
        boundary = part.exterior
        count = max(4, ceil(boundary.length / (size / 4)))
        for index in range(count):
            value = _bilinear(array, origin, size, boundary.interpolate(index/count*boundary.length))
            if value is None:
                return None
            levels.append(value)
    return min(levels) if levels else None


def _component(case, polygon, array, origin, size, vertical_factor):
    x, y = origin
    rows, cols = array.shape
    minx, miny, maxx, maxy = polygon.bounds
    r0, r1 = max(0, floor((y-maxy)/size)), min(rows, ceil((y-miny)/size))
    c0, c1 = max(0, floor((minx-x)/size)), min(cols, ceil((maxx-x)/size))
    cells, rim, covered = [], [], []
    missing = False
    for r in range(r0, r1):
        for c in range(c0, c1):
            cell = box(x+c*size, y-(r+1)*size, x+(c+1)*size, y-r*size)
            part = _area_only(cell.intersection(polygon))
            if part.is_empty or part.area <= 1e-12:
                continue
            covered.append(part)
            elevation = float(array[r, c])
            if not isfinite(elevation):
                missing = True
                continue
            area = case_area_sqft(part, case)
            cells.append((elevation, area))
            # Interior holes are islands/exclusions, not assumed open spillways.
            if polygon.exterior.intersection(cell).length > 1e-10:
                rim.append(elevation)
    outside = case_area_sqft(_area_only(polygon.difference(union(covered))), case)
    area = case_area_sqft(polygon, case)
    if missing or outside > max(.001, area*1e-9) or not cells or not rim:
        return {'status': 'unavailable', 'reason': 'Footprint or spill perimeter lacks complete source DEM coverage',
                'footprint_area_sqft': area, 'scenarios': []}
    levels = [('boundary_cell_minimum', min(rim), 0.,
               'Lowest unburned elevation among cells crossed by the mapped exterior perimeter'),
              ('bilinear_perimeter', _sample_perimeter(array, origin, size, polygon, 0.), 0.,
               'Lowest bilinear source-DEM elevation along the mapped exterior perimeter'),
              ('perimeter_inward_half_cell', _sample_perimeter(array, origin, size, polygon, -size/2), -size/2,
               'Bilinear spill at perimeter moved inward by half a source grid cell'),
              ('perimeter_outward_half_cell', _sample_perimeter(array, origin, size, polygon, size/2), size/2,
               'Bilinear spill at perimeter moved outward by half a source grid cell')]
    scenarios = []
    for name, level, offset, basis in levels:
        row = {'name': name, 'status': 'estimated' if level is not None else 'unavailable',
            'spill_elevation_source_units': level,
            'spill_elevation_m': level*vertical_factor if level is not None else None,
            'perimeter_offset_native': offset, 'rain_exposure_area_sqft': area,
            'storage_geometry': 'Original mapped footprint, fixed for all perimeter sensitivities',
            'volume_cuft': None, 'wetted_area_sqft': None, 'basis': basis}
        if level is not None:
            row['volume_cuft'] = sum(max(0., level-z)*a*vertical_factor/.3048 for z, a in cells)
            row['wetted_area_sqft'] = sum(a for z, a in cells if z < level)
        scenarios.append(row)
    return {'status': 'estimated', 'footprint_area_sqft': area,
        'boundary_cell_count': len(rim), 'covered_cell_count': len(cells), 'scenarios': scenarios}


def estimate_capacity(case, frozen_gis, system_id):
    """Return conservative local-spill storage and deterministic sensitivities.

    Disconnected polygon parts have their own local spill levels; their volumes
    are summed once. Missing coverage returns unknown, never invented zero storage.
    """
    if frozen_gis.get('input_sha256') and frozen_gis['input_sha256'] != input_hash(case):
        raise ValueError('Frozen GIS input does not match this case')
    if frozen_gis.get('analysis_sha256') and frozen_gis['analysis_sha256'] != result_hash(frozen_gis):
        raise ValueError('Frozen GIS content hash does not match')
    system_id = str(system_id)
    features = [f for f in effective_features(case)
                if str(f.get('properties', {}).get('gsi_system_id')) == system_id
                and f.get('properties', {}).get('kind') == 'system_footprint']
    if not features:
        raise ValueError('Mapped system footprint not found: ' + system_id)
    footprint = _area_only(union([shape(f['geometry']) for f in features]))
    if footprint.is_empty or not footprint.is_valid:
        raise ValueError('Mapped footprint must contain valid polygon area')
    result = {'version': VERSION, 'system_id': system_id, 'status': 'unavailable',
        'footprint_area_sqft': case_area_sqft(footprint, case),
        'surface_storage_volume_cuft': None, 'wetted_area_sqft': None,
        'rain_exposure_area_sqft': case_area_sqft(footprint, case),
        'volume_range_cuft': None, 'scenarios': [], 'components': [],
        'source_lineage': {'case_sha256': input_hash(case), 'gis_analysis_sha256': frozen_gis.get('analysis_sha256')},
        'basis': 'Conservative empty-at-start surface storage below lowest local perimeter cell elevation',
        'assumptions': ['Saved source DEM represents the facility bed and unblocked perimeter overflow',
            'Storage is empty at the start of the event and hydraulically accessible to receiving runoff',
            'No additional infiltration, media, underground storage or outlet retention volume is assigned',
            'Full original footprint remains the direct-rain exposure for every sensitivity'],
        'limitations': ['Surface event storage is not verified treatment, drawdown or credit eligibility',
            'Terrain timing, footprint alignment, subgrid inlets/low outlets and current condition are unresolved',
            'Sensitivity envelope is not a confidence interval or a bound on all real-world error']}
    kinds = {str(f.get('properties', {}).get('gsi_system_type', '')).lower() for f in features}
    if len(kinds) != 1 or any('subsurface' in kind or 'underground' in kind for kind in kinds):
        result['reason'] = 'Surface terrain does not identify underground storage or conflicting system types'
        return result
    if not any('rain garden' in kind or 'bioretention' in kind for kind in kinds):
        result['reason'] = 'Local source-ground capacity interpretation is currently limited to rain gardens/bioretention'
        return result
    issues = [issue for f in features for issue in installation_issues(f.get('properties', {}),
        case.get('imagery_age_policy', {}).get('as_of') or case.get('created_at'))]
    if issues:
        result.update(status='excluded', reason='; '.join(dict.fromkeys(issues)))
        return result
    terrain = case.get('terrain') or {}
    if not terrain.get('elevations') or terrain.get('crs') != case.get('crs'):
        result['reason'] = 'A source DEM aligned to the case CRS is required'
        return result
    factor = METRES.get(terrain.get('vertical_unit'))
    if factor is None:
        result['reason'] = 'Source DEM vertical units are not established'
        return result
    horizontal_factor = METRES.get(terrain.get('horizontal_unit'))
    crs_factor = projected_crs(case['crs']).axis_info[0].unit_conversion_factor
    if horizontal_factor is None or not isclose(horizontal_factor, crs_factor, rel_tol=1e-8):
        result['reason'] = 'Source DEM horizontal units do not match the declared projected CRS'
        return result
    size = _number(terrain.get('cell_size'), 'cell_size')
    if size <= 0:
        raise ValueError('cell_size must be positive')
    origin = terrain.get('origin')
    if not isinstance(origin, (list, tuple)) or len(origin) != 2:
        raise ValueError('Source DEM origin must contain x and y')
    origin = [_number(v, 'origin') for v in origin]
    array = np.asarray(terrain['elevations'], dtype=float)
    if array.ndim != 2 or not array.size or np.isinf(array).any():
        raise ValueError('Invalid source DEM')
    result['source_lineage'].update(source_dem_sha256=digest(terrain['elevations']),
        source_grid={k: deepcopy(terrain.get(k)) for k in ('origin', 'cell_size', 'crs', 'horizontal_unit', 'vertical_unit')})
    parts = list(footprint.geoms) if footprint.geom_type == 'MultiPolygon' else [footprint]
    components = [_component(case, part, array, origin, size, factor) for part in parts]
    result['components'] = components
    if any(c['status'] != 'estimated' for c in components):
        result['reason'] = 'At least one component lacks complete source DEM/perimeter coverage'
        return result
    for index, example in enumerate(components[0]['scenarios']):
        rows = [c['scenarios'][index] for c in components]
        available = all(row['status'] == 'estimated' for row in rows)
        result['scenarios'].append({'name': example['name'], 'status': 'estimated' if available else 'unavailable',
            'volume_cuft': sum(row['volume_cuft'] for row in rows) if available else None,
            'wetted_area_sqft': sum(row['wetted_area_sqft'] for row in rows) if available else None,
            'rain_exposure_area_sqft': result['rain_exposure_area_sqft'],
            'perimeter_offset_native': example['perimeter_offset_native'], 'basis': example['basis'],
            'component_spill_elevations_m': [row['spill_elevation_m'] for row in rows]})
    best = result['scenarios'][0]
    volumes = [row['volume_cuft'] for row in result['scenarios'] if row['volume_cuft'] is not None]
    result.update(status='estimated', surface_storage_volume_cuft=best['volume_cuft'],
                  wetted_area_sqft=best['wetted_area_sqft'], volume_range_cuft=[min(volumes), max(volumes)])
    return result
