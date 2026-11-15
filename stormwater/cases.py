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


def _analyze_pair(case):
    from .jurisdictions.philadelphia import apply
    start=time.perf_counter()
    gis=analyze_gis(case,source_dependencies=case.get('dependent_source_families',('PWD','City impervious','City buildings')))
    policy=apply(case,gis)
    result={**gis,**policy,'result_type':'jurisdiction-analysis',
            'warnings':list(dict.fromkeys(gis['warnings']+policy['warnings'])),
            'processing_seconds':round(time.perf_counter()-start,6),
            'claim':'Research screening; independent empirical validation and professional review required'}
    result.pop('analysis_sha256',None)
    return gis,result


def analyze(case):
    return _analyze_pair(case)[1]

class CaseStore:
    def __init__(self,root=None):
        self.root=Path(root or ROOT/'data/cases'); self.root.mkdir(parents=True,exist_ok=True)

    def directory(self,id):
        if not re.fullmatch(r'[A-Za-z0-9_-]{1,80}',id): raise ValueError('Invalid case ID')
        if (self.root/id).is_symlink():raise ValueError('Case directory cannot be a symlink')
        return self.root/id

    def list(self):
        return [{'id':p.parent.name,'name':json.loads(p.read_text()).get('name',p.parent.name)}
                for p in sorted(self.root.glob('*/case.json'))]

    def load(self,id):
        return json.loads((self.directory(id)/'case.json').read_text())

    def save(self,case):
        from .report import render_report, export_geojson
        from drainage_core.evidence import AttachmentStore, validate_references
        assessment=case.get('assessment',{})
        validate_references(assessment)
        if assessment.get('attachments'):
            AttachmentStore(self.directory(case['id'])/'attachments').verify(assessment['attachments'])
        gis,result=_analyze_pair(case); folder=self.directory(case['id']); folder.mkdir(exist_ok=True)
        revisions=folder/'revisions'; revisions.mkdir(exist_ok=True)
        digest=result['input_sha256']; payload=canonical(case)+'\n'
        frozen=revisions/(digest+'.json')
        if not frozen.exists(): frozen.write_text(payload)
        outputs={'case.json':payload,'analysis.json':json.dumps(result,indent=2,allow_nan=False),
                 'gis-analysis.json':json.dumps(gis,indent=2,allow_nan=False),
                 'report.html':render_report(case,result),
                 'measurements.geojson':json.dumps(export_geojson(case,result),indent=2,allow_nan=False,sort_keys=True)}
        for name,body in outputs.items():
            temp=folder/(name+'.tmp'); temp.write_text(body); temp.replace(folder/name)
        return result

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

    def run_assessment(self,case,cache=None):
        from drainage_core.sources import Cache
        from .assessment_workflow import gather
        updated=gather(case,cache or Cache(ROOT/'data/public',timeout=8),refresh=True)
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
        bundle['snapshots_without_content_hash']=[name for name,data in bundle['assessments'].items() if not data.get('snapshot_sha256')]
        from .assessment_policy import RULES
        bundle['rule_sources']=deepcopy(RULES.get('source_snapshots',[]))
        bundle['attachments']=AttachmentStore(folder/'attachments').export(self._bundle_manifests(bundle))
        bundle['public_blobs']=[];bundle['missing_public_blobs']=[]
        sources={s['sha256'] for c in self._bundle_cases(bundle) for s in c.get('sources',[])
                 if re.fullmatch('[a-f0-9]{64}',str(s.get('sha256','')))}
        sources.update(s['sha256'] for s in bundle['rule_sources'])
        for snapshot in bundle['assessments'].values():
            sources.update(s['sha256'] for s in snapshot.get('analysis',{}).get('assessment',{}).get('rules',{}).get('source_snapshots',[]))
        for digest in sorted(sources):
            path=ROOT/'data/public/blobs'/digest
            if not path.exists():path=ROOT/'data/rules/public/blobs'/digest
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
        referenced={s.get('sha256') for c in cases for s in c.get('sources',[])}
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
        cache=ROOT/'data/public/blobs';cache.mkdir(parents=True,exist_ok=True)
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
