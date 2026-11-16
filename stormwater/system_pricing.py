"""Shared gates and the one money path for per-system, pilot and portfolio alternatives.

Decisions D2, D4 and D7 of ``docs/FIX-PLAN-2026-11-16.md`` (review H2-H11, R4, R6).

Money (D7)
    Every adapter dollar is priced by the single assessment ledger
    (``assessment_policy._economics``) through ``price_benefit``. Per-account
    minimums, the NPDES residual, undeveloped-status alternatives (D6), existing-credit
    reconciliation and occupied-area checks, the 500 sq ft gross-area rule, rule and
    tariff periods, the pending baseline-refresh gate and the shared known-false
    prerequisite veto (``prerequisites.case_vetoes``) are therefore identical to the
    app. No adapter calls ``billing.calculate_scenarios``.

Route state (D2)
    One rule for the app paths and the pilot, read from frozen per-catchment
    diagnostics (``drainage_core.management_estimates.route_state``):
    ``complete_in_window`` is priced normally; ``partial_upstream_unknown`` is priced
    from the in-window figure and labelled ``PARTIAL_LABEL``; ``missing_terrain`` and
    ``invariant_failed`` block. A run-level ``extent_sufficient`` review setting is
    informational only.

Baseline gap (H7)
    Any published-versus-computed baseline difference is carried as a warning. A gap
    larger than ``BASELINE_GAP_THRESHOLD`` (the larger of $1.00/month and 1% of the
    published monthly charge) blocks adapter prices: the recorded areas, credits,
    accounts or tariff treatment then do not reproduce the public bill, so a computed
    change is not anchored to it. The threshold is a screening rule of this project,
    not a PWD rule.

Assessment date (H8)
    ``as_of_date`` normalizes ISO strings, dates and datetimes once. ``derive_as_of``
    takes an explicit date first, then dates recorded in the case; it never uses a
    hard-coded calendar date.
"""
from copy import deepcopy
from datetime import date, datetime
from decimal import Decimal

ROUTE_PRICED = ('complete_in_window', 'partial_upstream_unknown')
ROUTE_SEVERITY = ('complete_in_window', 'partial_upstream_unknown', 'missing_terrain', 'invariant_failed')
BASELINE_GAP_THRESHOLD = {'monthly_dollars': '1.00', 'fraction_of_published': '0.01',
    'rule': 'Block when |computed - published| monthly charge exceeds the larger value',
    'basis': 'Project screening threshold for rounding-level differences; not a PWD rule'}
PRICED_BY = 'assessment_policy._economics (single assessment ledger, decision D7)'
EMPTY = {'type': 'GeometryCollection', 'geometries': []}


def as_of_date(value):
    """One normalization for every adapter: ISO text, ``date`` or ``datetime``."""
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    if isinstance(value, str) and value.strip():
        return date.fromisoformat(value.strip()[:10])
    raise ValueError('Assessment date (as_of) is required as an ISO date')


def derive_as_of(case, explicit=None):
    """(date, source): explicit first, then dates recorded in the saved case."""
    if explicit not in (None, ''):
        return as_of_date(explicit), 'explicit'
    for source, value in (('case.imagery_age_policy.as_of', (case.get('imagery_age_policy') or {}).get('as_of')),
                          ('case.baseline.bill_date', (case.get('baseline') or {}).get('bill_date'))):
        if value not in (None, ''):
            return as_of_date(value), source
    raise ValueError('Assessment date unknown: pass an explicit as_of (--as-of); no calendar default is assumed')


def route_gate(state, reason=None):
    """Policy treatment of one route state (D2)."""
    from drainage_core.management_estimates import PARTIAL_LABEL
    if state not in ROUTE_SEVERITY:
        state, reason = 'missing_terrain', reason or 'Route state not recorded; catchment completeness is unknown'
    blocked = [] if state in ROUTE_PRICED else [
        ('Routing invariant failed: ' if state == 'invariant_failed' else 'Catchment extent cannot be tested: ')
        + (reason or state)]
    return {'route_state': state, 'route_state_reason': reason,
            'partial_label': PARTIAL_LABEL if state == 'partial_upstream_unknown' else None,
            'blocked_reasons': blocked}


