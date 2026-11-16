"""Surface storage below a mapped facility's local terrain spill elevation.

Empty-at-start geometric event-storage scenarios. This is not a hydraulic,
infiltration, drawdown or treatment-compliance finding. Only the saved, unburned
source DEM (``case['terrain']``) is used; frozen GIS rasters (fill depth, burned
or conditioned grids) never set storage. No jurisdiction rainfall depth or credit
rule belongs here.

Spill level (review H12, decision D4)
-------------------------------------
Water held inside a mapped footprint spills where the terrain along the
footprint's perimeter *line* is lowest. The line is read two ways, and the pair
is the headline range. Neither method bounds the other, so neither is described
as conservative:

``perimeter_cell_minimum``
    Lowest source-cell value among every DEM cell whose closed extent lies within
    ``CONTACT_TOLERANCE_CELLS`` x cell size of the perimeter line. Corner/vertex
    contacts count, and an edge-aligned perimeter touches the cells on both sides.
    Reads the DEM as flat cells (an 8-connected leak model).
``perimeter_bilinear``
    Lowest bilinear interpolation of cell-centre elevations, sampled at every
    perimeter vertex, every cell-centre grid-line crossing and
    ``SAMPLES_PER_CELL`` points per cell length. Fractional cell coordinates
    within the contact tolerance of a centre line snap to it, so a zero-weight
    neighbour (including NoData) never changes availability. Reads the DEM as a
    continuous surface.

Both methods are repeated along the half-cell inward and outward offset lines
(``<method>_inward_half_cell`` / ``<method>_outward_half_cell``). Each sensitivity
is reported against its matching zero-offset method (H17). Every row stores
volume over the *original* footprint.

A 1e-6 m footprint shift cannot change any contact set or availability: contacts
use a tolerance far above that, and volumes vary continuously with the
intersected cell areas. NoData or off-grid cells within the contact tolerance of
the footprint make that component unavailable, whatever the shift.

Output field contract (``estimate_capacity``; Phase 4b consumes these)
---------------------------------------------------------------------
``status``
    ``estimated``: both headline methods available for every component.
    ``unavailable``: evidence is missing or insufficient (no aligned DEM, units not
    established, NoData/off-grid at the footprint or perimeter, unsupported system
    type). ``blocked``: evidence contradicts a usable estimate (terrain predates the
    system, contradictory vertical units, or an inlet/outlet/curb-cut/overflow
    structure intersects the footprint). ``excluded``: installation contradictions.
``reason`` / ``blocking_reasons`` / ``unavailable_reasons``
    Joined text and the separate lists behind a non-estimated status.
``review_flags``
    Non-blocking ``{'code', 'message'}`` items that policy must label or gate:
    ``vertical_units_assumed``, ``vertical_unit_status_unrecorded``,
    ``vertical_unit_status_unrecognized``, ``dem_date_unknown``,
    ``installation_year_unknown``, ``dem_overlaps_installation_year``,
    ``implausible_ponding_depth``, ``disconnected_components``.
``storage_range_cuft`` / ``storage_range_scenarios``
    D4 headline: ``[min, max]`` total volume of ``perimeter_cell_minimum`` and
    ``perimeter_bilinear``. ``None`` unless ``status == 'estimated'``.
``volume_range_cuft`` / ``volume_range_status`` / ``volume_range_missing_scenarios``
    Envelope over all six scenario rows. Unavailable rows are listed, never
    dropped silently. Status is ``complete`` or ``incomplete`` when estimated,
    and ``unavailable`` otherwise.
``selected_scenario`` / ``surface_storage_volume_cuft`` / ``wetted_area_sqft``
    Compatibility reference row (``perimeter_cell_minimum``) for single-value
    consumers. ``selected_scenario_role`` states that it is neither a bound nor
    conservative.
``scenarios`` (aggregate rows; one per name, in a fixed order)
    ``name``, ``method`` (``cell_minimum``/``bilinear``), ``perimeter_offset_cells``,
    ``perimeter_offset_native``, ``matching_zero_offset_scenario``, ``status``,
    ``reason``, ``volume_cuft`` (sum of components; ``None`` if any component is
    unavailable), ``component_volumes_cuft``, ``component_spill_elevations_m``,
    ``wetted_area_sqft``, ``max_ponding_depth_m``, ``mean_ponding_depth_m`` (volume
    / wetted area), ``ponding_depth_check``, ``volume_change_fraction_vs_matching``,
    ``rain_exposure_area_sqft``, ``unavailable_components``, ``basis``,
    ``assumptions``.
``components`` (R7: budget runoff per component; storage is not shared)
    ``component_id``, ``geometry`` (GeoJSON, case CRS), ``footprint_area_sqft``,
    ``rain_exposure_area_sqft``, ``status``, ``reason``, ``covered_cell_count``,
    ``storage_range_cuft`` and ``scenarios`` with the per-row fields above plus
    ``spill_elevation_source_units``, ``spill_elevation_m`` and, for cell-minimum
    rows, ``perimeter_contact_cell_count``.
``component_count`` / ``per_component_budget_required``
    With more than one component, storage in one part cannot serve runoff that
    reaches another. Policy must budget each component separately.
``drainage_structures_in_footprint``
    Mapped inlet/outlet/curb-cut/overflow structures that intersect the footprint
    (``id``, ``role``, ``source`` and any recorded rim/invert values).
``vertical_unit_status``
    ``verified``, ``assumed``, ``unrecorded``, ``unrecognized`` or ``contradictory``
    (R9). The value comes from ``terrain.source_quality.vertical_units`` plus
    explicit linked records.
``terrain_timing``
    ``status`` (``after_installation``, ``predates_installation``,
    ``overlaps_installation_year``, ``dem_date_unknown`` or
    ``installation_year_unknown``), ``dem_capture_earliest``,
    ``dem_capture_latest``, ``dem_date_sources``, ``installation_year`` (H15).
``ponding_depth_screening_threshold_m``, ``contact_tolerance_native``
    The documented screening threshold and the contact tolerance actually used.
``source_lineage``
    Case/GIS hashes, the source DEM digest, the grid with its ``source_quality``,
    ``terrain_timing``, ``vertical_unit_status``, ``method_version`` and
    ``physical_interpretation_version``.
"""
from calendar import monthrange
from copy import deepcopy
from datetime import date
from math import ceil, floor, hypot, isclose, isfinite
import re

