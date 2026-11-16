import base64
from copy import deepcopy
from hashlib import sha256
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from drainage_core.evidence import AttachmentStore, validate_references
from stormwater.assessment_sources import normalize_gsi, normalize_permit, discover, _Fallback
from stormwater.assessment_workflow import review_record, gather


def case():
    return {'id':'evidence-test','crs':'EPSG:2272','parcel':{'type':'Polygon','coordinates':[[[0,0],[10,0],[10,10],[0,10],[0,0]]]},
            'sources':[],'assessment':{'records':[],'attachments':[],'credit_history':[],
            'identifiers':{'permit_id':'PA0001234'}}}


class AttachmentTests(unittest.TestCase):
    def test_original_bytes_roundtrip_and_portability(self):
        with tempfile.TemporaryDirectory() as one,tempfile.TemporaryDirectory() as two:
            store=AttachmentStore(one);raw=b'%PDF-1.4\nopaque original evidence\n'
            info=store.add('award letter.pdf',raw,{'document_date':'2024-01-01'})
            self.assertEqual(info['sha256'],sha256(raw).hexdigest())
            bundle=store.export([info]);imported=AttachmentStore(two)
            self.assertEqual(imported.import_bundle(bundle),[info])
            self.assertEqual(imported.read(info['sha256']),raw)
            self.assertEqual(list(Path(two).iterdir())[0].name,info['sha256'])
            c=case();c['assessment']['attachments']=[info]
            c['assessment']['records']=[{'evidence_refs':[{'attachment_id':info['id'],'page':2}]}]
            validate_references(c['assessment'])

    def test_traversal_executable_disguise_and_mismatch_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            store=AttachmentStore(folder)
            for name,content in [('../a.pdf',b'%PDF-1.4'),('a\\b.pdf',b'%PDF-1.4'),('script.py',b'print(1)'),
                                 ('bad.pdf',b'MZexecutable'),('bad.txt',b'#!/bin/sh'),('fake.png',b'not png'),
                                 ('binary.txt',b'\x00hidden'),('a\n.pdf',b'%PDF-1.4')]:
                with self.subTest(name=name), self.assertRaises(ValueError):store.add(name,content)
            good=store.add('a.txt',b'original')
            item={**good,'content_base64':base64.b64encode(b'changed').decode()}
            with self.assertRaises(ValueError):store.import_bundle([item])
            (Path(folder)/good['sha256']).write_bytes(b'tampered')
            with self.assertRaises(ValueError):store.read(good['sha256'])

    def test_symlink_and_reference_rejection(self):
        with tempfile.TemporaryDirectory() as folder:
            base=Path(folder);(base/'linked').symlink_to(base,target_is_directory=True)
            with self.assertRaises(ValueError):AttachmentStore(base/'linked')
            store=AttachmentStore(base/'bytes');digest='a'*64
            (base/'bytes'/digest).symlink_to(base/'missing')
            with self.assertRaises(ValueError):store.read(digest)
        with self.assertRaises(ValueError):validate_references({'records':[{'evidence_refs':[{'attachment_id':'missing'}]}]})
        with self.assertRaises(ValueError):validate_references({'records':[{'evidence_refs':[{'page':0}]}]})


