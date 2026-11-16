"""Public-record reruns against reviewed facts (review A4/R3); invented inputs only.

Derived from docs/review-2026-11-16-repros/prospects/gather_repro.py and roundtrip.py.
Discovery and soil acquisition are stubbed; nothing is fetched or saved.
"""
from copy import deepcopy
from hashlib import sha256
import json
import shutil
import subprocess
import unittest
from unittest.mock import patch

import network_guard
from stormwater.acquisition import normalize_billing
from stormwater.assessment_workflow import _digest,ensure_assessment,gather,reconcile_baseline,review_record

network_guard.install()
URL='https://example.test/records'
RAW={'Parcel':{'GrossArea':10000,'ImpervArea':8000,'BldgType':'NonRes'},
     'ChargeSummary':{'GrossCreditSqFt':0,'ImpervCreditSqFt':0}}


def public(facts=None,**extra):
    return {'id':'r1','category':'green_roof','decision':'candidate','basis':'public_candidate',
            'facts':facts if facts is not None else {'public_status':'Installed'},'source':{'url':URL},**extra}


def billing(raw):
    return {'provider':'PWD account/credit public record','raw_record':raw}


def run(case,records,observations=()):
    """One gather against a completed source query returning exactly ``records``."""
    discovery={'records':deepcopy(list(records)),'observations':deepcopy(list(observations)),
               'source_status':[{'url':URL,'status':'retrieved'}],'sources':[]}
    with patch('stormwater.assessment_sources.discover',return_value=discovery), \
         patch('stormwater.soil_sources.acquire',side_effect=lambda c,*a,**k:c):
        return gather(case,None)


def confirm(case,facts=None):
    record=case['assessment']['records'][0]
    corrected={**record,'decision':'confirmed','basis':'manual','facts':facts or {'existing_installation':True}}
    return review_record(case,corrected,'Synthetic reviewer corrected the public facts')


def browser_round_trip(value):
    """JSON.parse(JSON.stringify(value)) in JavaScript: whole-number floats come back as integers."""
    def number(text):
        parsed=float(text)
        return int(parsed) if parsed.is_integer() else parsed
    return json.loads(json.dumps(value),parse_float=number)


def record_of(case):
    return case['assessment']['records'][0]


class ReviewedRecordRerunTests(unittest.TestCase):
    def test_reviewed_corrections_are_not_a_public_change_for_legacy_records(self):
        # Saved before public snapshots existed: the public version comes from review history.
        case={'id':'x'};ensure_assessment(case)['records']=[public()]
        case=confirm(case)
        for _ in range(2):
            case=run(case,[public()])
            self.assertNotIn('source_update',record_of(case))
            self.assertEqual(record_of(case)['facts'],{'existing_installation':True})
            self.assertNotIn('record_history',case['assessment'])
        snapshot=case['assessment']['public_snapshots']['r1']
        self.assertEqual(snapshot['content']['facts'],public()['facts'])
        self.assertEqual(snapshot['origin'],'derived:first_review_before')
        self.assertEqual(len(case['assessment']['reviews']),1)

    def test_public_snapshot_recorded_at_discovery_is_the_comparison_basis(self):
        case=run({'id':'x'},[public()])
        self.assertEqual(case['assessment']['public_snapshots']['r1']['origin'],'source')
        case=run(confirm(case),[public()])
        self.assertNotIn('source_update',record_of(case))

    def test_whole_number_float_in_public_content_is_not_a_change(self):
        case=run({'id':'x'},[public({'area_sqft':1000.0})])
        case=run(confirm(case),[public({'area_sqft':1000})])
        self.assertNotIn('source_update',record_of(case))

    def test_changed_source_is_staged_once_and_stays_reviewed(self):
        case=confirm(run({'id':'x'},[public()]))
        changed=public({'public_status':'Removed'})
        case=run(case,[changed]);update=record_of(case)['source_update']
        self.assertEqual((update['status'],update['kind']),('pending_review','changed'))
        self.assertEqual(update['candidate'],changed)
        self.assertEqual(record_of(case)['facts'],{'existing_installation':True})
        history=len(case['assessment']['record_history'])
        case=run(case,[changed])
        self.assertEqual(record_of(case)['source_update'],update)
        case=review_record(case,record_of(case),'Reviewed the public change; corrected facts retained')
        self.assertEqual(record_of(case)['source_update']['status'],'reviewed')
        case=run(case,[changed])
        self.assertEqual(record_of(case)['source_update']['status'],'reviewed')
        self.assertEqual(len(case['assessment']['record_history']),history)

    def test_unestablished_public_version_is_staged_but_identical_raw_row_is_not(self):
        manual={**public(),'basis':'manual','decision':'confirmed','facts':{'existing_installation':True}}
        case=review_record({'id':'x'},manual,'Manual record created by a reviewer')
        self.assertEqual(record_of(run(case,[public()]))['source_update']['status'],'pending_review')
        row={'objectid':7,'type':'green roof'}
        case=review_record({'id':'x'},{**manual,'raw_record':row},'Manual record with its source row')
        self.assertNotIn('source_update',record_of(run(case,[public(raw_record=row)])))
        self.assertIn('source_update',record_of(run(case,[public(raw_record={**row,'objectid':8})])))


