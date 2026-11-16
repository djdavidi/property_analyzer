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

from shapely.geometry import shape, mapping
from shapely.ops import unary_union
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
# Owner screening (accepted decision D8). Names are normalized first: "&" -> AND,
# punctuation -> space, common PWD abbreviations expanded, single letters joined
# ("U S A" -> USA), a leading "THE" dropped. Then:
# - an exact public-body name (or a public body's agency, or a fixed-width field
#   truncation of a listed body) is government and excluded;
# - a name that only *begins* with a public-body name or a public-sounding
#   prefix (whole tokens) is held for review, never excluded;
# - everything else is a named non-government record.
# A private business containing "state", "city" or "Philadelphia" alone is not excluded.
OWNER_ABBREVIATIONS = {
    'PHILA': 'PHILADELPHIA', 'PHILADA': 'PHILADELPHIA', 'PENNA': 'PENNSYLVANIA', 'PA': 'PENNSYLVANIA',
    'AUTH': 'AUTHORITY', 'HSG': 'HOUSING', 'DEPT': 'DEPARTMENT', 'REDEV': 'REDEVELOPMENT',
    'DEV': 'DEVELOPMENT', 'CORP': 'CORPORATION', 'COMMW': 'COMMONWEALTH', 'COMWLTH': 'COMMONWEALTH',
    'ADMIN': 'ADMINISTRATION', 'ASSN': 'ASSOCIATION', 'NATL': 'NATIONAL', 'CTR': 'CENTER',
    'CONV': 'CONVENTION', 'DIST': 'DISTRICT', 'GOVT': 'GOVERNMENT', 'UNIV': 'UNIVERSITY',
    'SCH': 'SCHOOL', 'BD': 'BOARD', 'COMMN': 'COMMISSION', 'INDUST': 'INDUSTRIAL', 'INDUS': 'INDUSTRIAL',
}
GOVERNMENT_BODIES = (
    'CITY OF PHILADELPHIA', 'CITY AND COUNTY OF PHILADELPHIA', 'COUNTY OF PHILADELPHIA',
    'COMMONWEALTH OF PENNSYLVANIA', 'STATE OF PENNSYLVANIA',
    'UNITED STATES OF AMERICA', 'US OF AMERICA', 'UNITED STATES', 'USA', 'US',
    'UNITED STATES GOVERNMENT', 'US GOVERNMENT', 'USA GOVERNMENT',
    'UNITED STATES POSTAL SERVICE', 'US POSTAL SERVICE', 'POSTMASTER GENERAL', 'POST OFFICE DEPARTMENT',
    'UNITED STATES ARMY', 'US ARMY', 'UNITED STATES NAVY', 'US NAVY', 'US ARMY CORPS OF ENGINEERS',
    'SECRETARY OF HOUSING AND URBAN DEVELOPMENT', 'SECRETARY OF VETERANS AFFAIRS', 'VETERANS ADMINISTRATION',
    'NATIONAL PARK SERVICE', 'GENERAL SERVICES ADMINISTRATION', 'DEFENSE LOGISTICS AGENCY',
    'FEDERAL AVIATION ADMINISTRATION', 'FEDERAL HIGHWAY ADMINISTRATION', 'FEDERAL EMERGENCY MANAGEMENT AGENCY',
    'FEDERAL RESERVE BANK OF PHILADELPHIA', 'NATIONAL RAILROAD PASSENGER CORPORATION', 'AMTRAK',
    'SCHOOL DISTRICT OF PHILADELPHIA', 'BOARD OF EDUCATION', 'BOARD OF PUBLIC EDUCATION',
    'BOARD OF EDUCATION OF THE SCHOOL DISTRICT OF PHILADELPHIA', 'PHILADELPHIA BOARD OF EDUCATION',
    'PHILADELPHIA HOUSING AUTHORITY', 'PHILADELPHIA REDEVELOPMENT AUTHORITY',
    'REDEVELOPMENT AUTHORITY OF THE CITY OF PHILADELPHIA', 'REDEVELOPMENT AUTHORITY OF PHILADELPHIA',
    'PHILADELPHIA AUTHORITY FOR INDUSTRIAL DEVELOPMENT', 'PHILADELPHIA INDUSTRIAL DEVELOPMENT CORPORATION',
    'PHILADELPHIA HOUSING DEVELOPMENT CORPORATION', 'PHILADELPHIA PARKING AUTHORITY',
    'PHILADELPHIA MUNICIPAL AUTHORITY', 'PHILADELPHIA GAS WORKS', 'PHILADELPHIA LAND BANK',
    'BOARD OF CITY TRUSTS', 'BOARD OF DIRECTORS OF CITY TRUSTS', 'PHILADELPHIA WATER DEPARTMENT',
    'PHILADELPHIA REGIONAL PORT AUTHORITY', 'PHILADELPHIA ENERGY AUTHORITY',
    'PENNSYLVANIA CONVENTION CENTER AUTHORITY', 'PHILADELPHIA CONVENTION CENTER AUTHORITY',
    'COMMUNITY COLLEGE OF PHILADELPHIA', 'PHILADELPHIA COMMUNITY COLLEGE', 'FREE LIBRARY OF PHILADELPHIA',
    'FAIRMOUNT PARK COMMISSION', 'SOUTHEASTERN PENNSYLVANIA TRANSPORTATION AUTHORITY', 'SEPTA',
    'DELAWARE RIVER PORT AUTHORITY', 'DELAWARE RIVER PORT AUTHORITY OF PENNSYLVANIA AND NEW JERSEY',
    'DELAWARE RIVER JOINT TOLL BRIDGE COMMISSION', 'DELAWARE RIVER WATERFRONT CORPORATION',
    'PENNSYLVANIA TURNPIKE COMMISSION', 'PENNSYLVANIA HOUSING FINANCE AGENCY',
    'PENNSYLVANIA INDUSTRIAL DEVELOPMENT AUTHORITY', 'PENNSYLVANIA STATE POLICE', 'PENNDOT', 'PENN DOT',
)
# Sovereign bodies' named agencies ("COMMONWEALTH OF PENNSYLVANIA DEPARTMENT OF ...").
_SOVEREIGN = r'(?:CITY OF PHILADELPHIA|CITY AND COUNTY OF PHILADELPHIA|COUNTY OF PHILADELPHIA|COMMONWEALTH OF PENNSYLVANIA|PENNSYLVANIA|UNITED STATES OF AMERICA|US OF AMERICA|UNITED STATES|USA|US)'
GOVERNMENT_AGENCY = re.compile(_SOVEREIGN+r' (?:DEPARTMENT|DIVISION|BUREAU|OFFICE|BOARD|COMMISSION|AGENCY) OF(?: [A-Z0-9]+)+')
# Prefix-only signals: held for review (D8), never excluded.
REVIEW_OWNER = (
    r'^(?:CITY|COUNTY|CITY AND COUNTY|COMMONWEALTH|STATE) OF\b',
    r'^(?:UNITED STATES|USA|US) (?:OF AMERICA|GOVERNMENT|POSTAL|POST OFFICE|ARMY|NAVY|AIR FORCE|DEPARTMENT|GENERAL SERVICES|VETERANS|SECRETARY)\b',
    r'^SCHOOL DISTRICT\b', r'^BOARD OF (?:EDUCATION|PUBLIC EDUCATION|CITY TRUSTS|DIRECTORS OF CITY TRUSTS)\b',
    r'^PHILADELPHIA (?:HOUSING AUTHORITY|HOUSING DEVELOPMENT CORPORATION|REDEVELOPMENT|PARKING AUTHORITY|MUNICIPAL AUTHORITY|AUTHORITY FOR|INDUSTRIAL DEVELOPMENT|GAS WORKS|LAND BANK|REGIONAL PORT|WATER DEPARTMENT|ENERGY AUTHORITY|BOARD OF EDUCATION)\b',
    r'^REDEVELOPMENT AUTHORITY\b', r'^SOUTHEASTERN PENNSYLVANIA TRANSPORTATION\b', r'^DELAWARE RIVER (?:PORT|JOINT|WATERFRONT)\b',
    r'^PENNSYLVANIA (?:DEPARTMENT|TURNPIKE|CONVENTION|HOUSING FINANCE|INDUSTRIAL DEVELOPMENT|STATE POLICE)\b',
    r'^NATIONAL (?:PARK SERVICE|RAILROAD PASSENGER)\b', r'^FEDERAL (?:GOVERNMENT|AVIATION|HIGHWAY|EMERGENCY|RESERVE|BUREAU)\b',
    r'^(?:GENERAL SERVICES ADMINISTRATION|DEFENSE LOGISTICS|POSTMASTER GENERAL|POST OFFICE DEPARTMENT|SECRETARY OF)\b',
    r'\bAUTHORITY\b', r'^TEMPLE UNIVERSITY\b', r'^PENNSYLVANIA STATE UNIVERSITY\b', r'^PENN STATE\b',
    r'^UNKNOWN\b', r'^OWNER OF RECORD\b',
)
# Bodies too short or generic to act as a prefix signal on their own.
_NO_PREFIX = {'US', 'USA', 'UNITED STATES'}


