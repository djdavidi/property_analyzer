"""Conditional PWD management estimates over frozen, per-system GIS artifacts.

An upstream area is not a captured or adequately treated area. This adapter prices
the explicit hypothesis that the supplied candidate IA is managed; it never edits
evidence, invents storage depth, acquires data, or reroutes the physical model.

One money path (D7): every row is priced by ``system_pricing.price_benefit``, the
assessment ledger the app uses. ``system_context`` holds the gates shared with the
capacity adapter and the pilot:

* one assessment date (``system_pricing.as_of_date``, H8);
* the ledger baseline and its warnings; a published-versus-computed gap above
  ``system_pricing.BASELINE_GAP_THRESHOLD`` blocks (H7);
* required lineage: ``case_sha256`` and ``gis_analysis_sha256`` must be present and
  match the priced case and frozen artifact (H9);
* recorded contrary facts on every record or feature that the one identity
  resolver (``model_assessment.system_ids`` and ``match``) links to this system
  (H1/H10); the generic ``id`` counts only when no system-ID field exists;
* a physical ``excluded`` result is excluded, never priced (H10);
* the system's own bed is removed from every candidate (H16).

Presentation (D4, H2). ``headline`` is the range across the nominal run's labelled
interpretation scenarios. ``current_estimate`` is the nominal run's ``base`` row
(the D3 labelled default) and nothing else: when it is blocked the result is
blocked with its reasons, and a sensitivity run never substitutes. Route state
(D2) is per run: partial rows carry ``partial_label``; untestable extent or a failed
invariant blocks. Quantities keep runoff supplied, captured, stored, treated and
qualifying area separate; only "supplied" is a modeled figure here.
"""
from copy import deepcopy
from decimal import Decimal

from shapely.geometry import mapping, shape
from shapely.errors import ShapelyError
from shapely.ops import unary_union

from drainage_core.geometry import area_only, case_area_sqft, effective_features, polygon, union
from drainage_core.installation import installation_issues
from .assessment_policy import RULES
from .billing import decimal, default_tariff
from .model_assessment import match, system_identity, system_ids
from .system_pricing import (annual_values, as_of_date, ledger_context, lineage_errors, policy_gis,
                             price_benefit, run_route, value_range)


VERSION = 'pwd-system-management-estimates-v2'
TREATMENT_DEPTH_INCHES = Decimal('1.5')
BENCHMARK_AREAS_SQFT = (1000, 5000, 10000)
HEADLINE_RUN = 'nominal'
REFERENCE_SCENARIO = 'base'
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
QUANTITY_MEANING = {
    'runoff_supplied_cuft': 'First 1.5-inch runoff volume from the priced candidate area (modeled hypothesis)',
    'runoff_captured_cuft': 'Not established: inlets, conveyance and bypass are unverified',
    'runoff_stored_cuft': 'Not established here: see the runoff-capacity estimate for surface storage',
    'runoff_treated_cuft': 'Not established: treatment and drawdown are unverified',
    'qualifying_managed_area_sqft': 'Not established: no verified qualifying managed area or PWD award',
}


def _evidence():
    evidence = {key: True for key in PREREQUISITES}
    evidence['treatment_depth_inches'] = float(TREATMENT_DEPTH_INCHES)
    return evidence


def system_footprint(case, engineering):
    """The system bed: the physical result's footprint, else the mapped footprint features."""
    try:
        if engineering.get('footprint_geometry'):
            return area_only(shape(engineering['footprint_geometry']))
        target = system_identity(engineering.get('system_id'))
        parts = [shape(f['geometry']) for f in effective_features(case)
                 if (f.get('properties') or {}).get('kind') == 'system_footprint'
                 and target in system_ids(f, generic_id=True)]
        return area_only(union(parts)) if parts else None
    except (ValueError, TypeError, KeyError, AttributeError, ShapelyError):
        return None


def _record_link(record, case, identifier, footprint):
    """'linked', 'ambiguous' or None, using the app's own linker (``match``)."""
    target = system_identity(identifier)
    run = {'catchments': [{'kind': 'gsi', 'receiver_id': target}]}
    integration = {'receiving_features': [{'gsi_id': target, 'geometry': mapping(footprint)}]
                   if footprint is not None and not footprint.is_empty else []}
    try:
        linked = match(record, case, integration, run)
    except (ValueError, TypeError, KeyError, AttributeError, ShapelyError):
        return 'linked' if target in system_ids(record) else None
    if linked['status'] == 'linked':
        return 'linked'
    if linked['status'] == 'ambiguous' and target in linked.get('candidate_ids', []):
        return 'ambiguous'
    return None


