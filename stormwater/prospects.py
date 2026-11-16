"""Records-only Philadelphia lead screening. Never invokes imagery or site analysis."""
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date,datetime
from hashlib import sha256
from html import escape
from pathlib import Path
import argparse
import csv
import io
import json
import math
import re
import time
import uuid
from threading import Lock
from copy import deepcopy
from contextlib import contextmanager
import os
from zoneinfo import ZoneInfo

from shapely.geometry import shape
from shapely.strtree import STRtree
from drainage_core.sources import Cache, SourceError, arcgis_features, canonical, now
from .record_cache import SharedCache

ROOT = Path(__file__).resolve().parents[1]
SYSTEMS = 'https://services.arcgis.com/fLeGjb7u4uXqeF9q/ArcGIS/rest/services/GSI_SMP_TYPES/FeatureServer/0'
PARCELS = 'https://services.arcgis.com/fLeGjb7u4uXqeF9q/ArcGIS/rest/services/PWD_PARCELS/FeatureServer/0'
BILLING = 'https://stormwater.phila.gov/PwdWebApi/api/v1/parcel'
VERSION = 'philadelphia-prospect-v2'
GROUPS = {
    'no_area_credit': 'Mapped systems · no recorded area credits',
    'partial_area_credit': 'Mapped systems · partial recorded area credits',
    'substantial_area_credit': 'Substantial recorded credits · check remaining opportunity',
}
# Anchored public-body names, including common truncations in PWD owner fields.
# A private business containing "state", "city" or "Philadelphia" alone is not excluded.
GOVERNMENT = (
    r'^(?:THE )?CITY (?:OF |& COUNTY)', r'^(?:THE )?COUNTY OF ',
    r'^COMMONWEALTH', r'^(?:THE )?(?:UNITED STATES|U S)(?: OF AMERICA| GOVERNMENT| POST| ARMY| NAVY| AIR| DEPT| DEPARTMENT| GENERAL| GSA| VETERANS|$)',
    r'^(?:THE )?STATE OF ', r'^(?:THE )?(?:PHILADELPHIA|PHILA) (?:HOUSING|REDEVELOP|AUTH|SCHOOL|PARKING|MUNICIPAL)',
    r'^(?:THE )?SCHOOL DIST', r'^(?:THE )?BOARD OF (?:EDUCATION|PUBLIC)',
    r'^PHILADELPHIA (?:CITY|COUNTY|REDEV|WATER|HOUSING DEV)', r'^PHILA(?:DELPHIA)? CONV',
    r'^SOUTHEASTERN (?:PENNSYLVANIA|PA|PENNA)', r'^SEPTA\b', r'^DELAWARE RIVER (?:PORT|WATERFRONT|JOINT)',
    r'^(?:PENNSYLVANIA|PENNA|PA) (?:DEPT|DEPARTMENT|TURNPIKE|CONVENTION|CONV CTR|HOU?SING|INDUSTRIAL DEV|STATE)',
    r'^(?:PENNDOT|PENN DOT)\b', r'^(?:NATIONAL PARK SERVICE|UNITED STATES POSTAL|US POSTAL|POSTMASTER GENERAL)',
    r'^(?:FEDERAL (?:GOVERNMENT|AVIATION|BUREAU|HIGHWAY|EMERGENCY|RESERVE)|GENERAL SERVICES ADMIN|DEFENSE LOGISTICS|US ARMY|U S A GOVERNMENT)',
    r'^(?:COMMUNITY COLLEGE OF PHILADELPHIA|PHILADELPHIA COMMUNITY COLLEGE)',
    r'^(?:FREE LIBRARY OF PHILA|POST OFFICE DEPT|U S GOV|US GOV|U S A$)',
    r'^PHILA (?:HSG|REDEV)',
    r'^FAIRMOUNT PARK COMM', r'^PHILADELPHIA REGIONAL POR',
)
REVIEW_OWNER = (r'\bAUTHORITY\b', r'^TEMPLE UNIV', r'^PENNSYLVANIA STATE UNIV', r'^PENN STATE', r'^UNKNOWN\b', r'^OWNER OF RECORD\b')


class CappedCache:
    """Hard cap on new requests; cached evidence remains usable without a request."""
    def __init__(self, cache, max_requests=80, max_seconds=300,cancel=None,refresh_stale=False):
        self.cache=cache;self.max_requests=max_requests;self.requests=0
        self.deadline=time.monotonic()+max_seconds;self.lock=Lock()
        self.cancel=cancel
        self.refresh_stale=refresh_stale

    def fetch_json(self,url,refresh=False,metadata=None):
        if self.cancel and self.cancel.is_set():raise SourceError('Scan cancelled; no further request made')
        saved=self.cache._read(url) if not refresh else None
        if saved is not None:
            age=freshness(saved[1],datetime.now(ZoneInfo('America/New_York')).date().isoformat(),30 if '/parcel/' in url else 90)
            if not self.refresh_stale or age['status']=='fresh':
                data=json.loads(saved[0])
                if isinstance(data,dict) and data.get('error'):raise SourceError(str(data['error']))
                return {'data':data,'provenance':saved[1]}
            refresh=True
        with self.lock:
            if self.requests>=self.max_requests or time.monotonic()>=self.deadline:
                raise SourceError('Acquisition budget reached; no further network request made')
            self.requests+=1
        return self.cache.fetch_json(url,refresh,metadata)


