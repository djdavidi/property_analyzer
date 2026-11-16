"""Saved-result lifecycle (fix plan Phase 1, decision D1). Invented inputs only.

Converted review repros: cross/fingerprint_overreach.py, prospects/stuck.py,
prospects/benefit_map.py, prospects/race.py and prospects/blob.py. Results are
judged by explicit interpretation versions; recorded observations stay visible;
recompute from saved inputs is explicit and local; writes are atomic.
"""
from copy import deepcopy
from hashlib import sha256
from http.client import HTTPConnection
from http.server import ThreadingHTTPServer
from pathlib import Path
from tempfile import TemporaryDirectory
from threading import Thread
from unittest.mock import Mock, patch
import io
import json
import shutil
import subprocess
import sys
import unittest
import warnings
from shapely.geometry import box, mapping, shape
import network_guard
from drainage_core.engine import ENGINE_VERSION, canonical, input_hash
from drainage_core.quality import PHYSICAL_INTERPRETATION_VERSION, artifact_quality
from drainage_core.sources import Cache
from stormwater.cases import CaseStore, RevisionConflict
from stormwater.fixtures import synthetic_case
from stormwater.quality import (DERIVED_MONEY_KEYS, OBSERVATION_KEYS, POLICY_INTERPRETATION_VERSION,
                                safe_analysis)

ROOT=Path(__file__).resolve().parents[1]


def bump_physical():
    return patch('drainage_core.quality.PHYSICAL_INTERPRETATION_VERSION',PHYSICAL_INTERPRETATION_VERSION+1)


def bump_policy():
    return patch('stormwater.quality.POLICY_INTERPRETATION_VERSION',POLICY_INTERPRETATION_VERSION+1)


def derived_money(value,path=''):
    """Every non-null derived-money value with its path."""
    if isinstance(value,list):return [x for i,v in enumerate(value) for x in derived_money(v,f'{path}[{i}]')]
    if not isinstance(value,dict):return []
    found=[(path+'.'+k,v) for k,v in value.items() if k in DERIVED_MONEY_KEYS and v is not None]
    return found+[x for k,v in value.items() for x in derived_money(v,path+'.'+k)]


def legacy_saved():
    """An artifact written under byte fingerprints, with recorded observations."""
    return {'processing_fingerprint':'byte-hash-before-a-comment-edit',
            'policy_processing_fingerprint':'fingerprint-before-a-comment-edit',
            'engine_version':ENGINE_VERSION,'measurement':{'ga_sqft':6800,'ia_sqft':6500},
            'billing':{'status':'calculated','monthly_total':3138.21,'published_monthly_total':3138.21,
                       'baseline':{'status':'calculated','monthly_total':3138.21,'ga_sqft':6800,'ia_sqft':6500,
                                   'monthly_public_charge':3138.21},
                       'combined':{'status':'calculated','monthly_savings':81.5,'annual_savings':978.0,'monthly_total':3056.71}},
            'assessment':{'economics':{'baseline':{'status':'calculated','monthly_total':3138.21},
                                       'modeled':{'status':'calculated','gross_annual_reduction':978.0},'claim':'One baseline'},
                          'categories':[{'category':'canopy','records':[{'id':'r','status':'screen_pass','monthly_savings':81.5}]}],
                          'public_credit_observations':[{'annual_public_charge':37658.52,'credits_flag':1}],
                          'historical_flags':[{'published_monthly_total':3138.21,'difference':0.0}]}}