def _known_failures(case, engineering, day, footprint):
    """Unknown prerequisites may be modeled; recorded contrary facts may not."""
    identifier = engineering.get('system_id')
    target = system_identity(identifier)
    issues = installation_issues(engineering, day)
    issues.extend(str(x) for x in engineering.get('known_failures', []))
    try:
        features = effective_features(case)
    except (ValueError, TypeError, KeyError):
        features = case.get('features', {}).get('features', [])
    for feature in features:
        if target in system_ids(feature, generic_id=True):
            issues.extend(installation_issues(feature.get('properties') or {}, day))
    for record in case.get('assessment', {}).get('records', []):
        if not isinstance(record, dict):
            continue
        link = _record_link(record, case, identifier, footprint)
        if link is None:
            continue
        if link == 'ambiguous':
            issues.append('Record ' + str(record.get('id')) + ' carries conflicting system identifiers including this '
                          'system; review required')
            continue
        facts = record.get('facts') or {}
        issues.extend(installation_issues(facts, day))
        if record.get('decision') == 'rejected':
            issues.append('System assessment explicitly rejected')
        if (record.get('source_update') or {}).get('status') == 'pending_review':
            issues.append('Changed system evidence requires source-update review')
        for key in PREREQUISITES:
            if facts.get(key) is not None and facts.get(key) is not True:
                issues.append('Known failed prerequisite: ' + key)
        if facts.get('treatment_depth_inches') is not None:
            try:
                minimum = Decimal('1') if facts.get('old_standard_renewal_verified') is True else TREATMENT_DEPTH_INCHES
                if decimal(facts['treatment_depth_inches']) < minimum:
                    issues.append('Recorded treatment depth fails the applicable management standard')
            except ValueError as exc:
                issues.append(str(exc))
    if (case.get('baseline') or {}).get('account_current') is False:
        issues.append('Known failed prerequisite: account_current')
    return list(dict.fromkeys(issues))


def system_context(case, frozen_gis, engineering, as_of, tariff=None):
    """Gates and baseline shared by every priced row of one system."""
    from drainage_core.engine import input_hash, result_hash
    day = as_of_date(as_of)
    t = deepcopy(tariff or default_tariff())
    gis = policy_gis(case, frozen_gis)
    ledger = ledger_context(case, gis, day, t)
    errors, warnings = list(ledger['errors']), list(ledger['warnings'])
    case_hash = input_hash(case)
    errors.extend(lineage_errors(engineering.get('source_lineage'), case_hash, frozen_gis, 'Engineering estimate'))
    if frozen_gis.get('input_sha256') and frozen_gis['input_sha256'] != case_hash:
        errors.append('Frozen GIS inputs do not match policy case')
    if frozen_gis.get('analysis_sha256'):
        if frozen_gis['analysis_sha256'] != result_hash(frozen_gis):
            errors.append('Frozen GIS content hash does not match')
    else:
        warnings.append('Frozen GIS artifact carries no content hash; its lineage is checked by key only')
    footprint = system_footprint(case, engineering)
    failed = _known_failures(case, engineering, day, footprint)
    return {'day': day, 'tariff': t, 'gis': gis, 'case_sha256': case_hash, 'ledger': ledger,
            'baseline': ledger['baseline'], 'errors': list(dict.fromkeys(errors + failed)), 'failed': failed,
            'warnings': list(dict.fromkeys(warnings)), 'footprint': footprint,
            'excluded': engineering.get('status') == 'excluded',
            'excluded_reasons': list(engineering.get('installation_issues') or [])
                                or ['Physical layer excluded this system']}


def _candidate_geometry(case, scenario, area, benchmark):
    """Integrity of the supplied candidate hypothesis (geometry, scalar, components)."""
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