class CappedCache:
    """Hard cap on new requests; cached evidence remains usable without a request.

    A cached HTTP-200 error body is not evidence: it counts as missing, so it is
    fetched again within the budget. A stale record whose refresh fails (or is
    out of budget) is kept as the flagged stale copy instead of being dropped.
    """
    def __init__(self, cache, max_requests=80, max_seconds=300,cancel=None,refresh_stale=False):
        self.cache=cache;self.max_requests=max_requests;self.requests=0
        self.deadline=time.monotonic()+max_seconds;self.lock=Lock()
        self.cancel=cancel
        self.refresh_stale=refresh_stale
        self.stale_reuse=[]

    def _saved(self,url):
        usable=getattr(self.cache,'_read_usable',None)
        saved=(usable or self.cache._read)(url)
        if saved is None:return None
        problem=getattr(self.cache,'_problem',None)
        if problem and not usable and problem(url,saved[0]):return None
        try:data=json.loads(saved[0])
        except (TypeError,ValueError):return None
        if isinstance(data,dict) and data.get('error'):return None
        return data,saved[1]

    def fetch_json(self,url,refresh=False,metadata=None):
        if self.cancel and self.cancel.is_set():raise SourceError('Scan cancelled; no further request made')
        saved=self._saved(url) if not refresh else None
        stale=None
        if saved is not None:
            age=freshness(saved[1],datetime.now(ZoneInfo('America/New_York')).date().isoformat(),30 if '/parcel/' in url else 90)
            if not self.refresh_stale or age['status']=='fresh':
                return {'data':saved[0],'provenance':saved[1]}
            refresh=True;stale=(saved,age)
        try:
            with self.lock:
                if self.requests>=self.max_requests or time.monotonic()>=self.deadline:
                    raise SourceError('Acquisition budget reached; no further network request made')
                self.requests+=1
            return self.cache.fetch_json(url,refresh,metadata)
        except Exception as exc:
            if stale is None or (self.cancel and self.cancel.is_set()):raise
            (data,provenance),age=stale
            event={'url':url,'retrieved_at':provenance.get('retrieved_at'),'sha256':provenance.get('sha256'),
                   'age_days':age['age_days'],'max_age_days':age['max_age_days'],'error':str(exc),
                   'status':'stale_record_kept_after_failed_refresh'}
            with self.lock:self.stale_reuse.append(event)
            return {'data':data,'provenance':{**provenance,'refresh_failed':True,'refresh_error':str(exc)}}


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


