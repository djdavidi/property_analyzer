"""Conditional PWD management estimates over frozen, per-system GIS artifacts.

An upstream area is not a captured or adequately treated area. This adapter prices
the explicit hypothesis that the supplied candidate IA is managed; it never edits
evidence, invents storage depth, acquires data, or reroutes the physical model.
"""
from copy import deepcopy
from datetime import date
from decimal import Decimal

from shapely.geometry import shape
from shapely.errors import ShapelyError
from shapely.ops import unary_union

from drainage_core.geometry import case_area_sqft, polygon
from drainage_core.installation import installation_issues
from .assessment_policy import RULES, _existing_allocations
from .billing import calculate_scenarios, decimal, default_tariff


VERSION = 'pwd-system-management-estimates-v1'
TREATMENT_DEPTH_INCHES = Decimal('1.5')
BENCHMARK_AREAS_SQFT = (1000, 5000, 10000)
PREREQUISITES = (
    'existing_installation', 'account_current', 'physical_area_confirmed',
    'parcel_allocation_confirmed', 'routing_confirmed', 'approved_record_drawings',
    'current_condition_confirmed', 'maintenance_documented', 'professional_reviewed',
)
CONDITIONS = [
    'Candidate impervious area actually reaches this system, without bypass or duplicate allocation.',
    'The system adequately manages the first 1.5 inches of runoff from that area; capacity, drawdown and condition are unverified.',
    'Current account standing, approved drawings, maintenance and professional review satisfy PWD requirements.',
    'Gross current-rate credit illustration; PWD approval, an award and realized savings are not established.',
]


def _identity(value):
    text = str(value or '').strip()
    return str(int(text)) if text.isdigit() else text


def _matches(item, identifier):
    fields = ('system_id', 'gsi_system_id', 'smp_id', 'smpid', 'id')
    return any(_identity(item.get(key)) == _identity(identifier) for key in fields if item.get(key) is not None)


def _known_failures(case, engineering, day):
    """Unknown prerequisites may be modeled; recorded contrary facts may not."""
    identifier = engineering.get('system_id')
    issues = installation_issues(engineering, day)
    issues.extend(str(x) for x in engineering.get('known_failures', []))
    for feature in case.get('features', {}).get('features', []):
        properties = feature.get('properties', {})
        if _matches(properties, identifier) or _matches(feature, identifier):
            issues.extend(installation_issues(properties, day))
    for record in case.get('assessment', {}).get('records', []):
        containers = (record, record.get('source') or {}, record.get('facts') or {})
        if not any(isinstance(item, dict) and _matches(item, identifier) for item in containers):
            continue
        facts = record.get('facts') or {}
        issues.extend(installation_issues(facts, day))
        if record.get('decision') == 'rejected':
            issues.append('System assessment explicitly rejected')
        if record.get('source_update', {}).get('status') == 'pending_review':
            issues.append('Changed system evidence requires source-update review')
        for key in PREREQUISITES:
            if facts.get(key) is False:
                issues.append('Known failed prerequisite: ' + key)
        if facts.get('treatment_depth_inches') is not None:
            try:
                minimum = Decimal('1') if facts.get('old_standard_renewal_verified') is True else TREATMENT_DEPTH_INCHES
                if decimal(facts['treatment_depth_inches']) < minimum:
                    issues.append('Recorded treatment depth fails the applicable management standard')
            except ValueError as exc:
                issues.append(str(exc))
    if case.get('baseline', {}).get('account_current') is False:
        issues.append('Known failed prerequisite: account_current')
    return list(dict.fromkeys(issues))


def _baseline_context(case, gis, day, tariff):
    errors = []
    baseline = deepcopy(case.get('baseline') or {})
    if case.get('assessment', {}).get('baseline_refresh', {}).get('status') == 'pending_review':
        errors.append('New public billing/credit facts differ from the retained baseline; review required')
    if not RULES['effective_from'] <= day <= RULES['verified_through']:
        errors.append('Assessment date outside verified rule period')
    if not tariff['effective_from'] <= day <= tariff['verified_through']:
        errors.append('Assessment date outside verified tariff period')
    allocations = []
    base_bill = None
    try:
        amounts = [decimal(baseline.get(key, 0), key) for key in
                   ('existing_ga_credit_sqft', 'existing_ia_credit_sqft', 'existing_iar_sqft')]
        if any(amounts) or case.get('assessment', {}).get('existing_credit_allocations'):
            allocations, allocation_errors = _existing_allocations(case, gis, baseline)
            errors.extend(allocation_errors)
            if baseline.get('existing_credits_spatially_reconciled') is not True:
                errors.append('Existing aggregate credits require spatial reconciliation')
            regions = [shape(item['geometry']) for item in allocations]
            if any(a.intersection(b).area > 1e-8 for i, a in enumerate(regions) for b in regions[:i]):
                errors.append('Existing credit allocations overlap')
        base_bill = calculate_scenarios(baseline, tariff=tariff)['baseline']
    except (ValueError, TypeError, KeyError, AttributeError, ShapelyError) as exc:
        errors.append(str(exc))
    return baseline, base_bill, allocations, list(dict.fromkeys(errors))