import numpy as np
import shapely
from shapely.geometry import MultiLineString, mapping, shape

from .engine import input_hash, result_hash
from .geometry import SQFT_PER_M2, case_area_sqft, effective_features, projected_crs, union
from .installation import _year, installation_issues
from .model_integration import _area_only
from .quality import PHYSICAL_INTERPRETATION_VERSION
from .research import METRES, digest

VERSION = 'local-perimeter-storage-v2'
# Contact/snapping tolerance as a fraction of the source cell size (1 mm on a 1 m
# grid). Far above a 1e-6 m footprint shift, far below any mapped dimension.
CONTACT_TOLERANCE_CELLS = 1e-3
SAMPLES_PER_CELL = 8
# Screening threshold, not a design rule. Surface rain gardens/bioretention are
# designed for well under 0.5 m of ponding. A deeper implied pool usually means
# the footprint or DEM captures something else: a pit, misalignment, pre-construction
# grade or wrong vertical units.
PLAUSIBLE_MAX_PONDING_DEPTH_M = 1.
IMPLAUSIBLE_PONDING = 'implausible – check footprint/DEM'
HEADLINE = ('perimeter_cell_minimum', 'perimeter_bilinear')
SELECTED = 'perimeter_cell_minimum'
METHODS = {
    'cell_minimum': 'Lowest source-cell value touched (incl. corner contacts) by the {line}',
    'bilinear': 'Lowest bilinear source-DEM elevation sampled along the {line}'}
OFFSETS = ((0., None, 'mapped perimeter line'),
           (-.5, 'inward_half_cell', 'perimeter line moved inward by half a source cell'),
           (.5, 'outward_half_cell', 'perimeter line moved outward by half a source cell'))
STRUCTURE_WORDS = ('inlet', 'outlet', 'curb_cut', 'curb cut', 'curbcut', 'overflow', 'outfall')
CONTRADICTED_UNIT_STATUS = ('contradicted', 'contradictory', 'conflicting', 'conflict', 'rejected')
DATE_KEYS = ('acquisition_date', 'capture_date', 'observation_date')


def _number(value, name):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not isfinite(value):
        raise ValueError(name + ' must be a finite number')
    return float(value)


