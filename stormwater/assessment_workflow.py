"""Append-only assessment observations/reviews; no acquisition on ordinary case reads."""
from copy import deepcopy
from hashlib import sha256
import json
import uuid

from drainage_core.evidence import validate_references,now

CATEGORIES={'green_roof','permeable_pavement','direct_discharge','industrial_npdes'}


def _digest(value):
    return sha256(json.dumps(value,sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest()


def ensure_assessment(case):
    a=case.setdefault('assessment',{})
    a.setdefault('schema_version',1)
    for key in ('records','observations','credit_history','snapshots','attachments','reviews','source_status'):
        a.setdefault(key,[])
    a.setdefault('identifiers',{})
    return a


def credit_observations(case):
    """Readable PWD public flags, without inferring an award, lapse or deadline.

    Summaries retain each distinct saved source snapshot. Only named public flag
    fields are copied; account names, account identifiers and raw billing records
    are deliberately absent. Missing flags and dates stay unknown.
    """
    observations=[]
    for item in (case.get('assessment') or {}).get('observations',[]):
        if item.get('provider')!='PWD account/credit public record': continue
        raw=item.get('raw_record') or {}
        pending=raw.get('Pending',raw.get('pending')) if isinstance(raw,dict) else None
        observations.append((pending,item))
    # Baseline acquired cases already carry pending flags. Preserve them when no
    # assessment acquisition has been run; this does not initiate a public read.
    if not observations and 'pending' in case:
        source=next((s for s in reversed(case.get('sources',[]))
                     if '/PwdWebApi/api/v1/parcel/' in str(s.get('url','')) and '/details' in str(s.get('url',''))),{})
        observations.append((case['pending'],{'url':source.get('url'),
            'retrieved_at':source.get('retrieved_at'),'source_sha256':source.get('sha256')}))
    summaries=[];seen=set()
    for pending,source in observations:
        flags={str(k).lower():v for k,v in pending.items()} if isinstance(pending,dict) else {}
        summary={'provider':'PWD account/credit public record',
                 'source_url':source.get('url'),'retrieved_at':source.get('retrieved_at'),
                 'source_sha256':source.get('source_sha256'),
                 'effective_date':None,'expiry_date':None,
                 'interpretation':'Public flags are observations only. They do not establish an earlier award, lapse, denial, renewal deadline or refund entitlement.'}
        missing=[]
        for name in ('credits','expired','appeals'):
            value=flags.get(name)
            if isinstance(value,bool): value=int(value)
            elif isinstance(value,str) and value.strip().isdigit(): value=int(value.strip())
            if not isinstance(value,int) or value<0:
                value=None;missing.append('Public '+name+' flag meaning/value')
            summary[name+'_flag']=value
        expired=summary['expired_flag']
        summary['unknown_dates']=expired is not None and expired>0
        if summary['unknown_dates']:
            missing.extend(['Meaning and affected credit of public Expired flag',
                            'Award record and effective/expiry dates','Renewal or termination outcome'])
        else: missing.append('Complete award/credit history and supporting dates')
        summary['missing_evidence']=missing
        identity=_digest(summary)
        if identity not in seen:
            summaries.append(summary);seen.add(identity)
    return summaries


def review_record(case,record,reason,at=None):
    if not isinstance(reason,str) or not reason.strip(): raise ValueError('An evidence/review reason is required')
    result=deepcopy(case);a=ensure_assessment(result);entry=deepcopy(record)
    if entry.get('category') not in CATEGORIES: raise ValueError('Unsupported assessment category')
    if entry.get('decision') not in ('candidate','confirmed','rejected'): raise ValueError('Invalid candidate decision')
    if entry.get('basis') not in ('public_candidate','manual','documented','modeled'): raise ValueError('Invalid evidence basis')
    if not entry.get('id'): entry['id']=str(uuid.uuid4())
    if not isinstance(entry.get('facts',{}),dict): raise ValueError('Facts must be an object')
    previous=next((r for r in a['records'] if r['id']==entry['id']),None)
    # Source lineage stays associated even when the candidate is corrected.
    if previous:
        for key in ('source','raw_record','public_geometry','public_geometry_role'):
            if key not in entry and key in previous: entry[key]=deepcopy(previous[key])
    a['reviews'].append({'id':str(uuid.uuid4()),'at':at or now(),'reason':reason.strip(),
                         'record_id':entry['id'],'before':deepcopy(previous),'after':deepcopy(entry),
                         'before_sha256':_digest(previous) if previous else None,'after_sha256':_digest(entry)})
    a['records']=[r for r in a['records'] if r['id']!=entry['id']]+[entry]
    validate_references(a)
    return result


def gather(case,cache,refresh=True):
    from .assessment_sources import discover
    result=deepcopy(case);a=ensure_assessment(result)
    discovered=discover(result,cache,refresh)
    old={r['id'] for r in a['records']}
    # Rerun never replaces a reviewed candidate or erases a disappeared source record.
    a['records'].extend(deepcopy(r) for r in discovered['records'] if r['id'] not in old)
    for observation in discovered['observations']:
        observation={**observation,'observed_at':now()}
        observation['sha256']=_digest(observation)
        a['observations'].append(observation)
    a['source_status']=deepcopy(discovered['source_status'])
    count=len(discovered['observations'])
    a['acquisition_runs']=a.get('acquisition_runs',[])+[{'at':now(),'source_status':deepcopy(discovered['source_status']),
                                                       'observation_sha256':[o['sha256'] for o in a['observations'][-count:]] if count else []}]
    existing={_digest(s) for s in result.get('sources',[])}
    result.setdefault('sources',[]).extend(deepcopy(s) for s in discovered['sources'] if _digest(s) not in existing)
    return result