@contextmanager
def scan_lock(root):
    """One writer per scan folder, across local server and CLI processes."""
    root=Path(root);root.mkdir(parents=True,exist_ok=True);path=root/'scan.lock'
    try:fd=os.open(path,os.O_CREAT|os.O_EXCL|os.O_WRONLY)
    except FileExistsError:raise ValueError('A scan already owns this folder. Wait for it to finish or inspect scan.lock after a crash.')
    try:
        with os.fdopen(fd,'w') as stream:stream.write(str(os.getpid()))
        yield
    finally:path.unlink(missing_ok=True)


def freshness(source,as_of,max_days=30):
    captured=source.get('retrieved_at')
    try:
        instant=datetime.fromisoformat(captured.replace('Z','+00:00'))
        local=instant.astimezone(ZoneInfo('America/New_York')) if instant.tzinfo else instant
        age=(date.fromisoformat(as_of)-local.date()).days
    except (AttributeError,ValueError,TypeError):return {'status':'unknown','age_days':None,'max_age_days':max_days}
    return {'status':'future_date' if age<0 else 'stale' if age>max_days else 'fresh','age_days':age,'max_age_days':max_days}


def number(value):
    if value is None or isinstance(value, bool):
        return None
    try:
        result = float(value)
        return result if math.isfinite(result) and result >= 0 else None
    except (ValueError, TypeError):
        return None


def owner_status(*owners):
    names = [' '.join(re.sub(r'[^A-Z0-9 ]', ' ', str(s).upper()).split()) for s in owners if s and str(s).strip()]
    if not names:
        return {'status': 'unknown', 'reason': 'Owner missing from public record'}
    for name in names:
        if any(re.search(pattern, name) for pattern in GOVERNMENT):
            return {'status': 'government', 'reason': 'Public-body owner name: '+name}
    if any(re.search(pattern, name) for name in names for pattern in REVIEW_OWNER):
        return {'status': 'review', 'reason': 'Public-body/ownership classification requires review'}
    return {'status': 'nongovernment_record', 'reason': 'Named public-record owner; no government-name signal. Beneficial ownership is unverified.'}


def props(feature):
    return {str(k).lower(): v for k, v in feature.get('properties', {}).items()}


def system_status(p, as_of):
    if not str(p.get('project_type', '')).lower().startswith('private'):
        return 'public_project'
    state = str(p.get('status') or '').lower()
    if any(x in state for x in ('design', 'upcoming', 'construction', 'propos', 'plan')):
        return 'not_completed'
    year = number(p.get('year_installed'))
    if 'complete' in state or year is not None and 1900 <= year <= int(as_of[:4]):
        return 'mapped_existing'
    return 'installation_unknown'


def read_inventory(cache, refresh=False):
    return arcgis_features(SYSTEMS, cache, {'outSR': '2272'}, refresh, page_size=2000, max_pages=25)


def find_parcels(systems, cache, refresh=False, workers=4, progress=None):
    """Batch representative interior points; exact overlap subsequently validates matches.

    This fast join can miss other parcels crossed by a footprint. It never represents
    a system's managed area or proves parcel credit allocation.
    """
    points = []
    for feature in systems:
        geometry = shape(feature['geometry'])
        parts = list(geometry.geoms) if geometry.geom_type == 'MultiPolygon' else [geometry]
        for part in parts:
            pt = part.representative_point()
            points.append([round(pt.x, 3), round(pt.y, 3)])
    points = sorted({tuple(p) for p in points})
    chunks = [points[i:i+16] for i in range(0, len(points), 16)]
    output, sources, errors = {}, [], []

    def fetch(chunk):
        return arcgis_features(PARCELS, cache, {
            'geometry': json.dumps({'points': chunk, 'spatialReference': {'wkid': 2272}}, separators=(',', ':')),
            'geometryType': 'esriGeometryMultipoint', 'inSR': '2272', 'outSR': '2272',
            'spatialRel': 'esriSpatialRelIntersects',
            'outFields': 'parcelid,address,owner1,owner2,bldg_code,bldg_desc,brt_id,num_brt,num_accounts,gross_area',
        }, refresh, page_size=2000, max_pages=5)

    with ThreadPoolExecutor(max_workers=workers) as executor:
        tasks = {executor.submit(fetch, chunk): i for i, chunk in enumerate(chunks)}
        for done, task in enumerate(as_completed(tasks), 1):
            try:
                data = task.result()
                sources.extend(data['sources'])
                for feature in data['features']:
                    output[str(props(feature)['parcelid'])] = feature
            except Exception as exc:
                errors.append({'stage': 'parcel_query', 'chunk': tasks[task], 'error': str(exc)})
            if progress:
                progress(stage='parcel_matching', completed=done, total=len(chunks))
    return list(output.values()), sources, errors


def match_systems(systems, parcels):
    usable, shapes, errors = [], [], []
    for feature in parcels:
        try:
            g = shape(feature['geometry'])
            if not g.is_valid or g.area <= 0:
                raise ValueError('Invalid parcel geometry')
            usable.append(feature)
            shapes.append(g)
        except Exception as exc:
            errors.append({'stage': 'parcel_geometry', 'parcel_id': props(feature).get('parcelid'), 'error': str(exc)})
    tree = STRtree(shapes)
    matches, held = {}, []
    for feature in systems:
        p = props(feature)
        try:
            g = shape(feature['geometry'])
            if not g.is_valid or g.area <= 0:
                raise ValueError('Invalid system geometry')
            overlaps = [(int(i), g.intersection(shapes[int(i)]).area/g.area) for i in tree.query(g)]
            overlaps = sorted((x for x in overlaps if x[1] > .01), key=lambda x: -x[1])
            if not overlaps or overlaps[0][1] < .8 or len(overlaps) > 1 and overlaps[1][1] > .2:
                held.append({'system_id': p.get('gsi_system_id'), 'reason': 'No dominant parcel overlap',
                             'candidate_parcels': [{'parcel_id': props(usable[i]).get('parcelid'), 'footprint_overlap_fraction': round(f, 4)} for i, f in overlaps]})
                continue
            i, overlap = overlaps[0]
            parcel = usable[i]
            pid = str(props(parcel)['parcelid'])
            item = matches.setdefault(pid, {'parcel': parcel, 'systems': []})
            item['systems'].append({'system_id': str(p.get('gsi_system_id')), 'objectid': p.get('objectid'),
                'type': p.get('gsi_system_type'), 'project_number': p.get('project_number'),
                'project_type': p.get('project_type'), 'year_installed': p.get('year_installed'),
                'status': p.get('status'), 'footprint_overlap_fraction': round(overlap, 6)})
        except Exception as exc:
            errors.append({'stage': 'system_geometry', 'system_id': p.get('gsi_system_id'), 'error': str(exc)})
    return matches, held, errors


