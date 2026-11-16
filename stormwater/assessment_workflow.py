"""Append-only assessment observations/reviews; no acquisition on ordinary case reads."""
from copy import deepcopy
from hashlib import sha256
import json
import uuid

from drainage_core.evidence import validate_references,now
from .physical_reuse import normalize_numbers

CATEGORIES={'green_roof','permeable_pavement','direct_discharge','industrial_npdes'}
# Public source content of a record. Retrieval timestamps, snapshots and reviewer
# fields (decision, basis, evidence) are deliberately excluded.
SOURCE_FIELDS=('facts','public_geometry','raw_record','public_geometry_role')


def _digest(value):
    """Content hash in which JSON 1 and 1.0 are identical (browser round trips)."""
    normalized=normalize_numbers(value)
    return sha256(json.dumps(normalized,sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest()


def _unnormalized_digest(value):
    """Hash format recorded before number normalisation; used only to honour old comparisons."""
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
        if previous.get('source_update',{}).get('status')=='pending_review':
            entry['source_update']={**deepcopy(previous['source_update']),'status':'reviewed',
                'reason':reason.strip(),'reviewed_at':at or now()}
    a['reviews'].append({'id':str(uuid.uuid4()),'at':at or now(),'reason':reason.strip(),
                         'record_id':entry['id'],'before':deepcopy(previous),'after':deepcopy(entry),
                         'before_sha256':_digest(previous) if previous else None,'after_sha256':_digest(entry)})
    a['records']=[r for r in a['records'] if r['id']!=entry['id']]+[entry]
    validate_references(a)
    return result


def _source_content(record):
    return {key:deepcopy(record.get(key)) for key in SOURCE_FIELDS}


def _is_disappearance(update):
    """A not-returned flag. Older flags predate 'kind' and never carry a candidate."""
    if not isinstance(update,dict) or not update:
        return False
    if 'kind' in update:
        return update['kind']=='disappeared'
    return 'candidate' not in update


def _last_public_content(assessment,record,reviewed,incoming):
    """Last public source content seen for ``record``; never its reviewer-edited facts.

    Returns ``(content, origin)``. Records saved before ``public_snapshots`` existed
    are derived from their own history. ``(None, None)`` means no public version can
    be established, so the incoming record is staged for review rather than assumed
    unchanged.
    """
    saved=assessment.get('public_snapshots',{}).get(record['id'])
    if isinstance(saved,dict) and isinstance(saved.get('content'),dict):
        return saved['content'],saved.get('origin')
    update=record.get('source_update') or {}
    if isinstance(update.get('candidate'),dict):
        return _source_content(update['candidate']),'derived:source_update_candidate'
    history=[h for h in assessment.get('record_history',[])
             if h.get('record_id')==record['id'] and isinstance(h.get('incoming'),dict)]
    if history:
        return _source_content(history[-1]['incoming']),'derived:record_history'
    if record['id'] not in reviewed and record.get('basis')=='public_candidate':
        # Unreviewed public candidates are stored exactly as discovered.
        return _source_content(record),'derived:unreviewed_public_record'
    first=next((r for r in assessment.get('reviews',[]) if r.get('record_id')==record['id']),None)
    before=(first or {}).get('before')
    if isinstance(before,dict) and before.get('basis')=='public_candidate':
        # The record as discovered, before any reviewer edit.
        return _source_content(before),'derived:first_review_before'
    raw=record.get('raw_record')
    lineage=('raw_record','public_geometry','public_geometry_role')
    if isinstance(raw,dict) and raw and all(_digest(record.get(k))==_digest(incoming.get(k)) for k in lineage):
        # Identical original source row and geometry: public facts derive from it.
        return {**_source_content(record),'facts':deepcopy(incoming.get('facts'))},'derived:raw_record_match'
    return None,None


def _remember_public(assessment,record_id,content,origin):
    snapshots=assessment.setdefault('public_snapshots',{})
    digest=_digest(content)
    if snapshots.get(record_id,{}).get('sha256')==digest:
        return
    snapshots[record_id]={'sha256':digest,'content':deepcopy(content),'observed_at':now(),'origin':origin}


def _clear_disappearance(assessment,record):
    """An identical record returned: end the disappearance episode, keeping its history."""
    update=record.get('source_update')
    if not _is_disappearance(update):
        return
    assessment.setdefault('record_history',[]).append({'at':now(),'record_id':record['id'],
        'event':'returned_unchanged','before':deepcopy(record)})
    if isinstance(update.get('previous'),dict):
        record['source_update']=deepcopy(update['previous'])
    else:
        del record['source_update']


def _merge_incoming(assessment,previous,incoming,reviewed):
    """Compare one public record with the last *public* content, not reviewer facts."""
    content=_source_content(incoming)
    if previous is None:
        assessment['records'].append(deepcopy(incoming))
        _remember_public(assessment,incoming['id'],content,'source')
        return
    known,origin=_last_public_content(assessment,previous,reviewed,incoming)
    if known is not None and _digest(known)==_digest(content):
        _remember_public(assessment,incoming['id'],known,origin)
        _clear_disappearance(assessment,previous)
        return
    assessment.setdefault('record_history',[]).append({'at':now(),'record_id':incoming['id'],
        'before':deepcopy(previous),'incoming':deepcopy(incoming)})
    _remember_public(assessment,incoming['id'],content,'source')
    unreviewed=previous['id'] not in reviewed
    if unreviewed and previous.get('decision')=='candidate' and previous.get('basis')=='public_candidate':
        records=assessment['records']
        records[records.index(previous)]=deepcopy(incoming)
    else:
        previous['source_update']={'status':'pending_review','kind':'changed','candidate':deepcopy(incoming),
            'observed_at':now(),'reason':'Public source changed; retained reviewed facts require reconciliation'}


def _flag_disappearance(record):
    update=record.get('source_update') or {}
    # A staged update keeps its candidate, and a disappearance already flagged or
    # reviewed is not re-staged on every run while the record stays absent.
    if update.get('status')=='pending_review' or _is_disappearance(update):
        return
    flag={'status':'pending_review','kind':'disappeared','observed_at':now(),
          'reason':'Not returned by a completed source query; disappearance is not proof of removal or zero area'}
    if update:
        flag['previous']=deepcopy(update)
    record['source_update']=flag


def _retained_by_review(assessment,candidate,baseline):
    """True when a reviewer already kept ``baseline`` against this same public candidate."""
    wanted=_digest(candidate)
    kept=_digest(baseline)
    for review in assessment.get('baseline_reviews',[]):
        comparison=review.get('comparison') or {}
        reviewed=review.get('candidate_sha256') or _digest(comparison.get('candidate'))
        if review.get('accepted') is False and reviewed==wanted and _digest(review.get('after'))==kept:
            return True
    return False


def gather(case,cache,refresh=True):
    """Explicit public-record rerun; reviewed facts and review history are kept.

    Incoming records are compared with the last *public* content seen for each
    record (``assessment.public_snapshots``), never with reviewer-edited facts.
    A changed source is staged for review once. A record absent from a completed
    query is flagged once, and the flag ends when the identical record returns.
    A public baseline candidate already retained by review is not staged again.
    """
    from .assessment_sources import discover
    result=deepcopy(case);a=ensure_assessment(result)
    discovered=discover(result,cache,refresh)
    old={r['id']:r for r in a['records']};reviewed={r['record_id'] for r in a.get('reviews',[]) if r.get('record_id')}
    for incoming in discovered['records']:
        _merge_incoming(a,old.get(incoming['id']),incoming,reviewed)
    present={r['id'] for r in discovered['records']}
    complete_urls={s.get('url') for s in discovered['source_status'] if s.get('status') in ('retrieved','reused_recent_record')}
    for previous in a['records']:
        if previous['id'] not in present and (previous.get('source') or {}).get('url') in complete_urls:
            _flag_disappearance(previous)
    for observation in discovered['observations']:
        observation={**observation,'observed_at':now()}
        observation['sha256']=_digest(observation)
        a['observations'].append(observation)
        if observation.get('provider')=='PWD account/credit public record':
            from .acquisition import normalize_billing
            baseline=normalize_billing(observation.get('raw_record') or {})
            keys=('ga_sqft','ia_sqft','existing_ga_credit_sqft','existing_ia_credit_sqft',
                  'existing_iar_sqft','npdes_fraction','accounts','property_type','bill_date','published_monthly_total')
            changes=[k for k in keys if (result.get('baseline') or {}).get(k)!=baseline.get(k)]
            if changes and _retained_by_review(a,baseline,result.get('baseline')):
                # Reviewed already: this public candidate was explicitly not adopted.
                changes=[]
            if changes:
                a['baseline_refresh']={'status':'pending_review','candidate':baseline,'fields_changed':changes,
                    'retained_baseline_sha256':_digest(result.get('baseline')),
                    'source_observation_sha256':observation['sha256'],'observed_at':observation['observed_at'],
                    'reason':'Public baseline differs; old invoice/manual facts retained, savings blocked until reviewed'}
    a['source_status']=deepcopy(discovered['source_status'])
    count=len(discovered['observations'])
    a['acquisition_runs']=a.get('acquisition_runs',[])+[{'at':now(),'source_status':deepcopy(discovered['source_status']),
                                                       'observation_sha256':[o['sha256'] for o in a['observations'][-count:]] if count else []}]
    existing={_digest(s) for s in result.get('sources',[])}
    result.setdefault('sources',[]).extend(deepcopy(s) for s in discovered['sources'] if _digest(s) not in existing)
    from .soil_sources import acquire as acquire_soils
    return acquire_soils(result,cache,refresh=refresh)


def reconcile_baseline(case,reason,accept):
    if not isinstance(reason,str) or not reason.strip() or not isinstance(accept,bool):
        raise ValueError('Baseline review needs an explanation and explicit choice')
    result=deepcopy(case);a=ensure_assessment(result);pending=a.get('baseline_refresh',{})
    if pending.get('status')!='pending_review':raise ValueError('No pending public baseline change')
    current=result.get('baseline')
    # Comparisons recorded before number normalisation remain reviewable.
    if pending.get('retained_baseline_sha256') not in (_digest(current),_unnormalized_digest(current)):
        raise ValueError('Baseline changed since public comparison; review current source again')
    if accept:
        candidate=pending['candidate']
        if candidate.get('ga_sqft') is None or candidate.get('ia_sqft') is None:
            raise ValueError('Incomplete public areas cannot replace the baseline')
        result['baseline']=deepcopy(candidate)
    a.setdefault('baseline_reviews',[]).append({'at':now(),'reason':reason.strip(),'accepted':accept,
        'before':deepcopy(case.get('baseline')),'after':deepcopy(result.get('baseline')),'comparison':deepcopy(pending),
        'candidate_sha256':_digest(pending.get('candidate'))})
    a['baseline_refresh']={**pending,'status':'accepted' if accept else 'retained_by_review','reason':reason.strip()}
    return result
