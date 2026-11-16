"""Provider-neutral, frozen source-age checks for satellite/aerial imagery."""
from datetime import date
import re


def age_policy(as_of):
    day = date.fromisoformat(as_of[:10])
    try:
        cutoff = day.replace(year=day.year - 3)
    except ValueError:  # Leap-day anniversary.
        cutoff = day.replace(year=day.year - 3, day=28)
    return {'maximum_years': 3, 'as_of': day.isoformat(), 'cutoff': cutoff.isoformat(),
            'unknown_dates': 'excluded', 'year_only_dates': 'January 1 conservative bound',
            'scope': 'Satellite/aerial imagery only, including cached fallback images; other datasets retain their own validity rules'}


def freshness(source, policy):
    """Retrieval/review timestamps never substitute for a capture/observation date.

    A year-only vintage is accepted only if its earliest possible day passes.
    Invalid explicit dates do not fall back to a more convenient vintage.
    """
    value = source.get('acquisition_date') or source.get('capture_date') or source.get('observation_date')
    basis = 'capture/observation date'
    if not value:
        value = source.get('source_vintage') or source.get('service_vintage')
        basis = 'source year; conservative January 1 bound'
    try:
        text = str(value)
        if re.fullmatch(r'\d{4}', text):
            earliest = date(int(text), 1, 1)
        else:
            earliest = date.fromisoformat(text[:10])
    except (TypeError, ValueError):
        return {'eligible': False, 'status': 'unknown_capture_date', 'date_basis': basis}
    as_of = date.fromisoformat(policy['as_of'])
    # Recompute the cutoff instead of trusting a possibly stale serialized value.
    cutoff = date.fromisoformat(age_policy(policy['as_of'])['cutoff'])
    status = 'future_capture_date' if earliest > as_of else 'too_old' if earliest < cutoff else 'within_age_limit'
    return {'eligible': status == 'within_age_limit', 'status': status,
            'earliest_capture_date': earliest.isoformat(), 'date_basis': basis,
            'as_of': as_of.isoformat(), 'cutoff': cutoff.isoformat()}