def _name(method, label):
    return 'perimeter_' + method if label is None else method + '_' + label


SCENARIO_ORDER = tuple(_name(m, label) for _, label, _ in OFFSETS[:1] for m in METHODS) + tuple(
    _name(m, label) for m in METHODS for _, label, _ in OFFSETS[1:])


class _Grid:
    """Source DEM with off-grid cells read as NoData."""

    def __init__(self, array, origin, size):
        self.array, self.size = array, size
        self.x, self.y = origin
        self.rows, self.cols = array.shape
        self.tol = size * CONTACT_TOLERANCE_CELLS

    def value(self, r, c):
        return float(self.array[r, c]) if 0 <= r < self.rows and 0 <= c < self.cols else float('nan')

    def touched(self, geometry):
        """Cells (including off-grid indices) within the contact tolerance of ``geometry``."""
        minx, miny, maxx, maxy = geometry.bounds
        s, t = self.size, self.tol
        c0, c1 = floor((minx - t - self.x) / s), floor((maxx + t - self.x) / s)
        r0, r1 = floor((self.y - maxy - t) / s), floor((self.y - miny + t) / s)
        rr, cc = (a.ravel() for a in np.mgrid[r0:r1 + 1, c0:c1 + 1])
        boxes = shapely.box(self.x + cc*s, self.y - (rr+1)*s, self.x + (cc+1)*s, self.y - rr*s)
        hit = shapely.dwithin(geometry, boxes, t)
        rr, cc, boxes = rr[hit], cc[hit], boxes[hit]
        values = np.full(len(rr), np.nan)
        inside = (rr >= 0) & (rr < self.rows) & (cc >= 0) & (cc < self.cols)
        values[inside] = self.array[rr[inside], cc[inside]]
        return values, boxes

    def bilinear(self, px, py):
        col = (px - self.x) / self.size - .5
        row = (self.y - py) / self.size - .5
        col, row = (round(v) if abs(v - round(v)) <= CONTACT_TOLERANCE_CELLS else v for v in (col, row))
        r, c = floor(row), floor(col)
        dr, dc = row - r, col - c
        total = 0.
        for i, wr in ((r, 1 - dr), (r + 1, dr)):
            for j, wc in ((c, 1 - dc), (c + 1, dc)):
                if wr * wc == 0:
                    continue
                value = self.value(i, j)
                if not isfinite(value):
                    return None
                total += wr * wc * value
        return float(total)

    def line_points(self, line):
        """Vertices, cell-centre grid-line crossings and sub-cell samples of each ring."""
        points = []
        for ring in line.geoms:
            coords = np.asarray(ring.coords)[:, :2]
            for (x0, y0), (x1, y1) in zip(coords[:-1], coords[1:]):
                length = hypot(x1 - x0, y1 - y0)
                if not length:
                    continue
                n = max(1, ceil(length * SAMPLES_PER_CELL / self.size))
                ts = [k / n for k in range(n)]
                for a0, a1, u0, u1 in ((x0, x1, (x0 - self.x) / self.size - .5, (x1 - self.x) / self.size - .5),
                                       (y0, y1, (self.y - y0) / self.size - .5, (self.y - y1) / self.size - .5)):
                    if a0 == a1:
                        continue
                    lo, hi = sorted((u0, u1))
                    ts.extend((k - u0) / (u1 - u0) for k in range(ceil(lo), floor(hi) + 1))
                points.extend((x0 + t*(x1 - x0), y0 + t*(y1 - y0)) for t in ts if 0 <= t <= 1)
        return points


def _perimeter(polygon, offset):
    adjusted = _area_only(polygon.buffer(offset)) if offset else polygon
    if adjusted.is_empty:
        return None
    parts = list(adjusted.geoms) if adjusted.geom_type == 'MultiPolygon' else [adjusted]
    # Interior holes are islands/exclusions, not assumed open spillways.
    return MultiLineString([part.exterior.coords for part in parts])


def _cell_minimum(grid, line):
    values, _ = grid.touched(line)
    if not len(values):
        return None, 'Perimeter line touches no source cells', 0
    if not np.isfinite(values).all():
        return None, 'NoData or off-grid source cell touches the perimeter line', len(values)
    return float(values.min()), None, len(values)


