"""Actual local HTTP worksheet review/save/export; no public network needed."""
from copy import deepcopy
from unittest.mock import patch
import unittest
import json
import test_server as baseline
from test_curve_number import fixture


class CurveNumberHTTPTests(unittest.TestCase):
    setUpClass=classmethod(baseline.HTTPWorkflowTests.setUpClass.__func__)
    tearDownClass=classmethod(baseline.HTTPWorkflowTests.tearDownClass.__func__)
    request=baseline.HTTPWorkflowTests.request
    json_request=baseline.HTTPWorkflowTests.json_request

    def test_review_recalculates_without_acquisition_and_saved_export_contains_worksheet(self):
        c=fixture();body={'case':c,'feature_id':'lawn','cover':'lawn','condition':'fair','reason':'Synthetic manual review'}
        with patch('stormwater.soil_sources.acquire',side_effect=AssertionError('No acquisition on review')):
            code,_,r=self.json_request('/api/curve-number/review',body)
        self.assertEqual(code,200,r);self.assertAlmostEqual(r['analysis']['assessment']['open_space_curve_number']['average_cn'],63.4,places=6)
        self.assertEqual(len(r['case']['assessment']['open_space_reviews']),1)
        code,_,saved=self.json_request('/api/save',{'case':r['case']});self.assertEqual(code,200,saved)
        code,_,html=self.request('/exports/'+c['id']+'/report.html')
        self.assertEqual(code,200);self.assertIn(b'Open-space curve-number worksheet',html)
        code,_,bundle=self.json_request('/exports/'+c['id']+'/evidence-bundle.json')
        self.assertEqual(code,200,bundle);self.assertEqual(bundle['case']['assessment']['open_space_inputs']['lawn']['condition'],'fair')
        with patch('stormwater.soil_sources.acquire',side_effect=AssertionError('No acquisition on read')):
            code,_,opened=self.json_request('/api/saved/'+c['id'])
        self.assertEqual(code,200,opened);self.assertEqual(opened['analysis']['assessment']['open_space_curve_number'],saved['assessment']['open_space_curve_number'])
        code,_,error=self.json_request('/api/curve-number/review',{**body,'reason':''});self.assertEqual(code,400,error)

    def test_reviewer_ub_soil_choice_over_http_without_acquisition(self):
        from test_curve_number_ub import urban_case
        c=urban_case();body={'case':c,'mukey':'1479568','group':'UB','evidence_basis':'site_soil_test','reason':'Synthetic soil test'}
        with patch('stormwater.soil_sources.acquire',side_effect=AssertionError('No acquisition on review')):
            code,_,r=self.json_request('/api/curve-number/soil-review',body)
            self.assertEqual(code,200,r)
            sheet=r['analysis']['assessment']['open_space_curve_number']
            self.assertAlmostEqual(sheet['average_cn'],58.6,places=6)
            self.assertEqual(r['case']['assessment']['soil_group_reviews']['1479568']['evidence_basis'],'site_soil_test')
            code,_,error=self.json_request('/api/curve-number/soil-review',{**body,'evidence_basis':'guess'})
            self.assertEqual(code,400,error)
            code,_,back=self.json_request('/api/curve-number/soil-review',{'case':r['case'],'mukey':'1479568','group':None,'reason':'Withdrawn'})
        self.assertEqual(code,200,back);self.assertIsNone(back['analysis']['assessment']['open_space_curve_number']['average_cn'])

    def test_explicit_assessment_acquires_soil_and_preserves_previous_snapshot(self):
        c=fixture();before=json.loads(json.dumps(c['assessment']['soil_snapshot']))
        empty={'records':[],'observations':[],'source_status':[],'sources':[]}
        with patch('stormwater.assessment_sources.discover',return_value=empty),patch('drainage_core.sources.Cache.post_json',return_value={'data':{},'provenance':{'sha256':'b'*64,'url':'https://example.test/soil'}}) as request:
            code,_,r=self.json_request('/api/assessment/run',{'case':c})
        self.assertEqual(code,200,r);request.assert_called_once()
        self.assertEqual(r['case']['assessment']['soil_history'][-1],before)
        self.assertEqual(r['case']['assessment']['soil_snapshot']['status'],'retrieved')
        self.assertIsNone(r['analysis']['assessment']['open_space_curve_number']['average_cn'])
        self.assertFalse(r['case']['benefits'])


if __name__=='__main__':unittest.main()
