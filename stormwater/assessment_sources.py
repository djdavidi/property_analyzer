"""Best effort public candidates; discovery never confirms installations or permits."""
from copy import deepcopy
from hashlib import sha256
import json
from urllib.parse import urlencode

from drainage_core.sources import SourceError, arcgis_features, now

CITY='https://services.arcgis.com/fLeGjb7u4uXqeF9q/ArcGIS/rest/services'
SYSTEMS=CITY+'/GSI_SMP_TYPES/FeatureServer/0'
RETROFITS=CITY+'/GSI_Private_Projects_Retrofit/FeatureServer/0'
ECHO='https://echodata.epa.gov/echo/cwa_rest_services.'
PWD='https://stormwater.phila.gov/PwdWebApi/api/v1/parcel'


def digest(value):
    return sha256(json.dumps(value,sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest()


class _Fallback:
    """Outage fallback to the last good dated response (never to an error body)."""
    def __init__(self,cache):
        self.cache=cache;self.failures=[];self.used_cache=False;self.reused_recent=False;self.reused_expired=False

    def _saved(self,url):
        reader=getattr(self.cache,'_read_usable',None) or getattr(self.cache,'_read',None)
        return reader(url) if reader else None

    def fetch_json(self,url,refresh=False,metadata=None):
        try:
            events=getattr(self.cache,'reuse_events',[]);before=len(events) if isinstance(events,list) else 0
            result=self.cache.fetch_json(url,refresh,metadata)
            new=[e.get('status') for e in getattr(self.cache,'reuse_events',[])[before:]] if isinstance(events,list) else []
            self.reused_recent='reused_recent_record' in new
            if any(str(s).startswith('reused_expired_record') for s in new):
                self.reused_expired=True;self.used_cache=True
                self.failures.extend(str(e.get('error') or e.get('claim')) for e in self.cache.reuse_events[before:] if e.get('error') or e.get('claim'))
            return result
        except Exception as exc:
            saved=self._saved(url)
            self.failures.append(str(exc))
            if not saved: raise
            data=json.loads(saved[0])
            if not isinstance(data,dict) or data.get('error'): raise SourceError('Cached response is invalid')
            self.used_cache=True
            return {'data':data,'provenance':{**saved[1],'cache_reused_after_failure':True,
                                            'refresh_failed_at':now(),'refresh_error':str(exc)}}

    def fetch_bytes(self,url,refresh=False,metadata=None):
        try:return self.cache.fetch_bytes(url,refresh,metadata)
        except Exception as exc:
            saved=self.cache._read(url) if hasattr(self.cache,'_read') else None
            self.failures.append(str(exc))
            if not saved:raise
            self.used_cache=True
            return {'content':saved[0],'provenance':{**saved[1],'cache_reused_after_failure':True,
                    'refresh_failed_at':now(),'refresh_error':str(exc)}}


def _status(provider,url,proxy,*,count=None,error=None):
    return {'provider':provider,'url':url,'attempted_at':now(),
            'status':'unavailable' if error else 'cached_after_failure' if proxy.used_cache else 'reused_recent_record' if proxy.reused_recent else 'retrieved',
            'candidate_count':count,'errors':([str(error)] if error else proxy.failures),
            'coverage':'Candidates only. No match is not evidence of absence or eligibility.'}


def normalize_gsi(feature,source,crs,kind='system'):
    """Project points and SMP polygons nominate candidates; area is never inferred."""
    p={str(k).lower():v for k,v in feature.get('properties',feature.get('attributes',{})).items()}
    text=str(p.get('gsi_system_type','')).lower()
    def flag(key):
        value=p.get(key)
        return value is True or isinstance(value,(int,float)) and value!=0 or isinstance(value,str) and value.strip().lower() in ('true','yes','1','-1')
    categories=[]
    if 'green roof' in text or flag('green_roof') or flag('smp_greenroof'): categories.append('green_roof')
    if any(word in text for word in ('porous','pervious paving','permeable')) or flag('porous_pavement') or flag('smp_perviouspaving'): categories.append('permeable_pavement')
    if 'direct discharge' in text: categories.append('direct_discharge')
    state=str(p.get('status',p.get('overallstatuscategory',p.get('project_type','unknown'))))
    proposed=any(word in state.lower() for word in ('propos','upcoming','design','plan'))
    oid=feature.get('id',p.get('objectid',digest(feature)[:20]))
    output=[]
    for category in categories:
        identity='public-'+digest([source,oid,category])[:28]
        output.append({'id':identity,'category':category,'decision':'candidate','basis':'public_candidate',
                       'label':p.get('projectname',p.get('name',p.get('gsi_system_id',str(oid)))),
                       'facts':{'public_status':state,'proposed_only':proposed,
                                'installed':None,'public_year_installed':p.get('year_installed')},
                       'source':{'url':source,'record_id':str(oid),'crs':crs,
                                 'acquisition_date':None,'publication_date':None,'effective_date':None},
                       'evidence_refs':[{'source_url':source,'record_id':str(oid)}],
                       'public_geometry':deepcopy(feature.get('geometry')),
                       'public_geometry_role':'project location' if kind=='project' else 'system footprint, not managed catchment',
                       'managed_area_sqft':None,'physical_footprint_sqft':None,
                       'missing_evidence':['Parcel/site match review','Existing installation and condition',
                                           'Documented footprint and drainage served','Treatment and maintenance records'],
                       'raw_record':deepcopy(p)})
    return output


def normalize_permit(row,url,identifiers):
    pid=row.get('SourceID',row.get('NPDESIDs'))
    if not pid: raise SourceError('Permit result lacks identifier')
    requested=str(identifiers.get('permit_id','')).strip().upper()
    exact=bool(requested and requested==str(pid).upper())
    # Source search identity, industrial coverage and compliance are distinct facts.
    return {'id':'epa-'+digest(str(pid))[:28],'category':'industrial_npdes',
            'decision':'candidate','basis':'public_candidate','label':row.get('CWPName',str(pid)),
            'facts':{'permit_id':str(pid),'public_facility_name':row.get('CWPName'),
                     'public_street_address':row.get('CWPStreet'),
                     'public_master_permit_id':row.get('MasterExternalPermitNmbr'),
                     'identifier_exact_match':exact,'site_match':None,'operator_match':None,
                     'active':None,'industrial_stormwater':None,'compliance_confirmed':None},
            'evidence_refs':[{'source_url':url,'record_id':str(pid)}],
            'source':{'url':url,'record_id':str(pid),'acquisition_date':None,
                      'publication_date':None,'effective_date':None},
            'missing_evidence':['Site and operator identity','Applicable active industrial stormwater coverage',
                                'Current permit documents and required compliance evidence'],
            'raw_record':deepcopy(row)}


def discover(case,cache,refresh=True):
    """One explicitly initiated bounded read of City/PWD/EPA public records.

    Raw bytes/hash/retrieval time live in Cache. Empty successful queries report
    limited coverage. Outages preserve prior observations via workflow.gather.
    """
    from shapely.geometry import shape
    from shapely.ops import transform
    from pyproj import Transformer
    records=[];observations=[];sources=[];statuses=[]
    parcel=shape(case['parcel']); crs=case['crs']
    # A small surrounding envelope intentionally includes ambiguous adjacent matches.
    # Candidates require parcel/site review; it is never treated as a managed region.
    minx,miny,maxx,maxy=parcel.bounds
    pad=max(maxx-minx,maxy-miny)*.05
    query={'geometry':','.join(map(str,(minx-pad,miny-pad,maxx+pad,maxy+pad))),
           'geometryType':'esriGeometryEnvelope','inSR':crs.split(':')[-1],
           'spatialRel':'esriSpatialRelIntersects','outSR':crs.split(':')[-1]}
    for label,layer,kind in [('City GSI systems',SYSTEMS,'system'),('City retrofit projects',RETROFITS,'project')]:
        proxy=_Fallback(cache)
        try:
            response=arcgis_features(layer,proxy,query,refresh,page_size=1000,max_pages=5)
            sources.extend(response['sources']); found=[]
            for feature in response['features']:
                found.extend(normalize_gsi(feature,layer,response['crs'],kind))
            for record in found:
                record['source_snapshots']=deepcopy(response['sources'])
            records.extend(found)
            observations.append({'provider':label,'url':layer,'records':deepcopy(found),
                                 'source_sha256':[s.get('sha256') for s in response['sources']],
                                 'retrieved_at':[s.get('retrieved_at') for s in response['sources']]})
            statuses.append(_status(label,layer,proxy,count=len(found)))
        except Exception as exc: statuses.append(_status(label,layer,proxy,error=exc))
    identifiers=(case.get('assessment') or {}).get('identifiers',{})
    params={'output':'JSON','responseset':100,'p_st':'PA'}
    if identifiers.get('permit_id'): params['p_pid']=str(identifiers['permit_id'])
    elif identifiers.get('operator_name'): params['p_fn']=str(identifiers['operator_name'])
    elif identifiers.get('site_name'): params['p_fn']=str(identifiers['site_name'])
    elif identifiers.get('street_address') or case.get('address'):
        params.update(p_sa=str(identifiers.get('street_address') or case['address']),p_ct='Philadelphia')
    else:
        ll=transform(Transformer.from_crs(crs,'EPSG:4326',always_xy=True).transform,parcel)
        west,south,east,north=ll.bounds
        params.update(p_c1lat=south-.001,p_c1lon=west-.001,p_c2lat=north+.001,p_c2lon=east+.001)
    url=ECHO+'get_facilities?'+urlencode(params);proxy=_Fallback(cache)
    try:
        item=proxy.fetch_json(url,refresh);sources.append(item['provenance'])
        result=item['data'].get('Results',{})
        if result.get('Error'): raise SourceError(str(result['Error']))
        count=int(result.get('QueryRows','-1'))
        if count<0: raise SourceError('EPA response does not establish a result count')
        if count>100: raise SourceError('EPA search has more than 100 ambiguous matches; supply permit/site/operator identifiers')
        rows=result.get('Facilities')
        row_provenance=item['provenance']
        row_url=url
        if count and rows is None:
            qid=result.get('QueryID')
            if not qid or not str(qid).isdigit(): raise SourceError('EPA response lacks query identifier')
            row_url=ECHO+'get_qid?'+urlencode({'output':'JSON','qid':qid,'pageno':1,'responseset':100})
            page=proxy.fetch_json(row_url,refresh);sources.append(page['provenance'])
            rows=page['data'].get('Results',{}).get('Facilities')
            row_provenance=page['provenance']
        rows=rows or []
        if len(rows)!=count: raise SourceError('EPA response incomplete; facility count does not match rows')
        found=[normalize_permit(row,row_url,identifiers) for row in rows]
        for record in found:
            record['source_snapshots']=[deepcopy(item['provenance']),deepcopy(row_provenance)] if row_url!=url else [deepcopy(row_provenance)]
        records.extend(found)
        observations.append({'provider':'EPA NPDES','url':url,'records':deepcopy(found),
                             'source_sha256':row_provenance.get('sha256'),
                             'retrieved_at':row_provenance.get('retrieved_at')})
        statuses.append(_status('EPA NPDES',url,proxy,count=count))
    except Exception as exc: statuses.append(_status('EPA NPDES',url,proxy,error=exc))
    parcel_id=identifiers.get('pwd_parcel_id') or case.get('parcel_id')
    if not parcel_id and str(case.get('id','')).startswith('pwd-'):
        candidate=str(case['id'])[4:].split('-')[0]
        if candidate.isdigit(): parcel_id=candidate
    if parcel_id and str(parcel_id).isdigit():
        url=f'{PWD}/{int(parcel_id)}/details';proxy=_Fallback(cache)
        try:
            item=proxy.fetch_json(url,refresh);sources.append(item['provenance'])
            observations.append({'provider':'PWD account/credit public record','url':url,
                                 'source_sha256':item['provenance'].get('sha256'),
                                 'retrieved_at':item['provenance'].get('retrieved_at'),
                                 'raw_record':deepcopy(item['data']),
                                 'interpretation':'Public flags/totals are observations, not award letters, renewal dates, bills or refund entitlement.'})
            statuses.append(_status('PWD account/credit public record',url,proxy,count=None))
        except Exception as exc: statuses.append(_status('PWD account/credit public record',url,proxy,error=exc))
    else:
        statuses.append({'provider':'PWD account/credit public record','status':'missing_identifier',
                         'candidate_count':None,'coverage':'Supply PWD parcel identifier; no credit history absence inferred.'})
    return {'records':records,'observations':observations,'sources':sources,'source_status':statuses}
