"""Bounded saved-data pilot: surface hypotheses and separate PWD estimates.

Run against existing case/GIS files; never acquires, infers, routes or edits them.
Uncertainty is described by scenarios and limitations. No confidence percentage
is available without independent calibration.
"""
from copy import deepcopy
from pathlib import Path
import argparse
import hashlib
import json
from time import perf_counter

from shapely.geometry import mapping, shape

from drainage_core.geometry import case_area_sqft, union
from drainage_core.management_estimates import _frozen, estimate_system
from drainage_core.model_integration import _area_only
from drainage_core.surface_estimates import estimate_surfaces
from .billing import calculate_scenarios, default_tariff
from .management_estimates import _baseline_context, estimate_management

UNCERTAINTY_MEANING = ('Scenario estimates have not been independently calibrated; '
    'no numerical confidence or approval probability is available.')


def _uncertainty():
    return {'status': 'not_calibrated', 'meaning': UNCERTAINTY_MEANING}


def _canopy_money(case, gis, area, geometry, day, tariff):
    baseline, _, allocations, errors = _baseline_context(case, gis, day, tariff)
    if baseline.get('account_current') is False:
        errors.append('Known failed account standing')
    for record in case.get('assessment', {}).get('records', []):
        if record.get('category') not in ('canopy', 'tree_canopy'):
            continue
        facts = record.get('facts') or {}
        if record.get('decision') == 'rejected' or any(facts.get(k) is False for k in
                ('physical_area_confirmed', 'parcel_allocation_confirmed', 'account_current', 'ground_impervious_overlap_confirmed')):
            errors.append('Recorded canopy prerequisite fails')
    reserved = sum(a['area_sqft'] for a in allocations if a['category'] != 'open_space')
    if area + reserved > baseline['ia_sqft'] + .01:
        errors.append('Canopy and existing allocations exceed available IA')
    if area and any(shape(geometry).intersection(shape(a['geometry'])).area > 1e-8 for a in allocations):
        errors.append('Possible canopy area overlaps existing allocation')
    if errors:
        return {'status': 'blocked', 'annual_savings': None, 'reasons': errors}
    if not area:
        return {'status': 'calculated', 'annual_savings': 0., 'monthly_savings': 0.}
    benefit = {'id': 'pilot-canopy', 'category': 'canopy', 'area_sqft': area,
        'basis': 'modeled', 'ledger_ids': ['pilot-canopy'], 'existing_overlap_reconciled': True,
        'evidence': {k: True for k in ('physical_area_confirmed', 'parcel_allocation_confirmed',
                                    'account_current', 'ground_impervious_overlap_confirmed')}}
    return calculate_scenarios(baseline, benefits=[benefit], tariff=tariff)['credit_only']


def _ground_constraint(case, surface):
    """A billing-compatible cover scenario, never an independent IA measurement.

    Solve one ground hard-surface fraction using the recorded IA prior. Both
    developed appearance and unclassified ground remain mixed, rather than being
    automatically promoted to pavement. Canopy uses local context coefficients.
    """
    contexts = surface['canopy']['contexts']
    context = next((c for c in contexts if c['distance_metres'] == 5), contexts[0])
    fixed = surface['roof_and_observed_ia_sqft'] + surface['road_appearance_sqft']
    cr = context['road_context_under_canopy_sqft']
    cu = context['developed_context_under_canopy_sqft'] + context['unclassified_context_under_canopy_sqft']
    variable = surface['developed_appearance_sqft'] + surface['unclassified_ground_sqft'] + cu
    recorded = case['baseline']['ia_sqft']
    raw = (recorded - fixed - cr) / variable if variable else None
    compatible = raw is not None and 0 <= raw <= 1
    fraction = min(1., max(0., raw)) if raw is not None else None
    canopy = surface['canopy']['observed_ground_ia_overlap_sqft'] + cr + fraction * cu if compatible else None
    return {'impervious_fraction_of_mixed_ground': fraction, 'unclipped_fraction': raw,
        'compatible_with_recorded_ia': compatible, 'context_distance_metres': context['distance_metres'],
        'visible_context_coverage_fraction': context['visible_context_coverage_fraction'],
        'canopy_ground_ia_estimate_sqft': canopy,
        'basis': 'Recorded IA assumed correct; local crown-edge context distributes mixed ground beneath trees',
        'assumptions': ['Recorded total IA is a prior, not independent accuracy evidence',
            'Mixed developed/unclassified ground shares the solved fraction across this parcel',
            'Grass/soil/water appearances assumed nonimpervious for this scenario; physical permeability remains unverified',
            'This constraint cannot be used as evidence that recorded IA should be appealed']}