def summarize_bill(data, expected_id, as_of):
    """Use parcel-level current totals once; never expose account identifiers in reports."""
    p, s = data.get('Parcel') or {}, data.get('ChargeSummary') or {}
    if str(p.get('ParcelID')) != str(expected_id):
        raise ValueError('Billing parcel identity mismatch')
    if s.get('Errors'):
        raise ValueError('Public billing reports errors: '+str(s['Errors']))
    rows = [r for r in s.get('ParcelTotals', []) if r.get('RateSchedule', {}).get('IsCurrent') is True]
    if len(rows) != 1:
        raise ValueError('Exactly one current parcel total is required')
    row = rows[0]
    rate = row.get('RateSchedule') or {}
    start, end = str(rate.get('StartDate', ''))[:10], str(rate.get('EndDate', ''))[:10]
    if not start or not end or not start <= as_of <= end:
        raise ValueError('Public current rate period does not cover scan date')
    value = number(row.get('TotalStormwaterCharge'))
    if value is None:
        raise ValueError('Public current parcel charge missing/invalid')
    # Do not borrow account-level ImpervSqFt (which can differ from physical IA).
    ga, ia = number(p.get('GrossArea')), number(p.get('ImpervArea'))
    cg, ci = number(s.get('GrossCreditSqFt')), number(s.get('ImpervCreditSqFt'))
    npdes = number(p.get('NPDESCredit'))
    if ga is None or ia is None or ia > ga or any(x is not None and x > a for x, a in ((cg, ga), (ci, ia))):
        raise ValueError('Invalid or incomplete area ledger')
    # Currency calculation is confined to the public current charge, not a savings claim.
    from decimal import Decimal, ROUND_HALF_UP
    monthly = float(Decimal(str(value)).quantize(Decimal('.01'), rounding=ROUND_HALF_UP))
    pending = data.get('Pending') or {}
    return {'monthly_charge': monthly, 'annual_charge': round(monthly*12, 2),
        'gross_area_sqft': ga, 'impervious_area_sqft': ia,
        'ga_credit_sqft': cg, 'ia_credit_sqft': ci, 'npdes_fraction': npdes,
        'property_type': p.get('BldgType'), 'owner1': p.get('Owner1'), 'owner2': p.get('Owner2'),
        'address': p.get('Address'), 'rate_start': start, 'rate_end': end,
        'expired_flag': number(pending.get('Expired')), 'pending_credit_flag': number(pending.get('Credits')),
        'pending_appeal_flag': number(pending.get('Appeals')),
        'basis': 'Public current parcel calculation; actual invoice/account eligibility unverified'}


def rank_prospect(parcel_id, match, bill):
    p = props(match['parcel'])
    # Either source can veto ownership. No owner or unresolved public-body names are held.
    ownership = owner_status(p.get('owner1'), p.get('owner2'), bill.get('owner1'), bill.get('owner2'))
    if ownership['status'] != 'nongovernment_record':
        return None, ownership
    if not bill.get('owner1') or not p.get('owner1'):
        return None, {'status': 'unknown', 'reason': 'Ownership missing in parcel or billing source'}
    if bill['property_type'] not in ('NonRes', 'Condo') or bill['monthly_charge'] <= 0:
        return None, {'status': 'not_target', 'reason': 'Not a positive-charge nonresidential/condominium parcel'}
    cg, ci = bill['ga_credit_sqft'], bill['ia_credit_sqft']
    if cg is None or ci is None or bill['npdes_fraction'] is None:
        return None, {'status': 'credit_unknown', 'reason': 'Missing credit fields are not zero credits'}
    fraction = ci/bill['impervious_area_sqft'] if bill['impervious_area_sqft'] else 0
    group = 'no_area_credit' if cg == ci == 0 else 'partial_area_credit' if fraction < .75 else 'substantial_area_credit'
    tags = []
    if bill['expired_flag'] and bill['expired_flag'] > 0:
        tags.append('Public expired flag needs interpretation; no lapse or refund established')
    if bill['pending_credit_flag'] and bill['pending_credit_flag'] > 0:
        tags.append('Public pending-credit flag; review before assuming an unclaimed opportunity')
    reasons = [GROUPS[group], f"{len({s['system_id'] for s in match['systems']})} mapped existing private system(s)",
               'Current annual public charge ranks economic scale; it is not estimated savings']
    gaps = ['Managed/contributing area and treatment capacity', 'Existing award/credit allocation and current invoice',
            'Current installation condition and maintenance', 'Beneficial ownership and agency-controlled entities are not independently verified']
    return {'parcel_id': str(parcel_id), 'address': bill['address'] or p.get('address'),
        'owner': ' '.join(str(v) for v in (bill['owner1'],bill.get('owner2')) if v), 'owner2': bill.get('owner2'), 'ownership': ownership,
        'group': group, 'group_label': GROUPS[group], 'billing': bill,
        'systems': sorted(match['systems'], key=lambda s: (s['system_id'], str(s['objectid']))),
        'parcel_geometry':match['parcel'].get('geometry'),
        'parcel_record':p,
        'system_types': sorted({s['type'] for s in match['systems'] if s.get('type')}),
        'projects': sorted({s['project_number'] for s in match['systems'] if s.get('project_number')}),
        'reasons': reasons, 'history_flags': tags, 'evidence_gaps': gaps,
        'estimated_savings': None, 'next_action': 'Review imagery and credit/management records before full assessment'}, None