def owner_name(value):
    """Normalized owner name used only for public-body screening."""
    text = re.sub(r'[^A-Z0-9 ]', ' ', str(value).upper().replace('&', ' AND '))
    tokens, letters = [], []
    for token in text.split():
        if len(token) == 1 and token.isalpha():
            letters.append(token)
            continue
        if letters:
            tokens.append(''.join(letters)); letters = []
        tokens.append(token)
    if letters:
        tokens.append(''.join(letters))
    tokens = [OWNER_ABBREVIATIONS.get(t, t) for t in tokens]
    if len(tokens) > 1 and tokens[0] == 'THE':
        tokens = tokens[1:]
    return ' '.join(tokens)


def _government_match(name):
    if name in GOVERNMENT_BODIES or GOVERNMENT_AGENCY.fullmatch(name):
        return 'Exact public-body owner name: '+name
    # PWD owner fields are fixed-width; a long cut-off name that is the start of
    # exactly a listed body (e.g. "PHILADELPHIA AUTHORITY FO") is that body.
    if len(name) >= 20 and len(name.split()) >= 3 and any(body.startswith(name) for body in GOVERNMENT_BODIES):
        return 'Truncated public-body owner name: '+name
    return None


def _review_match(name):
    for body in GOVERNMENT_BODIES:
        if body not in _NO_PREFIX and name.startswith(body+' '):
            return 'Owner name only begins with public body "'+body+'"'
    for pattern in REVIEW_OWNER:
        if re.search(pattern, name):
            return 'Public-body/ownership signal "'+pattern+'"'
    return None