def _bilinear_minimum(grid, line):
    levels = []
    for x, y in grid.line_points(line):
        value = grid.bilinear(x, y)
        if value is None:
            return None, 'Bilinear perimeter sample needs a NoData or off-grid cell centre', None
        levels.append(value)
    return (min(levels), None, None) if levels else (None, 'No perimeter samples', None)


def _storage_cells(grid, polygon, case):
    """Elevation and footprint-intersection area (sq ft) of every storage cell."""
    values, boxes = grid.touched(polygon)
    if not len(values) or not np.isfinite(values).all():
        return None, 'NoData or off-grid source cell touches the footprint or its perimeter'
    parts = shapely.intersection(boxes, polygon)
    native = shapely.area(parts)
    keep = native > 0
    if case.get('area_crs', case['crs']) == case['crs']:
        factor = projected_crs(case['crs']).axis_info[0].unit_conversion_factor ** 2 * SQFT_PER_M2
        areas = native[keep] * factor
    else:
        areas = np.array([case_area_sqft(_area_only(part), case) for part in parts[keep]])
    return (values[keep], areas), None


def _storage(level, elevations, areas, vertical_factor):
    depth = np.maximum(0., level - elevations)
    wet = elevations < level
    volume = float((depth * areas).sum() * vertical_factor / .3048)
    wetted = float(areas[wet].sum())
    deepest = float(depth.max() * vertical_factor) if wet.any() else 0.
    return {'status': 'estimated', 'spill_elevation_source_units': level,
        'spill_elevation_m': level * vertical_factor, 'volume_cuft': volume, 'wetted_area_sqft': wetted,
        'max_ponding_depth_m': deepest, 'mean_ponding_depth_m': volume / wetted * .3048 if wetted else 0.,
        'ponding_depth_check': IMPLAUSIBLE_PONDING if deepest > PLAUSIBLE_MAX_PONDING_DEPTH_M else 'within_screening_threshold'}


def _change(rows):
    base = {r['name']: r.get('volume_cuft') for r in rows}
    for row in rows:
        reference = base.get(row['matching_zero_offset_scenario'])
        row['volume_change_fraction_vs_matching'] = (row['volume_cuft'] - reference) / reference \
            if row.get('volume_cuft') is not None and reference else None


def _component(case, index, polygon, grid, vertical_factor, assumptions):
    area = case_area_sqft(polygon, case)
    out = {'component_id': 'component-' + str(index + 1), 'geometry': mapping(polygon),
        'footprint_area_sqft': area, 'rain_exposure_area_sqft': area, 'status': 'unavailable',
        'reason': None, 'covered_cell_count': None, 'storage_range_cuft': None, 'scenarios': []}
    cells, reason = _storage_cells(grid, polygon, case)
    if cells is not None:
        elevations, areas = cells
        out['covered_cell_count'] = int(len(elevations))
    rows = {}
    for cells_offset, label, line_text in OFFSETS:
        offset = cells_offset * grid.size
        line = _perimeter(polygon, offset)
        for method, text in METHODS.items():
            name = _name(method, label)
            row = {'name': name, 'method': method, 'perimeter_offset_cells': cells_offset,
                'perimeter_offset_native': offset, 'matching_zero_offset_scenario': _name(method, None),
                'status': 'unavailable', 'reason': None, 'spill_elevation_source_units': None,
                'spill_elevation_m': None, 'volume_cuft': None, 'wetted_area_sqft': None,
                'max_ponding_depth_m': None, 'mean_ponding_depth_m': None, 'ponding_depth_check': None,
                'rain_exposure_area_sqft': area, 'basis': text.format(line=line_text),
                'storage_geometry': 'Original mapped footprint, fixed for every perimeter line',
                'assumptions': list(assumptions)}
            if cells is None:
                row['reason'] = reason
            elif line is None:
                row['reason'] = 'Offset perimeter vanishes for this footprint'
            else:
                level, why, count = (_cell_minimum if method == 'cell_minimum' else _bilinear_minimum)(grid, line)
                if method == 'cell_minimum':
                    row['perimeter_contact_cell_count'] = count
                if level is None:
                    row['reason'] = why
                else:
                    row.update(_storage(level, elevations, areas, vertical_factor))
            rows[name] = row
    out['scenarios'] = [rows[name] for name in SCENARIO_ORDER]
    _change(out['scenarios'])
    headline = [rows[name] for name in HEADLINE]
    missing = [r['name'] for r in headline if r['status'] != 'estimated']
    if cells is None:
        out['reason'] = reason
        return out
    if missing:
        out['reason'] = 'Perimeter-line spill unavailable: ' + '; '.join(
            name + ' (' + rows[name]['reason'] + ')' for name in missing)
        return out
    volumes = [r['volume_cuft'] for r in headline]
    out.update(status='estimated', storage_range_cuft=[min(volumes), max(volumes)])
    return out