def ordering(row):
    b=row['billing'];share=b['ia_credit_sqft']/b['impervious_area_sqft'] if b['impervious_area_sqft'] else 0
    # Current charges already reflect credits. Do not apply a second percentage
    # discount or present an invented savings value. Credit gap is a tie breaker.
    return (-b['annual_charge'],share,row['address'] or '',row['parcel_id'])


def group_sites(rows,as_of):
    """Same recorded owner plus a shared project or parcels within 100 ft.

    This is an explicit grouping hypothesis, never a legal ownership/route claim.
    Different owners or distant parcels remain separate site prospects.
    """
    rows=deepcopy(rows)
    ids=[r['parcel_id'] for r in rows]
    if len(ids)!=len(set(ids)):raise ValueError('Duplicate billing parcel rows; resolve before aggregating charges')
    for r in rows:
        r['freshness']=freshness(r.get('billing_source',{}),as_of)
        r['owner_key']=' '.join(re.sub(r'[^A-Z0-9 ]',' ',r['owner'].upper()).split())
    parent=list(range(len(rows)))
    def root(i):
        while parent[i]!=i:i=parent[i]
        return i
    for i,a in enumerate(rows):
        for j in range(i):
            b=rows[j]
            if a['owner_key']!=b['owner_key']:continue
            linked=bool(set(a.get('projects',[])) & set(b.get('projects',[])))
            if not linked and a.get('parcel_geometry') and b.get('parcel_geometry'):
                linked=shape(a['parcel_geometry']).distance(shape(b['parcel_geometry']))<=100
            if linked:parent[root(i)]=root(j)
    groups={}
    for i,r in enumerate(rows):groups.setdefault(root(i),[]).append(r)
    sites=[]
    for members in groups.values():
        members.sort(key=ordering);row=deepcopy(members[0]);row['member_parcels']=members
        row['parcel_ids']=sorted({m['parcel_id'] for m in members});row['parcel_count']=len(members)
        row['prospect_id']=sha256(canonical(row['parcel_ids'])).hexdigest()[:16]
        row['grouping_basis']='Same recorded owner; shared project or connected parcels within 100 ft (EPSG:2272); review site identity' if len(members)>1 else 'Single billing parcel'
        b=row['billing']
        for k in ('annual_charge','monthly_charge','gross_area_sqft','impervious_area_sqft','ga_credit_sqft','ia_credit_sqft'):
            b[k]=round(sum(m['billing'][k] for m in members),2)
        fraction=b['ia_credit_sqft']/b['impervious_area_sqft'] if b['impervious_area_sqft'] else 0
        row['credit_share']=round(fraction,4)
        row['group']='no_area_credit' if b['ga_credit_sqft']==b['ia_credit_sqft']==0 else 'partial_area_credit' if fraction<.75 else 'substantial_area_credit'
        row['group_label']=GROUPS[row['group']]
        row['systems']=[s for m in members for s in m['systems']]
        row['system_types']=sorted({s for m in members for s in m['system_types']})
        row['projects']=sorted({s for m in members for s in m['projects']})
        row['history_flags']=sorted({s for m in members for s in m['history_flags']})
        row['needs_record_review']=any(m['freshness']['status']!='fresh' or m.get('selected_record_update',{}).get('status')=='failed_previous_record_retained' for m in members) or bool(row['history_flags'])
        sites.append(row)
    sites.sort(key=ordering)
    for rank,row in enumerate(sites,1):row['rank']=rank
    return sites


def finish_ranking(result,rows,limit,as_of):
    sites=group_sites(rows,as_of)
    result.update(version=VERSION,ranking='Descending current annual public charge across all credit groups; recorded IA credit share breaks ties. Charges already reflect credits. Group labels describe evidence, not savings probability. Owner/site grouping remains a review hypothesis.',
        parcel_rows=rows,prospects=sites,top=sites[:limit])
    result['counts'].update(ranked_parcels=len(rows),ranked_prospects=len(sites),returned=min(limit,len(sites)),
        stale_or_undated_billing=sum(freshness(r.get('billing_source',{}),as_of)['status']!='fresh' for r in rows),
        recorded_owners=len({r['owner_key'] for s in sites for r in s['member_parcels']}))
    result['groups']=[{'id':k,'label':label,'count':sum(s['group']==k for s in sites[:limit])} for k,label in GROUPS.items()]
    result['freshness_policy']='Billing/ownership capture age >30 days requires review; unknown dates remain unknown. Cached records are never silently refreshed. These are operational screening defaults, not legal validity periods.'
    result['result_sha256']=sha256(canonical({k:v for k,v in result.items() if k!='result_sha256'})).hexdigest()
    return result


