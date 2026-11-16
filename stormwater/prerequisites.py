"""Known-false credit prerequisites shared by every alternative pricing path.

A modeled alternative may *assume* an unknown prerequisite, labelled as such. It
may never override a fact recorded as false. Account standing is an account/
parcel fact, not a property of one system: tariff 2026-09-01 section 4.5(a)(1)
("Accounts ... must be current to be eligible for credits") and manual sections
4.2 and 4.6.3. A false value recorded anywhere in the case therefore vetoes every
credit alternative (documented, modeled, research, catchment, canopy, permit).
Appeal/measurement-only scenarios are not credits and are not vetoed here.
"""
# Facts that describe the account or parcel rather than one system.
PARCEL_FACTS = ('account_current',)


def _false(value):
    return value is not None and value is not True


def baseline_vetoes(baseline):
    """Known-false account facts recorded on the billing baseline itself."""
    baseline = baseline or {}
    return ['Known failed prerequisite: ' + key + ' (billing baseline)'
            for key in PARCEL_FACTS if key in baseline and _false(baseline.get(key))]


def case_vetoes(case):
    """Reasons a known-false parcel/account prerequisite blocks all credit dollars."""
    from drainage_core.geometry import effective_features
    reasons = baseline_vetoes(case.get('baseline'))
    assessment = case.get('assessment') or {}
    for record in assessment.get('records', []) + assessment.get('existing_credit_allocations', []):
        facts = record.get('facts') or {}
        for key in PARCEL_FACTS:
            if _false(facts.get(key)):
                reasons.append('Known failed prerequisite: ' + key + ' (record ' + str(record.get('id')) + ')')
    benefits = list(case.get('benefits') or [])
    benefits.extend(f['properties']['benefit'] for f in effective_features(case)
                    if f.get('properties', {}).get('layer') == 'benefit' and isinstance(f['properties'].get('benefit'), dict))
    for benefit in benefits:
        evidence = benefit.get('evidence') or {}
        for key in PARCEL_FACTS:
            if _false(evidence.get(key)):
                reasons.append('Known failed prerequisite: ' + key + ' (benefit ' + str(benefit.get('id')) + ')')
    return list(dict.fromkeys(reasons))


def record_vetoes(record, required=()):
    """Reasons one source record cannot support any alternative for its system."""
    facts = record.get('facts') or {}
    reasons = []
    if record.get('decision') == 'rejected':
        reasons.append('Record ' + str(record.get('id')) + ' was manually rejected')
    for key in required:
        if _false(facts.get(key)):
            reasons.append('Known failed prerequisite: ' + key + ' (record ' + str(record.get('id')) + ')')
    from drainage_core.installation import installation_issues
    reasons.extend(installation_issues(facts))
    return list(dict.fromkeys(reasons))