def _aggregate(components, footprint_area):
    rows = []
    for index, name in enumerate(SCENARIO_ORDER):
        parts = [c['scenarios'][index] for c in components]
        example = parts[0]
        available = all(p['status'] == 'estimated' for p in parts)
        volume = sum(p['volume_cuft'] for p in parts) if available else None
        wetted = sum(p['wetted_area_sqft'] for p in parts) if available else None
        deepest = max(p['max_ponding_depth_m'] for p in parts) if available else None
        row = {key: deepcopy(example[key]) for key in ('name', 'method', 'perimeter_offset_cells',
            'perimeter_offset_native', 'matching_zero_offset_scenario', 'basis', 'assumptions')}
        row.update(status='estimated' if available else 'unavailable',
            reason=None if available else '; '.join(dict.fromkeys(
                c['component_id'] + ': ' + p['reason'] for c, p in zip(components, parts) if p['status'] != 'estimated')),
            volume_cuft=volume, wetted_area_sqft=wetted, max_ponding_depth_m=deepest,
            mean_ponding_depth_m=(volume / wetted * .3048 if wetted else 0.) if available else None,
            ponding_depth_check=(IMPLAUSIBLE_PONDING if deepest > PLAUSIBLE_MAX_PONDING_DEPTH_M
                                 else 'within_screening_threshold') if available else None,
            component_volumes_cuft=[p['volume_cuft'] for p in parts],
            component_spill_elevations_m=[p['spill_elevation_m'] for p in parts],
            unavailable_components=[c['component_id'] for c, p in zip(components, parts) if p['status'] != 'estimated'],
            rain_exposure_area_sqft=footprint_area,
            aggregation=('Sum of separately spilling disconnected components; storage in one component '
                         'cannot serve runoff reaching another' if len(parts) > 1 else 'Single component'))
        rows.append(row)
    _change(rows)
    return rows


def _date_bounds(value):
    match = re.fullmatch(r'(\d{4})(?:-(\d{1,2})(?:-(\d{1,2}))?)?(?:[T ].*)?', str(value).strip())
    if not match:
        return None
    year, month, day = (int(v) if v else None for v in match.groups())
    try:
        if day:
            return date(year, month, day), date(year, month, day)
        if month:
            return date(year, month, 1), date(year, month, monthrange(year, month)[1])
        return date(year, 1, 1), date(year, 12, 31)
    except ValueError:
        return None


def _record_dates(record):
    if not isinstance(record, dict):
        return []
    values = [record.get(k) for k in DATE_KEYS]
    for key in ('capture_period', 'acquisition_period'):
        period = record.get(key)
        values += list(period.values()) if isinstance(period, dict) else list(period) if isinstance(period, (list, tuple)) else []
    return [b for b in (_date_bounds(v) for v in values if v not in (None, '')) if b]


def _terrain_timing(case, terrain, features):
    """Compare the DEM capture period with the recorded installation year (H15)."""
    found = [(label, bounds) for label, record in (('terrain', terrain), ('terrain.provenance', terrain.get('provenance')),
             ('terrain_reuse', case.get('terrain_reuse'))) for bounds in _record_dates(record)]
    if not found:
        # Explicit source link first; otherwise every elevation provenance record
        # (an envelope when several DEMs were saved over the case history).
        linked = terrain.get('source_sha256') or (terrain.get('provenance') or {}).get('sha256')
        sources = [s for s in case.get('sources') or [] if isinstance(s, dict) and (
            s.get('sha256') == linked if linked else s.get('vertical_unit') is not None)]
        found = [('sources:' + str(s.get('sha256') or s.get('url') or s.get('path') or 'elevation'), bounds)
                 for s in sources for bounds in _record_dates(s)]
    years = sorted({y for f in features for y in [_year({str(k).lower(): v for k, v in
                    (f.get('properties') or {}).items()})[0]] if y is not None})
    timing = {'status': None, 'dem_capture_earliest': None, 'dem_capture_latest': None,
        'dem_date_sources': sorted({label for label, _ in found}), 'installation_year': years[-1] if years else None,
        'installation_years_recorded': years}
    if found:
        timing.update(dem_capture_earliest=min(b[0] for _, b in found).isoformat(),
                      dem_capture_latest=max(b[1] for _, b in found).isoformat())
    if not found:
        timing['status'] = 'dem_date_unknown'
    elif not years:
        timing['status'] = 'installation_year_unknown'
    elif date.fromisoformat(timing['dem_capture_latest']) < date(years[-1], 1, 1):
        timing['status'] = 'predates_installation'
    elif date.fromisoformat(timing['dem_capture_earliest']) > date(years[-1], 12, 31):
        timing['status'] = 'after_installation'
    else:
        timing['status'] = 'overlaps_installation_year'
    return timing