def rerank_saved(root,limit=50):
    start=time.perf_counter()
    with scan_lock(root):
        previous=load_result(root)
        if previous is None:raise ValueError('No saved records to rerank; explicit bounded acquisition is required')
        result=deepcopy(previous);as_of=datetime.now(ZoneInfo('America/New_York')).date().isoformat()
        rows=previous.get('parcel_rows') or [m for s in previous['prospects'] for m in s.get('member_parcels',[s])]
        result.update(id=uuid.uuid4().hex,at=now(),as_of=as_of,parent_run_id=previous['id'],elapsed_seconds=round(time.perf_counter()-start,3))
        result['acquisition_budget']={**previous['acquisition_budget'],'new_requests':0,'max_new_requests':0}
        finish_ranking(result,rows,limit,as_of)
        result['elapsed_seconds']=round(time.perf_counter()-start,3)
        result['result_sha256']=sha256(canonical({k:v for k,v in result.items() if k!='result_sha256'})).hexdigest()
        save_result(root,result)
    return result


def update_selected(root,parcel_ids,*,cache=None,max_requests=80,cancel=None,progress=None):
    """Update chosen member bills only. No inventory/matching/imagery/GIS calls."""
    if not isinstance(parcel_ids,list) or not parcel_ids or len(parcel_ids)>80 or any(not isinstance(v,str) or not v.isdecimal() for v in parcel_ids):
        raise ValueError('Select 1–80 known billing parcel IDs')
    if not 0<=max_requests<=80:raise ValueError('New request cap must be 0–80')
    started=time.perf_counter();root=Path(root)
    with scan_lock(root):
        previous=load_result(root)
        if not previous:raise ValueError('Build an initial shortlist before selecting updates')
        source_rows=previous.get('parcel_rows') or [m for s in previous['prospects'] for m in s.get('member_parcels',[s])]
        rows={r['parcel_id']:deepcopy(r) for r in source_rows};selected=sorted(set(parcel_ids))
        if set(selected)-set(rows):raise ValueError('Selection contains a parcel outside the saved candidate records')
        source=cache or SharedCache(fallback_roots=[root/'public'],timeout=20)
        bounded=CappedCache(source,max_requests,300,cancel,refresh_stale=True)
        as_of=datetime.now(ZoneInfo('America/New_York')).date().isoformat();result=deepcopy(previous)
        changes=[];errors=[];new_sources=[]
        def fetch(pid):
            item=bounded.fetch_json(f'{BILLING}/{int(pid)}/details')
            return item,summarize_bill(item['data'],pid,as_of)
        with ThreadPoolExecutor(max_workers=2) as executor:
            tasks={executor.submit(fetch,pid):pid for pid in selected}
            for done,task in enumerate(as_completed(tasks),1):
                pid=tasks[task];old=rows[pid]
                try:
                    item,bill=task.result();new_sources.append(item['provenance'])
                    if not old.get('parcel_record'):raise ValueError('Saved parcel match needs rebuilding before a targeted update')
                    identity_changed=any(old['billing'].get(k)!=bill.get(k) for k in ('owner1','owner2','address','gross_area_sqft','property_type'))
                    raw_shape=(item['data'].get('Parcel') or {}).get('Shape')
                    if raw_shape and old.get('parcel_geometry'):
                        from shapely import wkt
                        from shapely.ops import transform
                        from pyproj import Transformer
                        boundary=transform(Transformer.from_crs(4326,2272,always_xy=True).transform,wkt.loads(raw_shape))
                        identity_changed|=boundary.hausdorff_distance(shape(old['parcel_geometry']))>1
                    if identity_changed:changes.append({'parcel_id':pid,'reason':'Public parcel identity/boundary/owner changed; match index invalidated'})
                    match={'parcel':{'properties':old['parcel_record'],'geometry':old.get('parcel_geometry')},'systems':old['systems']}
                    row,excluded=rank_prospect(pid,match,bill)
                    result['excluded']=[e for e in result['excluded'] if e.get('parcel_id')!=pid]
                    if row:
                        row['billing_source']=item['provenance'];row['selected_record_update']={'status':'updated_or_reused_fresh','at':now()}
                        if identity_changed:row['history_flags'].append('Owner/boundary changed; verify site match before assessment')
                        rows[pid]=row
                    else:
                        rows.pop(pid);result['excluded'].append({'parcel_id':pid,'address':bill['address'],**excluded})
                except Exception as exc:
                    errors.append({'stage':'selected_billing','parcel_id':pid,'error':str(exc)})
                    old['selected_record_update']={'status':'failed_previous_record_retained','error':str(exc),'at':now()}
                if progress:progress(stage='selected_records',completed=done,total=len(selected))
        if cancel and cancel.is_set():raise SourceError('Selected update cancelled; previous saved result retained')
        if changes:invalidate_matches(root,'Selected parcel identity or boundary changed')
        result.update(id=uuid.uuid4().hex,at=now(),as_of=as_of,parent_run_id=previous['id'],selected_parcel_ids=selected,
            match_changes=changes,selected_update_failures=errors,elapsed_seconds=round(time.perf_counter()-started,3))
        result['failures']=result.get('failures',[])+errors;result['source_snapshots']+=new_sources
        result['status']='partial' if result['failures'] or result.get('invalid_systems') else 'complete'
        result['acquisition_budget']={'max_new_requests':max_requests,'new_requests':bounded.requests,'workers':2,'max_seconds':300,'selected_parcel_count':len(selected)}
        result['counts']['failed_requests_or_geometry']=len(result['failures'])
        result['counts']['exclusions_by_status']={s:sum(e['status']==s for e in result['excluded']) for s in sorted({e['status'] for e in result['excluded']})}
        finish_ranking(result,list(rows.values()),50,as_of);save_result(root,result)
    return result