def exclude_bed(case, scenario, area, geometry, footprint):
    """(priced area, priced geometry, weighted components, bed IA, errors) without the bed (H16)."""
    components = scenario.get('weighted_components')
    if geometry is None:
        return area, None, None, 0., []
    if footprint is None:
        bed = scenario.get('ia_within_footprint_sqft')
        try:
            bed = decimal(bed, 'ia_within_footprint_sqft')
        except ValueError:
            return None, None, None, None, ['System footprint unknown; its bed IA cannot be excluded from the candidate (H16)']
        return max(Decimal(0), area - bed), geometry, deepcopy(components), float(bed), []
    if components is not None:
        kept, weighted = [], Decimal(0)
        for component in components:
            region = area_only(shape(component['geometry']).difference(footprint))
            if region.is_empty:
                continue
            fraction = decimal(component['impervious_fraction'], 'impervious_fraction')
            weighted += Decimal(str(case_area_sqft(region, case))) * fraction
            kept.append({**deepcopy(component), 'geometry': mapping(region)})
        priced = min(area, weighted)
        region = area_only(union([shape(c['geometry']) for c in kept]))
        return priced, (region if not region.is_empty else None), kept or None, float(area - priced), []
    bed = Decimal(str(case_area_sqft(area_only(geometry.intersection(footprint)), case)))
    region = area_only(geometry.difference(footprint))
    return max(Decimal(0), area - bed), (region if not region.is_empty else None), None, float(bed), []


def _row(scenario, benchmark):
    row = {
        'id': scenario.get('id'), 'basis': scenario.get('basis'),
        'interpretation_scenario': scenario.get('interpretation_scenario'),
        'area_kind': 'illustrative_managed_ia_sensitivity' if benchmark else 'modeled_on_parcel_contributing_ia',
        'is_site_area_estimate': not benchmark,
        'candidate_ia_sqft': None, 'system_bed_ia_excluded_sqft': None, 'priced_candidate_ia_sqft': None,
        'assumed_managed_ia_sqft': None, 'verified_managed_area_sqft': None, 'captured_ia_sqft': None,
        'required_runoff_volume_cuft_at_1_5in': None,
        'quantities': {key: None for key in QUANTITY_MEANING}, 'quantity_meaning': deepcopy(QUANTITY_MEANING),
        'monthly_savings': None, 'annual_savings': None, 'bill': None, 'ledger': None,
        'status': 'blocked', 'reasons': [],
        'assumptions': deepcopy(scenario.get('assumptions') or []) + CONDITIONS,
        'confidence_pct': None,
    }
    if 'weighted_components' in scenario:
        row.update(area_kind='modeled_fractional_on_parcel_contributing_ia',
                   weighted_components=deepcopy(scenario['weighted_components']), fractional_ia_is_assumed=True)
        row['assumptions'].append('Impervious fractions are screening assumptions, not observed ground classification or independent IA validation.')
    return row


def price_scenario(context, case, scenario, benchmark=False, route=None):
    """One candidate hypothesis priced through the ledger, or blocked with reasons."""
    row = _row(scenario, benchmark)
    if route is not None:
        row.update(route_state=route['route_state'], partial_label=route['partial_label'])
    errors = list(context['errors']) + (list(route['blocked_reasons']) if route else [])
    try:
        area = decimal(scenario.get('area_sqft'), 'candidate_ia_sqft')
        row['candidate_ia_sqft'] = float(area)
        geometry, geometry_errors = _candidate_geometry(case, scenario, area, benchmark)
        errors.extend(geometry_errors)
        if benchmark:
            priced, region, components, bed = area, None, None, 0.
        elif geometry is None and not geometry_errors and area != 0:
            errors.append('Unlocated candidate area cannot be priced as a site estimate')
            priced = region = components = bed = None
        else:
            priced, region, components, bed, bed_errors = exclude_bed(case, scenario, area, geometry, context['footprint'])
            errors.extend(bed_errors)
        if priced is not None:
            volume = float(priced * TREATMENT_DEPTH_INCHES / 12)
            row.update(system_bed_ia_excluded_sqft=bed, priced_candidate_ia_sqft=float(priced),
                       assumed_managed_ia_sqft=float(priced), required_runoff_volume_cuft_at_1_5in=volume)
            row['quantities']['runoff_supplied_cuft'] = volume
            if components is not None:
                row['weighted_components'] = components
        if errors:
            row['reasons'] = list(dict.fromkeys(errors))
            return row
        if priced == 0 and region is None:
            # An unlocated zero scenario is a conditional bound, not proof of zero site
            # IA or no opportunity. A located zero still passes the ledger below, so
            # overlap with an existing award blocks it instead of showing $0.
            row.update(status='calculated', monthly_savings=0.0, annual_savings=0.0,
                       bill=deepcopy(context['baseline']), ledger={'allocated_physical_ia_sqft': 0.0},
                       note='No positive IA identified in this scenario; actual managed area remains unknown.')
            return row
        benefit = {'id': 'conditional-system-management', 'category': 'management', 'area_sqft': float(priced),
                   'geometry': mapping(region) if region is not None else None, 'basis': 'modeled',
                   'evidence': _evidence()}
        priced_row = price_benefit(case, context['gis'], context['day'], context['tariff'], benefit)
        row.update({k: v for k, v in priced_row.items() if k != 'ledger_assumptions'})
        row['assumptions'] += [a for a in priced_row.get('ledger_assumptions', []) if a not in row['assumptions']]
    except (ValueError, TypeError, KeyError, AttributeError, ShapelyError) as exc:
        row['reasons'] = list(dict.fromkeys(errors + [str(exc)]))
    return row