class InterpretationVersionTests(unittest.TestCase):
    def test_comment_only_source_edits_change_no_fingerprint_or_status(self):
        # fingerprint_overreach.py: comments added to every in-scope module of a copy.
        current={'engine_version':ENGINE_VERSION,'physical_interpretation_version':PHYSICAL_INTERPRETATION_VERSION,
                 'research_drainage':{'runs':[]},'policy_interpretation_version':POLICY_INTERPRETATION_VERSION,
                 'profile_version':'philadelphia-pwd-v1','billing':{'baseline':{'status':'calculated','monthly_total':1.0}}}
        script=('import json,sys\nsys.path.insert(0,sys.argv[1])\n'
                'from drainage_core.quality import processing_fingerprint\n'
                'from stormwater.quality import policy_fingerprint,safe_analysis\n'
                'view=safe_analysis(json.loads(sys.stdin.read()))\n'
                'print(json.dumps([processing_fingerprint(),policy_fingerprint(),view["quality_review"]["status"],'
                'view["billing"]["baseline"]["monthly_total"]]))\n')
        def run(root):
            done=subprocess.run([sys.executable,'-I','-c',script,str(root)],input=json.dumps(current),
                                capture_output=True,text=True,timeout=120,cwd=root)
            self.assertEqual(done.returncode,0,done.stderr);return json.loads(done.stdout)
        with TemporaryDirectory() as temp:
            for package in ('drainage_core','stormwater'):
                shutil.copytree(ROOT/package,Path(temp)/package,ignore=shutil.ignore_patterns('__pycache__','web'))
                for source in (Path(temp)/package).rglob('*.py'):
                    with source.open('a') as stream:stream.write('\n# comment-only edit\n')
            before,after=run(ROOT),run(Path(temp))
        self.assertEqual(before,after)
        self.assertEqual(after[2:],['not_independently_validated',1.0])

    def test_library_versions_are_provenance_only(self):
        current={'engine_version':ENGINE_VERSION,'physical_interpretation_version':PHYSICAL_INTERPRETATION_VERSION,
                 'library_versions':{'numpy':'0.0.1','shapely':'0.0.1'}}
        self.assertEqual(artifact_quality(current)['status'],'not_independently_validated')

    def test_pre_fingerprint_research_only_artifact_is_legacy_not_current(self):
        q=artifact_quality({'research_drainage':{'runs':[]}})
        self.assertEqual(q['status'],'outdated');self.assertTrue(q['recompute_available'])
        self.assertIn('unknown (legacy) physical interpretation version',q['label'])

    def test_legacy_artifact_is_labelled_but_recorded_bill_never_redacted(self):
        saved=legacy_saved();before=canonical(saved);view=safe_analysis(saved)
        self.assertEqual(canonical(saved),before)
        q=view['quality_review'];self.assertEqual(q['status'],'outdated');self.assertTrue(q['recompute_available'])
        self.assertTrue(q['observations_retained'])
        b=view['billing']
        self.assertEqual((b['status'],b['monthly_total'],b['published_monthly_total']),('calculated',3138.21,3138.21))
        self.assertEqual(b['baseline']['monthly_public_charge'],3138.21);self.assertEqual(b['baseline']['monthly_total'],3138.21)
        self.assertEqual((b['baseline']['ga_sqft'],b['baseline']['ia_sqft']),(6800,6500))
        self.assertEqual(b['interpretation_status'],'outdated');self.assertIn('legacy',b['baseline']['interpretation_label'])
        a=view['assessment']
        self.assertEqual(a['economics']['baseline']['monthly_total'],3138.21)
        self.assertEqual(a['public_credit_observations'][0]['annual_public_charge'],37658.52)
        self.assertEqual(a['historical_flags'][0]['published_monthly_total'],3138.21)
        self.assertEqual(view['measurement'],saved['measurement'])
        # Derived money is withheld, with the scenario blocks that carry it.
        self.assertEqual(b['combined']['status'],'outdated');self.assertNotIn('3056.71',canonical(b['combined']))
        self.assertEqual(a['economics']['modeled']['status'],'outdated')
        self.assertEqual(a['categories'][0]['records'][0]['status'],'outdated')
        self.assertEqual(derived_money(view),[])
        self.assertEqual(canonical(safe_analysis(view)),canonical(view))

    def test_withheld_allowlist_never_names_an_observation(self):
        self.assertFalse(DERIVED_MONEY_KEYS&OBSERVATION_KEYS)
        for key in ('published_monthly_total','monthly_public_charge','annual_public_charge','ga_sqft','ia_sqft'):
            self.assertIn(key,OBSERVATION_KEYS)