def run_scan(root=None,**kwargs):
    root=Path(root or ROOT/'data/prospects')
    with scan_lock(root):return _run_scan(root,**kwargs)


def match_key(systems):
    return sha256(canonical(sorted(systems,key=lambda f:str(props(f).get('objectid'))))).hexdigest()


def read_matches(root,systems,cache,as_of):
    path=Path(root)/'matches.json'
    if not path.exists():return None
    data=json.loads(path.read_text());digest=data.pop('sha256',None)
    if sha256(canonical(data)).hexdigest()!=digest:raise ValueError('Persistent match hash mismatch')
    if data['version']!=1 or data['match_key']!=match_key(systems):return None
    if freshness({'retrieved_at':data['at']},as_of,90)['status']!='fresh':return None
    source=getattr(cache,'cache',cache)
    for item in data['sources']:
        if not hasattr(source,'_read'):return None
        current=source._read(item['url'])
        if not current or current[1]['sha256']!=item['sha256']:return None
        if freshness(current[1],as_of,90)['status']!='fresh':return None
    return data


def write_matches(root,systems,parcels,matches,held,errors,sources):
    from drainage_core.saved import atomic_json
    data={'version':1,'at':now(),'match_key':match_key(systems),'parcels':parcels,'matches':matches,
          'held':held,'errors':errors,'sources':sources}
    data['sha256']=sha256(canonical(data)).hexdigest();atomic_json(Path(root)/'matches.json',data)


def invalidate_matches(root,reason):
    path=Path(root)/'matches.json'
    if path.exists():path.rename(Path(root)/('matches-invalidated-'+uuid.uuid4().hex+'.json'))
    return reason


