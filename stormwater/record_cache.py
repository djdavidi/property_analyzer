"""Shared public records, retaining original bytes and capture provenance."""
from datetime import datetime,timezone
import json
from pathlib import Path
from urllib.parse import urlparse
from drainage_core.sources import Cache,SourceError

ROOT=Path(__file__).resolve().parents[1]


def record_age_limit(url):
    host=urlparse(url).hostname or ''
    if host=='stormwater.phila.gov' and '/PwdWebApi/api/v1/parcel/' in url:return 30
    if host.endswith('arcgis.com') and any(s in url for s in ('PWD_PARCELS/','GSI_SMP_TYPES/','GSI_Private_Projects_Retrofit/','LI_BUILDING_FOOTPRINTS/','INLETS/')):return 90
    if host=='echodata.epa.gov' and '/echo/' in url:return 30
    return None


def captured(value):
    try:
        value=datetime.fromisoformat(value.replace('Z','+00:00'))
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    except (AttributeError,TypeError,ValueError):return datetime.min.replace(tzinfo=timezone.utc)


def billing_problem(url,content):
    """PWD parcel details report service failures inside an HTTP-200 body."""
    if (urlparse(url).hostname or '')!='stormwater.phila.gov' or '/PwdWebApi/api/v1/parcel/' not in url:return None
    try:data=json.loads(content)
    except (TypeError,ValueError):return None
    summary=data.get('ChargeSummary') if isinstance(data,dict) else None
    if isinstance(summary,dict) and summary.get('Errors'):
        return 'public billing service reported errors: '+str(summary['Errors'])[:300]
    return None


class SharedCache(Cache):
    """Primary cache plus read-only legacy roots, with per-record age limits.

    Within its age limit a record may be reused (``reuse_recent_records``). Past
    the limit it is fetched again while the record age policy is active
    (``reuse_recent_records``). If that fetch fails, or the policy is inactive
    and no refresh was requested, an expired record is reused only with an
    explicit ``reuse_events`` entry; it is never reused silently.
    """
    def __init__(self,root=None,*,fallback_roots=None,reuse_recent_records=False,**kw):
        root=Path(root or ROOT/'data/public')
        super().__init__(root,**kw)
        roots=[Path(p) for p in (fallback_roots if fallback_roots is not None else [ROOT/'data/prospects/public'])]
        self.fallbacks=[Cache(p,opener=self.opener,timeout=self.timeout,max_bytes=self.max_bytes) for p in roots if p!=root and p.exists()]
        self.reuse_recent_records=reuse_recent_records;self.reuse_events=[]

    def _problem(self,url,content):
        return super()._problem(url,content) or billing_problem(url,content)

    def _read(self,url):
        primary=super()._read(url);found=[primary] if primary else []
        for cache in self.fallbacks:
            item=cache._read(url)
            if item:found.append(item)
        if not found:return None
        chosen=max(found,key=lambda x:captured(x[1].get('retrieved_at')))
        if primary is None or chosen[1]!=primary[1]:
            # Promotion changes neither source bytes nor its recorded capture time.
            self._store(url,chosen[0],chosen[1],retrieved_at=chosen[1].get('retrieved_at'))
        return chosen

    def _read_usable(self,url,problem=None):
        problem=problem or self._problem
        found=[x for x in [super()._read_usable(url,problem),*(c._read_usable(url,problem) for c in self.fallbacks)] if x]
        return max(found,key=lambda x:captured(x[1].get('retrieved_at'))) if found else None

    def fetch_bytes(self,url,refresh=False,metadata=None,*,check=None):
        days=record_age_limit(url)
        if days is None:return super().fetch_bytes(url,refresh,metadata,check=check)
        saved=self._read_usable(url,check) if check else self._read(url)
        age=None
        if saved:
            age=(datetime.now(timezone.utc)-captured(saved[1].get('retrieved_at'))).total_seconds()/86400
            if 0<=age<=days:
                if self.reuse_recent_records:
                    self.reuse_events.append({'url':url,'sha256':saved[1]['sha256'],'retrieved_at':saved[1].get('retrieved_at'),'status':'reused_recent_record'})
                    return {'content':saved[0],'provenance':saved[1]}
                if not refresh:return {'content':saved[0],'provenance':saved[1]}
            elif not refresh and not self.reuse_recent_records:
                # Record policy inactive and no refresh requested: reuse, but explicitly.
                self.reuse_events.append(self._expired_event(url,saved,age,days,'reused_expired_record',None))
                return {'content':saved[0],'provenance':saved[1]}
        try:
            # An expired or undated record is refreshed instead of silently replayed.
            return super().fetch_bytes(url,True if saved else refresh,metadata,check=check)
        except SourceError as exc:
            if not saved or refresh:raise
            self.reuse_events.append(self._expired_event(url,saved,age,days,'reused_expired_record_after_failure',exc))
            return {'content':saved[0],'provenance':{**saved[1],'record_age_limit_exceeded':True,
                    'cache_reused_after_failure':True,'refresh_error':str(exc)}}

    @staticmethod
    def _expired_event(url,saved,age,days,status,error):
        return {'url':url,'sha256':saved[1]['sha256'],'retrieved_at':saved[1].get('retrieved_at'),'status':status,
                'age_days':None if age is None or age<0 or age>36500 else round(age,1),'max_age_days':days,
                **({'error':str(error)} if error else {}),
                'claim':'Record is past its age limit; reused as a dated observation, not current evidence.'}


def shared_records(*,reuse_recent_records=False,timeout=20):
    return SharedCache(reuse_recent_records=reuse_recent_records,timeout=timeout)
