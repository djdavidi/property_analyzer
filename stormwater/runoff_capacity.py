"""PWD screening over independent surface-storage estimates, without routing.

Static event storage is converted to an equivalent managed IA at the applicable
rule depth. It is an estimate of accommodation, not proof of treatment/drawdown.
"""
from copy import deepcopy

from shapely.geometry import mapping, shape
from shapely.errors import ShapelyError

from drainage_core.engine import input_hash
from drainage_core.geometry import case_area_sqft, union
from drainage_core.model_integration import _area_only
from .billing import decimal, default_tariff
from .management_estimates import _candidate_geometry, estimate_management, TREATMENT_DEPTH_INCHES

VERSION = 'pwd-storage-limited-management-v1'


def _external_candidate(case, scenario, footprint):
    area = decimal(scenario.get('area_sqft'), 'candidate area')
    geometry, errors = _candidate_geometry(case, scenario, area, False)
    if errors:
        raise ValueError('; '.join(errors))
    components = scenario.get('weighted_components')
    if components is None:
        components = [{'geometry': mapping(geometry), 'impervious_fraction': 1.,
                       'basis': scenario.get('basis') or 'Supplied contributing IA hypothesis'}] if geometry is not None else []
    external = []
    for component in components:
        region = _area_only(shape(component['geometry']).difference(footprint))
        if region.is_empty:
            continue
        external.append({**deepcopy(component), 'geometry': mapping(region)})
    external_area = sum(case_area_sqft(shape(c['geometry']), case) * float(decimal(c['impervious_fraction']))
                        for c in external)
    return external, external_area, float(area) - external_area


def _scaled_scenario(case, components, candidate, managed, name, assumptions):
    share = managed / candidate if candidate else 0.
    scaled = [{**deepcopy(c), 'impervious_fraction': float(c['impervious_fraction']) * share,
               'basis': c['basis'] + '; scaled to static-storage managed-IA equivalent'} for c in components]
    geometry = _area_only(union([shape(c['geometry']) for c in scaled]))
    out = {'id': 'base', 'area_sqft': managed, 'geometry': mapping(geometry),
        'basis': name, 'assumptions': assumptions}
    if scaled:
        out['weighted_components'] = scaled
    return out