def _run_scan(root, *, refresh=False, limit=50, workers=2, progress=None, cache=None,
             max_requests=80,max_seconds=300,candidate_projects=120,cancel=None,refresh_stale=False):
    root = Path(root or ROOT/'data/prospects')
    root.mkdir(parents=True, exist_ok=True)
    if not 1 <= limit <= 200 or not 1 <= workers <= 2 or not 0<=max_requests<=80 or not 0<max_seconds<=300:
        raise ValueError('Limit 1–200, workers 1–2, new requests 0–80, acquisition window <=300 seconds')
    raw_cache = cache or SharedCache(fallback_roots=[root/'public'],timeout=20)
    # Injected fixture caches have no network. Real caches always get a hard budget.
    cache = CappedCache(raw_cache,max_requests,max_seconds,cancel,refresh_stale) if isinstance(raw_cache,Cache) else raw_cache
    as_of = datetime.now(ZoneInfo('America/New_York')).date().isoformat()
    start = time.perf_counter()
    def notify(**kw):
        if cancel and cancel.is_set():raise SourceError('Scan cancelled; previous saved results retained')
        if progress:progress(**kw)
    notify(stage='system_inventory', completed=0, total=None)
    inventory = read_inventory(cache, refresh)
    source_states = {}
    systems = []
    invalid = []
    for feature in inventory['features']:
        state = system_status(props(feature), as_of)
        source_states[state] = source_states.get(state, 0)+1
        if state == 'mapped_existing':
            try:
                g = shape(feature['geometry'])
                if not g.is_valid or g.area <= 0:
                    raise ValueError('Invalid or empty polygon')
                systems.append(feature)
            except Exception as exc:
                invalid.append({'system_id': props(feature).get('gsi_system_id'), 'error': str(exc)})
    projects={}
    for feature in systems:
        key=props(feature).get('project_number') or 'system-'+str(props(feature).get('gsi_system_id'))
        projects.setdefault(key,[]).append(feature)
    selected=sorted(projects,key=lambda k:(-sum(shape(f['geometry']).area for f in projects[k]),str(k)))[:candidate_projects]
    selected_systems=[f for k in selected for f in projects[k]]
    seeds=[max(projects[k],key=lambda f:shape(f['geometry']).area) for k in selected]
    persisted=None if refresh else read_matches(root,selected_systems,cache,as_of)
    if persisted:
        parcels=persisted['parcels'];parcel_sources=persisted['sources'];failures=[]
        matches=persisted['matches'];ambiguous=persisted['held'];geometry_errors=persisted['errors']
    else:
        # First query five projects. If that small sample fails, do not expand.
        first, parcel_sources, failures = find_parcels(seeds[:5], cache, refresh, workers, notify)
        if failures or not first:raise SourceError('Five-project parcel smoke check failed; expansion stopped')
        rest, more_sources, more_failures=find_parcels(seeds[5:],cache,refresh,workers,notify)
        parcels=list({str(props(f)['parcelid']):f for f in first+rest}.values())
        parcel_sources+=more_sources;failures+=more_failures
        matches, ambiguous, geometry_errors = match_systems(selected_systems, parcels)
        if not failures:write_matches(root,selected_systems,parcels,matches,ambiguous,geometry_errors,parcel_sources)
    failures.extend(geometry_errors)
    exclusions, targets = [], {}
    for pid, match in matches.items():
        p = props(match['parcel'])
        owner = owner_status(p.get('owner1'), p.get('owner2'))
        if owner['status'] != 'nongovernment_record':
            exclusions.append({'parcel_id': pid, 'address': p.get('address'), 'owner': p.get('owner1'), **owner})
        else:
            targets[pid] = match
    candidates, bill_sources = [], []

    def fetch(pid):
        item = cache.fetch_json(f'{BILLING}/{int(pid)}/details', refresh)
        return summarize_bill(item['data'], pid, as_of), item['provenance']

    notify(stage='billing_and_credits', completed=0, total=len(targets))
    with ThreadPoolExecutor(max_workers=workers) as executor:
        # Preserve preselection by mapped system footprint scale when the cap cuts off.
        ordered=sorted(targets,key=lambda pid:(-float(props(targets[pid]['parcel']).get('gross_area') or 0),pid))
        tasks = {executor.submit(fetch, pid): pid for pid in ordered}
        for done, task in enumerate(as_completed(tasks), 1):
            pid = tasks[task]
            try:
                bill, source = task.result()
                bill_sources.append(source)
                row, excluded = rank_prospect(pid, targets[pid], bill)
                if row:
                    row['billing_source'] = source
                    candidates.append(row)
                else:
                    exclusions.append({'parcel_id': pid, 'address': props(targets[pid]['parcel']).get('address'), **excluded})
            except Exception as exc:
                failures.append({'stage': 'billing', 'parcel_id': pid, 'error': str(exc)})
            notify(stage='billing_and_credits', completed=done, total=len(targets))
    candidates.sort(key=ordering)
    for n, row in enumerate(candidates, 1):
        row['rank'] = n
    result = {'schema_version': 1, 'version': VERSION, 'id': uuid.uuid4().hex,
        'at': now(), 'as_of': as_of, 'elapsed_seconds': round(time.perf_counter()-start, 3),
        'status': 'partial' if failures or invalid else 'complete',
        'claim': 'Records-only prospect ranking. No imagery, AI classification, terrain, routing or full assessment run. No qualifying savings or award established.',
        'ranking': 'Known no area credit first, then partial IA credit (<75%), then substantial IA credit. Within each group: descending annual current public charge, address, parcel ID. Threshold is a screening heuristic, not eligibility or a calibrated probability.',
        'coverage': 'Bounded candidate pool, not an exhaustive citywide top 50. Preselect the largest mapped existing private projects by summed footprint area (not managed area), query one representative system per project, then check dominant (>=80%) footprint overlap. Shared/cross-parcel systems and unlisted systems may be missed. No imagery opportunity search.',
        'persistent_matches':'reused' if persisted else 'rebuilt',
        'acquisition_budget':{'max_new_requests':max_requests,'new_requests':getattr(cache,'requests',0),'max_seconds':max_seconds,'workers':workers,'candidate_project_limit':candidate_projects},
        'ownership_policy': 'Government/public-body names in either parcel or billing owner fields excluded. Missing owners and unresolved authority/state-related ownership held for review. Public name screening does not verify beneficial ownership.',
        'counts': {'inventory_features': len(inventory['features']), 'system_status': source_states,
            'usable_existing_private_features': len(systems),'selected_project_count':len(selected), 'matched_parcels': len(matches),
            'billing_attempts': len(targets), 'ranked_prospects': len(candidates), 'returned': min(limit, len(candidates)),
            'ambiguous_systems': len(ambiguous), 'failed_requests_or_geometry': len(failures), 'invalid_systems': len(invalid),
            'exclusions_by_status': {s: sum(e['status'] == s for e in exclusions) for s in sorted({e['status'] for e in exclusions})}},
        'groups': [{'id': key, 'label': label, 'count': sum(r['group'] == key for r in candidates[:limit])} for key, label in GROUPS.items()],
        'top': candidates[:limit], 'prospects': candidates, 'excluded': exclusions,
        'ambiguous_matches': ambiguous, 'invalid_systems': invalid, 'failures': failures,
        'source_snapshots': inventory['sources']+parcel_sources+bill_sources,
        'source_layers': {'systems': SYSTEMS, 'parcels': PARCELS, 'billing': BILLING},
        'not_run': ['imagery', 'AI inference', 'DEM', 'drainage', 'full assessment', 'actual invoice validation', 'independent ownership/credit accuracy'],
    }
    finish_ranking(result,candidates,limit,as_of)
    result['elapsed_seconds']=round(time.perf_counter()-start,3)
    result['result_sha256']=sha256(canonical({k:v for k,v in result.items() if k!='result_sha256'})).hexdigest()
    if cancel and cancel.is_set():raise SourceError('Scan cancelled; previous results retained')
    save_result(root, result)
    notify(stage='complete', completed=len(candidates), total=len(candidates), run_id=result['id'])
    return result


def csv_report(result):
    stream = io.StringIO(newline='')
    fields = ['rank','group','address','parcel_ids','owner','annual_public_charge','monthly_public_charge',
              'recorded_IA_credit_sqft','recorded_GA_credit_sqft','system_types','system_ids','projects','history_flags','estimated_savings','evidence_gaps','parcel_count','member_addresses','grouping_basis']
    writer = csv.DictWriter(stream, fields)
    writer.writeheader()
    for r in result['top']:
        b = r['billing']
        row = dict(zip(fields, [r['rank'],r['group_label'],r['address'],'; '.join(r.get('parcel_ids',[r['parcel_id']])),r['owner'],b['annual_charge'],b['monthly_charge'],
            b['ia_credit_sqft'],b['ga_credit_sqft'],'; '.join(r['system_types']),'; '.join(sorted({s['system_id'] for s in r['systems']})),
            '; '.join(r['projects']),'; '.join(r['history_flags']),'Unknown — not calculated','; '.join(r['evidence_gaps']),r.get('parcel_count',1),'; '.join(m['address'] for m in r.get('member_parcels',[r])),r.get('grouping_basis','Single billing parcel')]))
        # Spreadsheet formula injection must not turn public text into executable cells.
        writer.writerow({k: "'"+v if isinstance(v, str) and v.startswith(('=', '+', '-', '@', '\t', '\r')) else v for k,v in row.items()})
    return stream.getvalue()