def _candidate_geometry(case, scenario, area, benchmark):
    if benchmark:
        return None, []
    if area == 0 and not scenario.get('geometry') and 'weighted_components' not in scenario:
        return None, []
    try:
        # Frozen zero-area scenarios use an explicit empty geometry. This is a
        # lower bound and must not activate zero-area-credit account minimums.
        if area == 0 and shape(scenario['geometry']).is_empty and 'weighted_components' not in scenario:
            return None, []
        geometry = polygon(scenario.get('geometry'))
        parcel = polygon(case['parcel'])
        errors = []
        if geometry.difference(parcel).area > 1e-8:
            errors.append('Candidate IA geometry extends outside the billed parcel')
        if 'weighted_components' in scenario:
            components = scenario['weighted_components']
            if not isinstance(components, list) or not components:
                raise ValueError('Weighted components must be a nonempty list')
            regions = []
            weighted = Decimal(0)
            for component in components:
                if not isinstance(component, dict):
                    raise ValueError('Weighted component must be an object')
                region = polygon(component.get('geometry'))
                fraction = decimal(component.get('impervious_fraction'), 'impervious_fraction')
                if fraction > 1:
                    raise ValueError('impervious_fraction must be between 0 and 1')
                if not isinstance(component.get('basis'), str) or not component['basis'].strip():
                    raise ValueError('Weighted impervious fraction requires an explicit assumption basis')
                if any(region.intersection(other).area > 1e-8 for other in regions):
                    raise ValueError('Weighted component geometries overlap; impervious area would be double counted')
                regions.append(region)
                weighted += Decimal(str(case_area_sqft(region, case))) * fraction
            if geometry.symmetric_difference(unary_union(regions)).area > 1e-8:
                errors.append('Candidate geometry does not match the union of weighted components')
            measured = float(weighted)
        else:
            measured = case_area_sqft(geometry, case)
        if abs(measured - float(area)) > max(.1, float(area) * .001):
            errors.append('Candidate IA scalar does not match its geometry')
        return geometry, errors
    except (ValueError, TypeError, KeyError, AttributeError, ShapelyError) as exc:
        return None, ['Candidate IA geometry invalid: ' + str(exc)]