def _run_view(run, rows, route):
    return {
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
        'route_state': route['route_state'], 'route_state_reason': route['route_state_reason'],
        'partial_label': route['partial_label'],
        'scenarios': rows, 'diagnostics': deepcopy(run.get('diagnostics', {})),
    }


def headline(result, reference_id=REFERENCE_SCENARIO, basis=None, rows_key='scenarios'):
    """H2/D4: nominal run only; range first; a blocked nominal reference blocks."""
    nominal = next((r for r in result['runs'] if r['name'] == HEADLINE_RUN), None)
    if nominal is None:
        return None, None
    rows = nominal[rows_key]
    reference = next((s for s in rows if s.get('id') == reference_id), None)
    priced = [s for s in rows if annual_values(s)]
    blocked = (reference is not None and not annual_values(reference)) or not priced
    reasons = list(dict.fromkeys((reference or {}).get('reasons') or [r for s in rows for r in s.get('reasons', [])]
                                 or ['No priced nominal scenario'])) if blocked else []
    value = {'run': HEADLINE_RUN, 'status': 'blocked' if blocked else 'range',
             'route_state': nominal.get('route_state'), 'partial_label': nominal.get('partial_label'),
             'reference_scenario': reference_id if reference is not None else None,
             'reference_role': 'One labelled row of the range (D3 default interpretation); not a bound, best estimate or conservative figure',
             'annual_savings_range': None if blocked else value_range(rows),
             'candidate_ia_range_sqft': None if blocked else value_range(rows, 'priced_candidate_ia_sqft'),
             'scenarios': [{'id': s.get('id'), 'interpretation_scenario': s.get('interpretation_scenario'),
                            'status': s.get('status'), 'annual_savings': s.get('annual_savings'),
                            'annual_savings_alternatives': {k: v.get('annual_savings') for k, v in (s.get('alternatives') or {}).items()} or None,
                            'priced_candidate_ia_sqft': s.get('priced_candidate_ia_sqft')} for s in rows],
             'basis': basis or ('Range across the nominal run\'s labelled ground-interpretation scenarios; '
                                'conditional on capture, treatment and eligibility; not a confidence interval'),
             'reasons': reasons}
    current = None if blocked or reference is None else {'run': HEADLINE_RUN, **deepcopy(reference)}
    return value, current


