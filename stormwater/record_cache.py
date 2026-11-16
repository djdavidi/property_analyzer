"""Shared public records, retaining original bytes and capture provenance."""
from datetime import datetime,timezone
from pathlib import Path
from urllib.parse import urlparse
from drainage_core.sources import Cache,SourceError

ROOT=Path(__file__).resolve().parents[1]


def record_age_limit(url):
    host=urlparse(url).hostname or ''
    if host=='stormwater.phila.gov' and '/PwdWebApi/api/v1/parcel/' in url:return 30
    if host.endswith('arcgis.com') and any(s in url for s in ('PWD_PARCELS/','GSI_SMP_TYPES/','GSI_Private_Projects_Retrofit/','LI_BUILDING_FOOTPRINTS/')):return 90
    if host=='echodata.epa.gov' and '/echo/' in url:return 30
    return None


def captured(value):
    try:
        value=datetime.fromisoformat(value.replace('Z','+00:00'))
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    except (AttributeError,TypeError,ValueError):return datetime.min.replace(tzinfo=timezone.utc)


class SharedCache(Cache):
    def __init__(self,root=None,*,fallback_roots=None,reuse_recent_records=False,**kw):
        root=Path(root or ROOT/'data/public')
        super().__init__(root,**kw)
        roots=[Path(p) for p in (fallback_roots if fallback_roots is not None else [ROOT/'data/prospects/public'])]
        self.fallbacks=[Cache(p,opener=self.opener,timeout=self.timeout,max_bytes=self.max_bytes) for p in roots if p!=root and p.exists()]
        self.reuse_recent_records=reuse_recent_records;self.reuse_events=[]

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

    def fetch_bytes(self,url,refresh=False,metadata=None):
        days=record_age_limit(url)
        if self.reuse_recent_records and days is not None:
            saved=self._read(url)
            if saved:
                age=(datetime.now(timezone.utc)-captured(saved[1].get('retrieved_at'))).total_seconds()/86400
                if 0<=age<=days:
                    self.reuse_events.append({'url':url,'sha256':saved[1]['sha256'],'retrieved_at':saved[1].get('retrieved_at'),'status':'reused_recent_record'})
                    return {'content':saved[0],'provenance':saved[1]}
        return super().fetch_bytes(url,refresh,metadata)


def shared_records(*,reuse_recent_records=False,timeout=20):
    return SharedCache(reuse_recent_records=reuse_recent_records,timeout=timeout)
