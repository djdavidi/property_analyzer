"""Shared records, persistent matches and selected updates without public requests."""
from copy import deepcopy
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
import json
import unittest
from drainage_core.sources import Cache,SourceError,now,canonical
from stormwater.record_cache import SharedCache
from stormwater import prospects as p
from test_prospects import feature,system,billing

URL=p.BILLING+'/1/details'


class SharedRecordTests(unittest.TestCase):
    def test_workflow_reuses_fresh_records_and_records_capture_provenance(self):
        from stormwater.cases import CaseStore,new_case
        with TemporaryDirectory() as tmp:
            root=Path(tmp);case=new_case('Record-only workflow fixture');store=CaseStore(root/'cases')
            store.directory(case['id']).mkdir()
            cache=SharedCache(root/'cache',fallback_roots=[],opener=lambda *a,**kw:self.fail('No public request'))
            source=cache._store(URL,b'{}',retrieved_at=now())[1]
            def gather(value,selected,refresh):
                selected.fetch_json(URL,refresh=refresh);value['assessment']={};return value
            with patch('stormwater.assessment_workflow.gather',side_effect=gather),patch.object(store,'save',return_value={'fixture':True}):
                result=store.run_assessment(case,cache)
            event=result['case']['assessment']['record_reuse'][0]
            self.assertEqual(event['sha256'],source['sha256']);self.assertEqual(event['retrieved_at'],source['retrieved_at'])
            with patch('stormwater.assessment_workflow.gather',side_effect=lambda value,*a,**kw:value),patch.object(store,'save',return_value={'fixture':True}):
                refreshed=store.run_assessment(result['case'],cache,refresh_records=True)
            self.assertEqual(refreshed['case']['assessment']['record_reuse'],[])
            self.assertFalse(cache.reuse_recent_records)

    def test_latest_valid_legacy_capture_promoted_without_retimestamping(self):
        with TemporaryDirectory() as tmp:
            a=Path(tmp)/'a';b=Path(tmp)/'b';primary=Cache(a);legacy=Cache(b)
            old=primary._store(URL,b'{"old":1}',retrieved_at='2025-01-01T00:00:00+00:00')[1]
            expected=legacy._store(URL,b'{"new":1}',retrieved_at='2026-01-01T00:00:00+00:00')[1]
            c=SharedCache(a,fallback_roots=[b],opener=lambda *a,**kw:self.fail('No network'))
            value=c.fetch_json(URL);self.assertEqual(value['data'],{'new':1});self.assertEqual(value['provenance'],expected)
            self.assertEqual((a/'blobs'/old['sha256']).read_bytes(),b'{"old":1}')
            self.assertEqual(legacy._read(URL)[1],expected)

    def test_fresh_records_reused_even_when_full_workflow_requests_refresh(self):
        with TemporaryDirectory() as tmp:
            c=SharedCache(tmp,fallback_roots=[],reuse_recent_records=True,opener=lambda *a,**kw:self.fail('No network'))
            prov=c._store(URL,b'{}',retrieved_at=now())[1]
            self.assertEqual(c.fetch_json(URL,refresh=True)['provenance'],prov)
            self.assertEqual(len(c.reuse_events),1)

    def test_explicit_refresh_stale_and_nonrecord_image_are_not_silently_reused(self):
        for reuse,url,stamp in [(False,URL,now()),(True,URL,'2000-01-01T00:00:00Z'),(True,'https://example.test/image.png',now())]:
            with self.subTest(reuse=reuse,url=url),TemporaryDirectory() as tmp:
                calls=[]
                def blocked(*a,**kw):calls.append(1);raise OSError('Fixture network unavailable')
                c=SharedCache(tmp,fallback_roots=[],reuse_recent_records=reuse,opener=blocked)
                c._store(url,b'{}',retrieved_at=stamp)
                with self.assertRaises(SourceError):c.fetch_json(url,refresh=True)
                self.assertEqual(len(calls),1)

    def test_bad_legacy_bytes_are_rejected(self):
        with TemporaryDirectory() as tmp:
            root=Path(tmp);legacy=Cache(root/'old');prov=legacy._store(URL,b'{}')[1]
            (legacy.root/'blobs'/prov['sha256']).write_bytes(b'bad')
            with self.assertRaises(SourceError):SharedCache(root/'new',fallback_roots=[legacy.root])._read(URL)


class FakeRecords:
    def __init__(self):self.calls=[];self.fail=False;self.owner='PRIVATE HOLDINGS LLC'
    def _read(self,url):return None
    def fetch_json(self,url,refresh=False,metadata=None):
        if self.fail:raise OSError('record unavailable')
        pid=url.split('/')[-2];self.calls.append(pid)
        return {'data':billing(pid,1000,Owner1=self.owner),'provenance':{'url':url,'retrieved_at':now(),'sha256':'a'*64}}