class LifecycleStoreTests(unittest.TestCase):
    def setUp(self):
        warnings.simplefilter('ignore')
        self.temp=TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.store=CaseStore(self.temp.name);self.case=synthetic_case()
        self.case['baseline']['published_monthly_total']=150.0
        self.folder=self.store.directory(self.case['id'])

    def test_version_bump_labels_reuse_then_recompute_produces_current_results(self):
        # prospects/stuck.py: previously no route could leave quarantine.
        first=self.store.save(self.case);self.assertEqual(first['quality_review']['status'],'not_independently_validated')
        self.assertEqual(first['physical_interpretation_version'],PHYSICAL_INTERPRETATION_VERSION)
        self.assertTrue(derived_money(first),'fixture must exercise derived money')
        old_gis=(self.folder/'gis-analysis.json').read_bytes()
        with bump_physical():
            for route in ('analyze','save','analyze'):
                r=getattr(self.store,route)(self.case)
                self.assertEqual(r['physical_reuse']['status'],'reused_frozen_gis')
                self.assertEqual(r['physical_reuse']['interpretation_status'],'outdated')
                self.assertEqual(r['quality_review']['status'],'outdated');self.assertTrue(r['quality_review']['recompute_available'])
                self.assertEqual(r['billing']['baseline']['monthly_total'],first['billing']['baseline']['monthly_total'])
                self.assertEqual(r['billing']['baseline']['published_difference'],first['billing']['baseline']['published_difference'])
                self.assertEqual(canonical(r['measurement']),canonical(first['measurement']))
                self.assertEqual(canonical(r['assessment']['historical_flags']),canonical(first['assessment']['historical_flags']))
                self.assertEqual(derived_money(r),[])
            self.assertEqual((self.folder/'gis-analysis.json').read_bytes(),old_gis)
            status=self.store.saved(self.case['id'])['saved_status']
            self.assertEqual(status['state'],'outdated');self.assertTrue(status['recompute_available'])
            self.assertIn('older physical interpretation version',status['label'])
            preview=self.store.analyze(self.case,recompute_gis=True)
            self.assertNotIn('physical_reuse',preview);self.assertEqual(preview['quality_review']['status'],'not_independently_validated')
            self.assertEqual((self.folder/'gis-analysis.json').read_bytes(),old_gis,'Preview never writes')
            saved=self.store.save(self.case,recompute_gis=True)
            self.assertEqual(saved['quality_review']['status'],'not_independently_validated')
            self.assertEqual(saved['physical_interpretation_version'],PHYSICAL_INTERPRETATION_VERSION+1)
            self.assertTrue(derived_money(saved))
            self.assertEqual(self.store.saved(self.case['id'])['saved_status']['state'],'saved')
            self.assertEqual(self.store.analyze(self.case)['physical_reuse']['interpretation_status'],'current')
        archived=self.folder/'superseded'/(sha256(old_gis).hexdigest()+'.gis-analysis.json')
        self.assertEqual(archived.read_bytes(),old_gis,'Superseded outdated GIS bytes are preserved')

    def test_recompute_reuses_current_frozen_gis_without_rerouting(self):
        self.store.save(self.case)
        with patch('stormwater.cases.analyze_gis',side_effect=AssertionError('Current GIS is not rerun')):
            r=self.store.save(self.case,recompute_gis=True)
        self.assertEqual(r['physical_reuse']['status'],'reused_frozen_gis')
        with self.assertRaises(ValueError):self.store.analyze(self.case,recompute_gis='yes')

    def test_policy_bump_labels_saved_result_and_a_save_recomputes_policy(self):
        self.store.save(self.case)
        with bump_policy():
            view=self.store.saved(self.case['id'])
            self.assertEqual(view['saved_status']['state'],'outdated')
            self.assertIn('older policy interpretation version',view['saved_status']['label'])
            self.assertIsNotNone(view['analysis']['billing']['baseline']['monthly_total'])
            self.assertEqual(derived_money(view['analysis']),[])
            exported=json.loads(self.store.export_artifact(self.case['id'],'analysis.json'))
            self.assertEqual(exported['quality_review']['status'],'outdated')
            r=self.store.save(self.case,recompute_gis=True)
            self.assertEqual(r['quality_review']['status'],'not_independently_validated')
            self.assertEqual(self.store.saved(self.case['id'])['saved_status']['state'],'saved')

    def test_cached_saved_view_is_reevaluated_after_a_version_bump(self):
        # C12 / R10: the display cache key carries the interpretation versions.
        from drainage_core.saved import saved_view
        self.store.save(self.case);case=self.store.load(self.case['id'])
        self.assertEqual(saved_view(self.folder,case)['saved_status']['state'],'saved')
        with patch('stormwater.cases._analyze_pair',side_effect=AssertionError('No analysis')),bump_physical():
            self.assertEqual(saved_view(self.folder,case)['saved_status']['state'],'outdated')
            self.assertEqual(self.store.saved(self.case['id'])['saved_status']['state'],'outdated')
        self.assertEqual(saved_view(self.folder,case)['saved_status']['state'],'saved')

    def test_generic_exports_apply_the_same_gate(self):
        from drainage_core.server import Handler
        from drainage_core.workspace import ProjectStore
        store=ProjectStore(Path(self.temp.name)/'gis-project');store.save(self.case)
        stored=(store.root/'analysis.json').read_bytes()
        self.assertEqual(store.export_artifact('analysis.json'),stored)
        with bump_physical():
            handler=object.__new__(Handler);handler.path='/exports/'+self.case['id']+'/analysis.json'
            handler.headers={'Host':'127.0.0.1'};handler.store=store;handler.send=Mock()
            Handler.do_GET(handler)
            served=json.loads(handler.send.call_args.args[0])
            self.assertEqual(served['quality_review']['status'],'outdated')
            self.assertEqual(served['modeled_integration']['status'],'outdated')
            self.assertEqual(served['measurement'],json.loads(stored)['measurement'])
            self.assertIn(b'older physical interpretation version',store.export_artifact('report.html'))
            self.assertEqual(store.saved()['saved_status']['state'],'outdated')
        self.assertEqual((store.root/'analysis.json').read_bytes(),stored)


