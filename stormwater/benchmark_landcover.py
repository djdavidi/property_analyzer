"""G4: agreement of modeled OEM classes with the 2018 Philadelphia land cover.

Reads one saved case (its frozen OpenEarthMap semantic polygons and City building
footprints), obtains the 2018 land cover for the parcel from the PASDA PhillyLULC
MapServer (layer 2, decoded exactly through its published legend), and writes an
area-weighted agreement table over the whole parcel and over stable strata
(``drainage_core.benchmark``). No model inference is run and the case is not
changed.

This is agreement with an independent, older product, not accuracy. The 2018
product is itself a classification (University of Vermont Spatial Analysis Lab /
City of Philadelphia), seven to eight years older than 2025 imagery.

Usage::

    python -m stormwater.benchmark_landcover --case data/cases/pwd-123 --output agreement.json [--cache DIR]
"""
from __future__ import annotations

import argparse
import json
import math
from hashlib import sha256
from pathlib import Path
from urllib.parse import urlencode

from drainage_core.benchmark import CORRESPONDENCE, benchmark
from drainage_core.geometry import reproject
from drainage_core.remote_sensing import classified_features, decode_classification, legend_palette
from drainage_core.sources import Cache, SourceError, canonical, crs_from_declaration, now
from shapely.geometry import mapping, shape

from .automatic import LANDCOVER

LAYER = 2
LAYER_NAME = 'Philadelphia Land Cover 2018'
LEGEND_URL = LANDCOVER+'/legend?f=json'
LAYER_URL = f'{LANDCOVER}/{LAYER}?f=json'
MAX_SIDE = 4096
REFERENCE_PRODUCT = ('Philadelphia Land Cover 2018 (University of Vermont Spatial Analysis Laboratory with the City of '
                     'Philadelphia 2018 Tree Canopy Assessment), PASDA PhillyLULC MapServer layer 2')
CLAIM = ('Agreement with an independent, older land-cover product over the stated areas; not accuracy, not a '
         'calibrated error rate and not evidence for any credit or bill. Both products can be wrong where they agree.')


def _unit(crs):
    from pyproj import CRS
    return CRS(crs).axis_info[0].unit_conversion_factor


def reference_request(case, *, cell_ft=1.0, pad_cells=2):
    """Export parameters for the parcel box, cells near ``cell_ft`` (max 4096 px a side)."""
    unit = _unit(case['crs']); cell = cell_ft*.3048/unit
    minx, miny, maxx, maxy = shape(case['parcel']).bounds
    pad = pad_cells*cell
    box = [minx-pad, miny-pad, maxx+pad, maxy+pad]
    # Tolerant ceiling: 64.00000000002 cells is 64, not 65.
    width, height = (max(1, math.ceil((box[i+2]-box[i])/cell-1e-6)) for i in (0, 1))
    if max(width, height) > MAX_SIDE:
        scale = max(width, height)/MAX_SIDE; width, height = math.ceil(width/scale), math.ceil(height/scale)
    code = case['crs'].split(':')[-1]
    params = {'f': 'json', 'bbox': ','.join(map(str, box)), 'bboxSR': code, 'imageSR': code,
              'size': f'{width},{height}', 'layers': f'show:{LAYER}', 'format': 'png32', 'transparent': 'true',
              'interpolation': 'RSP_NearestNeighbor'}
    return {'url': LANDCOVER+'/export?'+urlencode(params), 'bounds': box, 'size': [width, height]}


def fetch_reference(case, cache, refresh=False, *, cell_ft=1.0, pad_cells=2):
    """Exact 2018 classes for the parcel box; any source problem is a ``SourceError``."""
    legend = cache.fetch_json(LEGEND_URL, refresh)
    try:
        palette = legend_palette(legend['data'], LAYER)
    except (ValueError, KeyError, TypeError) as exc:
        raise SourceError(f'2018 land-cover legend unusable: {exc}') from exc
    layer = cache.fetch_json(LAYER_URL, refresh)
    if layer['data'].get('name') != LAYER_NAME:
        raise SourceError(f'PhillyLULC layer {LAYER} is {layer["data"].get("name")!r}, not {LAYER_NAME!r}')
    request = reference_request(case, cell_ft=cell_ft, pad_cells=pad_cells)
    width, height = request['size']
    export = cache.fetch_json(request['url'], refresh, {'crs': case['crs'], 'source_vintage': '2018', 'acquisition_date': None})
    data = export['data']; extent = data.get('extent') or {}
    sr = extent.get('spatialReference') or {}
    declared = sr.get('latestWkid', sr.get('wkid', sr.get('wkt')))
    if declared is None or not crs_from_declaration(declared).equals(crs_from_declaration(case['crs']), ignore_axis_order=True):
        raise SourceError('2018 land-cover export CRS differs from the case CRS')
    if not data.get('href') or not all(k in extent for k in ('xmin', 'ymin', 'xmax', 'ymax')):
        raise SourceError('2018 land-cover export lacks an image URL or exact bounds')
    bounds = [float(extent[k]) for k in ('xmin', 'ymin', 'xmax', 'ymax')]
    href = data['href']
    if href.startswith('http://'):
        href = 'https://'+href[len('http://'):]
    image = cache.fetch_bytes(href, refresh, {'crs': case['crs'], 'bounds': extent, 'source_vintage': '2018',
                                              'format': 'png32 nearest-neighbour rendering of layer 2'})
    try:
        classes = decode_classification(image['content'], palette)
    except ValueError as exc:
        raise SourceError(f'2018 land-cover rendering unreadable: {exc}') from exc
    if classes.shape != (height, width):
        raise SourceError(f'2018 land-cover rendering is {classes.shape[1]}x{classes.shape[0]}, requested {width}x{height}')
    if not (classes > 0).any():
        raise SourceError('2018 land-cover rendering has no classified pixels for this parcel box')
    if not shape(case['parcel']).within(_box(bounds, 1e-6*max(abs(v) for v in bounds))):
        raise SourceError('2018 land-cover rendering does not cover the parcel')
    unit = _unit(case['crs'])
    return {'classes': classes, 'bounds': bounds, 'crs': case['crs'], 'size': [width, height],
            'cell_size_crs_units': [(bounds[2]-bounds[0])/width, (bounds[3]-bounds[1])/height],
            'cell_size_ft': [(bounds[2]-bounds[0])/width*unit/.3048, (bounds[3]-bounds[1])/height*unit/.3048],
            'sources': [legend['provenance'], layer['provenance'], export['provenance'], image['provenance']],
            'layer_name': layer['data'].get('name'), 'copyright': layer['data'].get('copyrightText'),
            'image_sha256': image['provenance']['sha256']}