def _scenario(case, baseline, base_bill, allocations, common_errors, scenario, tariff, benchmark=False):
    result = {
        'id': scenario.get('id'), 'basis': scenario.get('basis'),
        'area_kind': 'illustrative_managed_ia_sensitivity' if benchmark else 'modeled_on_parcel_contributing_ia',
        'is_site_area_estimate': not benchmark,
        'candidate_ia_sqft': None, 'assumed_managed_ia_sqft': None,
        'verified_managed_area_sqft': None, 'captured_ia_sqft': None,
        'required_runoff_volume_cuft_at_1_5in': None,
        'monthly_savings': None, 'annual_savings': None, 'bill': None, 'ledger': None,
        'status': 'blocked', 'reasons': [],
        'assumptions': deepcopy(scenario.get('assumptions') or []) + CONDITIONS,
        'confidence_pct': None,
    }
    if 'weighted_components' in scenario:
        result.update(area_kind='modeled_fractional_on_parcel_contributing_ia',
                      weighted_components=deepcopy(scenario['weighted_components']),
                      fractional_ia_is_assumed=True)
        result['assumptions'].append('Impervious fractions are screening assumptions, not observed ground classification or independent IA validation.')
    errors = list(common_errors)
    try:
        area = decimal(scenario.get('area_sqft'), 'candidate_ia_sqft')
        result['candidate_ia_sqft'] = result['assumed_managed_ia_sqft'] = float(area)
        result['required_runoff_volume_cuft_at_1_5in'] = float(area * TREATMENT_DEPTH_INCHES / 12)
        geometry, geometry_errors = _candidate_geometry(case, scenario, area, benchmark)
        errors.extend(geometry_errors)
        reserved = sum((decimal(item['area_sqft']) for item in allocations
                        if item['category'] != 'open_space'), Decimal(0))
        if area + reserved > decimal(baseline.get('ia_sqft'), 'ia_sqft'):
            errors.append('Candidate and existing allocations exceed available billed physical IA')
        if allocations and area:
            if geometry is None:
                errors.append('Unlocated area cannot be reconciled against existing credit allocations')
            elif any(geometry.intersection(shape(item['geometry'])).area > 1e-8 for item in allocations):
                errors.append('Candidate IA overlaps an existing credit allocation')
        if errors:
            result['reasons'] = list(dict.fromkeys(errors))
            return result
        if area == 0:
            # A zero lower scenario is a conditional bound, not proof of zero site
            # IA or no opportunity. Do not activate a zero-area credit/minimum.
            result.update(status='calculated', monthly_savings=0.0, annual_savings=0.0,
                          bill=deepcopy(base_bill), ledger={'allocated_physical_ia_sqft': 0.0},
                          note='No positive IA identified in this scenario; actual managed area remains unknown.')
            return result
        evidence = {key: True for key in PREREQUISITES}
        evidence['treatment_depth_inches'] = float(TREATMENT_DEPTH_INCHES)
        benefit = {'id': 'conditional-system-management', 'category': 'management',
                   'area_sqft': float(area), 'basis': 'modeled', 'evidence': evidence,
                   'ledger_ids': ['conditional-system-management'],
                   'existing_overlap_reconciled': True}
        calculated = calculate_scenarios(baseline, benefits=[benefit], tariff=tariff)['credit_only']
        result['status'] = calculated['status']
        if calculated['status'] == 'calculated':
            result.update(monthly_savings=calculated['monthly_savings'], annual_savings=calculated['annual_savings'],
                          bill=calculated, ledger=calculated['ledger'])
        else:
            result['reasons'] = calculated['reasons']
    except (ValueError, TypeError, KeyError, AttributeError, ShapelyError) as exc:
        result['reasons'] = list(dict.fromkeys(errors + [str(exc)]))
    return result


