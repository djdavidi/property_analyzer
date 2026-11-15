"""Saved-record reminders, never public monitoring or inferred award dates."""
from copy import deepcopy
from datetime import date, datetime
from zoneinfo import ZoneInfo

DEFAULT_LEAD_DAYS = 90  # Product reminder preference, not a legal filing deadline.
STATUSES = {'awarded', 'renewed', 'terminated', 'expired', 'applied', 'denied', 'unknown'}


def today():
    return datetime.now(ZoneInfo('America/New_York')).date()


def parse_date(value):
    if value in (None, ''):
        return None
    if not isinstance(value, str):
        raise ValueError('Evidence dates must be ISO YYYY-MM-DD strings')
    parsed = date.fromisoformat(value)
    if parsed.isoformat() != value:
        raise ValueError('Evidence dates must use YYYY-MM-DD')
    return parsed


def credit_renewals(history, as_of=None, lead_days=DEFAULT_LEAD_DAYS):
    """Reconcile explicit event chains; competing unsuperseded records stay disputed.

    Expiry/deadline is inclusive. A renewal does not erase earlier evidence or
    imply a new expiration. No period is derived from a program's maximum term.
    """
    current = parse_date(as_of) if isinstance(as_of, str) else as_of or today()
    if isinstance(lead_days, bool) or not isinstance(lead_days, int) or not 0 <= lead_days <= 730:
        raise ValueError('Reminder lead_days must be an integer between 0 and 730')
    grouped = {}
    ids = set()
    for record in history:
        if not record.get('id') or record['id'] in ids:
            raise ValueError('Credit history requires unique event IDs')
        ids.add(record['id'])
        grouped.setdefault(record.get('credit_id') or record['id'], []).append(record)
    result = []
    for credit_id, events in grouped.items():
        superseded = {x.get('supersedes') for x in events if x.get('supersedes')}
        leaves = [x for x in events if x['id'] not in superseded]
        row = {'credit_id':credit_id, 'id':leaves[-1]['id'] if leaves else events[-1]['id'],
               'category':events[-1].get('category','unknown'), 'deadline':None,
               'days_remaining':None, 'missing':[], 'warnings':[],
               'history_ids':[x['id'] for x in events]}
        contradictions = []
        if len(leaves) != 1:
            contradictions.append('Competing credit records need explicit supersedes reconciliation')
        # Ensure supersedes only refers to an earlier event for this credit.
        seen = set()
        for event in events:
            if event.get('supersedes') and event['supersedes'] not in seen:
                contradictions.append('Invalid or forward supersedes reference')
            seen.add(event['id'])
        event = leaves[-1] if leaves else events[-1]
        state = event.get('status', event.get('event','unknown'))
        if state not in STATUSES:
            contradictions.append('Unknown history status')
        dates = {}
        for key in ('effective_from','expires_on','renewal_due','terminated_on'):
            try:
                dates[key] = parse_date(event.get(key))
            except (ValueError, TypeError):
                dates[key] = None
                contradictions.append('Invalid '+key)
        if dates['effective_from'] and dates['expires_on'] and dates['expires_on'] < dates['effective_from']:
            contradictions.append('Expiry precedes effective date')
        if dates['effective_from'] and dates['terminated_on'] and dates['terminated_on'] < dates['effective_from']:
            contradictions.append('Termination precedes effective date')
        if event.get('source_contradiction'):
            contradictions.append('Source records contradict one another')
        if contradictions:
            row.update(status='contradictory', warnings=list(dict.fromkeys(contradictions)))
        elif state == 'terminated' and dates['terminated_on'] and dates['terminated_on'] <= current:
            row['status'] = 'terminated'
        elif state in ('applied','denied','unknown','expired'):
            row['status'] = 'not_awarded' if state in ('applied','denied') else 'unknown_dates'
            row['warnings'].append('An application, denial or unexplained expired flag does not establish an award or refund')
        elif state == 'terminated':
            row['status'] = 'unknown_dates'
            row['missing'].append('effective termination date')
        else:
            deadline = dates['renewal_due'] or dates['expires_on']
            if not event.get('evidence_refs') and not event.get('source_url'):
                row['warnings'].append('Award/renewal supporting record is missing; recorded history is unverified')
            if dates['effective_from'] is None:
                row['missing'].append('effective_from')
            if not deadline:
                row['status'] = 'unknown_dates'
                row['missing'].append('renewal_due or expires_on')
            else:
                remaining = (deadline-current).days
                row.update(deadline=deadline.isoformat(), days_remaining=remaining,
                           status='overdue' if remaining < 0 else 'upcoming' if remaining <= lead_days else 'current')
                if dates['effective_from'] and dates['effective_from'] > current:
                    row['warnings'].append('Recorded award/renewal is not effective yet')
        result.append(row)
    return result


def history_assessment(case, as_of=None):
    from .assessment_workflow import credit_observations
    assessment = case.get('assessment') or {}
    lead = assessment.get('renewal_lead_days', DEFAULT_LEAD_DAYS)
    history = assessment.get('credit_history', [])
    renewals = credit_renewals(history, as_of, lead)
    observations=credit_observations(case)
    for index,observation in enumerate(observations):
        if observation['unknown_dates']:
            renewals.append({'id':'public-expired-'+str(index),'credit_id':'Unexplained public Expired flag',
                'category':'unknown','status':'unknown_dates','deadline':None,'days_remaining':None,
                'missing':observation['missing_evidence'],'warnings':[observation['interpretation']],
                'source_url':observation['source_url'],'source_sha256':observation['source_sha256'],
                'retrieved_at':observation['retrieved_at']})
    return {'category':'prior_credits', 'label':'Prior credits and renewals',
            'status':'recorded_history' if history else 'missing_evidence',
            'missing':[] if history else ['Award letters, credited areas and effective/expiry/renewal records'],
            'records':deepcopy(history), 'renewals':renewals,'public_observations':observations,
            'reminder_lead_days':lead, 'reminder_basis':'Configurable product reminder; not a legal deadline'}
