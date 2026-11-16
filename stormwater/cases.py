"""Philadelphia workflow composition over the independent physical GIS engine.

Legacy imports remain compatible. Use drainage_core for location-neutral analysis.
"""
from pathlib import Path
import json
import re
import time
from copy import deepcopy
from datetime import datetime, timezone
from hashlib import sha256
import uuid
from drainage_core.engine import canonical,input_hash,validate_input,routing
from drainage_core.engine import new_case as _new_case,analyze as analyze_gis

ROOT=Path(__file__).resolve().parents[1]


def new_case(name='Untitled property'):
    case=_new_case(name,crs='EPSG:2272')
    case.update(benefits=[],baseline=None)
    return case


def _analyze_pair(case,frozen=None,as_of=None):
    from .jurisdictions.philadelphia import apply
    start=time.perf_counter()
    if frozen:
        from .physical_reuse import policy_overlay,physical_signature
        validate_input(case)
        original,gis=frozen
        policy=apply(original,gis,policy_inputs=policy_overlay(case),as_of=as_of)
    else:
        gis=analyze_gis(case,source_dependencies=case.get('dependent_source_families',('PWD','City impervious','City buildings')))
        policy=apply(case,gis,tariff=case.get('tariff'),as_of=as_of)
    result={**gis,**policy,'result_type':'jurisdiction-analysis',
            'warnings':list(dict.fromkeys(gis['warnings']+policy['warnings'])),
            'processing_seconds':round(time.perf_counter()-start,6),
            'claim':'Research screening; independent empirical validation and professional review required'}
    result.pop('analysis_sha256',None)
    result['input_sha256']=input_hash(case)
    if frozen:
        result['physical_reuse']={'status':'reused_frozen_gis','frozen_input_sha256':gis['input_sha256'],
            'current_case_sha256':input_hash(case),'physical_signature':physical_signature(case),
            'claim':'Original GIS input and artifact hashes retained; only policy recomputed'}
    if case.get('automatic'):
        result['automatic']=deepcopy(case['automatic'])
    from .quality import safe_analysis
    return gis,safe_analysis(result)


def analyze(case,as_of=None):
    """``as_of`` pins the policy assessment date (ISO); default is today."""
    return _analyze_pair(case,as_of=as_of)[1]

