"""Provider-neutral contradictions to an existing physical receiving feature."""
import re


def installation_issues(properties,as_of=None):
    p={str(k).lower():v for k,v in properties.items()};issues=[]
    if p.get('installed') is False or p.get('existing_installation') is False:
        issues.append('Installation explicitly recorded false')
    if p.get('proposed_only') is True:issues.append('Proposed-only feature')
    for key in ('status','public_status','gsi_status','overallstatuscategory'):
        state=str(p.get(key) or '').lower()
        if re.search(r'propos|upcoming|design|planning|cancel|removed|decommission|not installed',state):
            issues.append('Nonexisting installation status: '+state)
    year=p.get('year_installed',p.get('public_year_installed'))
    if year not in (None,'',0,'0'):
        try:
            if isinstance(year,bool) or int(year)!=float(year):raise ValueError()
            if as_of and int(year)>int(str(as_of)[:4]):issues.append('Installation year is after observation date')
        except (TypeError,ValueError):issues.append('Invalid installation year')
    return list(dict.fromkeys(issues))