def _weighted_engineering(case, gis, engineering, fraction, canopy_fraction):
    """Keep physical scenarios; add a separate policy interpretation of ground."""
    result = deepcopy(engineering)
    observation, ai, _, _ = _frozen(case, gis)
    parcel = shape(case['parcel'])
    fixed = union([shape(observation['geometries']['physical_ia']), shape(ai['geometries']['roof']),
                   shape(ai['geometries']['road'])]).difference(shape(observation['geometries']['pervious']))
    soft = union([shape(ai['geometries'][k]) for k in ('grass_shrub', 'bare_soil', 'water')])
    crowns = shape(ai['geometries']['canopy']).difference(union([fixed, shape(observation['geometries']['pervious'])]))
    for run in result['runs']:
        region = _area_only(shape(run['on_parcel_geometry']).intersection(parcel))
        hard = _area_only(fixed.intersection(region))
        mixed = _area_only(region.difference(union([fixed, soft, crowns, shape(observation['geometries']['pervious'])])))
        hidden = _area_only(crowns.intersection(region))
        components = [{'geometry': mapping(g), 'impervious_fraction': f, 'basis': basis}
            for g, f, basis in [(hard, 1., 'Observed IA / roof and road hypotheses'),
                (mixed, fraction, 'Mixed ground under recorded-IA-compatible fraction'),
                (hidden, canopy_fraction, 'Crown ground under same local-context and billing-compatible model')]
            if not g.is_empty]
        candidate = sum(case_area_sqft(shape(c['geometry']), case) * c['impervious_fraction'] for c in components)
        # Retain the strict road-only base as its own diagnostic alternative.
        for scenario in run['area_scenarios']:
            if scenario['id'] == 'base':
                scenario['id'] = 'road_only'
        run['area_scenarios'].append({'id': 'base', 'area_sqft': candidate,
            'geometry': mapping(union([shape(c['geometry']) for c in components])),
            'weighted_components': components,
            'basis': 'Best preliminary ground-mix hypothesis constrained by current recorded IA',
            'assumptions': ['Recorded IA is approximately correct',
                'Mixed ground within this catchment resembles mixed ground elsewhere on this property',
                'Grass/soil/water appearances assumed nonimpervious, not observed permeability',
                'All modeled candidate runoff is captured and adequately treated; this is a conditional estimate']})
    return result