def _box(bounds, tolerance):
    from shapely.geometry import box
    return box(bounds[0]-tolerance, bounds[1]-tolerance, bounds[2]+tolerance, bounds[3]+tolerance)


def reference_features(reference, case):
    """Parcel-clipped 2018 class polygons (``classification`` = 2018 class name)."""
    result = classified_features(reference['classes'], reference['bounds'], case,
                                 {'family': REFERENCE_PRODUCT, 'url': LANDCOVER+f'/{LAYER}',
                                  'sha256': reference['image_sha256'], 'vintage': '2018'})
    return result['features'], result['unclassified_sqft']


def modeled_features(case):
    """Frozen OEM semantic polygons and their lineage; never RGB-fallback masks."""
    features = [f for f in case.get('features', {}).get('features', [])
                if (f.get('properties') or {}).get('source_kind') == 'modeled semantic estimate'
                and (f.get('properties') or {}).get('layer') != 'historical']
    landcover = (case.get('automatic') or {}).get('landcover') or {}
    origin = 'case.features (frozen auto-semantic polygons)'
    if not features and landcover.get('status') == 'modeled_semantic_estimates':
        features = [f for f in landcover.get('features', []) if (f.get('properties') or {}).get('source_kind') == 'modeled semantic estimate']
        source_crs = landcover.get('crs') or case['crs']
        if source_crs != case['crs']:
            features = [{**f, 'geometry': mapping(reproject(shape(f['geometry']), source_crs, case['crs']))} for f in features]
        origin = 'automatic.landcover.features'
    if not features:
        raise ValueError('No modeled OpenEarthMap semantic classes in this case (model not run or RGB fallback); nothing to benchmark')
    props = features[0]['properties']
    settings = landcover.get('settings') or {}
    return features, {'origin': origin, 'product': settings.get('algorithm') or 'OpenEarthMap semantic model',
                      'model_sha256': props.get('model_sha256'), 'interpretation_version': props.get('interpretation_version'),
                      'prediction_sha256': landcover.get('prediction_sha256'),
                      'imagery_sha256': props.get('source_sha256'), 'imagery_vintage': props.get('source_vintage'),
                      'imagery_acquisition_date': props.get('acquisition_date'),
                      'target_pixel_metres': settings.get('target_pixel_metres'),
                      'minimum_top_score': settings.get('minimum_top_score'),
                      'feature_ids': sorted(str(f.get('id')) for f in features)}


def footprints(case):
    """Current City building footprints saved in the case (independent of both products)."""
    return [(f['id'], f['geometry']) for f in case.get('features', {}).get('features', [])
            if (f.get('properties') or {}).get('source_family') == 'City buildings'
            and (f.get('properties') or {}).get('layer') == 'surface'
            and (f.get('properties') or {}).get('class') == 'roof']


def caveats(modeled, reference, settings):
    cell = reference['cell_size_ft']
    when = modeled.get('imagery_acquisition_date') or modeled.get('imagery_vintage') or 'unknown date'
    return [CLAIM,
            f'Temporal change: reference 2018 versus imagery {when}. Stable strata reduce but do not remove change '
            '(demolition, new construction, resurfacing, tree growth or removal).',
            f'Resolution and registration: the reference is a server rendering at {cell[0]:.2f} x {cell[1]:.2f} ft cells '
            '(nearest neighbour; native resolution not stated by the service), the model output at '
            f'{modeled.get("target_pixel_metres") or "unknown"} m cells. Boundary misregistration counts as disagreement; '
            f'stable strata are eroded by {settings["edge_buffer_m"]} m.',
            'Stable strata are chosen partly from the reference (footprints mostly 2018 building; 2018 road outside '
            'footprints). They show how much modeled area agrees where the reference shows buildings or roads '
            '(recall-type), not modeled precision elsewhere. Parcels rarely contain much road.',
            'Class meanings differ: modeled developed space is compared with 2018 other paved surfaces; both products '
            'label tree crowns as canopy, and the ground beneath is unobserved in both. Season and shadow may differ.',
            'Modeled low-score pixels and reference NoData are unclassified and reported separately; they are neither '
            'agreement nor disagreement.',
            'One parcel is not representative of the city; no statistical confidence interval is implied.']