def catchment_route(catchment, invariants):
    """Route state of one research/integration catchment from its frozen extent fields."""
    from drainage_core.management_estimates import route_state
    state, reason = route_state({'invariants': invariants or {},
        **{k: (catchment or {}).get(k) for k in ('touches_window_edge', 'touches_nodata', 'extent_complete')}})
    return route_gate(state, reason)


def combine_routes(gates):
    """Worst state of several catchments; reasons are kept."""
    gates = list(gates)
    if not gates:
        return route_gate('missing_terrain', 'No modeled catchment to test')
    worst = max(gates, key=lambda g: ROUTE_SEVERITY.index(g['route_state']))
    out = deepcopy(worst)
    out['route_state_reason'] = '; '.join(dict.fromkeys(g['route_state_reason'] for g in gates
                                                        if g['route_state'] == worst['route_state'] and g['route_state_reason']))
    out['blocked_reasons'] = list(dict.fromkeys(r for g in gates for r in g['blocked_reasons']))
    return out


def run_route(run):
    """Route gate of an engineering (``estimate_system``) run."""
    return route_gate(run.get('route_state'), run.get('route_state_reason'))


def lineage_errors(lineage, case_hash, frozen_gis, owner):
    """Required lineage (H9): both keys must be present and match the priced inputs.

    ``case_sha256`` must be a non-empty hash of this exact case. ``gis_analysis_sha256``
    must be present and equal the frozen artifact's own ``analysis_sha256`` (both
    absent counts as a match only for an unhashed artifact, which is labelled).
    """
    lineage = lineage if isinstance(lineage, dict) else {}
    errors = []
    if not lineage.get('case_sha256'):
        errors.append(owner + ' lacks required case_sha256 lineage; it cannot be bound to this case')
    elif lineage['case_sha256'] != case_hash:
        errors.append(owner + ' belongs to different case inputs')
    if 'gis_analysis_sha256' not in lineage:
        errors.append(owner + ' lacks required gis_analysis_sha256 lineage')
    elif lineage['gis_analysis_sha256'] != (frozen_gis or {}).get('analysis_sha256'):
        errors.append(owner + ' belongs to a different frozen GIS artifact')
    return errors


def policy_gis(case, gis):
    """Frozen GIS with an observation measurement for ledger occupancy checks."""
    if (gis or {}).get('measurement'):
        return gis
    from drainage_core.geometry import measure
    return {**(gis or {}), 'measurement': measure(case)}


def _gap(bill, baseline):
    if not isinstance(bill, dict) or bill.get('monthly_total') is None or baseline.get('published_monthly_total') is None:
        return None
    from .billing import decimal, cents
    published = decimal(baseline['published_monthly_total'], 'published_monthly_total')
    computed = decimal(bill['monthly_total'])
    difference = cents(computed - published)
    limit = max(Decimal(BASELINE_GAP_THRESHOLD['monthly_dollars']),
                abs(published) * Decimal(BASELINE_GAP_THRESHOLD['fraction_of_published']))
    return {'published_monthly_total': float(published), 'computed_monthly_total': float(computed),
            'difference_monthly': float(difference), 'threshold_monthly': float(cents(limit)),
            'status': 'exceeds_threshold' if abs(difference) > limit else 'within_threshold'}


def baseline_gap(base, baseline):
    """Published-versus-computed check (H7); alternatives are checked separately."""
    if isinstance(base, dict) and isinstance(base.get('alternatives'), dict):
        rows = {name: _gap(bill, baseline) for name, bill in base['alternatives'].items()}
        rows = {k: v for k, v in rows.items() if v is not None}
        if not rows:
            return {'status': 'not_published', 'threshold': deepcopy(BASELINE_GAP_THRESHOLD)}
        within = [k for k, v in rows.items() if v['status'] == 'within_threshold']
        return {'status': 'within_threshold' if within else 'exceeds_threshold', 'alternatives': rows,
                'consistent_alternatives': within, 'threshold': deepcopy(BASELINE_GAP_THRESHOLD)}
    row = _gap(base, baseline)
    if row is None:
        return {'status': 'not_published', 'threshold': deepcopy(BASELINE_GAP_THRESHOLD)}
    return {**row, 'threshold': deepcopy(BASELINE_GAP_THRESHOLD)}