class DisappearanceTests(unittest.TestCase):
    def test_flag_set_once_and_cleared_when_identical_record_returns(self):
        case=run(run({'id':'x'},[public()]),[])
        flag=record_of(case)['source_update']
        self.assertEqual((flag['status'],flag['kind']),('pending_review','disappeared'))
        self.assertIn('not proof of removal or zero area',flag['reason'])
        self.assertEqual(record_of(run(case,[]))['source_update'],flag)
        case=run(case,[public()])
        self.assertNotIn('source_update',record_of(case))
        event=case['assessment']['record_history'][-1]
        self.assertEqual((event['event'],event['before']['source_update']),('returned_unchanged',flag))
        self.assertEqual(record_of(case)['facts'],public()['facts'])

    def test_legacy_disappearance_flag_also_clears(self):
        legacy={'status':'pending_review','observed_at':'2026-11-01T00:00:00Z',
                'reason':'Not returned by a completed source query; disappearance is not proof of removal or zero area'}
        case={'id':'x'};ensure_assessment(case)['records']=[public(source_update=legacy)]
        self.assertNotIn('source_update',record_of(run(case,[public()])))

    def test_disappearance_does_not_overwrite_a_staged_change(self):
        changed=public({'public_status':'Removed'})
        case=run(confirm(run({'id':'x'},[public()])),[changed])
        staged=record_of(case)['source_update']
        self.assertEqual(record_of(run(case,[]))['source_update'],staged)

    def test_reviewed_disappearance_is_not_restaged_and_earlier_review_is_restored(self):
        changed=public({'public_status':'Removed'})
        case=run(confirm(run({'id':'x'},[public()])),[changed])
        case=review_record(case,record_of(case),'Reviewed public change')
        reviewed=record_of(case)['source_update']
        case=run(case,[])
        self.assertEqual(record_of(case)['source_update']['previous'],reviewed)
        case=review_record(case,record_of(case),'Absence reviewed; documented installation retained')
        self.assertEqual(record_of(run(case,[]))['source_update']['status'],'reviewed')
        case=run(case,[changed])
        self.assertEqual(record_of(case)['source_update'],reviewed)


class BaselineRefreshTests(unittest.TestCase):
    def test_retained_baseline_is_not_restaged_for_identical_public_data(self):
        case={'id':'x','baseline':{**normalize_billing(RAW),'ia_sqft':7000.0,'actual_bill_verified':True}}
        case=run(case,[],[billing(RAW)])
        self.assertEqual(case['assessment']['baseline_refresh']['fields_changed'],['ia_sqft'])
        case=reconcile_baseline(case,'Invoice verified; keep 7000 sqft',False)
        for _ in range(2):
            case=run(case,[],[billing(RAW)])
            self.assertEqual(case['assessment']['baseline_refresh']['status'],'retained_by_review')
            self.assertEqual(case['baseline']['ia_sqft'],7000.0)
        changed={**RAW,'Parcel':{**RAW['Parcel'],'ImpervArea':7500}}
        case=run(case,[],[billing(changed)])
        self.assertEqual(case['assessment']['baseline_refresh']['status'],'pending_review')

    def test_accepted_baseline_is_not_restaged(self):
        case=run({'id':'x','baseline':{**normalize_billing(RAW),'ia_sqft':7000.0}},[],[billing(RAW)])
        case=run(reconcile_baseline(case,'Public areas reviewed',True),[],[billing(RAW)])
        self.assertEqual(case['assessment']['baseline_refresh']['status'],'accepted')

    def test_review_survives_browser_number_round_trip(self):
        changed={**RAW,'Parcel':{**RAW['Parcel'],'ImpervArea':7500}}
        case={'id':'pwd-1','baseline':normalize_billing(RAW)}
        self.assertIsInstance(case['baseline']['ga_sqft'],float)
        returned=browser_round_trip(run(case,[],[billing(changed)]))
        self.assertIsInstance(returned['baseline']['ga_sqft'],int)
        self.assertEqual(reconcile_baseline(returned,'Reviewed public areas',True)['baseline']['ia_sqft'],7500)
        retained=browser_round_trip(reconcile_baseline(returned,'Invoice supports the earlier baseline',False))
        again=run(retained,[],[billing(changed)])
        self.assertEqual(again['assessment']['baseline_refresh']['status'],'retained_by_review')

    @unittest.skipUnless(shutil.which('node'),'Node is unavailable; real JavaScript round trip omitted')
    def test_review_survives_real_javascript_round_trip(self):
        changed={**RAW,'Parcel':{**RAW['Parcel'],'ImpervArea':7500}}
        wire=json.dumps(run({'id':'pwd-1','baseline':normalize_billing(RAW)},[],[billing(changed)]))
        script='process.stdout.write(JSON.stringify(JSON.parse(require("fs").readFileSync(0,"utf8"))))'
        output=subprocess.run(['node','-e',script],input=wire,capture_output=True,text=True,check=True).stdout
        self.assertNotEqual(output,wire)
        self.assertEqual(reconcile_baseline(json.loads(output),'Reviewed invoice',True)['baseline']['ia_sqft'],7500)

    def test_comparison_hashed_before_normalisation_remains_reviewable(self):
        baseline=normalize_billing(RAW)
        legacy=sha256(json.dumps(baseline,sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest()
        self.assertNotEqual(legacy,_digest(baseline))
        case={'id':'x','baseline':baseline,'assessment':{'baseline_refresh':{'status':'pending_review',
              'retained_baseline_sha256':legacy,'candidate':{**baseline,'ia_sqft':7500.0}}}}
        self.assertEqual(reconcile_baseline(case,'Reviewed',False)['assessment']['baseline_refresh']['status'],'retained_by_review')


if __name__=='__main__':
    unittest.main()