def _vertical_status(case, terrain):
    """Vertical-unit verification status and explicit contradictions (R9)."""
    unit = terrain.get('vertical_unit')
    quality = terrain.get('source_quality') or {}
    conflicts = []
    linked = terrain.get('source_sha256')
    records = [('terrain.provenance', (terrain.get('provenance') or {}).get('vertical_unit')),
               ('terrain.source_quality.vertical_unit', quality.get('vertical_unit')),
               ('terrain_reuse', (case.get('terrain_reuse') or {}).get('vertical_unit'))]
    records += [('linked source ' + linked[:12], s.get('vertical_unit')) for s in case.get('sources') or []
                if linked and isinstance(s, dict) and s.get('sha256') == linked]
    for label, other in records:
        if other not in (None, '') and other != unit:
            conflicts.append(f'{label} records vertical unit {other} but the DEM is interpreted as {unit}')
    recorded = quality.get('vertical_units')
    text = str(recorded).strip().lower() if recorded is not None else None
    if text in CONTRADICTED_UNIT_STATUS:
        conflicts.append('Source quality records contradictory vertical units')
    status = ('contradictory' if conflicts else 'verified' if text == 'verified' else 'assumed' if text == 'assumed'
              else 'unrecorded' if text is None else 'unrecognized')
    return status, conflicts


def _structures(case, footprint, terrain, as_of):
    """Mapped collection/overflow structures that intersect the footprint (H14)."""
    found = []
    for f in effective_features(case):
        p = f.get('properties') or {}
        if p.get('kind') == 'system_footprint':
            continue
        role = ' '.join(str(p.get(k) or '') for k in ('drainage_role', 'layer', 'kind', 'structure_type', 'feature_type')).lower()
        word = next((w for w in STRUCTURE_WORDS if w in role), None)
        if not word or installation_issues(p, as_of):
            continue
        try:
            geometry = shape(f['geometry'])
        except (KeyError, TypeError, ValueError, AttributeError):
            continue
        if geometry.intersects(footprint):
            found.append({'id': str(f.get('id')), 'role': 'curb_cut' if 'curb' in word else word,
                'source': 'mapped feature', **{k: deepcopy(p[k]) for k in
                ('rim_elevation_m', 'rim_elevation', 'invert_elevation', 'invert_elevation_m', 'gsi_system_id') if k in p}})
    for f in (case.get('research_drainage') or {}).get('features', []):
        if f.get('role') in ('inlet', 'curb_cut') and f.get('geometry') and shape(f['geometry']).intersects(footprint):
            found.append({'id': str(f.get('id')), 'role': f['role'], 'source': 'research drainage feature'})
    size, origin = terrain.get('cell_size'), terrain.get('origin')
    for inlet in terrain.get('inlets') or []:
        if not size or not origin:
            break
        r, c = inlet['cell']
        cell = shapely.box(origin[0] + c*size, origin[1] - (r+1)*size, origin[0] + (c+1)*size, origin[1] - r*size)
        if cell.intersects(footprint):
            found.append({'id': str(inlet.get('id')), 'role': 'inlet', 'source': 'terrain inlet cell'})
    return found


def _flag(result, code, message):
    if code not in {f['code'] for f in result['review_flags']}:
        result['review_flags'].append({'code': code, 'message': message})


