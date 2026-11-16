"""Real loopback saved-view/control routes; analysis and network acquisition mocked."""
from http.client import HTTPConnection
from http.server import ThreadingHTTPServer
from pathlib import Path
from tempfile import TemporaryDirectory
from threading import Thread,Event
from unittest.mock import patch,Mock
import json
import unittest
from test_saved_results import fixture
from drainage_core.engine import canonical
from stormwater.cases import CaseStore
from stormwater.server import Handler
from stormwater.prospect_jobs import ProspectJobs
import network_guard


class SavedHTTPTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        network_guard.install()
        cls.temp=TemporaryDirectory();cls.root=Path(cls.temp.name);c,r=fixture()
        folder=cls.root/c['id'];folder.mkdir();(folder/'case.json').write_text(canonical(c));(folder/'analysis.json').write_text(canonical(r))
        class LocalHandler(Handler):
            def log_message(self,*args):pass
        LocalHandler.store=CaseStore(cls.root);LocalHandler.prospect_jobs=Mock()
        LocalHandler.data_root=LocalHandler.store.data_root;LocalHandler.source_opener=network_guard.offline_opener
        LocalHandler.prospect_jobs.start.return_value={'status':'running'}
        LocalHandler.prospect_jobs.cancel.return_value={'status':'cancelling'}
        cls.handler=LocalHandler;cls.server=ThreadingHTTPServer(('127.0.0.1',0),LocalHandler)
        cls.thread=Thread(target=cls.server.serve_forever,daemon=True);cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown();cls.server.server_close();cls.thread.join();cls.temp.cleanup()

    def request(self,path,payload=None):
        c=HTTPConnection('127.0.0.1',self.server.server_port,timeout=5)
        try:
            c.request('POST' if payload is not None else 'GET',path,json.dumps(payload) if payload is not None else None,{'Content-Type':'application/json'})
            r=c.getresponse();return r.status,json.loads(r.read())
        finally:c.close()

    def test_saved_route_never_calls_analysis_or_acquisition(self):
        with patch('stormwater.cases._analyze_pair',side_effect=AssertionError('No analysis')),patch('stormwater.automatic.acquire',side_effect=AssertionError('No acquisition')):
            code,r=self.request('/api/saved/saved-test')
        self.assertEqual(code,200);self.assertEqual(r['saved_status']['state'],'saved')
        self.assertEqual(r['analysis']['measurement']['ia_sqft'],25)

    def test_default_scan_is_local_rerank_and_cancel_is_available(self):
        code,_=self.request('/api/prospects/scan',{});self.assertEqual(code,202)
        self.handler.prospect_jobs.start.assert_called_with(False,'rerank',None)
        code,_=self.request('/api/prospects/cancel',{});self.assertEqual(code,202)
        self.handler.prospect_jobs.cancel.assert_called_once()

    def test_traversal_does_not_read_another_case(self):
        code,_=self.request('/api/saved/..');self.assertEqual(code,404)

    def test_selected_parcels_reach_update_job(self):
        code,_=self.request('/api/prospects/scan',{'mode':'update','parcel_ids':['1','2']})
        self.assertEqual(code,202);self.handler.prospect_jobs.start.assert_called_with(False,'update',['1','2'])

    def test_analysis_route_uses_saved_case_store(self):
        with patch.object(self.handler.store,'analyze',return_value={'physical_reuse':{'status':'reused_frozen_gis'}}) as analyze:
            code,result=self.request('/api/analyze',{'case':{'id':'fixture'}})
        self.assertEqual(code,200);analyze.assert_called_once_with({'id':'fixture'})
        self.assertEqual(result['physical_reuse']['status'],'reused_frozen_gis')


class JobControlTests(unittest.TestCase):
    def test_saved_update_requires_selection_and_selected_job_skips_scan(self):
        done=Event()
        def updated(*args,**kw):done.set();return {'id':'selected-fixture'}
        with TemporaryDirectory() as root,patch('stormwater.prospect_jobs.run_scan',side_effect=AssertionError('No scan')),patch('stormwater.prospect_jobs.update_selected',side_effect=updated) as update:
            (Path(root)/'latest.json').write_text('{}');jobs=ProspectJobs(root)
            with self.assertRaises(ValueError):jobs.start(mode='update')
            jobs.start(mode='update',parcel_ids=['1']);self.assertTrue(done.wait(2))
            self.assertEqual(update.call_args.args[1],['1'])

    def test_cancel_and_duplicate_start_use_one_worker(self):
        started=Event();release=Event();finished=Event()
        def work(*args,**kw):
            started.set();release.wait(2)
            try:
                self.assertTrue(kw['cancel'].is_set());raise ValueError('cancelled')
            finally:finished.set()
        with TemporaryDirectory() as root,patch('stormwater.prospect_jobs.run_scan',side_effect=work) as run:
            jobs=ProspectJobs(root);jobs.start(mode='update');self.assertTrue(started.wait(2))
            self.assertEqual(jobs.start(mode='update')['status'],'running');jobs.cancel();release.set();self.assertTrue(finished.wait(2))
            self.assertEqual(run.call_count,1)

    def test_rerank_job_cannot_invoke_acquisition(self):
        done=Event()
        def ranked(*a,**kw):done.set();return {'id':'fixture'}
        with TemporaryDirectory() as root,patch('stormwater.prospect_jobs.run_scan',side_effect=AssertionError('No acquisition')),patch('stormwater.prospect_jobs.rerank_saved',side_effect=ranked):
            jobs=ProspectJobs(root);jobs.start();self.assertTrue(done.wait(2))


if __name__=='__main__':unittest.main()