def owner_status(*owners):
    names = [owner_name(s) for s in owners if s and str(s).strip()]
    names = [n for n in names if n]
    if not names:
        return {'status': 'unknown', 'reason': 'Owner missing from public record'}
    for name in names:
        reason = _government_match(name)
        if reason:
            return {'status': 'government', 'reason': reason}
    for name in names:
        reason = _review_match(name)
        if reason:
            return {'status': 'review', 'reason': reason+'; partial-name match held for review, not excluded: '+name}
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


def representative_points(geometry):
    """One interior point per polygon part, rounded as sent to the parcel query."""
    parts = list(geometry.geoms) if hasattr(geometry, 'geoms') else [geometry]
    output = []
    for part in parts:
        if part.is_empty or part.area <= 0:
            continue
        pt = part.representative_point()
        output.append((round(pt.x, 3), round(pt.y, 3)))
    return output


def coverage_gaps(systems, parcels, minimum_fraction=.01):
    """Footprint parts of selected systems not covered by any fetched parcel.

    Only one seed system per project is queried first; every other selected
    system's uncovered footprint is queried next, so an unfetched parcel is not
    mistaken for an ambiguous overlap.
    """
    shapes = []
    for feature in parcels:
        try:
            g = shape(feature['geometry'])
            if g.is_valid and g.area > 0:
                shapes.append(g)
        except Exception:
            continue
    tree = STRtree(shapes) if shapes else None
    gaps = []
    for feature in systems:
        try:
            g = shape(feature['geometry'])
            if not g.is_valid or g.area <= 0:
                continue
            covering = [shapes[int(i)] for i in tree.query(g)] if tree is not None else []
            remaining = g.difference(unary_union(covering)) if covering else g
        except Exception:
            continue
        if remaining.area > g.area*minimum_fraction:
            gaps.append({'type': 'Feature', 'geometry': mapping(remaining),
                         'properties': {'gsi_system_id': props(feature).get('gsi_system_id')}})
    return gaps


def find_parcels(systems, cache, refresh=False, workers=4, progress=None):
    """Batch representative interior points; exact overlap subsequently validates matches.

    This fast join can miss other parcels crossed by a footprint. It never represents
    a system's managed area or proves parcel credit allocation.
    """
    points = sorted({pt for feature in systems for pt in representative_points(shape(feature['geometry']))})
    chunks = [[list(pt) for pt in points[i:i+16]] for i in range(0, len(points), 16)]
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
                errors.append({'stage': 'parcel_query', 'chunk': tasks[task], 'points': chunks[tasks[task]], 'error': str(exc)})
            if progress:
                progress(stage='parcel_matching', completed=done, total=len(chunks))
    return list(output.values()), sources, errors