def run(case, cache, *, refresh=False, min_footprint_fraction=.8, edge_buffer_m=.5, cell_ft=1.0, pad_cells=2, case_ref=None):
    min_footprint_fraction, edge_buffer_m, cell_ft, pad_cells = float(min_footprint_fraction), float(edge_buffer_m), float(cell_ft), int(pad_cells)
    model_features, model_info = modeled_features(case)
    reference = fetch_reference(case, cache, refresh, cell_ft=cell_ft, pad_cells=pad_cells)
    ref_features, ref_unclassified = reference_features(reference, case)
    edge = edge_buffer_m/_unit(case['crs'])
    settings = {'min_footprint_reference_fraction': min_footprint_fraction, 'edge_buffer_m': edge_buffer_m,
                'reference_cell_ft_requested': cell_ft, 'reference_pad_cells': pad_cells}
    table = benchmark(case, model_features, ref_features, footprints(case), min_footprint_fraction=min_footprint_fraction,
                      edge=edge, modeled_aliases={'other_pavement': 'developed_space'}, correspondence=CORRESPONDENCE)
    out = {'benchmark_version': table['version'], 'generated_at': now(),
           'kind': 'agreement with an independent older product; not accuracy',
           'case': {'id': case.get('id'), 'ref': case_ref, 'crs': case['crs'], 'parcel_sqft': table['parcel_sqft'],
                    'case_sha256': sha256(canonical(case)).hexdigest()},
           'modeled': {**model_info, 'class_area_sqft': table['modeled_class_area_sqft'],
                       'polygon_parts': table['modeled_polygon_parts'], 'conflict_sqft': table['modeled_conflict_sqft']},
           'reference': {'product': REFERENCE_PRODUCT, 'vintage': '2018', 'layer': LANDCOVER+f'/{LAYER}',
                         'layer_name': reference['layer_name'], 'copyright': reference['copyright'],
                         'rendering': {'crs': reference['crs'], 'bounds': reference['bounds'], 'pixel_dimensions': reference['size'],
                                       'cell_size_ft': reference['cell_size_ft'], 'interpolation': 'RSP_NearestNeighbor',
                                       'decoding': 'exact legend colours; other colours and transparency are unclassified'},
                         'sources': reference['sources'], 'class_area_sqft': table['reference_class_area_sqft'],
                         'polygon_parts': table['reference_polygon_parts'], 'unclassified_in_parcel_sqft': ref_unclassified},
           'correspondence': [list(p) for p in CORRESPONDENCE], 'settings': settings,
           'strata': table['strata'], 'caveats': caveats(model_info, reference, settings), 'claim': CLAIM}
    # Content hash: excludes the run time and the local path the case was read from.
    hashed = {**{k: v for k, v in out.items() if k != 'generated_at'}, 'case': {k: v for k, v in out['case'].items() if k != 'ref'}}
    out['result_sha256'] = sha256(json.dumps(hashed, sort_keys=True, separators=(',', ':'), default=str).encode()).hexdigest()
    return out


def load_case(path):
    path = Path(path)
    file = path/'case.json' if path.is_dir() else path
    return json.loads(file.read_text()), str(file)


def main(argv=None):
    parser = argparse.ArgumentParser(description='Agreement of modeled OEM classes with the 2018 Philadelphia land cover.')
    parser.add_argument('--case', required=True, type=Path, help='Saved case folder or case.json (read only)')
    parser.add_argument('--output', required=True, type=Path, help='JSON result path')
    parser.add_argument('--cache', type=Path, help='Public-source cache folder (default: data/public)')
    parser.add_argument('--refresh', action='store_true', help='Fetch the reference again instead of replaying the cache')
    parser.add_argument('--min-footprint-fraction', type=float, default=.8)
    parser.add_argument('--edge-buffer-m', type=float, default=.5)
    parser.add_argument('--reference-cell-ft', type=float, default=1.0)
    parser.add_argument('--reference-pad-cells', type=int, default=2)
    args = parser.parse_args(argv)
    case, ref = load_case(args.case)
    from .record_cache import ROOT
    cache = Cache(args.cache or ROOT/'data'/'public')
    result = run(case, cache, refresh=args.refresh, min_footprint_fraction=args.min_footprint_fraction,
                 edge_buffer_m=args.edge_buffer_m, cell_ft=args.reference_cell_ft, pad_cells=args.reference_pad_cells,
                 case_ref=ref)
    args.output.write_text(json.dumps(result, indent=1, sort_keys=True, default=str)+'\n')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