class CaseStore:
    def __init__(self,root=None,data_root=None):
        self.root=Path(root or ROOT/'data/cases'); self.root.mkdir(parents=True,exist_ok=True)
        # Public-source blobs and caches live under data_root/public (rule sources under
        # data_root/rules/public). A store outside the repository's data/cases, such as
        # a test's temporary store, keeps a private data root and never touches data/.
        if data_root is None:
            in_repository=self.root.resolve()==(ROOT/'data'/'cases').resolve()
            data_root=ROOT/'data' if in_repository else self.root/'.data'
        self.data_root=Path(data_root)

    def directory(self,id):
        if not re.fullmatch(r'[A-Za-z0-9_-]{1,80}',id): raise ValueError('Invalid case ID')
        if (self.root/id).is_symlink():raise ValueError('Case directory cannot be a symlink')
        return self.root/id

    def list(self):
        return [{'id':p.parent.name,'name':json.loads(p.read_text()).get('name',p.parent.name)}
                for p in sorted(self.root.glob('*/case.json'))]

    def load(self,id):
        return json.loads((self.directory(id)/'case.json').read_text())

    def saved(self,id):
        from drainage_core.saved import saved_view
        from .rules import RULE_VERSION
        view=saved_view(self.directory(id),self.load(id))
        from .quality import safe_analysis
        if view['analysis']:
            view['analysis']=safe_analysis(view['analysis'])
            if view['analysis']['quality_review']['status']=='invalidated':
                view['saved_status'].update(state='invalidated',message=view['analysis']['quality_review']['reason'])
        if view['analysis'] and view['analysis'].get('rule_version') not in (None,RULE_VERSION):
            view['saved_status']['policy_changed']=True
            view['saved_status']['message']+=' Saved policy version differs from current code.'
        return view

    def export_artifact(self,id,name):
        """Read-only safe exports; never recalculate a property to open a report."""
        from .quality import safe_analysis
        from .report import render_report,export_geojson
        folder=self.directory(id)
        if name=='case.json':return (folder/name).read_bytes()
        source='gis-analysis.json' if name=='gis-analysis.json' else 'analysis.json'
        raw=json.loads((folder/source).read_text());view=safe_analysis(raw)
        if source=='analysis.json' and raw.get('input_sha256')!=input_hash(self.load(id)):
            raise ValueError('Saved result does not match current inputs; no automatic recalculation')
        if name in ('analysis.json','gis-analysis.json'):return canonical(view).encode()
        case=self.load(id)
        if name=='report.html':return render_report(case,view).encode()
        if name=='measurements.geojson':return canonical(export_geojson(case,view)).encode()
        raise ValueError('Unknown export')

    def save(self,case):
        from .report import render_report, export_geojson
        from drainage_core.evidence import AttachmentStore, validate_references
        assessment=case.get('assessment',{})
        validate_references(assessment)
        if assessment.get('attachments'):
            AttachmentStore(self.directory(case['id'])/'attachments').verify(assessment['attachments'])
        gis,result=self._pair(case); folder=self.directory(case['id']); folder.mkdir(exist_ok=True)
        revisions=folder/'revisions'; revisions.mkdir(exist_ok=True)
        digest=result['input_sha256']; payload=canonical(case)+'\n'
        frozen=revisions/(digest+'.json')
        if not frozen.exists(): frozen.write_text(payload)
        outputs={'case.json':payload,'analysis.json':canonical(result),
                 'report.html':render_report(case,result),
                 'measurements.geojson':canonical(export_geojson(case,result))}
        if not result.get('physical_reuse'):outputs['gis-analysis.json']=canonical(gis)
        for name,body in outputs.items():
            temp=folder/(name+'.tmp'); temp.write_text(body); temp.replace(folder/name)
        return result

    def _pair(self,case):
        from .physical_reuse import load_frozen
        # Policy edits and saves must not silently reroute after a code update.
        # A matching old artifact is retained as historical, with derived finance
        # quarantined. Explicit acquisition/physical changes take the normal path.
        frozen=load_frozen(self.directory(case['id']),case,allow_historical=True)
        return _analyze_pair(case,frozen) if frozen else _analyze_pair(case)

    def analyze(self,case):
        return self._pair(case)[1]

    def policy_analysis(self,case):
        from .physical_reuse import load_frozen
        frozen=load_frozen(self.directory(case['id']),case,allow_historical=True)
        if not frozen:raise ValueError('Matching frozen physical GIS required; no automatic property rerun')
        return _analyze_pair(case,frozen)[1]

    def renewals(self,as_of=None):
        from .renewals import history_assessment,today
        day=as_of or today().isoformat()
        properties=[]
        for row in self.list():
            try:
                result=history_assessment(self.load(row['id']),day)
                properties.append({**row,'renewals':result['renewals'],
                                   'lead_days':result['reminder_lead_days']})
            except (ValueError,KeyError,TypeError) as exc:
                properties.append({**row,'renewals':[],'error':str(exc)})
        return {'as_of':day,'lead_days':90,'properties':properties}

    def attach(self,case,filename,content):
        from drainage_core.evidence import AttachmentStore
        from .assessment_workflow import ensure_assessment
        updated=deepcopy(case);ensure_assessment(updated)
        attachment=AttachmentStore(self.directory(case['id'])/'attachments').add(filename,content)
        if not any(x['id']==attachment['id'] and x['filename']==attachment['filename']
                   for x in updated['assessment']['attachments']):
            updated['assessment']['attachments'].append(attachment)
        return updated,attachment

    def run_assessment(self,case,cache=None,*,refresh_records=False):
        if not isinstance(refresh_records,bool):raise ValueError('Record refresh must be true or false')
        from .record_cache import SharedCache
        from .assessment_workflow import gather
        if cache is None:
            cache=SharedCache(self.data_root/'public',fallback_roots=[self.data_root/'prospects'/'public'],timeout=15)
        selected_cache=cache
        if isinstance(selected_cache,SharedCache):selected_cache.reuse_recent_records=not refresh_records
        reuse_events=getattr(selected_cache,'reuse_events',[])
        reuse_start=len(reuse_events) if isinstance(reuse_events,list) else 0
        updated=case
        if re.match(r'^pwd-\d+',case.get('id','')) or case.get('automatic'):
            from .automatic import acquire,enrich_candidates
            updated=acquire(case,selected_cache,refresh=True,case_root=self.root)
        updated=gather(updated,selected_cache,refresh=True)
        reuse_events=getattr(selected_cache,'reuse_events',[])
        updated.setdefault('assessment',{})['record_reuse']=deepcopy(reuse_events[reuse_start:] if isinstance(reuse_events,list) else [])
        if updated.get('automatic'):
            from .automatic import enrich_candidates
            updated=enrich_candidates(updated)
        now=datetime.now(timezone.utc).isoformat()
        run_id=uuid.uuid4().hex
        updated['assessment'].setdefault('snapshots',[]).append({'id':run_id,'at':now,
            'source_status':deepcopy(updated['assessment'].get('source_status',[])),
            'artifact':'assessments/'+run_id+'.json'})
        result=self.save(updated)
        folder=self.directory(updated['id'])/'assessments';folder.mkdir(exist_ok=True)
        snapshot={'id':run_id,'at':now,'case':updated,'analysis':result}
        body=canonical(snapshot)
        snapshot['snapshot_sha256']=sha256(body.encode()).hexdigest()
        (folder/(run_id+'.json')).write_text(canonical(snapshot)+'\n')
        return {'case':updated,'analysis':result,'snapshot_sha256':snapshot['snapshot_sha256']}

    @staticmethod
    def _bundle_cases(bundle):
        return [bundle['case'], *bundle.get('revisions',{}).values(),
                *(x['case'] for x in bundle.get('assessments',{}).values())]

    @staticmethod
    def _public_sources(case):
        a=case.get('assessment',{})
        return [*case.get('sources',[]),
                *(source for snapshot in [a.get('soil_snapshot',{}),*a.get('soil_history',[])]
                  for source in snapshot.get('sources',[]))]

    @staticmethod
    def _bundle_manifests(bundle):
        manifests={}
        for case in CaseStore._bundle_cases(bundle):
            for item in case.get('assessment',{}).get('attachments',[]):
                manifests[(item['sha256'],item['filename'])]=item
        return list(manifests.values())

    @staticmethod
    def _verify_snapshot(snapshot):
        digest=snapshot.get('snapshot_sha256')
        if digest and digest!=sha256(canonical({k:v for k,v in snapshot.items() if k!='snapshot_sha256'}).encode()).hexdigest():
            raise ValueError('Assessment snapshot content hash mismatch')

    def portable_bundle(self,id):
        import base64
        from drainage_core.evidence import AttachmentStore
        case=self.load(id);folder=self.directory(id)
        def files(directory):
            return {p.name:json.loads(p.read_text()) for p in sorted((folder/directory).glob('*.json'))}
        bundle={'schema_version':1,'artifact_type':'existing-site-evidence-bundle','case':case,
                'revisions':files('revisions'),'assessments':files('assessments')}
        for snapshot in bundle['assessments'].values():self._verify_snapshot(snapshot)
        from drainage_core.quality import artifact_quality
        bundle['quality_review']={'claim':'Historical snapshots retain original bytes/hashes, not current usable savings.',
            'snapshots':{name:artifact_quality(s.get('analysis',{})) for name,s in bundle['assessments'].items()}}
        bundle['snapshots_without_content_hash']=[name for name,data in bundle['assessments'].items() if not data.get('snapshot_sha256')]
        from .assessment_policy import RULES
        bundle['rule_sources']=deepcopy(RULES.get('source_snapshots',[]))
        bundle['attachments']=AttachmentStore(folder/'attachments').export(self._bundle_manifests(bundle))
        bundle['public_blobs']=[];bundle['missing_public_blobs']=[]
        sources={s['sha256'] for c in self._bundle_cases(bundle) for s in self._public_sources(c)
                 if re.fullmatch('[a-f0-9]{64}',str(s.get('sha256','')))}
        sources.update(s['sha256'] for s in bundle['rule_sources'])
        for snapshot in bundle['assessments'].values():
            sources.update(s['sha256'] for s in snapshot.get('analysis',{}).get('assessment',{}).get('rules',{}).get('source_snapshots',[]))
        for digest in sorted(sources):
            path=self.data_root/'public'/'blobs'/digest
            if not path.exists():path=self.data_root/'rules'/'public'/'blobs'/digest
            if not path.exists():
                bundle['missing_public_blobs'].append(digest);continue
            content=path.read_bytes()
            if sha256(content).hexdigest()!=digest:raise ValueError('Public source snapshot hash mismatch')
            bundle['public_blobs'].append({'sha256':digest,'content_base64':base64.b64encode(content).decode('ascii')})
        return bundle

    def import_bundle(self,bundle):
        import base64
        from drainage_core.evidence import AttachmentStore,validate_references
        from drainage_core.engine import input_hash,validate_input
        if bundle.get('artifact_type')!='existing-site-evidence-bundle' or bundle.get('schema_version')!=1:
            raise ValueError('Unsupported portable evidence bundle')
        case=deepcopy(bundle['case']);folder=self.directory(case['id'])
        cases=self._bundle_cases(bundle)
        for value in cases:
            if value['id']!=case['id']:raise ValueError('Historical case identifier mismatch')
            validate_input(value);validate_references(value.get('assessment',{}))
        manifests=self._bundle_manifests(bundle);blobs=bundle.get('attachments',[])
        if {(x['sha256'],x['filename']) for x in manifests}!={(x['sha256'],x['filename']) for x in blobs}:
            raise ValueError('Portable bundle attachment inventory mismatch')
        # Preflight every historical filename, hash and conflict before altering a case.
        for name,data in bundle.get('revisions',{}).items():
            if name!=input_hash(data)+'.json':raise ValueError('Revision hash mismatch')
        for name,data in bundle.get('assessments',{}).items():
            self._verify_snapshot(data)
            if not re.fullmatch(r'[a-f0-9]{32}\.json',name) or name!=data.get('id','')+'.json':
                raise ValueError('Invalid assessment snapshot ID')
            if data.get('analysis',{}).get('input_sha256')!=input_hash(data['case']):
                raise ValueError('Assessment snapshot input hash mismatch')
        for directory in ('revisions','assessments'):
            for name,data in bundle.get(directory,{}).items():
                path=folder/directory/name
                if path.exists() and canonical(json.loads(path.read_text()))!=canonical(data):
                    raise ValueError('Import conflicts with preserved '+directory)
        public=[]
        referenced={s.get('sha256') for c in cases for s in self._public_sources(c)}
        referenced.update(s['sha256'] for s in bundle.get('rule_sources',[]))
        for snapshot in bundle.get('assessments',{}).values():
            referenced.update(s['sha256'] for s in snapshot.get('analysis',{}).get('assessment',{}).get('rules',{}).get('source_snapshots',[]))
        for item in bundle.get('public_blobs',[]):
            digest=item['sha256']
            if not re.fullmatch('[a-f0-9]{64}',digest) or digest not in referenced:
                raise ValueError('Unreferenced public blob')
            content=base64.b64decode(item['content_base64'],validate=True)
            if sha256(content).hexdigest()!=digest:raise ValueError('Public blob hash mismatch')
            public.append((digest,content))
        # Evaluate before any case overwrite; attachment import validates all bytes first.
        analyze(case)
        store=AttachmentStore(folder/'attachments');store.import_bundle(blobs);store.verify(manifests)
        cache=self.data_root/'public'/'blobs';cache.mkdir(parents=True,exist_ok=True)
        for digest,content in public:
            path=cache/digest
            if not path.exists():path.write_bytes(content)
            elif sha256(path.read_bytes()).hexdigest()!=digest:raise ValueError('Existing public blob corrupted')
        result=self.save(case)
        for directory in ('revisions','assessments'):
            target=folder/directory;target.mkdir(exist_ok=True)
            for name,data in bundle.get(directory,{}).items():
                path=target/name
                if not path.exists():path.write_text(canonical(data)+'\n')
        return {'case':case,'analysis':result}