def estimate_management(case, frozen_gis, engineering, as_of, tariff=None):
    """Price one system at retained billed GA/IA, with explicit treatment conditions.

    ``engineering`` is drainage_core.management.estimate_system's frozen result.
    Scenario geometry must describe only its candidate on-parcel IA. Each run is
    an alternative; neither runs, systems nor other savings should be added
    without a joint disjoint-area ledger. Unknown basin service areas receive
    labeled unit sensitivities, never a fabricated site best estimate.
    """
    day = date.fromisoformat(as_of).isoformat() if isinstance(as_of, str) else as_of.isoformat()
    t = deepcopy(tariff or default_tariff())
    baseline, base_bill, allocations, errors = _baseline_context(case, frozen_gis, day, t)
    from drainage_core.engine import input_hash, result_hash
    lineage = engineering.get('source_lineage') or {}
    if lineage.get('case_sha256') and lineage['case_sha256'] != input_hash(case):
        errors.append('Engineering estimate belongs to different case inputs')
    if lineage.get('gis_analysis_sha256') and lineage['gis_analysis_sha256'] != frozen_gis.get('analysis_sha256'):
        errors.append('Engineering estimate belongs to a different frozen GIS artifact')
    if frozen_gis.get('input_sha256') and frozen_gis['input_sha256'] != input_hash(case):
        errors.append('Frozen GIS inputs do not match policy case')
    if frozen_gis.get('analysis_sha256') and frozen_gis['analysis_sha256'] != result_hash(frozen_gis):
        errors.append('Frozen GIS content hash does not match')
    failed = _known_failures(case, engineering, day)
    errors.extend(failed)
    result = {
        'version': VERSION, 'system_id': engineering.get('system_id'),
        'system_type': engineering.get('system_type'), 'as_of': day,
        'footprint_area_sqft': engineering.get('footprint_area_sqft'),
        'basis': 'conditional_current_rate_management_credit', 'baseline': base_bill,
        'scope': 'Credit-only change at retained billed GA/IA, one system allocation at a time; no IA appeal or other new benefits included.',
        'do_not_sum': True, 'verified_managed_area_sqft': None,
        'captured_ia_sqft': None, 'capture_fraction': None, 'treatment_capacity_cuft': None,
        'eligibility': {'status': 'requirements_failed' if failed else 'unverified', 'failed': failed,
                        'missing': ['Verified inlet/conveyance and bypass', 'Effective storage/treatment and drawdown',
                                    'Current condition and maintenance', 'Approved drawings and professional review',
                                    'PWD award and actual account bill']},
        'confidence': {'status': 'not_calibrated', 'percentage': None,
                       'meaning': 'Scenario sensitivity is not a statistical confidence interval or approval probability.'},
        'warnings': [] if baseline.get('actual_bill_verified') is True else
                    ['Actual account bill, payer and special-rate enrollment are unverified.'],
        'runs': [], 'sensitivity_examples': [], 'current_estimate': None, 'range': None,
        'source_lineage': deepcopy(engineering.get('source_lineage', {})),
        'missing_evidence': deepcopy(engineering.get('missing_evidence', [])),
        'rules': deepcopy(RULES), 'tariff': t,
        'required_volume_basis': 'Candidate IA × 1.5/12 ft; runoff-volume equivalent, not available storage or proof of adequate treatment.',
    }
    all_scenarios = []
    for run in engineering.get('runs', []):
        scenarios = [_scenario(case, baseline, base_bill, allocations, errors,
                               {**item, 'assumptions': deepcopy(run.get('assumptions') or []) + deepcopy(item.get('assumptions') or [])}, t)
                     for item in run.get('area_scenarios', [])]
        result['runs'].append({
            'name': run.get('name'), 'contributing_area_sqft': run.get('contributing_area_sqft'),
            'on_parcel_area_sqft': run.get('on_parcel_area_sqft'),
            'off_parcel_area_sqft': run.get('off_parcel_area_sqft'),
            'identified_ia_sqft': run.get('identified_ia_sqft'),
            'connection_hypothesis': deepcopy(run.get('connection_hypothesis')),
            'kind': run.get('kind'),
            'connection_scope': deepcopy(run.get('connection_scope')),
            'candidate_collection_points': deepcopy(run.get('candidate_collection_points')),
            'assumptions': deepcopy(run.get('assumptions', [])),
            'evidence': deepcopy(run.get('evidence', [])),
            'scenarios': scenarios, 'diagnostics': deepcopy(run.get('diagnostics', {})),
        })
        all_scenarios.extend((run.get('name'), item) for item in scenarios)
    if not engineering.get('runs'):
        result['sensitivity_examples'] = [_scenario(
            case, baseline, base_bill, allocations, errors,
            {'id': 'per-' + str(area) + '-sqft', 'area_sqft': area,
             'basis': 'Unit sensitivity only; contributing/captured area is unknown, not a site estimate.',
             'assumptions': ['This example supplies an illustrative managed area, not an inferred basin catchment.']},
            t, benchmark=True) for area in BENCHMARK_AREAS_SQFT]
    calculated = [(name, item) for name, item in all_scenarios if item['status'] == 'calculated']
    bases = [(name, item) for name, item in calculated if item['id'] == 'base']
    if bases:
        # Prefer the native/base run when supplied; preserve all alternatives.
        name, selected = next(((name, item) for name, item in bases if name in ('native', 'base')), bases[0])
        result['current_estimate'] = {'run': name, **deepcopy(selected)}
    if calculated:
        result['range'] = {
            'candidate_ia_sqft': [min(item['candidate_ia_sqft'] for _, item in calculated), max(item['candidate_ia_sqft'] for _, item in calculated)],
            'annual_savings': [min(item['annual_savings'] for _, item in calculated), max(item['annual_savings'] for _, item in calculated)],
            'basis': 'Envelope of supplied routing/cover scenarios; conditional on capture, treatment and eligibility; not a confidence interval.',
        }
    calculated_examples = any(item['status'] == 'calculated' for item in result['sensitivity_examples'])
    result['status'] = 'conditional_estimate' if calculated else 'unit_sensitivities_only' if calculated_examples else 'blocked'
    if result['status'] == 'blocked':
        errors.extend(reason for _, item in all_scenarios for reason in item['reasons'])
        errors.extend(reason for item in result['sensitivity_examples'] for reason in item['reasons'])
    result['reasons'] = list(dict.fromkeys(errors))
    return result
