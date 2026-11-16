"""Real loopback HTTP checks for review/save/reopen/export and trust boundaries.

Run using the same Python environment as the app. These tests intentionally bind
an ephemeral loopback port; they do not access the internet or the user's browser.
"""
from copy import deepcopy
from hashlib import sha256
from http.client import HTTPConnection
from http.server import ThreadingHTTPServer
import json
from pathlib import Path
import tempfile
from threading import Thread
import unittest
from unittest.mock import patch

from shapely.geometry import box, mapping
from stormwater.cases import CaseStore, canonical, new_case
from stormwater.server import Handler
import network_guard


def fixture():
    c=new_case('HTTP evidence <script>unsafe()</script>')
    c['crs']='EPSG:26918'
    c['parcel']=mapping(box(500000,4420000,500100,4420100))
    c['features']['features']=[{'id':'pavement','type':'Feature',
        'geometry':deepcopy(c['parcel']),
        'properties':{'layer':'surface','class':'pavement','source_family':'independent synthetic fixture'}}]
    c['sources']=[{'url':'https://example.test/frozen-observation',
        'retrieved_at':'2026-11-15T12:00:00Z','acquisition_date':'2026-11-01',
        'sha256':sha256(b'independent synthetic fixture').hexdigest(),
        'crs':c['crs'],'horizontal_unit':'m','resolution':1}]
    c['manual_review_minutes']=2.5
    return c


class HTTPWorkflowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        network_guard.install()
        cls.temp=tempfile.TemporaryDirectory()
        store=CaseStore(cls.temp.name)
        class TestHandler(Handler):
            def log_message(self,*args): pass
        TestHandler.store=store
        # Public caches (including USDA soil queries) stay in the temporary folder,
        # and every public source is unavailable unless a test stubs it.
        TestHandler.data_root=store.data_root
        TestHandler.source_opener=network_guard.offline_opener
        cls.server=ThreadingHTTPServer(('127.0.0.1',0),TestHandler)
        cls.server.daemon_threads=True
        cls.thread=Thread(target=cls.server.serve_forever,daemon=True)
        cls.thread.start();cls.port=cls.server.server_address[1]

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown();cls.server.server_close();cls.thread.join(timeout=5)
        cls.temp.cleanup()

    def request(self,path,payload=None,headers=None,method=None,raw=None):
        conn=HTTPConnection('127.0.0.1',self.port,timeout=10)
        data=raw if raw is not None else json.dumps(payload).encode() if payload is not None else None
        request_headers={'Content-Type':'application/json'} if data is not None else {}
        request_headers.update(headers or {})
        try:
            conn.request(method or ('POST' if data is not None else 'GET'),path,body=data,headers=request_headers)
            response=conn.getresponse();body=response.read()
            return response.status,dict(response.getheaders()),body
        finally:conn.close()

    def json_request(self,path,payload=None,**kwargs):
        code,headers,body=self.request(path,payload,**kwargs)
        return code,headers,json.loads(body)

    def test_static_interface_served_locally(self):
        for path,part in [('/',b'Drainage workbench'),('/app.js',b'/api/analyze'),('/style.css',b'body')]:
            code,headers,body=self.request(path)
            self.assertEqual(code,200,path);self.assertIn(part,body)
            self.assertEqual(headers['X-Content-Type-Options'],'nosniff')

    def test_save_reopen_rerun_all_exports_without_acquisition(self):
        c=fixture()
        with patch('stormwater.acquisition.acquire_property',side_effect=AssertionError('Frozen case must not reacquire')):
            code,_,result=self.json_request('/api/save',{'case':c})
            self.assertEqual(code,200,result)
            digest=result['input_sha256']
            code,_,reopened=self.json_request('/api/cases/'+c['id'])
            self.assertEqual(code,200);self.assertEqual(canonical(c),canonical(reopened))
            code,_,rerun=self.json_request('/api/analyze',{'case':reopened})
            self.assertEqual(code,200);self.assertEqual(rerun['input_sha256'],digest)
            self.assertEqual(rerun['measurement'],result['measurement'])
            for name in ['case.json','analysis.json','measurements.geojson','report.html']:
                code,headers,body=self.request('/exports/'+c['id']+'/'+name)
                self.assertEqual(code,200,name);self.assertGreater(len(body),0)
                if name!='report.html':
                    data=json.loads(body)
                    self.assertEqual(data.get('input_sha256',digest),digest)
                    if name=='case.json':self.assertEqual(data['sources'],c['sources'])
                    if name=='measurements.geojson':
                        self.assertEqual(data['type'],'FeatureCollection')
                        x,y=data['features'][0]['geometry']['coordinates'][0][0]
                        self.assertTrue(-180<=x<=180);self.assertTrue(-90<=y<=90)
                else:
                    self.assertIn(b'&lt;script&gt;unsafe()&lt;/script&gt;',body)
                    self.assertNotIn(b'<script>unsafe()',body)
                    self.assertIn(digest.encode(),body)
            code,_,listed=self.json_request('/api/cases')
            self.assertEqual(code,200);self.assertIn(c['id'],[x['id'] for x in listed])

    def test_corrections_and_prior_source_revision_are_retained(self):
        c=fixture();code,_,before=self.json_request('/api/save',{'case':c});self.assertEqual(code,200)
        original=deepcopy(c)
        c['corrections']=[{'id':'garden-review','at':'2026-11-15T12:01:00Z','reason':'Synthetic independent lawn evidence',
            'action':'add','feature':{'id':'garden','type':'Feature','geometry':mapping(box(500000,4420000,500050,4420100)),
                                   'properties':{'layer':'surface','class':'pervious'}}}]
        code,_,after=self.json_request('/api/save',{'case':c});self.assertEqual(code,200,after)
        self.assertNotEqual(before['input_sha256'],after['input_sha256'])
        self.assertAlmostEqual(after['measurement']['ia_sqft'],before['measurement']['ia_sqft']/2)
        code,_,loaded=self.json_request('/api/cases/'+c['id']);self.assertEqual(code,200)
        self.assertEqual(canonical(loaded['features']),canonical(original['features']))
        self.assertEqual(loaded['sources'],original['sources'])
        self.assertEqual(canonical(loaded['corrections']),canonical(c['corrections']))
        revision=Path(self.temp.name)/c['id']/'revisions'/(before['input_sha256']+'.json')
        self.assertEqual(canonical(json.loads(revision.read_text())),canonical(original))
        _,_,export1=self.request('/exports/'+c['id']+'/measurements.geojson')
        code,_,again=self.json_request('/api/save',{'case':loaded});self.assertEqual(code,200)
        _,_,export2=self.request('/exports/'+c['id']+'/measurements.geojson')
        self.assertEqual(export1,export2)
        self.assertEqual(after['input_sha256'],again['input_sha256'])

    def test_invalid_json_nan_and_case_path_rejected(self):
        for raw in [b'{',b'{"case":NaN}',b'{"case":{"schema_version":1,"id":"../escape","crs":"EPSG:26918"}}']:
            code,_,body=self.json_request('/api/save',raw=raw)
            self.assertEqual(code,400,body)
        c=fixture();c['parcel']=None
        code,_,body=self.json_request('/api/analyze',{'case':c})
        self.assertEqual(code,400);self.assertIn('parcel',body['error'])

    def test_exports_cannot_traverse_or_select_arbitrary_files(self):
        for path in ['/exports/../report.html','/exports/%2e%2e/report.html',
                     '/exports/case/../../README.md','/exports/case/other-file',
                     '/api/cases/%2e%2e','/api/blob/../README.md','/../../../README.md']:
            code,_,body=self.request(path)
            self.assertEqual(code,404,(path,body))

    def test_foreign_origins_and_hosts_cannot_mutate(self):
        c=fixture()
        for headers in [{'Origin':'https://foreign.example'}, {'Origin':'null'}, {'Host':'foreign.example'}]:
            code,_,body=self.json_request('/api/save',{'case':c},headers=headers)
            self.assertEqual(code,403,body)
        code,_,body=self.json_request('/api/save',{'case':c},headers={'Origin':f'http://127.0.0.1:{self.port}'})
        self.assertEqual(code,200,body)

    def test_foreign_host_cannot_read_local_case_inventory(self):
        code,_,body=self.request('/api/cases',headers={'Host':'foreign.example'})
        self.assertEqual(code,403,body)

    def test_acquisition_imagery_failure_remains_explicit(self):
        c=fixture()
        acquired={k:deepcopy(c[k]) for k in ['crs','parcel','features','sources']}
        acquired.update(parcel_id=98627,address='Synthetic acquired property',warnings=['Ground surfaces unavailable'])
        with patch('stormwater.acquisition.acquire_property',return_value=acquired), \
             patch('stormwater.acquisition.acquire_imagery',side_effect=OSError('Synthetic unavailable tile')):
            code,_,case=self.json_request('/api/acquire',{'parcel_id':98627,'refresh':False})
        self.assertEqual(code,200,case)
        self.assertIn('Ground surfaces unavailable',case['warnings'])
        self.assertTrue(any('Imagery unavailable' in x for x in case['warnings']))
        self.assertNotIn('imagery',case)
        self.assertEqual(case['sources'],c['sources'])

if __name__=='__main__':unittest.main()