def html_report(result):
    e = lambda v: escape(str(v if v is not None else 'Unknown'))
    body = '<h1>Philadelphia quick prospect scan</h1><p>'+e(result['at'])+'</p><p>'+e(result['claim'])+'</p><p>'+e(result['ranking'])+'</p><p>'+e(result['ownership_policy'])+'</p>'
    for group in result['groups']:
        body += '<h2>'+e(group['label'])+' ('+str(group['count'])+')</h2><div class="scroll"><table><tr><th>Rank</th><th>Property / owner</th><th>Annual public charge</th><th>Recorded IA / GA credit (sq ft)</th><th>Systems / projects</th><th>History / next evidence</th></tr>'
        for r in result['top']:
            if r['group'] != group['id']:
                continue
            b = r['billing']
            members='<br>'.join(e(m['address'])+' · parcel '+e(m['parcel_id'])+' · $'+f"{m['billing']['annual_charge']:,.2f}"+'/year' for m in r.get('member_parcels',[r]))
            body += '<tr><td>'+str(r['rank'])+'</td><td>'+e(r['owner'])+'<br>'+str(r.get('parcel_count',1))+' billing parcel(s)<br>'+members+'<br>'+e(r.get('grouping_basis','Single parcel'))+'</td><td>$'+f"{b['annual_charge']:,.2f}"+'</td><td>'+e(b['ia_credit_sqft'])+' / '+e(b['ga_credit_sqft'])+'</td><td>'+e('; '.join(r['system_types']))+'<br>'+e('; '.join(r['projects']))+'</td><td>'+e('; '.join(r['history_flags']))+'<br>'+e('; '.join(r['evidence_gaps'][:3]))+'</td></tr>'
        body += '</table></div>'
    body += '<h2>Coverage and unresolved records</h2><p>'+e(result['coverage'])+'</p><pre>'+e(json.dumps(result['counts'], indent=2))+'</pre><p>All charge figures are public calculations, not verified invoices or estimated savings. Source snapshots and excluded/failed matches are retained in the JSON export.</p>'
    return '<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Philadelphia top prospects</title><style>body{font:15px/1.5 system-ui;margin:24px;color:#183c34}table{border-collapse:collapse;width:100%;font-size:13px}td,th{padding:10px;border-bottom:1px solid #ccd8cf;text-align:left;vertical-align:top}.scroll{overflow:auto}pre{white-space:pre-wrap}h2{margin-top:32px}</style>'+body+'</html>'


def save_result(root, result):
    folder = Path(root)/'runs'/result['id']
    folder.mkdir(parents=True, exist_ok=False)
    (folder/'results.json').write_bytes(canonical(result)+b'\n')
    (folder/'top50.csv').write_text(csv_report(result))
    (folder/'report.html').write_text(html_report(result))
    temp = Path(root)/'latest.tmp'
    temp.write_text(json.dumps({'id': result['id']}))
    temp.replace(Path(root)/'latest.json')


def load_result(root, run_id=None):
    root = Path(root)
    if run_id is None:
        if not (root/'latest.json').exists():
            return None
        run_id = json.loads((root/'latest.json').read_text())['id']
    if not re.fullmatch('[a-f0-9]{32}', str(run_id)):
        raise ValueError('Invalid scan ID')
    result = json.loads((root/'runs'/run_id/'results.json').read_text())
    if result['result_sha256'] != sha256(canonical({k:v for k,v in result.items() if k != 'result_sha256'})).hexdigest():
        raise ValueError('Prospect result hash mismatch')
    return result


def public_result(result):
    if result is None:
        return None
    return {k:v for k,v in result.items() if k not in ('prospects','parcel_rows','excluded','ambiguous_matches','invalid_systems','source_snapshots')}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=ROOT/'data/prospects')
    parser.add_argument('--limit', type=int, default=50)
    parser.add_argument('--workers', type=int, choices=(1,2),default=2)
    parser.add_argument('--refresh', action='store_true')
    parser.add_argument('--offline', action='store_true',help='Use cached records only; make zero network requests')
    parser.add_argument('--rerank', action='store_true',help='Rank saved matched parcels only; zero acquisition or spatial queries')
    parser.add_argument('--update-stale',action='store_true',help='Explicitly refresh only stale/undated or missing cached records, under the same cap')
    parser.add_argument('--parcels',nargs='+',help='Update only these saved member parcel IDs; no inventory or matching calls')
    args = parser.parse_args()
    if args.parcels:
        if args.refresh or args.rerank:parser.error('Selected updates cannot use --refresh or --rerank')
        result=update_selected(args.output,args.parcels,max_requests=0 if args.offline else 80)
        print(json.dumps({'id':result['id'],'selected':args.parcels,'new_requests':result['acquisition_budget']['new_requests']}));return
    if args.rerank and (args.refresh or args.update_stale):parser.error('Local reranking cannot refresh records')
    if args.rerank:
        result=rerank_saved(args.output,args.limit);print(json.dumps({'id':result['id'],'counts':result['counts'],'new_requests':0}));return
    def progress(**state):
        if state.get('completed',0) % 25 == 0 or state['stage'] == 'complete':
            print(json.dumps(state), flush=True)
    if args.offline and (args.refresh or args.update_stale):parser.error('Offline mode cannot refresh records')
    result = run_scan(args.output, limit=args.limit, workers=args.workers, refresh=args.refresh, progress=progress,
                      max_requests=0 if args.offline else 80,refresh_stale=args.update_stale)
    print(json.dumps({'id':result['id'],'counts':result['counts'],'groups':result['groups'],'elapsed_seconds':result['elapsed_seconds']}, indent=2))


if __name__ == '__main__':
    main()