class FrozenMapFeatureTests(unittest.TestCase):
    def test_moved_benefit_is_drawn_where_policy_uses_it(self):
        # prospects/benefit_map.py
        warnings.simplefilter('ignore')
        with TemporaryDirectory() as temp:
            store=CaseStore(temp);case=synthetic_case();first=store.save(case)
            edited=deepcopy(case);x,y=2690000,250000
            edited['benefits'][0]['geometry']=mapping(box(x+80,y-95,x+95,y-80))
            with patch('stormwater.cases.analyze_gis',side_effect=AssertionError('Policy-only edit')):
                r=store.analyze(edited)
        self.assertEqual(r['physical_reuse']['status'],'reused_frozen_gis')
        drawn=next(f for f in r['map_features'] if f['id']=='canopy-hypothesis')
        self.assertEqual(shape(drawn['geometry']).bounds,shape(edited['benefits'][0]['geometry']).bounds)
        self.assertEqual(canonical(r['measurement']),canonical(first['measurement']))


class ConcurrencyAndRevisionTests(unittest.TestCase):
    def setUp(self):
        warnings.simplefilter('ignore')
        self.temp=TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.store=CaseStore(self.temp.name);self.case=synthetic_case()
        self.folder=self.store.directory(self.case['id'])

    def test_concurrent_saves_leave_a_consistent_pair_and_no_temp_files(self):
        # prospects/race.py
        self.store.save(self.case);errors=[]
        def save(i):
            c=deepcopy(self.case);c['name']=f'edit {i}'
            try:self.store.save(c)
            except Exception as exc:errors.append(f'{type(exc).__name__}: {exc}')
        for trial in range(2):
            threads=[Thread(target=save,args=(trial*10+i,)) for i in range(4)]
            for t in threads:t.start()
            for t in threads:t.join()
            case=json.loads((self.folder/'case.json').read_text())
            analysis=json.loads((self.folder/'analysis.json').read_text())
            self.assertEqual(analysis['input_sha256'],input_hash(case))
        self.assertEqual(errors,[]);self.assertEqual(list(self.folder.rglob('*.tmp')),[])

    def test_expected_revision_mismatch_conflicts_without_writing(self):
        first=self.store.save(self.case);revision=first['input_sha256']
        self.assertEqual(self.store.revision(self.case['id']),revision)
        mine=deepcopy(self.case);mine['name']='Mine'
        second=self.store.save(mine,expected_revision=revision)
        theirs=deepcopy(self.case);theirs['name']='Theirs';before=(self.folder/'case.json').read_bytes()
        with self.assertRaises(RevisionConflict) as caught:self.store.save(theirs,expected_revision=revision)
        self.assertEqual(caught.exception.current,second['input_sha256'])
        self.assertEqual((self.folder/'case.json').read_bytes(),before)

    def test_long_assessment_run_cannot_overwrite_a_save_made_while_it_ran(self):
        self.store.save(self.case);interim=deepcopy(self.case);interim['name']='Interim save'
        def gather(case,cache,refresh=True):
            self.store.save(interim);return deepcopy(case)
        with patch('stormwater.assessment_workflow.gather',side_effect=gather):
            with self.assertRaises(RevisionConflict):self.store.run_assessment(deepcopy(self.case),cache=object())
        self.assertEqual(self.store.load(self.case['id'])['name'],'Interim save')

    def test_http_save_conflict_is_409_and_old_clients_still_save(self):
        from stormwater.server import Handler
        network_guard.install()
        class LocalHandler(Handler):
            def log_message(self,*args):pass
        LocalHandler.store=self.store;LocalHandler.data_root=self.store.data_root
        LocalHandler.source_opener=network_guard.offline_opener;LocalHandler.prospect_jobs=Mock()
        server=ThreadingHTTPServer(('127.0.0.1',0),LocalHandler)
        thread=Thread(target=server.serve_forever,daemon=True);thread.start()
        def post(path,payload):
            c=HTTPConnection('127.0.0.1',server.server_port,timeout=30)
            try:
                c.request('POST',path,json.dumps(payload),{'Content-Type':'application/json'})
                r=c.getresponse();return r.status,json.loads(r.read())
            finally:c.close()
        try:
            code,saved=post('/api/save',{'case':self.case});self.assertEqual(code,200)
            code,body=post('/api/save',{'case':self.case,'expected_revision':'0'*64})
            self.assertEqual(code,409);self.assertEqual(body['current_revision'],saved['input_sha256'])
            code,_=post('/api/save',{'case':self.case,'expected_revision':saved['input_sha256'],'recompute_gis':True})
            self.assertEqual(code,200)
            code,_=post('/api/analyze',{'case':self.case,'recompute_gis':'yes'});self.assertEqual(code,400)
        finally:
            server.shutdown();server.server_close();thread.join()