def estimate_property(case, frozen_gis, system_ids, as_of='2026-11-16', tariff=None):
    tariff = deepcopy(tariff or default_tariff())
    surface = estimate_surfaces(case, frozen_gis)
    constraint = _ground_constraint(case, surface)
    canopy = surface['canopy']
    amounts = [canopy['range_sqft'][0], constraint['canopy_ground_ia_estimate_sqft'], canopy['range_sqft'][1]]
    priced = [_canopy_money(case, frozen_gis, a, canopy['geometry'], as_of, tariff)
              if a is not None else {'status': 'unknown', 'annual_savings': None} for a in amounts]
    systems = []
    canopy_fraction = ((amounts[1] - canopy['observed_ground_ia_overlap_sqft']) / canopy['hidden_ground_sqft']
                       if amounts[1] is not None and canopy['hidden_ground_sqft'] else 0.)
    for identifier in system_ids:
        engineering = estimate_system(case, frozen_gis, identifier)
        interpreted = _weighted_engineering(case, frozen_gis, engineering,
            constraint['impervious_fraction_of_mixed_ground'], canopy_fraction) if constraint['compatible_with_recorded_ia'] else engineering
        value = estimate_management(case, frozen_gis, interpreted, as_of, tariff)
        value.pop('confidence', None)
        value['uncertainty'] = _uncertainty()
        system = {'physical': engineering, 'policy': value}
        if str(identifier) == '01073':
            from drainage_core.runoff_capacity import estimate_capacity
            from .runoff_capacity import estimate_capacity_management
            capacity = estimate_capacity(case, frozen_gis, identifier)
            managed = estimate_capacity_management(case, frozen_gis, interpreted, capacity, as_of, tariff)
            system['capacity'] = capacity
            system['managed_runoff'] = managed
            system['full_area_management_scenario'] = {**value, 'status': 'superseded',
                'usable_for_current_savings': False,
                'superseded_reason': 'Earlier price included candidate IA within the garden bed and assumed unlimited management; use the runoff-capacity estimate'}
            # Primary amount follows estimated storage-supported runoff. Retain
            # the former full-management price as a separately labeled alternative.
            value = deepcopy(value)
            selected = managed.get('current_estimate')
            value.update(status=managed['status'], basis='storage_limited_management_estimate',
                current_estimate=deepcopy(selected.get('priced')) if selected and selected['status'] == 'calculated' else None,
                runs=deepcopy(managed['runs']),
                range=deepcopy(managed.get('range')), reasons=deepcopy(managed.get('reasons', [])))
            if value['current_estimate'] is not None:
                value['current_estimate'].update(run=selected['run'],
                    estimated_managed_ia_equivalent_sqft=selected['estimated_managed_ia_equivalent_sqft'],
                    estimated_managed_runoff_volume_cuft=selected['estimated_managed_runoff_volume_cuft'],
                    external_contributing_ia_sqft=selected['external_contributing_ia_sqft'])
            system['policy'] = value
        systems.append(system)
    return {'case_id': case.get('id'), 'name': case.get('name'), 'as_of': as_of,
        'baseline': deepcopy(case['baseline']), 'surface': surface, 'ground_constraint': constraint,
        'canopy': {'estimated_ground_ia_beneath_canopy_sqft': amounts[1], 'area_range_sqft': [amounts[0], amounts[2]],
            'annual_savings_estimate': priced[1]['annual_savings'],
            'annual_savings_range': [priced[0]['annual_savings'], priced[2]['annual_savings']],
            'uncertainty': _uncertainty(), 'scenarios': priced,
            'basis': 'Conditional canopy credit, local context plus recorded-IA prior; concealed ground not verified'},
        'impervious_area': {'estimated_reduction_sqft': 0., 'annual_savings_estimate': 0.,
            'status': 'no_supported_reduction_identified', 'uncertainty': _uncertainty(),
            'basis': 'Retain recorded IA as current best prior; saved imagery does not independently support a downward correction',
            'actual_available_savings_verified': False},
        'systems': systems, 'do_not_sum': True,
        'nonadditivity': 'System/canopy/appeal estimates are alternatives until their shared areas are allocated once.'}


def run_saved(specifications, output, as_of='2026-11-16'):
    destination = Path(output)
    destination.mkdir(parents=True, exist_ok=True)
    results, manifest = [], []
    started = perf_counter()
    for directory, identifiers in specifications:
        root = Path(directory)
        paths = [root / 'case.json', root / 'gis-analysis.json']
        before = [p.read_bytes() for p in paths]
        case, gis = [json.loads(b) for b in before]
        begin = perf_counter()
        result = estimate_property(case, gis, identifiers, as_of)
        result['estimate_seconds'] = perf_counter() - begin
        results.append(result)
        for path, blob in zip(paths, before):
            if path.read_bytes() != blob:
                raise RuntimeError('Pilot input changed: ' + str(path))
            manifest.append({'path': str(path), 'sha256': hashlib.sha256(blob).hexdigest()})
    output_result = {'version': 'saved-three-system-pilot-v3', 'as_of': as_of,
        'elapsed_seconds': perf_counter() - started, 'uncertainty': _uncertainty(),
        'input_manifest': manifest, 'properties': results}
    project = Path(__file__).resolve().parents[1]
    output_result['implementation_sha256'] = {name: hashlib.sha256((project / name).read_bytes()).hexdigest()
        for name in ('drainage_core/management_estimates.py', 'drainage_core/surface_estimates.py',
                     'drainage_core/runoff_capacity.py', 'stormwater/runoff_capacity.py',
                     'stormwater/management_estimates.py', 'stormwater/management_pilot.py')}
    (destination / 'estimates.json').write_text(json.dumps(output_result, separators=(',', ':'), allow_nan=False))
    return output_result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--whitaker')
    parser.add_argument('--south-61st', required=True)
    parser.add_argument('--only-system', choices=('01073',))
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    if args.only_system:
        specifications = [(args.south_61st, [args.only_system])]
    else:
        if not args.whitaker:
            parser.error('--whitaker is required unless --only-system 01073 is selected')
        specifications = [(args.whitaker, ['62571']), (args.south_61st, ['01073', '01074'])]
    result = run_saved(specifications, args.output)
    print(json.dumps({'output': str(Path(args.output) / 'estimates.json'), 'seconds': result['elapsed_seconds']}))


if __name__ == '__main__':
    main()
