"""Jurisdiction-neutral, reproducible public-source caching and pagination."""
from __future__ import annotations
import hashlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlencode, urlparse
from urllib.request import Request, urlopen, build_opener, HTTPSHandler
import ssl

def now():
    return datetime.now(timezone.utc).isoformat()



def canonical(data):
    return json.dumps(data, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()



def _instant(value):
    """Comparable capture instant; undated or invalid captures sort oldest."""
    try:
        stamp = datetime.fromisoformat(str(value).replace('Z', '+00:00'))
        return stamp if stamp.tzinfo else stamp.replace(tzinfo=timezone.utc)
    except (TypeError, ValueError):
        return datetime.min.replace(tzinfo=timezone.utc)



class SourceError(RuntimeError):
    pass



def _atomic_write(path, data):
    """Unique same-folder temporary file, then os.replace; concurrent writers never share a temp."""
    import tempfile
    descriptor, temp = tempfile.mkstemp(dir=path.parent, prefix='.'+path.name+'.', suffix='.tmp')
    try:
        with os.fdopen(descriptor, 'wb') as stream:
            stream.write(data)
        os.replace(temp, path)
    except BaseException:
        try:
            os.unlink(temp)
        except FileNotFoundError:
            pass
        raise



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
        if opener is None:
            import certifi
            opener=build_opener(HTTPSHandler(context=ssl.create_default_context(cafile=certifi.where()))).open
        self.opener = opener
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

    def _store(self, url, content, metadata=None, retrieved_at=None, *, invalid=None):
        """Retain bytes and a history entry; only a usable response moves the manifest.

        ``invalid`` (a reason) keeps an HTTP-200 error body as dated evidence in
        history without replacing the last good current manifest.
        """
        sha = hashlib.sha256(content).hexdigest()
        info = {'url': url, 'retrieved_at': retrieved_at or now(),
                'acquisition_date': None, 'crs': None, 'horizontal_unit': None,
                'vertical_unit': None, 'resolution': None, 'sha256': sha,
                'bytes': len(content), **(metadata or {})}
        info.update({'url': url, 'sha256': sha, 'bytes':len(content)})
        if invalid:
            info['invalid_response'] = str(invalid)
        blob = self.root/'blobs'/sha
        # Content-addressed: an existing blob is reused only when its bytes verify.
        # A partial or corrupt blob (crash, concurrent writer) is repaired here.
        if not blob.exists() or hashlib.sha256(blob.read_bytes()).hexdigest() != sha:
            _atomic_write(blob, content)
        encoded = canonical(info)
        history = self.root/'history'/f'{self._key(url)}-{hashlib.sha256(encoded).hexdigest()}.json'
        if not history.exists():
            _atomic_write(history, encoded)
        if not invalid:
            _atomic_write(self.root/'manifests'/f'{self._key(url)}.json', encoded)
        return content, info

    def _problem(self, url, content):
        """Why bytes are not a usable JSON source response (None when usable).

        HTTP-200 bodies carrying an ``error`` member are source failures, not data.
        """
        try:
            data = json.loads(content)
        except (TypeError, ValueError) as exc:
            return f'response is not JSON: {exc}'
        if isinstance(data, dict) and data.get('error'):
            return 'source reported an error: '+str(data['error'])[:500]
        return None

    def _read_usable(self, url, problem=None):
        """Newest hash-verified capture that passes ``problem`` (a usable response).

        The manifest normally is that capture. A legacy manifest that points at an
        error body is skipped for the last good dated capture kept in history.
        """
        problem = problem or self._problem
        saved = self._read(url)
        if saved and problem(url, saved[0]) is None:
            return saved
        best = None
        for path in (self.root/'history').glob(f'{self._key(url)}-*.json'):
            try:
                info = json.loads(path.read_text())
                if info.get('url') != url or info.get('invalid_response'):
                    continue
                content = (self.root/'blobs'/info['sha256']).read_bytes()
            except (OSError, ValueError, KeyError, TypeError):
                continue
            if hashlib.sha256(content).hexdigest() != info['sha256'] or problem(url, content) is not None:
                continue
            if best is None or _instant(info.get('retrieved_at')) > _instant(best[1].get('retrieved_at')):
                best = (content, info)
        return best

    def _log_failure(self, url, error):
        with (self.root/'failures.jsonl').open('a') as stream:
            stream.write(json.dumps({'url':url,'attempted_at':now(),'error':str(error)})+'\n')

    def fetch_bytes(self, url, refresh=False, metadata=None, *, check=None):
        """Replay or fetch bytes. ``check(url, content)`` returns why a response is
        unusable; such a response is kept as history only and raises SourceError."""
        parsed = urlparse(url)
        if parsed.scheme != 'https' or not parsed.hostname or parsed.username:
            raise SourceError('Only credential-free HTTPS public sources are supported')
        if not refresh:
            saved = self._read_usable(url, check) if check else self._read(url)
            if saved:
                return {'content': saved[0], 'provenance': saved[1]}
        try:
            request = Request(url, headers={'User-Agent':'DrainageGISLocal/1.0'})
            with self.opener(request, timeout=self.timeout) as response:
                content = response.read(self.max_bytes+1)
            if len(content) > self.max_bytes:
                raise SourceError('Source exceeds bounded-download limit')
        except Exception as exc:
            self._log_failure(url, exc)
            raise SourceError(f'Public source unavailable: {url}: {exc}') from exc
        reason = check(url, content) if check else None
        content, info = self._store(url, content, metadata, invalid=reason)
        if reason:
            # Invalid responses remain preserved for evidence, never become data
            # and never replace the last good capture.
            self._log_failure(url, reason)
            raise SourceError(f'Invalid source response: {url}: {reason}')
        return {'content': content, 'provenance': info}

    def fetch_json(self, url, refresh=False, metadata=None):
        item = self.fetch_bytes(url, refresh, metadata, check=self._problem)
        return {'data': json.loads(item['content']), 'provenance': item['provenance']}

    def import_json(self, url, data, *, retrieved_at, metadata=None):
        _, info = self._store(url, canonical(data), metadata, retrieved_at)
        return {'data':data, 'provenance':info}

    def post_json(self, url, payload, refresh=False, metadata=None):
        """Cache a read-only public query by endpoint and exact request body.

        Original response bytes and the request are retained, including invalid
        responses. A failed refresh can reuse a hash-checked dated response.
        """
        parsed=urlparse(url)
        if parsed.scheme!='https' or not parsed.hostname or parsed.username or parsed.password:
            raise SourceError('Only credential-free HTTPS public sources are supported')
        body=canonical(payload)
        if len(body)>128*1024:raise SourceError('Public query exceeds request limit')
        key=url+'#request-sha256='+hashlib.sha256(body).hexdigest()
        info={**(metadata or {}),'request_url':url,'request_method':'POST','request':payload,
              'request_sha256':hashlib.sha256(body).hexdigest()}
        def problem(_url,content):
            reason=self._problem(_url,content)
            if reason is None and not isinstance(json.loads(content),dict):
                reason='expected a JSON object'
            return reason
        saved=self._read_usable(key,problem)
        if saved and not refresh:
            content,provenance=saved
        else:
            try:
                req=Request(url,data=body,headers={'Content-Type':'application/json','User-Agent':'DrainageGISLocal/1.0'})
                with self.opener(req,timeout=self.timeout) as response:content=response.read(self.max_bytes+1)
                if len(content)>self.max_bytes:raise SourceError('Source exceeds bounded-download limit')
                reason=problem(key,content)
                content,provenance=self._store(key,content,info,invalid=reason)
                if reason:raise SourceError('Invalid public query response: '+reason)
            except Exception as exc:
                self._log_failure(key,exc)
                if not saved:raise SourceError(f'Public query unavailable: {exc}') from exc
                content,provenance=saved
                provenance={**provenance,'cache_reused_after_failure':True,'refresh_error':str(exc),'refresh_failed_at':now()}
        data=json.loads(content)
        return {'data':data,'provenance':provenance}



def arcgis_features(layer, cache, params=None, refresh=False, page_size=1000, max_pages=100):
    """Fetch an entire stable-ID ordered bounded ArcGIS result, reject truncation.

    Uses standard JSON features rather than service Shape__Area fields. Offset
    pagination advances by the records actually received, so a service whose
    maxRecordCount is below ``page_size`` cannot silently skip rows. Repeated
    IDs, a truncated page without progress, contradictory or undeclared CRS
    geometry and the page limit are source failures.
    """
    settings = {'where':'1=1', 'outFields':'*', 'returnGeometry':'true',
                'outSR':'4326','f':'geojson', **(params or {})}
    requested_crs=_crs_metadata(settings['outSR'])
    if requested_crs['crs'].startswith('EPSG:'):
        settings['outSR']=requested_crs['crs'].split(':',1)[1]
    features, sources, seen = [], [], set()
    offset = 0
    for page in range(max_pages):
        query = {**settings, 'resultOffset':offset, 'resultRecordCount':page_size,
                 'orderByFields':settings.get('orderByFields','objectid ASC')}
        item = cache.fetch_json(layer+'/query?'+urlencode(query), refresh,
                                requested_crs)
        data = item['data']
        declared=data.get('crs') or data.get('spatialReference')
        if declared:
            if isinstance(declared,dict):
                declared=(declared.get('properties',{}).get('name') or declared.get('latestWkid') or declared.get('wkid') or declared.get('wkt'))
            if not crs_from_declaration(declared).equals(crs_from_declaration(requested_crs['crs']),ignore_axis_order=True):
                raise SourceError('ArcGIS response CRS contradicts requested CRS')
        batch = data.get('features')
        if not isinstance(batch, list):
            raise SourceError('ArcGIS response has no feature list')
        if not declared and batch:
            _check_undeclared_geometry(batch, requested_crs['crs'], settings)
        sources.append(item['provenance'])
        for feature in batch:
            attrs = feature.get('properties', feature.get('attributes',{})) or {}
            oid = feature.get('id', attrs.get('objectid',attrs.get('OBJECTID')))
            if oid is None:
                oid = hashlib.sha256(canonical(feature)).hexdigest()
            if oid in seen:
                raise SourceError('ArcGIS pagination repeated a feature; completeness unknown')
            seen.add(oid)
            features.append(feature)
        exceeded = data.get('exceededTransferLimit', (data.get('properties') or {}).get('exceededTransferLimit', False))
        if not batch:
            if exceeded:
                raise SourceError('ArcGIS truncation with no pagination progress')
            return {'type':'FeatureCollection','features':features, 'sources':sources, 'crs':requested_crs['crs']}
        if not exceeded and len(batch)<page_size:
            return {'type':'FeatureCollection','features':features, 'sources':sources, 'crs':requested_crs['crs']}
        # Advance by what the service actually returned (its own page cap may be lower).
        offset += len(batch)
    raise SourceError('ArcGIS page limit reached; result incomplete')



def crs_from_declaration(value):
    """CRS from an EPSG/ESRI code, name or WKT; unparseable declarations are SourceError.

    ArcGIS may report ESRI-only codes (e.g. ``102729`` for PA South ftUS), which
    are not EPSG codes. Those are resolved in the ESRI authority instead.
    """
    from pyproj import CRS
    from pyproj.exceptions import CRSError
    if value is None or isinstance(value, bool):
        raise SourceError('Missing source CRS declaration')
    text = str(value).strip()
    code = text.split(':', 1)[1] if text.upper().startswith(('EPSG:', 'ESRI:')) else text
    candidates = [text] if not code.isdigit() else [f'EPSG:{code}', f'ESRI:{code}']
    for candidate in candidates:
        try:
            return CRS.from_user_input(candidate)
        except (CRSError, TypeError, ValueError):
            continue
    raise SourceError(f'Unrecognized source CRS declaration: {text[:80]}')



def _coordinates(geometry):
    """Yield (x, y) pairs from GeoJSON or ArcGIS JSON geometry."""
    if not isinstance(geometry, dict):
        return
    if 'x' in geometry and 'y' in geometry:
        yield float(geometry['x']), float(geometry['y'])
        return
    for part in geometry.get('geometries') or []:
        yield from _coordinates(part)
    stack = [geometry[key] for key in ('coordinates', 'rings', 'paths', 'points') if geometry.get(key) is not None]
    while stack:
        item = stack.pop()
        if isinstance(item, (list, tuple)):
            if len(item) >= 2 and all(isinstance(v, (int, float)) and not isinstance(v, bool) for v in item[:2]):
                yield float(item[0]), float(item[1])
            else:
                stack.extend(item)


def _query_bounds(settings):
    """Bounds of the query's spatial filter when it was sent in the output CRS."""
    geometry = settings.get('geometry')
    if geometry is None or str(settings.get('inSR', '')) != str(settings.get('outSR')):
        return None
    try:
        value = json.loads(geometry) if isinstance(geometry, str) else geometry
    except ValueError:
        value = geometry
    if isinstance(value, dict) and all(k in value for k in ('xmin', 'ymin', 'xmax', 'ymax')):
        return tuple(float(value[k]) for k in ('xmin', 'ymin', 'xmax', 'ymax'))
    if isinstance(value, dict):
        points = list(_coordinates(value))
    else:
        try:
            numbers = [float(v) for v in str(value).split(',')]
        except ValueError:
            return None
        points = [tuple(numbers[i:i+2]) for i in range(0, len(numbers)-1, 2)] if len(numbers) in (2, 4) else []
    if not points:
        return None
    return (min(x for x, _ in points), min(y for _, y in points), max(x for x, _ in points), max(y for _, y in points))


def _check_undeclared_geometry(batch, requested, settings):
    """A GeoJSON body without a ``crs`` member is RFC 7946 lon/lat unless shown otherwise.

    ArcGIS declares the CRS for non-4326 output. When it does not, returned
    coordinates must intersect the query's spatial filter (sent in that CRS),
    and lon/lat-looking coordinates inside the requested CRS's area of use are
    rejected rather than relabelled.
    """
    crs = crs_from_declaration(requested)
    if crs.is_geographic:
        return
    points = [xy for feature in batch for xy in _coordinates(feature.get('geometry'))]
    if not points:
        return
    xs, ys = [x for x, _ in points], [y for _, y in points]
    bounds = (min(xs), min(ys), max(xs), max(ys))
    query = _query_bounds(settings)
    if query is not None:
        pad = max(query[2]-query[0], query[3]-query[1])*.01+1
        if bounds[0] > query[2]+pad or bounds[2] < query[0]-pad or bounds[1] > query[3]+pad or bounds[3] < query[1]-pad:
            raise SourceError(f'ArcGIS response has no CRS member and its geometry misses the {requested} query geometry')
    area = crs.area_of_use
    if area is not None and area.west-1 <= bounds[0] and bounds[2] <= area.east+1 and area.south-1 <= bounds[1] and bounds[3] <= area.north+1:
        raise SourceError(f'ArcGIS response has no CRS member and its coordinates are lon/lat for the {requested} area, not {requested}')



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
    crs=crs_from_declaration(value)
    unit=crs.axis_info[0].unit_name if crs.axis_info else None
    units={'metre':'m','foot':'ft','US survey foot':'us-ft','degree':'degree'}
    return {'crs':crs.to_string(),'horizontal_unit':units.get(unit,unit)}