def estimate_capacity(case, frozen_gis, system_id):
    """Return named local-spill storage scenarios and their range (see module docstring).

    Disconnected footprint parts are separate components with their own spill
    levels and volumes. Missing coverage returns unknown, never invented zero storage.
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
    parts = list(footprint.geoms) if footprint.geom_type == 'MultiPolygon' else [footprint]
    area = case_area_sqft(footprint, case)
    recorded_types = sorted({str(f.get('properties', {}).get('gsi_system_type', '')) for f in features})
    kinds = {kind.lower() for kind in recorded_types}
    result = {'version': VERSION, 'system_id': system_id, 'system_type': recorded_types[0] if len(kinds) == 1 else None,
        'status': 'unavailable', 'reason': None, 'blocking_reasons': [], 'unavailable_reasons': [], 'review_flags': [],
        'footprint_area_sqft': area, 'rain_exposure_area_sqft': area,
        'storage_range_cuft': None, 'storage_range_scenarios': list(HEADLINE),
        'storage_range_basis': ('Spill read along the mapped perimeter line as source cells (cell minimum) and as a '
            'continuous surface (bilinear). Neither bounds the other; this is a method range, not a confidence interval'),
        'volume_range_cuft': None, 'volume_range_status': 'unavailable', 'volume_range_missing_scenarios': [],
        'selected_scenario': SELECTED,
        'selected_scenario_role': ('Compatibility reference row for single-value consumers; neither a bound nor '
            'conservative. Lead with storage_range_cuft and the named scenarios'),
        'surface_storage_volume_cuft': None, 'wetted_area_sqft': None,
        'scenarios': [], 'components': [], 'component_count': len(parts),
        'per_component_budget_required': len(parts) > 1,
        'drainage_structures_in_footprint': [], 'vertical_unit_status': None, 'terrain_timing': None,
        'ponding_depth_screening_threshold_m': PLAUSIBLE_MAX_PONDING_DEPTH_M, 'contact_tolerance_native': None,
        'source_lineage': {'case_sha256': input_hash(case), 'gis_analysis_sha256': frozen_gis.get('analysis_sha256'),
            'method_version': VERSION, 'physical_interpretation_version': PHYSICAL_INTERPRETATION_VERSION},
        'basis': 'Empty-at-start surface storage below the local spill level read along the mapped perimeter line',
        'assumptions': ['Saved source DEM represents the facility bed and unblocked perimeter overflow',
            'Storage is empty at the start of the event and hydraulically accessible to receiving runoff',
            'No additional infiltration, media, underground storage or outlet retention volume is assigned',
            'Full original footprint remains the direct-rain exposure for every scenario'],
        'limitations': ['Surface event storage is not verified treatment, drawdown or credit eligibility',
            'Footprint alignment, subgrid inlets/low outlets and current condition are unverified',
            'Scenario envelope is not a confidence interval or a bound on all real-world error']}
    if len(parts) > 1:
        _flag(result, 'disconnected_components', 'Footprint has disconnected parts; budget runoff and storage per component')

    def finish():
        reasons = result['blocking_reasons'] + result['unavailable_reasons']
        result['reason'] = '; '.join(dict.fromkeys(reasons)) or None
        if result['blocking_reasons']:
            result['status'] = 'blocked'
        return result

    if len(kinds) != 1 or any('subsurface' in kind or 'underground' in kind for kind in kinds):
        result['unavailable_reasons'].append('Surface terrain does not identify underground storage or conflicting system types')
        return finish()
    if not any('rain garden' in kind or 'bioretention' in kind for kind in kinds):
        result['unavailable_reasons'].append('Local source-ground capacity interpretation is currently limited to rain gardens/bioretention')
        return finish()
    as_of = case.get('imagery_age_policy', {}).get('as_of') or case.get('created_at')
    issues = [issue for f in features for issue in installation_issues(f.get('properties', {}), as_of)]
    if issues:
        result.update(status='excluded', reason='; '.join(dict.fromkeys(issues)))
        return result
    terrain = case.get('terrain') or {}
    structures = _structures(case, footprint, terrain, as_of)
    result['drainage_structures_in_footprint'] = structures
    if structures:
        result['blocking_reasons'].append('Mapped inlet/outlet/curb-cut/overflow structure(s) intersect the footprint ('
            + ', '.join(s['role'] + ' ' + s['id'] for s in structures)
            + '); their unmapped rim/invert levels, not the DEM perimeter, control ponding')
    if not terrain.get('elevations') or terrain.get('crs') != case.get('crs'):
        result['unavailable_reasons'].append('A source DEM aligned to the case CRS is required')
        return finish()
    timing = _terrain_timing(case, terrain, features)
    result['terrain_timing'] = timing
    result['source_lineage']['terrain_timing'] = deepcopy(timing)
    if timing['status'] == 'predates_installation':
        result['blocking_reasons'].append(f'Terrain predates system: DEM captured {timing["dem_capture_earliest"]} to '
            f'{timing["dem_capture_latest"]}, before the {timing["installation_year"]} installation, so it can show pre-construction grade')
    elif timing['status'] == 'dem_date_unknown':
        _flag(result, 'dem_date_unknown', 'DEM capture date unknown; it may predate construction of the system')
    elif timing['status'] == 'installation_year_unknown':
        _flag(result, 'installation_year_unknown', 'Installation year unknown; DEM timing relative to construction is unverified')
    elif timing['status'] == 'overlaps_installation_year':
        _flag(result, 'dem_overlaps_installation_year', 'DEM capture period overlaps the installation year; it may show pre-construction grade')
    unit_status, conflicts = _vertical_status(case, terrain)
    result['vertical_unit_status'] = result['source_lineage']['vertical_unit_status'] = unit_status
    result['blocking_reasons'].extend(conflicts)
    unit_note = {'assumed': ('vertical_units_assumed', 'Vertical units assumed for this scenario; not verified source metadata'),
        'unrecorded': ('vertical_unit_status_unrecorded', 'Vertical-unit verification status is not recorded'),
        'unrecognized': ('vertical_unit_status_unrecognized', 'Vertical-unit verification status is not recognized')}.get(unit_status)
    if unit_note:
        _flag(result, *unit_note)
    factor = METRES.get(terrain.get('vertical_unit'))
    if factor is None:
        result['unavailable_reasons'].append('Source DEM vertical units are not established')
        return finish()
    horizontal_factor = METRES.get(terrain.get('horizontal_unit'))
    crs_factor = projected_crs(case['crs']).axis_info[0].unit_conversion_factor
    if horizontal_factor is None or not isclose(horizontal_factor, crs_factor, rel_tol=1e-8):
        result['unavailable_reasons'].append('Source DEM horizontal units do not match the declared projected CRS')
        return finish()
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
        source_grid={k: deepcopy(terrain.get(k)) for k in ('origin', 'cell_size', 'crs', 'horizontal_unit',
                                                            'vertical_unit', 'source_quality')})
    if result['blocking_reasons']:
        return finish()
    grid = _Grid(array, origin, size)
    result['contact_tolerance_native'] = grid.tol
    assumptions = (['Vertical units assumed (' + str(terrain.get('vertical_unit')) + '); not verified source metadata']
                   if unit_status == 'assumed' else [])
    components = [_component(case, i, part, grid, factor, assumptions) for i, part in enumerate(parts)]
    result['components'] = components
    result['scenarios'] = _aggregate(components, area)
    missing = [row['name'] for row in result['scenarios'] if row['status'] != 'estimated']
    result['volume_range_missing_scenarios'] = missing
    if any(c['status'] != 'estimated' for c in components):
        result['unavailable_reasons'].extend(c['component_id'] + ': ' + c['reason'] for c in components if c['status'] != 'estimated')
        return finish()
    rows = {row['name']: row for row in result['scenarios']}
    headline = [rows[name]['volume_cuft'] for name in HEADLINE]
    volumes = [row['volume_cuft'] for row in result['scenarios'] if row['status'] == 'estimated']
    result.update(status='estimated', storage_range_cuft=[min(headline), max(headline)],
        volume_range_cuft=[min(volumes), max(volumes)], volume_range_status='incomplete' if missing else 'complete',
        surface_storage_volume_cuft=rows[SELECTED]['volume_cuft'], wetted_area_sqft=rows[SELECTED]['wetted_area_sqft'])
    if any(rows[name]['ponding_depth_check'] == IMPLAUSIBLE_PONDING for name in HEADLINE):
        _flag(result, 'implausible_ponding_depth', f'Implied ponding depth exceeds {PLAUSIBLE_MAX_PONDING_DEPTH_M:g} m: '
              + IMPLAUSIBLE_PONDING)
    return finish()