def estimate_capacity_management(case, frozen_gis, engineering, capacity, as_of, tariff=None):
    """Budget garden rainfall, external runoff and storage before pricing credit.

    The base event omits additional soft-ground runoff and infiltration/recovery.
    A full-soft-ground runoff sensitivity is separate; neither is a probability.
    Uniform fractional allocation retains all possible contributing geometry for
    conservative overlap checks. It does not identify a proven creditable subarea.
    """
    result = {'version': VERSION, 'system_id': engineering.get('system_id'),
        'status': 'unavailable', 'current_estimate': None, 'runs': [], 'range': None,
        'verified_managed_area_sqft': None, 'verified_treatment_capacity_cuft': None,
        'source_lineage': deepcopy(engineering.get('source_lineage') or {}),
        'capacity_source_lineage': deepcopy(capacity.get('source_lineage') or {}),
        'uncertainty': {'status': 'not_calibrated', 'basis': 'Explicit event, terrain and surface hypotheses; no numerical confidence'},
        'do_not_sum': True, 'reasons': [],
        'basis': 'Dry-start static surface-storage estimate, with direct garden rainfall reserved first',
        'limitations': ['Equivalent IA is a screening allocation, not a demonstrated qualifying drainage subarea',
            'Infiltration/media/underdrain recovery are excluded from capacity, not assumed measured zero',
            'Treatment, drawdown and current operation remain unverified'],
    }
    try:
        if str(capacity.get('system_id')) != str(engineering.get('system_id')):
            raise ValueError('Capacity belongs to a different system')
        lineage = capacity.get('source_lineage') or {}
        if lineage.get('case_sha256') and lineage['case_sha256'] != input_hash(case):
            raise ValueError('Capacity belongs to different case inputs')
        if lineage.get('gis_analysis_sha256') and lineage['gis_analysis_sha256'] != frozen_gis.get('analysis_sha256'):
            raise ValueError('Capacity belongs to different frozen GIS')
        if capacity.get('surface_storage_volume_cuft') is None or capacity.get('status') not in ('estimated', 'modeled'):
            result['reasons'] = ['Usable local surface-storage estimate unavailable; no savings estimate calculated']
            return result
        full_footprint = _area_only(shape(engineering['footprint_geometry']))
        if full_footprint.difference(shape(case['parcel'])).area > 1e-8:
            raise ValueError('Cross-parcel system storage allocation is unknown')
        footprint = _area_only(full_footprint.intersection(shape(case['parcel'])))
        if footprint.is_empty:
            raise ValueError('On-parcel garden footprint unavailable')
        garden_area = case_area_sqft(footprint, case)
        if capacity.get('rain_exposure_area_sqft') is not None and abs(float(decimal(capacity['rain_exposure_area_sqft'])) - garden_area) > .1:
            raise ValueError('Capacity rainfall exposure does not match the garden footprint')
        depth_ft = float(TREATMENT_DEPTH_INCHES / 12)
        garden_rain = garden_area * depth_ft
        result.update(garden_area_sqft=garden_area, treatment_depth_inches=float(TREATMENT_DEPTH_INCHES),
            direct_garden_rainfall_cuft=garden_rain)
        storage_rows = [dict(s) for s in capacity.get('scenarios', [])
                        if s.get('volume_cuft') is not None and s.get('status') in ('estimated', 'modeled')]
        best_name = capacity.get('selected_scenario', 'boundary_cell_minimum')
        if not any(s['name'] == best_name for s in storage_rows):
            storage_rows.insert(0, {'name': best_name, 'status': 'estimated',
                                   'volume_cuft': capacity['surface_storage_volume_cuft']})
        primary_volume = float(decimal(capacity['surface_storage_volume_cuft'], 'primary surface storage'))
        if any(s['name'] == best_name and abs(float(decimal(s['volume_cuft'])) - primary_volume) > .001 for s in storage_rows):
            raise ValueError('Primary storage volume does not match its selected scenario')
        pricing_runs = []
        for run in engineering.get('runs', []):
            base = next((s for s in run.get('area_scenarios', []) if s['id'] == 'base'), None)
            if base is None:
                continue
            components, external_area, excluded_area = _external_candidate(case, base, footprint)
            external_region = _area_only(shape(run.get('on_parcel_geometry') or case['parcel']).difference(footprint))
            other_ground = max(0., case_area_sqft(external_region, case) - external_area)
            scenarios = []
            pricing_rows = []
            for storage in storage_rows:
                volume = float(decimal(storage['volume_cuft'], 'surface storage'))
                for other_fraction in (0., 1.):
                    other_runoff = other_ground * depth_ft * other_fraction
                    available = max(0., volume - garden_rain - other_runoff)
                    managed = min(external_area, available / depth_ft)
                    assumptions = ['Surface storage starts empty for the event',
                        'Garden footprint assumed noncreditable system bed; its full direct rainfall reserves storage first',
                        'First 1.5-inch runoff depth and dry-start volume-equivalent managed-IA allocation',
                        'No infiltration/media/outlet recovery added to capacity',
                        ('No additional runoff assigned from external soft/mixed-pervious ground' if not other_fraction
                         else 'All external soft/mixed-pervious ground contributes rainfall as runoff (load sensitivity)'),
                        'Static accommodation does not verify treatment or drawdown']
                    source = _scaled_scenario(case, components, external_area, managed,
                        'Storage-limited managed-IA equivalent', assumptions)
                    source['id'] = storage['name'] + ('/soft_runoff_max' if other_fraction else '/soft_runoff_omitted')
                    pricing_rows.append(source)
                    value = {'name': storage['name'] + ('/soft_runoff_max' if other_fraction else '/soft_runoff_omitted'),
                        'storage_scenario': storage['name'], 'additional_soft_ground_runoff_fraction': other_fraction,
                        'surface_storage_volume_cuft': volume, 'direct_garden_rainfall_cuft': garden_rain,
                        'other_ground_area_sqft': other_ground, 'other_ground_runoff_cuft': other_runoff,
                        'external_contributing_ia_sqft': external_area,
                        'garden_ia_excluded_sqft': excluded_area,
                        'available_storage_for_external_runoff_cuft': available,
                        'estimated_managed_ia_equivalent_sqft': managed,
                        'estimated_managed_runoff_volume_cuft': managed * depth_ft,
                        'unaccommodated_external_ia_runoff_cuft': max(0., external_area * depth_ft - managed * depth_ft),
                        'monthly_savings': None, 'annual_savings': None,
                        'status': 'pending', 'reasons': [], 'assumptions': assumptions, 'priced': None}
                    scenarios.append(value)
            result['runs'].append({'name': run.get('name'), 'scenarios': scenarios})
            pricing_runs.append({**deepcopy(run), 'area_scenarios': pricing_rows})
        # Validate lineage/rules/ledger once, price all alternative scenarios in one
        # adapter call. Large frozen rasters are not rehashed for every sensitivity.
        view = deepcopy(engineering)
        view['runs'] = pricing_runs
        priced = estimate_management(case, frozen_gis, view, as_of, tariff or default_tariff())
        for run, priced_run in zip(result['runs'], priced['runs'], strict=True):
            for value, amount in zip(run['scenarios'], priced_run['scenarios'], strict=True):
                value.update(monthly_savings=amount.get('monthly_savings'), annual_savings=amount.get('annual_savings'),
                    status=amount['status'], reasons=amount.get('reasons', []),
                    priced=deepcopy(amount) if amount['status'] == 'calculated' else None)
                if value['storage_scenario'] == best_name and not value['additional_soft_ground_runoff_fraction']:
                    if result['current_estimate'] is None or run.get('name') == 'nominal':
                        result['current_estimate'] = {'run': run.get('name'), **deepcopy(value)}
        calculated = [s for r in result['runs'] for s in r['scenarios'] if s['status'] == 'calculated']
        if calculated:
            result['range'] = {key: [min(s[key] for s in calculated), max(s[key] for s in calculated)]
                for key in ('estimated_managed_ia_equivalent_sqft', 'estimated_managed_runoff_volume_cuft', 'annual_savings')}
            result['range']['basis'] = 'Terrain/routing/event-load sensitivity envelope, not a confidence interval'
        selected = result['current_estimate']
        result['status'] = 'storage_limited_estimate' if selected and selected['status'] == 'calculated' else 'blocked'
        if result['status'] == 'blocked':
            result['reasons'] = list(dict.fromkeys(reason for r in result['runs'] for s in r['scenarios'] for reason in s['reasons'])) or ['No usable base contributing-area estimate']
    except (ValueError, KeyError, TypeError, AttributeError, ShapelyError) as exc:
        result.update(status='blocked', current_estimate=None, reasons=[str(exc)])
    return result