def estimate_management(case, frozen_gis, engineering, as_of, tariff=None, context=None):
    """Price one system at retained billed GA/IA, with explicit treatment conditions.

    ``engineering`` is drainage_core.management_estimates.estimate_system's frozen
    result. Each run is an alternative; neither runs, systems nor other savings
    should be added without a joint disjoint-area ledger. Unknown basin service
    areas receive labelled unit sensitivities, never a fabricated site estimate.
    """
    ctx = context or system_context(case, frozen_gis, engineering, as_of, tariff)
    result = {
        'version': VERSION, 'system_id': engineering.get('system_id'),
        'system_type': engineering.get('system_type'), 'as_of': ctx['day'].isoformat(),
        'footprint_area_sqft': engineering.get('footprint_area_sqft'),
        'basis': 'conditional_current_rate_management_credit', 'baseline': deepcopy(ctx['baseline']),
        'baseline_gap': deepcopy(ctx['ledger'].get('gap')),
        'scope': 'Credit-only change at retained billed GA/IA, one system allocation at a time; no IA appeal or other new benefits included.',
        'do_not_sum': True, 'verified_managed_area_sqft': None,
        'captured_ia_sqft': None, 'capture_fraction': None, 'treatment_capacity_cuft': None,
        'eligibility': {'status': 'requirements_failed' if ctx['failed'] else 'unverified', 'failed': ctx['failed'],
                        'missing': ['Verified inlet/conveyance and bypass', 'Effective storage/treatment and drawdown',
                                    'Current condition and maintenance', 'Approved drawings and professional review',
                                    'PWD award and actual account bill']},
        'confidence': {'status': 'not_calibrated', 'percentage': None,
                       'meaning': 'Scenario sensitivity is not a statistical confidence interval or approval probability.'},
        'warnings': list(ctx['warnings']),
        'runs': [], 'sensitivity_examples': [], 'headline': None, 'current_estimate': None, 'range': None,
        'route_state': None, 'partial_label': None,
        'source_lineage': deepcopy(engineering.get('source_lineage', {})),
        'missing_evidence': deepcopy(engineering.get('missing_evidence', [])),
        'rules': deepcopy(RULES), 'tariff': ctx['tariff'], 'priced_by': 'assessment_policy._economics',
        'required_volume_basis': 'Candidate IA × 1.5/12 ft; runoff-volume equivalent, not available storage or proof of adequate treatment.',
    }
    if ctx['excluded']:
        result.update(status='excluded', reasons=list(ctx['excluded_reasons']))
        result['eligibility']['status'] = 'requirements_failed'
        result['eligibility']['failed'] = list(dict.fromkeys(ctx['failed'] + ctx['excluded_reasons']))
        return result
    for run in engineering.get('runs', []):
        route = run_route(run)
        rows = [price_scenario(ctx, case, {**item, 'assumptions': deepcopy(run.get('assumptions') or [])
                                           + deepcopy(item.get('assumptions') or [])}, route=route)
                for item in run.get('area_scenarios', [])]
        result['runs'].append(_run_view(run, rows, route))
    if not engineering.get('runs'):
        result['sensitivity_examples'] = [price_scenario(ctx, case,
            {'id': 'per-' + str(area) + '-sqft', 'area_sqft': area,
             'basis': 'Unit sensitivity only; contributing/captured area is unknown, not a site estimate.',
             'assumptions': ['This example supplies an illustrative managed area, not an inferred basin catchment.']},
            benchmark=True) for area in BENCHMARK_AREAS_SQFT]
    rows = [row for run in result['runs'] for row in run['scenarios']]
    value, current = headline(result)
    errors = list(ctx['errors'])
    if value is not None:
        result.update(headline=value, current_estimate=current, route_state=value['route_state'],
                      partial_label=value['partial_label'])
        result['status'] = 'blocked' if value['status'] == 'blocked' else 'conditional_estimate'
        if value['status'] == 'blocked':
            errors.extend(value['reasons'])
    elif rows:
        priced = any(annual_values(r) for r in rows)
        result['status'] = 'alternatives_only' if priced else 'blocked'
        errors.append('No nominal run: connection hypotheses or sensitivities are alternatives, not a headline')
        if not priced:
            errors.extend(r for row in rows for r in row['reasons'])
    else:
        priced = any(annual_values(r) for r in result['sensitivity_examples'])
        result['status'] = 'unit_sensitivities_only' if priced else 'blocked'
        if not priced:
            errors.extend(r for row in result['sensitivity_examples'] for r in row['reasons'])
    if result['status'] != 'blocked' and rows:
        result['range'] = {
            'candidate_ia_sqft': value_range(rows, 'priced_candidate_ia_sqft'),
            'annual_savings': value_range(rows),
            'basis': 'Envelope of every run and interpretation scenario; conditional on capture, treatment and eligibility; not a confidence interval.',
        }
    result['reasons'] = list(dict.fromkeys(errors))
    return result
