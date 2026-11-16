"""Known answer for examples/assessment-synthetic, hand-derived in its README.

Invented inputs only; nothing is saved and no source is contacted.
"""
from datetime import date
import importlib.util
import json
from pathlib import Path
import unittest
from unittest.mock import patch

EXAMPLE=Path(__file__).resolve().parents[1]/'examples'/'assessment-synthetic'


def load_example():
    spec=importlib.util.spec_from_file_location('assessment_synthetic_build',EXAMPLE/'build.py')
    module=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class SyntheticExampleKnownAnswerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.example=load_example()
        # A later wall clock must not change the pinned answer.
        with patch('stormwater.renewals.today',return_value=date(2030,1,1)), \
             patch('stormwater.cases.CaseStore.save',side_effect=AssertionError('Known answer must not save')):
            cls.result=cls.example.known_answer()
        cls.assessment=cls.result['assessment']
        cls.economics=cls.assessment['economics']

    def test_pinned_date_and_every_category_screens(self):
        self.assertEqual(self.example.AS_OF,'2026-11-15')
        self.assertEqual(self.assessment['as_of'],'2026-11-15')
        statuses={c['category']:c['status'] for c in self.assessment['categories']}
        for category in ('green_roof','permeable_pavement','direct_discharge','industrial_npdes'):
            self.assertEqual(statuses[category],'screen_pass',category)

    def test_baseline_bill_matches_hand_derivation(self):
        bill=self.economics['baseline']
        self.assertEqual(bill['status'],'calculated')
        self.assertEqual((bill['ga_charge'],bill['ia_charge'],bill['monthly_total']),(20.06,112.77,135.64))

    def test_single_ledger_credits_3060_square_feet(self):
        ledger=self.economics['modeled']['ledger']
        credits=[(x['id'],x['ga_credit_sqft'],x['ia_credit_sqft']) for x in ledger['allocations']]
        self.assertEqual(credits,[('green_roof-modeled',870.0,870.0),('permeable_pavement-modeled',870.0,870.0),
                                  ('direct_discharge-modeled',970.0,970.0),('npdes-residual',350.0,350.0)])
        self.assertEqual((ledger['new_ga_credit_sqft'],ledger['new_ia_credit_sqft']),(3060.0,3060.0))

    def test_final_bill_and_conditional_reduction(self):
        modeled=self.economics['modeled']
        self.assertEqual((modeled['status'],modeled['basis']),('calculated','conditional'))
        bill=modeled['bill']
        self.assertEqual((bill['billed_ga_sqft'],bill['billed_ia_sqft']),(7000.0,5000.0))
        self.assertEqual((bill['ga_charge'],bill['ia_charge'],bill['monthly_total']),(14.04,70.48,87.33))
        self.assertEqual((modeled['gross_monthly_reduction'],modeled['gross_annual_reduction']),(48.31,579.72))
        self.assertEqual(self.economics['documented']['status'],'blocked')

    def test_fabricated_public_total_is_review_only_never_a_refund(self):
        flag=next(f for f in self.assessment['historical_flags'] if f['kind']=='billing_discrepancy')
        self.assertEqual((flag['status'],flag['observed_discrepancy']),('review_only',5.64))
        self.assertIsNone(flag['refund_entitlement'])

    def test_readme_states_the_tested_numbers(self):
        readme=(EXAMPLE/'README.md').read_text()
        for text in ('2026-11-15','3,060','870 + 870 + 970 + 350','$135.64','$87.33','$48.31','$579.72'):
            self.assertIn(text,readme)

    def test_saved_fixture_is_the_built_case(self):
        built=json.loads(json.dumps(self.example.build()))
        self.assertEqual(json.loads((EXAMPLE/'case.json').read_text()),built)
        for record in built['assessment']['records']:
            self.assertIn('SYNTHETIC reviewer assertion',record['evidence_review']['note'])


if __name__=='__main__':
    unittest.main()
