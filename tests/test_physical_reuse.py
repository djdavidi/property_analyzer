"""Policy updates reuse hand-built frozen GIS; physical changes invalidate it."""
from copy import deepcopy
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
import json
import unittest
from drainage_core.engine import canonical,input_hash,result_hash,ENGINE_VERSION
from stormwater.cases import CaseStore
from stormwater.physical_reuse import load_frozen
from stormwater.billing import default_tariff
from test_jurisdiction_adapter import fixture


def frozen(root):
    case,gis,policy=fixture();case['baseline']=policy['baseline'];case['benefits']=policy['benefits']
    from drainage_core.quality import PHYSICAL_INTERPRETATION_VERSION
    gis['engine_version']=ENGINE_VERSION;gis['physical_interpretation_version']=PHYSICAL_INTERPRETATION_VERSION
    gis['input_sha256']=input_hash(case);gis['analysis_sha256']=result_hash(gis)
    folder=Path(root)/case['id'];(folder/'revisions').mkdir(parents=True)
    (folder/'case.json').write_text(canonical(case));(folder/'gis-analysis.json').write_text(canonical(gis))
    (folder/'revisions'/(input_hash(case)+'.json')).write_text(canonical(case))
    return case,gis,folder


class PhysicalReuseTests(unittest.TestCase):
    def test_removed_policy_fact_does_not_reappear_from_original_revision(self):
        with TemporaryDirectory() as root:
            case,_,_=frozen(root);changed=deepcopy(case);del changed['baseline'];del changed['benefits']
            with patch('stormwater.cases.analyze_gis',side_effect=AssertionError('No GIS')):
                result=CaseStore(root).analyze(changed)
            self.assertEqual(result['billing']['status'],'blocked')

    def test_billing_and_tariff_changes_reuse_original_artifact_and_hash(self):
        with TemporaryDirectory() as root:
            case,gis,folder=frozen(root);changed=deepcopy(case);changed['tariff']=default_tariff();changed['tariff']['ia_rate']='8.048'
            changed['assessment']={'records':[],'review_note':'Synthetic policy change'}
            before=(folder/'gis-analysis.json').read_bytes()
            with patch('stormwater.cases.analyze_gis',side_effect=AssertionError('No GIS analysis')):
                result=CaseStore(root).analyze(changed)
            self.assertEqual(result['physical_reuse']['status'],'reused_frozen_gis')
            self.assertEqual(result['gis_input_sha256'],input_hash(case));self.assertEqual(result['input_sha256'],input_hash(changed))
            self.assertEqual(result['gis_analysis_sha256'],gis['analysis_sha256'])
            self.assertEqual(result['billing']['baseline']['monthly_total'],183.83)
            self.assertEqual((folder/'gis-analysis.json').read_bytes(),before)

    def test_save_policy_edit_keeps_frozen_gis_and_adds_current_revision(self):
        with TemporaryDirectory() as root:
            case,gis,folder=frozen(root);changed=deepcopy(case);changed['baseline']['accounts'][0]['discount_factor']=.75;changed['baseline']['accounts'][0]['discount_verified']=True
            with patch('stormwater.cases.analyze_gis',side_effect=AssertionError('No GIS')),patch('stormwater.report.render_report',return_value='fixture'),patch('stormwater.report.export_geojson',return_value={'features':[]}):
                result=CaseStore(root).save(changed)
            self.assertEqual(json.loads((folder/'gis-analysis.json').read_text())['input_sha256'],input_hash(case))
            self.assertTrue((folder/'revisions'/(input_hash(changed)+'.json')).exists())
            self.assertNotEqual(result['input_sha256'],result['gis_input_sha256'])

    def test_physical_and_unknown_fields_invalidate(self):
        with TemporaryDirectory() as root:
            case,_,folder=frozen(root)
            changes=[('terrain',{'cell_size':2}),('sources',[{'sha256':'new'}]),('imagery',{'sha256':'new'}),('automatic',{'model_sha256':'new'}),('references',{'survey':'new'}),('unknown_new_setting',1),('corrections',[{'reason':'new'}])]
            for key,value in changes:
                changed=deepcopy(case);changed[key]=value
                with self.subTest(key=key):self.assertIsNone(load_frozen(folder,changed))
            changed=deepcopy(case);changed['parcel']['coordinates']=[[[0,0],[1,0],[1,1],[0,0]]]
            self.assertIsNone(load_frozen(folder,changed))

    def test_corrupt_input_and_artifact_do_not_silently_reuse_or_reroute(self):
        with TemporaryDirectory() as root:
            case,gis,folder=frozen(root);path=folder/'gis-analysis.json';gis['measurement']['ia_sqft']=1;path.write_text(canonical(gis))
            with self.assertRaises(ValueError):load_frozen(folder,case)

    def test_physical_change_reaches_normal_analysis_path(self):
        with TemporaryDirectory() as root:
            case,_,_=frozen(root);changed=deepcopy(case);changed['sources']=[{'url':'new-source'}]
            with patch('stormwater.cases._analyze_pair',return_value=({},{})) as analyze:
                CaseStore(root).analyze(changed)
            analyze.assert_called_once_with(changed)


if __name__=='__main__':unittest.main()
