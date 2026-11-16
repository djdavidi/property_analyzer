"""Bounded saved-data pilot: surface hypotheses and separate PWD estimates.

Run against existing case/GIS files; never acquires, infers, routes or edits them.
Uncertainty is described by scenarios and limitations. No confidence percentage
is available without independent calibration.

* One money path (D7): canopy and system prices go through the assessment ledger
  (``system_pricing.price_benefit``), so minimums, NPDES, undeveloped alternatives,
  existing-credit occupancy, the baseline-refresh gate and prerequisite vetoes match
  the app.
* Dates (H8): one assessment date per property, explicit (``--as-of``) or recorded in
  the case (``system_pricing.derive_as_of``); no calendar default.
* Capacity by system type (H5): every surface rain garden/bioretention system takes
  the storage-limited range; other systems take the management range. The system
  bed is excluded everywhere (H16).
* Ground interpretation (A3/D3, R15): the shared class table
  (``drainage_core.class_interpretation``) labels every scenario. The recorded-IA
  family solves one parcel-wide mixed-ground fraction from the recorded IA and is
  reported with a spatial-allocation sensitivity: the recorded total cannot locate
  impervious ground, so the catchment may hold as little or as much of it as the
  uncertain ground allows. It is a labelled hypothesis and is circular when credits
  are measured against the same recorded IA.
* Canopy (R5): observed canopy polygons and dated modeled canopy both conceal ground.
* Impervious area (R4): ``not_estimated`` with a retained-baseline scenario unless a
  complete measured GA/IA exists, which then uses the shared measured-area ledger path.
"""
from copy import deepcopy
from pathlib import Path
import argparse
import hashlib
import json
from time import perf_counter

from shapely.geometry import mapping, shape

from drainage_core.class_interpretation import VERSION as INTERPRETATION_VERSION, classes as interpreted
from drainage_core.geometry import area_only, case_area_sqft, union
from drainage_core.management_estimates import _frozen, estimate_system
from drainage_core.quality import PHYSICAL_INTERPRETATION_VERSION
from drainage_core.surface_estimates import estimate_surfaces
from .billing import default_tariff
from .management_estimates import estimate_management, system_context
from .quality import POLICY_INTERPRETATION_VERSION
from .system_pricing import derive_as_of, ledger_context, policy_gis, price_benefit

VERSION = 'saved-three-system-pilot-v4'
UNCERTAINTY_MEANING = ('Scenario estimates have not been independently calibrated; '
    'no numerical confidence or approval probability is available.')
RECORDED_IA_SCENARIO = 'road_impervious_soft_pervious'
CANOPY_FACTS = ('physical_area_confirmed', 'parcel_allocation_confirmed', 'account_current',
                'ground_impervious_overlap_confirmed')
IMPLEMENTATION_FILES = (
    'drainage_core/management_estimates.py', 'drainage_core/surface_estimates.py', 'drainage_core/runoff_capacity.py',
    'drainage_core/class_interpretation.py', 'drainage_core/model_integration.py', 'drainage_core/geometry.py',
    'drainage_core/extent.py', 'drainage_core/installation.py', 'drainage_core/quality.py',
    'stormwater/runoff_capacity.py', 'stormwater/management_estimates.py', 'stormwater/management_pilot.py',
    'stormwater/system_pricing.py', 'stormwater/assessment_policy.py', 'stormwater/model_assessment.py',
    'stormwater/billing.py', 'stormwater/rules.py', 'stormwater/prerequisites.py', 'stormwater/quality.py',
    'config/rules-pwd-2026-09.json')


def _uncertainty():
    return {'status': 'not_calibrated', 'meaning': UNCERTAINTY_MEANING}


def surface_storage_system(system_type):
    """H5: capacity path by system type (surface rain gardens/bioretention), never by ID."""
    kind = str(system_type or '').lower()
    return ('rain garden' in kind or 'bioretention' in kind) and not ('subsurface' in kind or 'underground' in kind)