def match_systems(systems, parcels, unqueried=()):
    """Assign systems with a dominant (>=80%) parcel overlap.

    Held systems carry ``reason_code``: ``ambiguous_overlap`` (fetched parcels
    share the footprint), ``no_parcel_found`` (queried, nothing returned) or
    ``parcel_not_queried`` (the parcel query for an uncovered part failed or was
    not made, e.g. request budget). Coverage gaps are not ambiguity.
    """
    from shapely.geometry import Point
    missing = [Point(pt) for pt in unqueried]
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
                covered = sum(f for _, f in overlaps)
                remaining = g.difference(unary_union([shapes[i] for i, _ in overlaps])) if overlaps else g
                if covered < .99 and any(remaining.buffer(.01).intersects(pt) for pt in missing):
                    code, reason = 'parcel_not_queried', 'Parcel at an uncovered part of the system was not queried (request failed or budget reached)'
                elif not overlaps:
                    code, reason = 'no_parcel_found', 'No parcel returned at the system location'
                else:
                    code, reason = 'ambiguous_overlap', 'No dominant parcel overlap'
                held.append({'system_id': p.get('gsi_system_id'), 'reason': reason, 'reason_code': code,
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
        parcel_rows=rows,prospects=sites,top=sites[:limit],limit=limit)
    result['counts'].update(ranked_parcels=len(rows),ranked_prospects=len(sites),returned=min(limit,len(sites)),
        stale_or_undated_billing=sum(freshness(r.get('billing_source',{}),as_of)['status']!='fresh' for r in rows),
        recorded_owners=len({r['owner_key'] for s in sites for r in s['member_parcels']}))
    result['retry_parcel_ids']=sorted(t['parcel_id'] for t in result.get('retry_targets',[]))
    result['counts']['retryable_billing_failures']=len(result['retry_parcel_ids'])
    result['groups']=[{'id':k,'label':label,'count':sum(s['group']==k for s in sites[:limit])} for k,label in GROUPS.items()]
    result['freshness_policy']='Billing/ownership capture age >30 days requires review; unknown dates remain unknown. Cached records are never silently refreshed. A failed refresh keeps the earlier stale record, flagged for review. These are operational screening defaults, not legal validity periods.'
    result['result_sha256']=sha256(canonical({k:v for k,v in result.items() if k!='result_sha256'})).hexdigest()
    return result


def saved_limit(previous,limit=None):
    """Explicit limit, else the saved run's own limit (older runs: 50)."""
    value=limit if limit is not None else previous.get('limit',50)
    if not isinstance(value,int) or isinstance(value,bool) or not 1<=value<=200:raise ValueError('Limit 1–200')
    return value


def rerank_saved(root,limit=None):
    start=time.perf_counter()
    with scan_lock(root):
        previous=load_result(root)
        if previous is None:raise ValueError('No saved records to rerank; explicit bounded acquisition is required')
        limit=saved_limit(previous,limit)
        result=deepcopy(previous);as_of=datetime.now(ZoneInfo('America/New_York')).date().isoformat()
        rows=previous.get('parcel_rows') or [m for s in previous['prospects'] for m in s.get('member_parcels',[s])]
        result.update(id=uuid.uuid4().hex,at=now(),as_of=as_of,parent_run_id=previous['id'],elapsed_seconds=round(time.perf_counter()-start,3))
        result['acquisition_budget']={**previous['acquisition_budget'],'new_requests':0,'max_new_requests':0}
        finish_ranking(result,rows,limit,as_of)
        result['elapsed_seconds']=round(time.perf_counter()-start,3)
        result['result_sha256']=sha256(canonical({k:v for k,v in result.items() if k!='result_sha256'})).hexdigest()
        save_result(root,result)
    return result


def update_selected(root,parcel_ids,*,cache=None,max_requests=80,cancel=None,progress=None,limit=None):
    """Update chosen member bills only. No inventory/matching/imagery/GIS calls.

    Ranked member parcels and parcels whose billing failed earlier (``retry_parcel_ids``)
    can be selected. A failed update keeps the previous row (or retry entry); a
    stale bill whose refresh fails is kept as the flagged stale copy.
    """
    if not isinstance(parcel_ids,list) or not parcel_ids or len(parcel_ids)>80 or any(not isinstance(v,str) or not v.isdecimal() for v in parcel_ids):
        raise ValueError('Select 1–80 known billing parcel IDs')
    if not 0<=max_requests<=80:raise ValueError('New request cap must be 0–80')
    started=time.perf_counter();root=Path(root)
    with scan_lock(root):
        previous=load_result(root)
        if not previous:raise ValueError('Build an initial shortlist before selecting updates')
        limit=saved_limit(previous,limit)
        source_rows=previous.get('parcel_rows') or [m for s in previous['prospects'] for m in s.get('member_parcels',[s])]
        rows={r['parcel_id']:deepcopy(r) for r in source_rows};selected=sorted(set(parcel_ids))
        retry={t['parcel_id']:deepcopy(t) for t in previous.get('retry_targets',[])}
        if set(selected)-set(rows)-set(retry):raise ValueError('Selection contains a parcel outside the saved candidate records')
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
                pid=tasks[task];old=rows.get(pid) or retry[pid]
                try:
                    item,bill=task.result();new_sources.append(item['provenance'])
                    if not old.get('parcel_record'):raise ValueError('Saved parcel match needs rebuilding before a targeted update')
                    identity_changed=bool(old.get('billing')) and any(old['billing'].get(k)!=bill.get(k) for k in ('owner1','owner2','address','gross_area_sqft','property_type'))
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
                    stale=bool(item['provenance'].get('refresh_failed'))
                    if row:
                        row['billing_source']=item['provenance']
                        row['selected_record_update']={'status':'stale_record_kept_after_failed_refresh' if stale else 'updated_or_reused_fresh','at':now(),
                                                       **({'error':item['provenance'].get('refresh_error')} if stale else {})}
                        if identity_changed:row['history_flags'].append('Owner/boundary changed; verify site match before assessment')
                        rows[pid]=row
                    else:
                        rows.pop(pid,None);result['excluded'].append({'parcel_id':pid,'address':bill['address'],**excluded})
                    retry.pop(pid,None)
                except Exception as exc:
                    errors.append({'stage':'selected_billing','parcel_id':pid,'error':str(exc)})
                    if pid in rows:old['selected_record_update']={'status':'failed_previous_record_retained','error':str(exc),'at':now()}
                    else:old.update(error=str(exc),last_retry_at=now())
                if progress:progress(stage='selected_records',completed=done,total=len(selected))
        if cancel and cancel.is_set():raise SourceError('Selected update cancelled; previous saved result retained')
        if changes:invalidate_matches(root,'Selected parcel identity or boundary changed')
        result.update(id=uuid.uuid4().hex,at=now(),as_of=as_of,parent_run_id=previous['id'],selected_parcel_ids=selected,
            match_changes=changes,selected_update_failures=errors,elapsed_seconds=round(time.perf_counter()-started,3))
        # Earlier billing failures of re-attempted parcels are replaced by this attempt's outcome.
        result['failures']=[f for f in result.get('failures',[]) if f.get('parcel_id') not in selected or f.get('stage') not in ('billing','selected_billing')]+errors
        result['retry_targets']=sorted(retry.values(),key=lambda t:t['parcel_id'])
        result['source_snapshots']+=new_sources
        result['stale_records_kept']=bounded.stale_reuse
        result['status']='partial' if result['failures'] or result.get('invalid_systems') else 'complete'
        result['acquisition_budget']={'max_new_requests':max_requests,'new_requests':bounded.requests,'workers':2,'max_seconds':300,'selected_parcel_count':len(selected)}
        result['counts']['failed_requests_or_geometry']=len(result['failures'])
        result['counts']['exclusions_by_status']={s:sum(e['status']==s for e in result['excluded']) for s in sorted({e['status'] for e in result['excluded']})}
        finish_ranking(result,list(rows.values()),limit,as_of);save_result(root,result)
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
        # Every other selected system: query the parts not covered by a fetched parcel.
        gaps=coverage_gaps(selected_systems,parcels)
        if gaps:
            extra, extra_sources, extra_failures=find_parcels(gaps,cache,refresh,workers,notify)
            parcels=list({str(props(f)['parcelid']):f for f in parcels+extra}.values())
            parcel_sources+=extra_sources;failures+=extra_failures
        unqueried=[tuple(pt) for f in failures for pt in f.get('points',[])]
        matches, ambiguous, geometry_errors = match_systems(selected_systems, parcels, unqueried)
        if not failures:write_matches(root,selected_systems,parcels,matches,ambiguous,geometry_errors,parcel_sources)
    failures.extend(geometry_errors)
    exclusions, targets, retry_targets = [], {}, []
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
                # Kept so the failed bill can be retried as a selected update.
                retry_targets.append({'parcel_id': str(pid), 'address': props(targets[pid]['parcel']).get('address'),
                    'parcel_record': props(targets[pid]['parcel']), 'parcel_geometry': targets[pid]['parcel'].get('geometry'),
                    'systems': sorted(targets[pid]['systems'], key=lambda s: (s['system_id'], str(s['objectid']))), 'error': str(exc)})
            notify(stage='billing_and_credits', completed=done, total=len(targets))
    candidates.sort(key=ordering)
    for n, row in enumerate(candidates, 1):
        row['rank'] = n
    stale_kept = list(cache.stale_reuse) if isinstance(getattr(cache, 'stale_reuse', None), list) else []
    held_codes = [h.get('reason_code', 'ambiguous_overlap') for h in ambiguous]
    result = {'schema_version': 1, 'version': VERSION, 'id': uuid.uuid4().hex,
        'at': now(), 'as_of': as_of, 'elapsed_seconds': round(time.perf_counter()-start, 3),
        'status': 'partial' if failures or invalid or stale_kept else 'complete',
        'claim': 'Records-only prospect ranking. No imagery, AI classification, terrain, routing or full assessment run. No qualifying savings or award established.',
        'ranking': 'Known no area credit first, then partial IA credit (<75%), then substantial IA credit. Within each group: descending annual current public charge, address, parcel ID. Threshold is a screening heuristic, not eligibility or a calibrated probability.',
        'coverage': 'Bounded candidate pool, not an exhaustive citywide top 50. Preselect the largest mapped existing private projects by summed footprint area (not managed area), query the largest system per project, then the footprint of every other selected system not covered by a fetched parcel, then check dominant (>=80%) footprint overlap. Systems whose parcel could not be queried are labelled parcel_not_queried, not ambiguous. Shared/cross-parcel systems and unlisted systems may be missed. No imagery opportunity search.',
        'persistent_matches':'reused' if persisted else 'rebuilt',
        'acquisition_budget':{'max_new_requests':max_requests,'new_requests':getattr(cache,'requests',0),'max_seconds':max_seconds,'workers':workers,'candidate_project_limit':candidate_projects},
        'ownership_policy': 'Government/public-body names in either parcel or billing owner fields excluded. Missing owners and unresolved authority/state-related ownership held for review. Public name screening does not verify beneficial ownership.',
        'counts': {'inventory_features': len(inventory['features']), 'system_status': source_states,
            'usable_existing_private_features': len(systems),'selected_project_count':len(selected), 'matched_parcels': len(matches),
            'billing_attempts': len(targets), 'ranked_prospects': len(candidates), 'returned': min(limit, len(candidates)),
            'ambiguous_systems': held_codes.count('ambiguous_overlap'), 'parcel_not_queried_systems': held_codes.count('parcel_not_queried'),
            'no_parcel_found_systems': held_codes.count('no_parcel_found'), 'stale_billing_kept_after_failed_refresh': len(stale_kept),
            'failed_requests_or_geometry': len(failures), 'invalid_systems': len(invalid),
            'exclusions_by_status': {s: sum(e['status'] == s for e in exclusions) for s in sorted({e['status'] for e in exclusions})}},
        'groups': [{'id': key, 'label': label, 'count': sum(r['group'] == key for r in candidates[:limit])} for key, label in GROUPS.items()],
        'top': candidates[:limit], 'prospects': candidates, 'excluded': exclusions,
        'ambiguous_matches': ambiguous, 'invalid_systems': invalid, 'failures': failures,
        'retry_targets': sorted(retry_targets, key=lambda t: t['parcel_id']), 'stale_records_kept': stale_kept,
        'source_snapshots': inventory['sources']+parcel_sources+bill_sources,
        'source_layers': {'systems': SYSTEMS, 'parcels': PARCELS, 'billing': BILLING},
        'not_run': ['imagery', 'AI inference', 'DEM', 'drainage', 'full assessment', 'actual invoice validation', 'independent ownership/credit accuracy'],
    }
    finish_ranking(result,candidates,limit,as_of)
    # A run that lost ranked rows to source failures is kept as evidence but does
    # not replace the last good shortlist.
    previous = _latest_summary(root)
    degraded = previous is not None and result['status'] == 'partial' and len(candidates) < previous['ranked_parcels']
    result['promoted'] = not degraded
    if degraded:
        result['not_promoted_reason'] = (f"Partial run ranked {len(candidates)} parcels, fewer than the {previous['ranked_parcels']} "
                                         f"in saved run {previous['id']}; that run remains the latest shortlist.")
    result['elapsed_seconds']=round(time.perf_counter()-start,3)
    result['result_sha256']=sha256(canonical({k:v for k,v in result.items() if k!='result_sha256'})).hexdigest()
    if cancel and cancel.is_set():raise SourceError('Scan cancelled; previous results retained')
    if degraded:save_result(root, result, promote=False)
    else:save_result(root, result)
    # Saved: a cancel arriving now no longer changes the outcome, so it is not checked.
    if progress:progress(stage='complete', completed=len(candidates), total=len(candidates), run_id=result['id'], promoted=not degraded)
    return result


def _latest_summary(root):
    try:
        latest = load_result(root)
    except (OSError, ValueError, KeyError):
        return None
    if latest is None:
        return None
    rows = latest.get('parcel_rows') or [m for s in latest.get('prospects', []) for m in s.get('member_parcels', [s])]
    return {'id': latest['id'], 'ranked_parcels': len(rows)}


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


_GEOMETRY_ROWS = ('parcel_rows', 'prospects', 'top', 'retry_targets')


def _row_dicts(result):
    for key in _GEOMETRY_ROWS:
        for row in result.get(key) or []:
            yield row
            yield from row.get('member_parcels') or []


def compact_result(result):
    """Store each parcel geometry once (``parcel_geometries``) and reference it."""
    data = deepcopy(result)
    geometries, conflicts = {}, set()
    for row in _row_dicts(data):
        pid, geometry = row.get('parcel_id'), row.get('parcel_geometry')
        if pid is None or geometry is None:
            continue
        if geometries.setdefault(str(pid), geometry) != geometry:
            conflicts.add(str(pid))
    for row in _row_dicts(data):
        pid = str(row.get('parcel_id'))
        if row.get('parcel_geometry') is not None and pid in geometries and pid not in conflicts:
            row['parcel_geometry_ref'] = pid
            del row['parcel_geometry']
    data['parcel_geometries'] = {k: v for k, v in geometries.items() if k not in conflicts}
    return data


def expand_result(data):
    geometries = data.pop('parcel_geometries', None)
    if geometries is None:
        return data
    for row in _row_dicts(data):
        if 'parcel_geometry_ref' in row:
            row['parcel_geometry'] = geometries[row.pop('parcel_geometry_ref')]
    return data


def save_result(root, result, promote=True):
    folder = Path(root)/'runs'/result['id']
    folder.mkdir(parents=True, exist_ok=False)
    (folder/'results.json').write_bytes(canonical(compact_result(result))+b'\n')
    (folder/'top50.csv').write_text(csv_report(result))
    (folder/'report.html').write_text(html_report(result))
    if promote:
        # Unique temporary name, then an atomic replace: concurrent writers never share it.
        from drainage_core.saved import atomic_json
        atomic_json(Path(root)/'latest.json', {'id': result['id']})


def load_result(root, run_id=None):
    root = Path(root)
    if run_id is None:
        if not (root/'latest.json').exists():
            return None
        run_id = json.loads((root/'latest.json').read_text())['id']
    if not re.fullmatch('[a-f0-9]{32}', str(run_id)):
        raise ValueError('Invalid scan ID')
    result = expand_result(json.loads((root/'runs'/run_id/'results.json').read_text()))
    if result['result_sha256'] != sha256(canonical({k:v for k,v in result.items() if k != 'result_sha256'})).hexdigest():
        raise ValueError('Prospect result hash mismatch')
    return result


def public_result(result):
    if result is None:
        return None
    return {k:v for k,v in result.items() if k not in ('prospects','parcel_rows','excluded','ambiguous_matches','invalid_systems','source_snapshots','retry_targets')}


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