class CandidateTests(unittest.TestCase):
    def test_project_and_system_candidates_never_claim_installed_area(self):
        feature={'id':4,'geometry':{'type':'Point','coordinates':[1,2]},
                 'properties':{'green_roof':1,'porous_pavement':1,'overallstatuscategory':'Proposed'}}
        rows=normalize_gsi(feature,'https://city.test','EPSG:2272','project')
        self.assertEqual({r['category'] for r in rows},{'green_roof','permeable_pavement'})
        for r in rows:
            self.assertEqual(r['decision'],'candidate');self.assertIsNone(r['managed_area_sqft'])
            self.assertIsNone(r['facts']['installed']);self.assertTrue(r['facts']['proposed_only'])
            self.assertNotIn('geometry',r)

    def test_name_and_exact_permit_candidates_require_site_operator_and_compliance(self):
        row={'SourceID':'PA0001234','CWPName':'Example Factory','CWPStreet':'A Street'}
        match=normalize_permit(row,'https://epa.test',{'permit_id':'PA0001234'})
        self.assertTrue(match['facts']['identifier_exact_match'])
        self.assertIsNone(match['facts']['site_match']);self.assertIsNone(match['facts']['operator_match'])
        self.assertIsNone(match['facts']['industrial_stormwater']);self.assertIsNone(match['facts']['compliance_confirmed'])
        self.assertFalse(normalize_permit(row,'https://epa.test',{'operator_name':'Example Factory'})['facts']['identifier_exact_match'])

    def test_review_preserves_old_candidate_and_manual_refs_through_rerun(self):
        c=case();candidate=normalize_gsi({'id':1,'properties':{'gsi_system_type':'Green Roof'}},'https://city.test','EPSG:2272')[0]
        c['assessment']['records']=[candidate];original=deepcopy(c)
        changed={**candidate,'decision':'rejected','facts':{'installed':False}}
        reviewed=review_record(c,changed,'Site review: proposed only','2026-11-15')
        self.assertEqual(c,original)
        self.assertEqual(reviewed['assessment']['reviews'][0]['before'],candidate)
        result={'records':[candidate],'observations':[],'source_status':[{'status':'unavailable'}],'sources':[]}
        with patch('stormwater.assessment_sources.discover',return_value=result):rerun=gather(reviewed,None)
        self.assertEqual(rerun['assessment']['records'][0]['decision'],'rejected')
        self.assertEqual(rerun['assessment']['reviews'],reviewed['assessment']['reviews'])
        self.assertEqual(rerun['assessment']['source_status'][:-1],result['source_status'])
        self.assertEqual(rerun['assessment']['source_status'][-1]['provider'],'USDA NRCS SSURGO / Soil Data Access')
        self.assertEqual(rerun['assessment']['source_status'][-1]['status'],'unavailable')

    def test_outage_reuses_dated_cache_without_false_empty(self):
        class Cache:
            def fetch_json(self,*args,**kwargs):raise OSError('offline')
            def _read(self,url):return b'{"features":[{"id":1}]}',{'retrieved_at':'2024-01-01','sha256':'abc'}
        proxy=_Fallback(Cache());item=proxy.fetch_json('https://city.test',True)
        self.assertEqual(item['data']['features'],[{'id':1}])
        self.assertEqual(item['provenance']['retrieved_at'],'2024-01-01')
        self.assertTrue(item['provenance']['cache_reused_after_failure'])
        self.assertTrue(proxy.used_cache)

    def test_invalid_or_partial_epa_rows_and_city_failures_are_explicit(self):
        class Cache:
            def fetch_json(self,url,*args,**kwargs):
                if 'get_facilities' in url:return {'data':{'Results':{'QueryRows':'1','QueryID':'42'}},'provenance':{'sha256':'abc'}}
                if 'get_qid' in url:return {'data':{'Results':{'Facilities':[]}},'provenance':{'sha256':'def'}}
                raise OSError('city offline')
            def _read(self,url):return None
        with patch('pyproj.Transformer.from_crs'):
            result=discover(case(),Cache())
        self.assertEqual(result['records'],[])
        self.assertEqual([s['status'] for s in result['source_status']],['unavailable','unavailable','unavailable','missing_identifier'])
        self.assertIn('incomplete',result['source_status'][2]['errors'][0])

    def test_review_rejects_missing_reason_and_dangling_reference(self):
        record={'category':'green_roof','decision':'confirmed','basis':'documented','facts':{},'evidence_refs':[{'attachment_id':'absent'}]}
        with self.assertRaises(ValueError):review_record(case(),record,'')
        with self.assertRaises(ValueError):review_record(case(),record,'reviewed document')

class FrozenPublicExamples(unittest.TestCase):
    def test_primary_public_example_hashes_and_conservative_normalization(self):
        folder=Path(__file__).resolve().parents[1]/'examples/assessment-public/sources'
        records=[];direct_rows=None
        for item in json.loads((folder/'manifest.json').read_text()):
            content=(folder/item['filename']).read_bytes()
            self.assertEqual(sha256(content).hexdigest(),item['sha256'])
            data=json.loads(content)
            if item['label'] in ('green_roof','permeable_pavement','direct_discharge'):
                for feature in data['features']:records.extend(normalize_gsi(feature,item['url'],'EPSG:2272'))
                if item['label']=='direct_discharge':direct_rows=len(data['features'])
            if item['label']=='npdes_rows':
                records.extend(normalize_permit(row,item['url'],{'permit_id':'PA0054241'}) for row in data['Results']['Facilities'])
        self.assertEqual([r['category'] for r in records].count('green_roof'),2)
        self.assertEqual([r['category'] for r in records].count('permeable_pavement'),1)
        self.assertEqual([r['category'] for r in records].count('industrial_npdes'),1)
        self.assertEqual(direct_rows,0)
        self.assertTrue(all(r['decision']=='candidate' for r in records))