def _canopy_money(case, gis, area, geometry, day, tariff, ledger):
    """One canopy scenario through the ledger; recorded contrary canopy facts block."""
    errors = list(ledger['errors'])
    for record in case.get('assessment', {}).get('records', []):
        if record.get('category') not in ('canopy', 'tree_canopy'):
            continue
        facts = record.get('facts') or {}
        if record.get('decision') == 'rejected' or any(facts.get(k) is False for k in CANOPY_FACTS):
            errors.append('Recorded canopy prerequisite fails')
    if errors:
        return {'status': 'blocked', 'annual_savings': None, 'monthly_savings': None,
                'reasons': list(dict.fromkeys(errors))}
    region = shape(geometry) if geometry else None
    if not area and (region is None or region.is_empty):
        return {'status': 'calculated', 'annual_savings': 0., 'monthly_savings': 0.,
                'note': 'No positive canopy-ground IA in this scenario; actual area remains unknown'}
    benefit = {'id': 'pilot-canopy', 'category': 'canopy', 'area_sqft': area, 'basis': 'modeled',
               'geometry': geometry, 'evidence': {k: True for k in CANOPY_FACTS}}
    return price_benefit(case, gis, day, tariff, benefit)


def _ground_constraint(case, surface):
    """A billing-compatible cover scenario, never an independent IA measurement.

    Solve one ground hard-surface fraction using the recorded IA prior under the
    class table's ``road_impervious_soft_pervious`` scenario. Developed appearance
    and unclassified ground remain mixed. Canopy uses local context coefficients.
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
        'canopy_ground_ia_estimate_sqft': canopy, 'interpretation_scenario': RECORDED_IA_SCENARIO,
        'interpretation_version': INTERPRETATION_VERSION,
        'basis': 'Recorded IA assumed correct; local crown-edge context distributes mixed ground beneath trees',
        'assumptions': ['Recorded total IA is a prior, not independent accuracy evidence',
            'Mixed developed/unclassified ground shares the solved fraction across this parcel',
            'Grass/soil/water appearances assumed pervious for this labelled scenario; physical permeability remains unverified',
            'This constraint cannot be used as evidence that recorded IA should be appealed']}


def _ground_layers(case, gis):
    """Interpretation layers from the shared class table, with observed canopy (R5)."""
    observation, ai, _, _ = _frozen(case, gis)
    parcel = shape(case['parcel'])
    pervious = shape(observation['geometries']['pervious'])
    fixed = union([shape(observation['geometries']['physical_ia'])]
                  + [shape(ai['geometries'][k]) for k in interpreted(RECORDED_IA_SCENARIO, 'impervious')]).difference(pervious)
    soft = union([shape(ai['geometries'][k]) for k in interpreted(RECORDED_IA_SCENARIO, 'pervious')])
    developed = shape(ai['geometries']['developed_space'])
    observed_canopy = shape(observation['geometries']['canopy']).intersection(parcel)
    # Observed canopy conceals ground only where the image shows no visible ground class.
    crowns = area_only(union([observed_canopy, shape(ai['geometries']['canopy'])]).intersection(parcel)
                       .difference(union([fixed, pervious, soft, developed])))
    return {'parcel': parcel, 'pervious': pervious, 'fixed': fixed, 'soft': soft, 'crowns': crowns}


def _pools(case, layers, region):
    hard = area_only(layers['fixed'].intersection(region))
    mixed = area_only(region.difference(union([layers['fixed'], layers['soft'], layers['crowns'], layers['pervious']])))
    hidden = area_only(layers['crowns'].intersection(region))
    return hard, mixed, hidden


def _allocation(case, layers, recorded):
    """Parcel-wide implied hard area in the uncertain pool, or None if incompatible."""
    hard, mixed, hidden = _pools(case, layers, layers['parcel'])
    implied = recorded - case_area_sqft(hard, case)
    pool = case_area_sqft(mixed, case) + case_area_sqft(hidden, case)
    return {'implied_hard_in_uncertain_ground_sqft': implied, 'uncertain_ground_sqft': pool,
            'compatible': pool > 0 and 0 <= implied <= pool}


def _recorded_ia_family(case, gis, engineering, constraint, canopy_fraction):
    """Keep physical scenarios; add labelled recorded-IA scenarios with allocation sensitivity (R15)."""
    result = deepcopy(engineering)
    layers = _ground_layers(case, gis)
    allocation = _allocation(case, layers, case['baseline']['ia_sqft'])
    for run in result['runs']:
        region = area_only(shape(run['on_parcel_geometry']).intersection(layers['parcel']))
        hard, mixed, hidden = _pools(case, layers, region)
        local = case_area_sqft(mixed, case) + case_area_sqft(hidden, case)
        family = []
        if constraint['compatible_with_recorded_ia']:
            family.append(('recorded_ia_uniform', constraint['impervious_fraction_of_mixed_ground'], canopy_fraction,
                           'Recorded-IA-compatible fraction applied uniformly inside this catchment (hypothesis)'))
        if allocation['compatible'] and local > 0:
            implied, pool = allocation['implied_hard_in_uncertain_ground_sqft'], allocation['uncertain_ground_sqft']
            low = max(0., implied - (pool - local)) / local
            high = min(local, implied) / local
            family += [('recorded_ia_allocation_low', low, low,
                        'Spatial-allocation sensitivity: as little of the recorded-IA hard area inside this catchment as the uncertain ground allows'),
                       ('recorded_ia_allocation_high', high, high,
                        'Spatial-allocation sensitivity: as much of the recorded-IA hard area inside this catchment as the uncertain ground allows')]
        run['recorded_ia_allocation'] = {**allocation, 'catchment_uncertain_ground_sqft': local}
        for scenario_id, mixed_fraction, crown_fraction, label in family:
            components = [{'geometry': mapping(g), 'impervious_fraction': f, 'basis': basis}
                for g, f, basis in [(hard, 1., 'Observed IA / roof and road (class-table labelled default)'),
                    (mixed, mixed_fraction, label), (hidden, crown_fraction, label + ' (ground beneath crowns)')]
                if not g.is_empty]
            if not components:
                continue
            run['area_scenarios'].append({'id': scenario_id, 'interpretation_scenario': RECORDED_IA_SCENARIO,
                'area_sqft': sum(case_area_sqft(shape(c['geometry']), case) * c['impervious_fraction'] for c in components),
                'geometry': mapping(union([shape(c['geometry']) for c in components])),
                'weighted_components': components, 'basis': label,
                'assumptions': ['Recorded IA is approximately correct (a prior, not independent evidence)',
                    'Grass/soil/water appearances assumed pervious for this labelled scenario, not observed permeability',
                    'The recorded total cannot locate impervious ground; circular if credits are measured against it',
                    'All modeled candidate runoff is captured and adequately treated; this is a conditional estimate']})
    return result


def _impervious_area(case, gis, day, tariff):
    """R4: unknown unless a complete measured GA/IA exists (shared measured-area path)."""
    recorded = (case.get('baseline') or {}).get('ia_sqft')
    retained = {'name': 'retained_recorded_ia', 'ia_sqft': recorded, 'annual_change': None,
        'basis': 'Recorded IA retained as the billing prior; no correction is estimated',
        'meaning': 'Not a zero-savings estimate: the bill stays as recorded only because no correction is evaluated'}
    measurement = (gis or {}).get('measurement') or {}
    out = {'estimated_reduction_sqft': None, 'annual_savings_estimate': None, 'status': 'not_estimated',
           'uncertainty': _uncertainty(), 'scenarios': [retained], 'actual_available_savings_verified': False,
           'basis': 'Saved imagery does not independently measure IA; recorded IA is retained as a prior, not confirmed'}
    if measurement.get('complete') is not True:
        out['reason'] = 'No complete measured GA/IA in the frozen GIS; unknown is not zero'
        return out
    from .assessment_policy import _economics
    s = _economics(case, gis, [], day, tariff).get('measurement_only') or {}
    reduction = recorded - measurement['ia_sqft'] if recorded is not None and measurement.get('ia_sqft') is not None else None
    out.update(status='measured_area_scenario' if s.get('status') == 'calculated' else 'blocked',
               estimated_reduction_sqft=reduction, annual_savings_estimate=s.get('gross_annual_reduction'),
               measured_scenario={k: deepcopy(s.get(k)) for k in ('status', 'reasons', 'gross_monthly_reduction',
                                                                  'gross_annual_reduction', 'bill', 'alternatives')},
               basis='Complete measured GA/IA priced by the shared assessment ledger (measurement_only); not a filed appeal')
    out['scenarios'].append({'name': 'complete_measured_area', 'ia_sqft': measurement.get('ia_sqft'),
                             'annual_change': s.get('gross_annual_reduction') if s.get('status') == 'calculated' else None})
    return out


def _system(case, frozen_gis, identifier, constraint, canopy_fraction, day, tariff):
    engineering = estimate_system(case, frozen_gis, identifier)
    interpreted_engineering = (_recorded_ia_family(case, frozen_gis, engineering, constraint, canopy_fraction)
                               if engineering.get('status') != 'excluded' else engineering)
    context = system_context(case, frozen_gis, interpreted_engineering, day, tariff)
    value = estimate_management(case, frozen_gis, interpreted_engineering, day, tariff, context=context)
    value.pop('confidence', None)
    value['uncertainty'] = _uncertainty()
    system = {'physical': engineering, 'policy': value,
              'capacity_path': surface_storage_system(engineering.get('system_type'))}
    if not system['capacity_path']:
        return system
    from drainage_core.runoff_capacity import estimate_capacity
    from .runoff_capacity import estimate_capacity_management
    try:
        capacity = estimate_capacity(case, frozen_gis, identifier)
    except ValueError as exc:
        capacity = {'system_id': str(identifier), 'status': 'unavailable', 'reason': str(exc),
                    'unavailable_reasons': [str(exc)], 'source_lineage': {}}
    managed = estimate_capacity_management(case, frozen_gis, interpreted_engineering, capacity, day, tariff, context=context)
    system['capacity'] = capacity
    system['managed_runoff'] = managed
    system['full_area_management_scenario'] = {**value, 'status': 'superseded', 'usable_for_current_savings': False,
        'superseded_reason': ('Assumes every candidate IA outside the bed is managed without a storage limit; '
                              'use the storage-limited range')}
    system['policy'] = {'version': managed['version'], 'system_id': managed['system_id'],
        'system_type': engineering.get('system_type'), 'as_of': day.isoformat(),
        'status': managed['status'], 'basis': 'storage_limited_management_range',
        'headline': deepcopy(managed.get('headline')), 'current_estimate': deepcopy(managed.get('current_estimate')),
        'current_estimate_withheld_reason': managed.get('current_estimate_withheld_reason'),
        'runs': deepcopy(managed['runs']), 'range': deepcopy(managed.get('range')),
        'review_flags': deepcopy(managed.get('review_flags')), 'reasons': deepcopy(managed.get('reasons', [])),
        'warnings': deepcopy(managed.get('warnings', value.get('warnings', []))),
        'eligibility': deepcopy(value['eligibility']), 'captured_ia_sqft': None,
        'verified_managed_area_sqft': None, 'uncertainty': _uncertainty(), 'do_not_sum': True}
    return system


def estimate_property(case, frozen_gis, system_ids, as_of=None, tariff=None):
    day, as_of_source = derive_as_of(case, as_of)
    tariff = deepcopy(tariff or default_tariff())
    gis = policy_gis(case, frozen_gis)
    surface = estimate_surfaces(case, frozen_gis)
    constraint = _ground_constraint(case, surface)
    canopy = surface['canopy']
    amounts = [canopy['range_sqft'][0], constraint['canopy_ground_ia_estimate_sqft'], canopy['range_sqft'][1]]
    ledger = ledger_context(case, gis, day, tariff)
    priced = [_canopy_money(case, gis, a, canopy['geometry'], day, tariff, ledger)
              if a is not None else {'status': 'unknown', 'annual_savings': None} for a in amounts]
    canopy_fraction = ((amounts[1] - canopy['observed_ground_ia_overlap_sqft']) / canopy['hidden_ground_sqft']
                       if amounts[1] is not None and canopy['hidden_ground_sqft'] else 0.)
    systems = [_system(case, frozen_gis, identifier, constraint, canopy_fraction, day, tariff) for identifier in system_ids]
    money = [p.get('annual_savings') if p.get('status') == 'calculated' else None for p in priced]
    return {'case_id': case.get('id'), 'name': case.get('name'), 'as_of': day.isoformat(), 'as_of_source': as_of_source,
        'baseline': deepcopy(case['baseline']), 'baseline_warnings': deepcopy(ledger['warnings']),
        'baseline_gap': deepcopy(ledger['gap']), 'surface': surface, 'ground_constraint': constraint,
        'canopy': {'estimated_ground_ia_beneath_canopy_sqft': amounts[1], 'area_range_sqft': [amounts[0], amounts[2]],
            'annual_savings_estimate': money[1],
            'annual_savings_range': [money[0], money[2]],
            'uncertainty': _uncertainty(), 'scenarios': priced,
            'basis': 'Conditional canopy credit, local context plus recorded-IA prior; concealed ground not verified'},
        'impervious_area': _impervious_area(case, gis, day, tariff),
        'systems': systems, 'do_not_sum': True,
        'nonadditivity': 'System/canopy/appeal estimates are alternatives until their shared areas are allocated once.'}


def run_saved(specifications, output, as_of=None):
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
    output_result = {'version': VERSION, 'as_of': as_of if as_of is None else str(as_of),
        'as_of_rule': 'Explicit --as-of, otherwise each property\'s recorded case date (see properties[].as_of_source)',
        'policy_interpretation_version': POLICY_INTERPRETATION_VERSION,
        'physical_interpretation_version': PHYSICAL_INTERPRETATION_VERSION,
        'elapsed_seconds': perf_counter() - started, 'uncertainty': _uncertainty(),
        'input_manifest': manifest, 'properties': results}
    project = Path(__file__).resolve().parents[1]
    output_result['implementation_sha256'] = {name: hashlib.sha256((project / name).read_bytes()).hexdigest()
                                              for name in IMPLEMENTATION_FILES}
    (destination / 'estimates.json').write_text(json.dumps(output_result, separators=(',', ':'), allow_nan=False))
    return output_result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--whitaker')
    parser.add_argument('--south-61st', required=True)
    parser.add_argument('--only-system', help='Price one mapped system ID on the --south-61st property')
    parser.add_argument('--as-of', help='Assessment date (YYYY-MM-DD); default: each case\'s recorded date')
    parser.add_argument('--output', required=True)
    args = parser.parse_args(argv)
    if args.only_system:
        specifications = [(args.south_61st, [args.only_system])]
    else:
        if not args.whitaker:
            parser.error('--whitaker is required unless --only-system is selected')
        specifications = [(args.whitaker, ['62571']), (args.south_61st, ['01073', '01074'])]
    result = run_saved(specifications, args.output, args.as_of)
    print(json.dumps({'output': str(Path(args.output) / 'estimates.json'), 'seconds': result['elapsed_seconds']}))


if __name__ == '__main__':
    main()