class SourceCacheIntegrityTests(unittest.TestCase):
    body=b'{"Parcel":{"ParcelID":1}}'

    def opener(self,content=None):
        class Response(io.BytesIO):
            def __enter__(self):return self
            def __exit__(self,*args):return False
        return lambda request,timeout=None:Response(content or self.body)

    def test_corrupt_blob_is_repaired_by_the_next_store(self):
        # prospects/blob.py
        with TemporaryDirectory() as temp:
            cache=Cache(temp,opener=self.opener());digest=sha256(self.body).hexdigest()
            (Path(temp)/'blobs'/digest).write_bytes(self.body[:7])
            self.assertEqual(cache.fetch_json('https://x.example/a')['data'],{'Parcel':{'ParcelID':1}})
            self.assertEqual((Path(temp)/'blobs'/digest).read_bytes(),self.body)
            self.assertEqual(cache._read('https://x.example/a')[0],self.body)
            self.assertEqual(list(Path(temp).rglob('*.tmp')),[])

    def test_concurrent_writers_of_one_url_share_no_temporary_file(self):
        with TemporaryDirectory() as temp:
            cache=Cache(temp,opener=self.opener());errors=[]
            def store(i):
                try:cache._store('https://x.example/a',b'{"version":%d}'%i)
                except Exception as exc:errors.append(repr(exc))
            threads=[Thread(target=store,args=(i,)) for i in range(16)]
            for t in threads:t.start()
            for t in threads:t.join()
            self.assertEqual(errors,[])
            content,info=cache._read('https://x.example/a')
            self.assertEqual(sha256(content).hexdigest(),info['sha256'])
            self.assertEqual(list(Path(temp).rglob('*.tmp')),[])


if __name__=='__main__':unittest.main()