class PublicCreditObservations(unittest.TestCase):
    @staticmethod
    def observed(pending, digest='a'*64, retrieved='2026-11-15T06:48:06+00:00'):
        return {'provider':'PWD account/credit public record','url':'https://stormwater.phila.gov/PwdWebApi/api/v1/parcel/98627/details',
                'retrieved_at':retrieved,'source_sha256':digest,'raw_record':{'Pending':pending,
                    'Accounts':[{'AccountName':'must not copy','AccountId':'private-looking-identifier'}]}}

    def test_flag_zero_and_one_are_observations_without_awards_or_dates(self):
        from stormwater.assessment_workflow import credit_observations
        c=case();c['assessment']['observations']=[self.observed({'Credits':0,'Expired':1,'Appeals':0})]
        before=deepcopy(c);rows=credit_observations(c)
        self.assertEqual(len(rows),1);row=rows[0]
        self.assertEqual((row['credits_flag'],row['expired_flag'],row['appeals_flag']),(0,1,0))
        self.assertTrue(row['unknown_dates']);self.assertIsNone(row['effective_date']);self.assertIsNone(row['expiry_date'])
        self.assertEqual(row['source_sha256'],'a'*64);self.assertEqual(row['retrieved_at'],'2026-11-15T06:48:06+00:00')
        self.assertEqual(c,before);self.assertEqual(c['assessment']['credit_history'],[])
        self.assertNotIn('must not copy',json.dumps(rows));self.assertNotIn('private-looking-identifier',json.dumps(rows))
        self.assertIn('do not establish',row['interpretation'])

    def test_missing_flags_stay_unknown_and_zero_does_not_establish_absence(self):
        from stormwater.assessment_workflow import credit_observations
        c=case();self.assertEqual(credit_observations(c),[])
        c['assessment']['observations']=[self.observed({'Credits':0,'Expired':0})]
        row=credit_observations(c)[0]
        self.assertEqual(row['expired_flag'],0);self.assertIsNone(row['appeals_flag'])
        self.assertFalse(row['unknown_dates']);self.assertIsNone(row['expiry_date'])
        self.assertIn('Complete award/credit history and supporting dates',row['missing_evidence'])
        c['assessment']['observations']=[self.observed(None)]
        row=credit_observations(c)[0]
        self.assertTrue(all(row[name+'_flag'] is None for name in ('credits','expired','appeals')))

    def test_saved_flags_with_conflicting_sources_are_retained_and_duplicate_snapshots_collapsed(self):
        from stormwater.assessment_workflow import credit_observations
        c=case();first=self.observed({'Credits':0,'Expired':1,'Appeals':0})
        second=self.observed({'Credits':1,'Expired':0,'Appeals':0},'b'*64,'2026-11-16')
        c['assessment']['observations']=[first,deepcopy(first),second]
        rows=credit_observations(c)
        self.assertEqual(len(rows),2);self.assertEqual([r['expired_flag'] for r in rows],[1,0])
        self.assertTrue(all(r['expiry_date'] is None for r in rows))

    def test_baseline_pending_retains_available_source_and_invalid_value_is_unknown(self):
        from stormwater.assessment_workflow import credit_observations
        c=case();c['pending']={'Credits':0,'Expired':'unknown','Appeals':1}
        c['sources']=[{'url':'https://stormwater.phila.gov/PwdWebApi/api/v1/parcel/98627/details',
                       'retrieved_at':'2026-01-01','sha256':'c'*64}]
        row=credit_observations(c)[0]
        self.assertIsNone(row['expired_flag']);self.assertEqual(row['appeals_flag'],1)
        self.assertEqual(row['source_sha256'],'c'*64);self.assertEqual(row['retrieved_at'],'2026-01-01')


if __name__=='__main__':unittest.main()
