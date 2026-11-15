from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path
import json
import tempfile
import unittest

from shapely.geometry import box, mapping

from stormwater.cases import CaseStore, analyze, canonical, input_hash
from stormwater.cli import benchmark, main
from stormwater.fixtures import synthetic_case


class SyntheticFixtureTests(unittest.TestCase):
    def test_fixture_reproducible_and_known_vector_answers(self):
        first,second=synthetic_case(),synthetic_case()
        self.assertEqual(canonical(first),canonical(second))
        self.assertEqual(input_hash(first),input_hash(second))
        result=analyze(first);m=result['measurement']
        factor=(1200/3937/.3048)**2
        for key,known in [('ga_sqft',6400),('ia_sqft',6100),('pervious_sqft',300),
                          ('roof_sqft',900),('canopy_ground_ia_sqft',1050)]:
            self.assertAlmostEqual(m[key],known*factor,places=6)
        self.assertTrue(m['complete'])
        self.assertTrue(first['synthetic_case'])
        self.assertEqual(first['references'],[])
        self.assertEqual(result['validation']['ia']['status'],'incomplete')
        self.assertEqual(result['validation']['drainage']['status'],'incomplete')

    def test_fixture_has_documented_pipe_unknown_roof_and_separate_screens(self):
        result=analyze(synthetic_case())
        self.assertGreater(result['drainage']['counts']['outlet:garden-outlet'],0)
        self.assertTrue(any(label.startswith('unresolved:roof:') for label in result['drainage']['counts']))
        screens={s['id']:s for s in result['screens']}
        self.assertEqual(screens['canopy-hypothesis']['status'],'screen_pass')
        self.assertEqual(screens['roof-disconnection-unresolved']['status'],'missing_evidence')
        self.assertEqual(result['billing']['combined']['basis'],'modeled')
        self.assertEqual(result['billing']['documented_credit_only']['status'],'blocked')


class CliTests(unittest.TestCase):
    def call(self,arguments):
        capture=StringIO()
        with redirect_stdout(capture):code=main(arguments)
        return code,json.loads(capture.getvalue())

    def test_demo_analyze_and_reopen(self):
        with tempfile.TemporaryDirectory() as temp:
            store=Path(temp)/'cases'
            code,out=self.call(['demo','--store',str(store)])
            self.assertEqual(code,0);self.assertEqual(out['case_id'],'synthetic-demo')
            self.assertTrue(Path(out['report']).exists())
            analysis=Path(temp)/'analysis.json'
            code,next_out=self.call(['analyze','synthetic-demo','--store',str(store),'--output',str(analysis)])
            self.assertEqual(code,0);self.assertEqual(out['input_sha256'],next_out['input_sha256'])
            self.assertEqual(json.loads(analysis.read_text())['input_sha256'],out['input_sha256'])

    def test_missing_case_reports_error(self):
        with tempfile.TemporaryDirectory() as temp:
            code,out=self.call(['analyze','missing','--store',temp])
            self.assertEqual(code,1);self.assertIn('error',out)

    def test_import_uses_only_frozen_acquisition(self):
        with tempfile.TemporaryDirectory() as temp:
            data={'parcel_id':98627,'address':'Synthetic import test address','parcel':mapping(box(2690000,250000,2690100,250100)),
                  'crs':'EPSG:2272','baseline':None,'features':{'type':'FeatureCollection','features':[]},
                  'sources':[{'url':'synthetic://fixture','retrieved_at':'2026-11-15T00:00:00Z'}]}
            source=Path(temp)/'saved.json';source.write_text(json.dumps(data))
            code,out=self.call(['import-whitaker','--source',str(source),'--store',str(Path(temp)/'cases')])
            self.assertEqual(code,0);self.assertEqual(out['case_id'],'pwd-98627')
            stored=CaseStore(Path(temp)/'cases').load('pwd-98627')
            self.assertEqual(stored['sources'],data['sources'])
            self.assertEqual(stored['created_at'],data['sources'][0]['retrieved_at'])
            self.assertFalse(stored['references'])

    def test_benchmark_reports_separate_missing_reference_blockers(self):
        with tempfile.TemporaryDirectory() as temp:
            case=synthetic_case();case['synthetic_case']=False;case['id']='real-evidence-missing-references'
            path=Path(temp)/'case.json';path.write_text(canonical(case))
            output=Path(temp)/'benchmarks.json';doc=Path(temp)/'VALIDATION.md'
            code,result=self.call(['benchmark',str(path),'--store',str(Path(temp)/'cases'),
                                  '--output',str(output),'--documentation',str(doc)])
            self.assertEqual(code,0)
            for kind in ['ia','drainage']:
                self.assertEqual(result['assessment'][kind]['status'],'incomplete')
                self.assertEqual(result['assessment'][kind]['real_cases_with_independent_metrics'],0)
                self.assertIsNone(result['assessment'][kind]['accuracy_target'])
            self.assertIn('## Outstanding',doc.read_text())
            self.assertEqual(len(json.loads(output.read_text())['cases']),1)

    def test_synthetic_reference_cannot_count_as_real_empirical_validation(self):
        case=synthetic_case()
        case['references']=[{'id':'known-answer','kind':'ia','independent':True,'stable_site_verified':True,
                             'source_url':'synthetic://fixture','crs':case['crs'],
                             'geometry':analyze(case)['measurement']['geometries']['physical_ia'],'holdout':True}]
        with tempfile.TemporaryDirectory() as temp:
            result=benchmark([case],Path(temp)/'benchmarks.json')
            self.assertFalse(result['cases'][0]['eligible_for_empirical_summary'])
            self.assertEqual(result['assessment']['ia']['real_cases_with_independent_metrics'],0)
            self.assertEqual(result['assessment']['ia']['real_holdout_cases'],0)
            self.assertEqual(result['cases'][0]['synthetic_reference_ids_excluded'],['known-answer'])
            # An incorrectly omitted synthetic-case flag cannot promote a
            # reference explicitly declaring its own synthetic origin.
            case['synthetic_case']=False
            result=benchmark([case],Path(temp)/'benchmarks.json')
            self.assertEqual(result['assessment']['ia']['real_cases_with_independent_metrics'],0)


if __name__=='__main__':unittest.main()