class PersistentSelectedTests(unittest.TestCase):
    def test_utc_capture_uses_philadelphia_day(self):
        self.assertEqual(p.freshness({'retrieved_at':'2026-11-16T02:00:00Z'},'2026-11-15')['status'],'fresh')

    def initial(self,root,records,two=False):
        systems=[system('1')]+([system('2',bounds=(210,10,220,20),project_number='P2')] if two else [])
        parcels=[feature(1)]+([feature(2,(200,0,300,100))] if two else [])
        with patch.object(p,'read_inventory',return_value={'features':systems,'sources':[]}),patch.object(p,'find_parcels',return_value=(parcels,[],[])):
            return p.run_scan(root,cache=records)

    def test_repeat_cached_scan_does_not_query_or_recompute_matches(self):
        with TemporaryDirectory() as root:
            records=FakeRecords();self.initial(root,records)
            with patch.object(p,'read_inventory',return_value={'features':[system()],'sources':[]}),patch.object(p,'find_parcels',side_effect=AssertionError('Reuse matches')),patch.object(p,'match_systems',side_effect=AssertionError('Reuse bindings')):
                result=p.run_scan(root,cache=records)
            self.assertEqual(result['persistent_matches'],'reused')

    def test_changed_system_geometry_and_tampered_index_are_rejected(self):
        with TemporaryDirectory() as root:
            records=FakeRecords();self.initial(root,records)
            self.assertIsNone(p.read_matches(root,[system(bounds=(11,10,20,20))],records,'2026-11-15'))
            path=Path(root)/'matches.json';value=json.loads(path.read_text());value['version']=2;path.write_text(json.dumps(value))
            with self.assertRaises(ValueError):p.read_matches(root,[system()],records,'2026-11-15')

    def test_changed_cached_parcel_source_invalidates_match(self):
        with TemporaryDirectory() as root,TemporaryDirectory() as cache_root:
            cache=Cache(cache_root);url='https://example.test/parcels';old=cache._store(url,b'{}')[1]
            matches,held,errors=p.match_systems([system()],[feature(1)])
            p.write_matches(root,[system()],[feature(1)],matches,held,errors,[old])
            self.assertIsNotNone(p.read_matches(root,[system()],cache,now()[:10]))
            cache._store(url,b'{"geometry_changed":true}')
            self.assertIsNone(p.read_matches(root,[system()],cache,now()[:10]))

    def test_selected_update_only_reads_selected_bill_and_preserves_others(self):
        with TemporaryDirectory() as root:
            records=FakeRecords();before=self.initial(root,records,two=True);records.calls=[]
            with patch.object(p,'read_inventory',side_effect=AssertionError('No inventory')),patch.object(p,'find_parcels',side_effect=AssertionError('No matching')):
                after=p.update_selected(root,['1'],cache=records)
            self.assertEqual(records.calls,['1']);self.assertEqual(after['selected_parcel_ids'],['1'])
            old=next(r for r in before['parcel_rows'] if r['parcel_id']=='2');new=next(r for r in after['parcel_rows'] if r['parcel_id']=='2')
            self.assertEqual(p.canonical(old),p.canonical(new))

    def test_unknown_selection_never_requests_data(self):
        with TemporaryDirectory() as root:
            records=FakeRecords();self.initial(root,records);records.calls=[]
            with self.assertRaises(ValueError):p.update_selected(root,['999'],cache=records)
            self.assertEqual(records.calls,[])

    def test_failed_selected_record_retains_earlier_value_and_flags_review(self):
        with TemporaryDirectory() as root:
            records=FakeRecords();before=self.initial(root,records);records.fail=True
            after=p.update_selected(root,['1'],cache=records)
            self.assertEqual(before['top'][0]['billing']['monthly_charge'],after['top'][0]['billing']['monthly_charge'])
            self.assertTrue(after['top'][0]['needs_record_review']);self.assertEqual(len(after['selected_update_failures']),1)

    def test_new_government_owner_excluded_and_match_index_invalidated(self):
        with TemporaryDirectory() as root:
            records=FakeRecords();self.initial(root,records);records.owner='CITY OF PHILADELPHIA'
            after=p.update_selected(root,['1'],cache=records)
            self.assertEqual(after['top'],[]);self.assertEqual(after['counts']['exclusions_by_status']['government'],1)
            self.assertFalse((Path(root)/'matches.json').exists())
            self.assertTrue(list(Path(root).glob('matches-invalidated-*.json')))


if __name__=='__main__':unittest.main()