def ledger_context(case, gis, day, tariff):
    """Baseline, warnings and blocking errors from the single ledger (no new benefit)."""
    from .assessment_policy import _economics
    from .billing import UNDEVELOPED_UNKNOWN
    baseline = case.get('baseline') or {}
    errors, warnings = [], []
    try:
        economics = _economics(case, gis, [], day, tariff)
    except (ValueError, TypeError, KeyError, AttributeError) as exc:
        return {'baseline': None, 'errors': [str(exc)], 'warnings': [], 'gap': None, 'economics': None}
    base = economics.get('baseline')
    if base is None:
        errors.extend((economics.get('modeled') or {}).get('reasons') or ['Billing baseline unavailable'])
    if baseline.get('actual_bill_verified') is not True:
        warnings.append('Actual account bill, payer and special-rate enrollment are unverified.')
    gap = baseline_gap(base, baseline) if base is not None else None
    if gap and gap.get('difference_monthly'):
        warnings.append('Computed baseline differs from the published monthly charge by $'
                        + f"{gap['difference_monthly']:.2f}" + '/month.')
    if gap and gap['status'] == 'exceeds_threshold':
        detail = (f"${gap['difference_monthly']:.2f}/month (threshold ${gap['threshold_monthly']:.2f})"
                  if 'difference_monthly' in gap else 'for every undeveloped-status alternative')
        errors.append('Computed baseline differs from the published charge by ' + detail
                      + '; recorded areas, credits, accounts or tariff treatment do not reproduce the public bill')
    if isinstance(base, dict) and isinstance(base.get('allocation_status'), dict):
        warnings.append(base['allocation_status']['note'])
    check = economics.get('billed_area_check') or {}
    if check.get('warning'):
        warnings.append(check['warning'])
    if (economics.get('undeveloped_status') or {}).get('status') == 'unknown_alternatives':
        warnings.append(UNDEVELOPED_UNKNOWN)
    return {'baseline': deepcopy(base), 'errors': list(dict.fromkeys(errors)), 'warnings': list(dict.fromkeys(warnings)),
            'gap': gap, 'billed_area_check': deepcopy(economics.get('billed_area_check')),
            'undeveloped_status': deepcopy(economics.get('undeveloped_status'))}


def _money(s):
    out = {'status': s.get('status'), 'reasons': list(s.get('reasons') or []),
           'monthly_savings': s.get('gross_monthly_reduction'), 'annual_savings': s.get('gross_annual_reduction'),
           'bill': deepcopy(s.get('bill')), 'ledger': deepcopy(s.get('ledger')),
           'ledger_assumptions': list(s.get('assumptions') or []), 'priced_by': PRICED_BY}
    if out['status'] != 'calculated':
        out.update(monthly_savings=None, annual_savings=None, bill=None, ledger=None)
    return out


def price_benefit(case, gis, day, tariff, benefit):
    """Price one hypothetical modeled benefit through the single assessment ledger.

    ``benefit``: ``id``, ``category``, ``area_sqft`` (credited area, may be a weighted
    fraction of the possible geometry), ``geometry`` (the whole possible region, for
    overlap checks; ``None`` only for unlocated unit sensitivities) and ``evidence``
    (assumed prerequisites; known-false facts are vetoed by the ledger). Other saved
    case benefits are not credited: each system is one alternative.
    """
    from .assessment_policy import _economics
    economics = _economics(case, gis, [], day, tariff, hypothetical=[benefit])
    s = economics.get('modeled') or {'status': 'blocked', 'reasons': ['Ledger scenario unavailable']}
    out = _money(s)
    if isinstance(s.get('alternatives'), dict):
        out.update(status='unverified_alternatives',
                   alternatives={name: _money(value or {}) for name, value in s['alternatives'].items()})
    return out


def annual_values(row):
    """Calculated annual changes of a priced row, including D6 alternatives."""
    if row.get('status') == 'calculated' and row.get('annual_savings') is not None:
        return [row['annual_savings']]
    if row.get('status') == 'unverified_alternatives':
        return [a['annual_savings'] for a in (row.get('alternatives') or {}).values()
                if a.get('status') == 'calculated' and a.get('annual_savings') is not None]
    return []


def value_range(rows, key='annual_savings'):
    values = []
    for row in rows:
        if key == 'annual_savings':
            values.extend(annual_values(row))
        elif row.get('status') in ('calculated', 'unverified_alternatives') and row.get(key) is not None:
            values.append(row[key])
    return [min(values), max(values)] if values else None
