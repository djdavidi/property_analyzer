from copy import deepcopy
import json
from pathlib import Path
import tempfile
import unittest
from stormwater.cases import CaseStore,canonical
from stormwater.fixtures import synthetic_case


class AssessmentPortabilityTests(unittest.TestCase):
    def test_originals_from_old_revisions_export_even_if_current_inventory_empty(self):
        with tempfile.TemporaryDirectory() as one,tempfile.TemporaryDirectory() as two:
            source=CaseStore(one);case=synthetic_case();case['id']='portable-history'
            case,attachment=source.attach(case,'original.txt',b'Original superseded record')
            old=source.save(case)
            case['assessment']['attachments']=[];source.save(case)
            bundle=source.portable_bundle(case['id'])
            self.assertEqual(bundle['case']['assessment']['attachments'],[])
            self.assertEqual(len(bundle['attachments']),1)
            destination=CaseStore(two);destination.import_bundle(bundle)
            self.assertEqual((Path(two)/case['id']/'attachments'/attachment['sha256']).read_bytes(),b'Original superseded record')
            self.assertEqual(json.loads((Path(two)/case['id']/'revisions'/(old['input_sha256']+'.json')).read_text())['assessment']['attachments'][0],attachment)

    def test_conflicting_snapshot_rejected_before_current_case_overwrite(self):
        with tempfile.TemporaryDirectory() as root:
            store=CaseStore(root);case=synthetic_case();case['id']='protected'
            store.save(case);bundle=store.portable_bundle(case['id'])
            key='a'*32
            bundle['assessments']={key+'.json':{'id':key,'case':case,'analysis':{'input_sha256':__import__('drainage_core.engine',fromlist=['input_hash']).input_hash(case)}}}
            folder=Path(root)/case['id']/'assessments';folder.mkdir()
            (folder/(key+'.json')).write_text('{"preserved":"different prior work"}')
            bundle['case']['name']='Should never overwrite'
            with self.assertRaisesRegex(ValueError,'conflicts'):
                store.import_bundle(bundle)
            self.assertEqual(store.load(case['id'])['name'],case['name'])
            self.assertEqual(json.loads((folder/(key+'.json')).read_text()),{'preserved':'different prior work'})

    def test_case_directory_symlink_rejected(self):
        with tempfile.TemporaryDirectory() as root,tempfile.TemporaryDirectory() as other:
            (Path(root)/'linked').symlink_to(other,target_is_directory=True)
            with self.assertRaises(ValueError):CaseStore(root).directory('linked')

    def test_snapshot_content_hash_detects_changed_analysis(self):
        from hashlib import sha256
        from unittest.mock import patch
        from stormwater.assessment_workflow import ensure_assessment
        with tempfile.TemporaryDirectory() as root:
            store=CaseStore(root);case=synthetic_case();case['id']='snapshot-integrity'
            def offline(c,*args,**kwargs):
                c=deepcopy(c);ensure_assessment(c);return c
            with patch('stormwater.assessment_workflow.gather',side_effect=offline):
                store.run_assessment(case)
            bundle=store.portable_bundle(case['id'])
            snapshot=next(iter(bundle['assessments'].values()))
            self.assertEqual(snapshot['snapshot_sha256'],sha256(canonical({k:v for k,v in snapshot.items() if k!='snapshot_sha256'}).encode()).hexdigest())
            snapshot['analysis']['assessment']['economics']['modeled']['gross_monthly_reduction']=999999
            with self.assertRaisesRegex(ValueError,'snapshot content hash'):
                store.import_bundle(bundle)
