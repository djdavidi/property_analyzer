"""Jurisdiction-neutral, reproducible public-source caching and pagination."""
from __future__ import annotations
import hashlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlencode, urlparse
from urllib.request import Request, urlopen

def now():
    return datetime.now(timezone.utc).isoformat()



def canonical(data):
    return json.dumps(data, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()



class SourceError(RuntimeError):
    pass



class Cache:
    """URL manifests point at immutable SHA256 blobs; explicit refresh creates history.

    ``fetch_json`` accepts metadata values, never infers acquisition dates from
    retrieval time. ``import_json`` preserves the original observation timestamp.
    An injected opener makes failure/replay tests independent of the network.
    """
    def __init__(self, root, opener=None, timeout=20, max_bytes=64*1024*1024):
        self.root = Path(root)
        for name in ('blobs', 'manifests', 'history'):
            (self.root/name).mkdir(parents=True, exist_ok=True)
        self.opener = opener or urlopen
        self.timeout = timeout
        self.max_bytes = max_bytes

    def _key(self, url):
        return hashlib.sha256(url.encode()).hexdigest()

    def _read(self, url):
        manifest = self.root/'manifests'/f'{self._key(url)}.json'
        if not manifest.exists():
            return None
        info = json.loads(manifest.read_text())
        path = self.root/'blobs'/info['sha256']
        content = path.read_bytes()
        if hashlib.sha256(content).hexdigest() != info['sha256']:
            raise SourceError('Cached source failed SHA256 verification')
        return content, info

    def _store(self, url, content, metadata=None, retrieved_at=None):
        sha = hashlib.sha256(content).hexdigest()
        info = {'url': url, 'retrieved_at': retrieved_at or now(),
                'acquisition_date': None, 'crs': None, 'horizontal_unit': None,
                'vertical_unit': None, 'resolution': None, 'sha256': sha,
                'bytes': len(content), **(metadata or {})}
        info.update({'url': url, 'sha256': sha, 'bytes':len(content)})
        blob = self.root/'blobs'/sha
        if not blob.exists():
            blob.write_bytes(content)
        encoded = canonical(info)
        (self.root/'history'/f'{self._key(url)}-{hashlib.sha256(encoded).hexdigest()}.json').write_bytes(encoded)
        manifest = self.root/'manifests'/f'{self._key(url)}.json'
        temp = manifest.with_suffix('.tmp')
        temp.write_bytes(encoded)
        os.replace(temp, manifest)
        return content, info

    def fetch_bytes(self, url, refresh=False, metadata=None):
        parsed = urlparse(url)
        if parsed.scheme != 'https' or not parsed.hostname or parsed.username:
            raise SourceError('Only credential-free HTTPS public sources are supported')
        if not refresh:
            saved = self._read(url)
            if saved:
                return {'content': saved[0], 'provenance': saved[1]}
        try:
            request = Request(url, headers={'User-Agent':'DrainageGISLocal/1.0'})
            with self.opener(request, timeout=self.timeout) as response:
                content = response.read(self.max_bytes+1)
            if len(content) > self.max_bytes:
                raise SourceError('Source exceeds bounded-download limit')
            content, info = self._store(url, content, metadata)
            return {'content': content, 'provenance': info}
        except Exception as exc:
            with (self.root/'failures.jsonl').open('a') as stream:
                stream.write(json.dumps({'url':url,'attempted_at':now(),'error':str(exc)})+'\n')
            raise SourceError(f'Public source unavailable: {url}: {exc}') from exc

    def fetch_json(self, url, refresh=False, metadata=None):
        item = self.fetch_bytes(url, refresh, metadata)
        try:
            data = json.loads(item['content'])
            if isinstance(data, dict) and data.get('error'):
                raise SourceError(str(data['error']))
        except (ValueError, SourceError) as exc:
            # Invalid responses remain preserved for evidence, never become empty data.
            raise SourceError(f'Invalid source response: {url}: {exc}') from exc
        return {'data': data, 'provenance': item['provenance']}

    def import_json(self, url, data, *, retrieved_at, metadata=None):
        _, info = self._store(url, canonical(data), metadata, retrieved_at)
        return {'data':data, 'provenance':info}



def arcgis_features(layer, cache, params=None, refresh=False, page_size=1000, max_pages=100):
    """Fetch an entire stable-ID ordered bounded ArcGIS result, reject truncation.

    Uses standard JSON features rather than service Shape__Area fields. Supports
    offset pagination; repeated IDs/no-progress pages are source failures.
    """
    settings = {'where':'1=1', 'outFields':'*', 'returnGeometry':'true',
                'outSR':'4326','f':'geojson', **(params or {})}
    requested_crs=_crs_metadata(settings['outSR'])
    if requested_crs['crs'].startswith('EPSG:'):
        settings['outSR']=requested_crs['crs'].split(':',1)[1]
    features, sources, seen = [], [], set()
    for page in range(max_pages):
        query = {**settings, 'resultOffset':page*page_size, 'resultRecordCount':page_size,
                 'orderByFields':settings.get('orderByFields','objectid ASC')}
        item = cache.fetch_json(layer+'/query?'+urlencode(query), refresh,
                                requested_crs)
        data = item['data']
        batch = data.get('features')
        if not isinstance(batch, list):
            raise SourceError('ArcGIS response has no feature list')
        sources.append(item['provenance'])
        for feature in batch:
            attrs = feature.get('properties', feature.get('attributes',{}))
            oid = feature.get('id', attrs.get('objectid',attrs.get('OBJECTID')))
            if oid is None:
                oid = hashlib.sha256(canonical(feature)).hexdigest()
            if oid in seen:
                raise SourceError('ArcGIS pagination repeated a feature; completeness unknown')
            seen.add(oid)
            features.append(feature)
        exceeded = data.get('exceededTransferLimit', data.get('properties',{}).get('exceededTransferLimit', False))
        if not exceeded and len(batch)<page_size:
            return {'type':'FeatureCollection','features':features, 'sources':sources, 'crs':requested_crs['crs']}
        if not batch:
            if exceeded:
                raise SourceError('ArcGIS truncation with no pagination progress')
            return {'type':'FeatureCollection','features':features, 'sources':sources, 'crs':requested_crs['crs']}
    raise SourceError('ArcGIS page limit reached; result incomplete')



def quality_checks(sources, *, expected_crs=None, construction_completed=None):
    """Non-destructive diagnostics: unknown metadata is not a passing check."""
    warnings=[]
    dates=[]
    for item in sources:
        label=item.get('url',item.get('path','source'))
        for flag in item.get('quality_flags',[]):
            warnings.append(f'{label}: {flag}')
        for field in ['acquisition_date','crs','horizontal_unit']:
            if item.get(field) is None:
                warnings.append(f'{label}: {field} unknown')
        if expected_crs and item.get('crs') not in (None,expected_crs):
            warnings.append(f'{label}: coordinate transform required from {item["crs"]} to {expected_crs}')
        date=item.get('acquisition_date')
        if date:
            dates.append(date)
            if construction_completed and date < construction_completed:
                warnings.append(f'{label}: predates final construction; unsuitable for as-built validation')
    if len(set(dates))>1:
        warnings.append('Source acquisition dates differ; verify no intervening site changes')
    return warnings



def _crs_metadata(value):
    """Describe the explicitly requested source CRS without region-specific defaults."""
    from pyproj import CRS
    crs=CRS.from_user_input(value)
    unit=crs.axis_info[0].unit_name if crs.axis_info else None
    units={'metre':'m','foot':'ft','US survey foot':'us-ft','degree':'degree'}
    return {'crs':crs.to_string(),'horizontal_unit':units.get(unit,unit)}
