"""Saved results are read, hash checked and reduced without running analysis."""
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
import json
import unittest
from drainage_core.engine import input_hash,ENGINE_VERSION,canonical
from drainage_core.quality import PHYSICAL_INTERPRETATION_VERSION
from drainage_core.saved import saved_view,display_analysis
from stormwater.cases import CaseStore


def fixture():
    case={'id':'saved-test','schema_version':1,'name':'Saved fixture','features':{'type':'FeatureCollection','features':[]}}
    result={'engine_version':ENGINE_VERSION,'physical_interpretation_version':PHYSICAL_INTERPRETATION_VERSION,
        'input_sha256':input_hash(case),'measurement':{'ia_sqft':25},
        'drainage':{'labels':[0]*1000,'outlets':[1]*1000,'counts':[3],'next_cells':[2]*1000,'catchments':[]},
        'research_drainage':{'primary':{'rasters':{'dem':[1]*1000},'catchments':[]}},
        'modeled_integration':{'version':'ai-drainage-integration-v2','ai_roof_drainage':{'primary':{'rasters':[1]*1000}},'runs':[]},
        'assessment':{'as_of':'2026-11-15','economics':{'nominal':{'monthly':15.2}}}}
    return case,result


class SavedResultsTests(unittest.TestCase):
    def test_display_keeps_measurements_findings_without_mutating_full_result(self):
        _,r=fixture();before=canonical(r);v=display_analysis(r)
        self.assertEqual(v['measurement'],r['measurement']);self.assertEqual(v['assessment'],r['assessment'])
        self.assertNotIn('labels',v['drainage']);self.assertNotIn('rasters',v['research_drainage']['primary'])
        self.assertEqual(canonical(r),before);self.assertLess(len(canonical(v)),len(before)/5)

    def test_open_builds_small_saved_view_then_reuses_it_without_analysis(self):
        c,r=fixture()
        with TemporaryDirectory() as tmp,patch('stormwater.cases._analyze_pair',side_effect=AssertionError('No analysis')):
            p=Path(tmp);(p/'analysis.json').write_text(canonical(r));first=saved_view(p,c)
            with patch('drainage_core.saved.display_analysis',side_effect=AssertionError('Reuse saved view')):
                second=saved_view(p,c)
            self.assertEqual(first,second);self.assertEqual(second['saved_status']['state'],'saved')

    def test_missing_or_input_mismatch_never_automatically_recalculates(self):
        c,r=fixture()
        with TemporaryDirectory() as tmp:
            p=Path(tmp);self.assertIsNone(saved_view(p,c)['analysis'])
            (p/'analysis.json').write_text(canonical(r));c['name']='Changed'
            self.assertEqual(saved_view(p,c)['saved_status']['state'],'input_changed')

    def test_tampered_view_rejected_and_source_change_invalidates_it(self):
        c,r=fixture()
        with TemporaryDirectory() as tmp:
            p=Path(tmp);source=p/'analysis.json';source.write_text(canonical(r));saved_view(p,c)
            (p/'analysis-view.json').write_text('{}')
            with self.assertRaises(ValueError):saved_view(p,c)
            r['measurement']['ia_sqft']=30;source.write_text(canonical(r))
            self.assertEqual(saved_view(p,c)['analysis']['measurement']['ia_sqft'],30)

    def test_generated_json_is_compact_with_identical_values(self):
        c,r=fixture()
        with TemporaryDirectory() as tmp,patch('stormwater.cases._analyze_pair',return_value=(r,r)),patch('stormwater.report.render_report',return_value='report'),patch('stormwater.report.export_geojson',return_value={'features':[]}):
            store=CaseStore(tmp);store.save(c);content=(Path(tmp)/c['id']/'analysis.json').read_text()
            self.assertNotIn('\n',content);self.assertEqual(json.loads(content),r)


if __name__=='__main__':unittest.main()
