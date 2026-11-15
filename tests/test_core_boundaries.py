"""The geographic engine runs without importing any jurisdiction or its tariffs."""
import io
from copy import deepcopy
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import Mock

from shapely.geometry import box,mapping
from drainage_core.geometry import measure,SQFT_PER_M2,area_m2,case_area_m2
from drainage_core.drainage import route_grid
from drainage_core.sources import Cache,arcgis_features


class CoreBoundaryTests(unittest.TestCase):
    def test_gis_artifact_remains_frozen_when_caller_edits_source_lineage(self):
        from drainage_core.engine import analyze,new_case,result_hash
        c=new_case('Source lineage edits',crs='EPSG:32756')
        c['parcel']=mapping(box(334000,6250000,334003,6250001))
        c['dependent_source_families']=['Council land cover']
        c['features']['features']=[{'id':'surface','type':'Feature','geometry':c['parcel'],
            'properties':{'layer':'surface','class':'pavement','source_family':'Council land cover'}}]
        result=analyze(c);frozen=deepcopy(result)
        c['dependent_source_families'].append('New dataset')
        c['features']['features'][0]['properties']['source_family']='Changed observation'
        self.assertEqual(result,frozen)
        self.assertEqual(result['analysis_sha256'],result_hash(result))

    def test_generic_workspace_replay_preserves_input_revisions_and_stable_physical_artifact(self):
        from drainage_core.engine import new_case,canonical
        from drainage_core.workspace import ProjectStore
        c=new_case('Portable physical project',crs='EPSG:32756')
        c['parcel']=mapping(box(334000,6250000,334003,6250001))
        c['features']['features']=[{'id':'surface','type':'Feature','geometry':c['parcel'],
                                  'properties':{'layer':'surface','class':'pavement'}}]
        before=canonical(c)
        with tempfile.TemporaryDirectory() as directory:
            store=ProjectStore(directory);first=store.save(c)
            geojson=(Path(directory)/'measurements.geojson').read_bytes()
            second=store.save(store.load())
            self.assertEqual(canonical(c),before)
            self.assertEqual(first['analysis_sha256'],second['analysis_sha256'])
            self.assertEqual((Path(directory)/'measurements.geojson').read_bytes(),geojson)
            self.assertEqual(len(list((Path(directory)/'revisions').glob('*.json'))),1)
            old_snapshot=(Path(directory)/'revisions'/(first['input_sha256']+'.json')).read_text()
            c['corrections'].append({'id':'review','at':'2026-11-15','reason':'Known lawn review',
                'action':'add','feature':{'type':'Feature','id':'lawn','geometry':mapping(box(334000,6250000,334001,6250001)),
                                        'properties':{'layer':'surface','class':'pervious'}}})
            third=store.save(c)
            self.assertNotEqual(first['analysis_sha256'],third['analysis_sha256'])
            self.assertAlmostEqual(first['measurement']['ia_m2']-third['measurement']['ia_m2'],1)
            self.assertEqual(len(list((Path(directory)/'revisions').glob('*.json'))),2)
            self.assertEqual((Path(directory)/'revisions'/(first['input_sha256']+'.json')).read_text(),old_snapshot)

    def test_fresh_core_imports_cannot_load_legacy_or_jurisdiction_packages(self):
        # A denylist import hook catches runtime dependencies rather than merely
        # searching strings in source. Import all core modules, not compatibility shims.
        script='''
import importlib,importlib.abc,pkgutil,sys
class DenyJurisdiction(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if fullname=='stormwater' or fullname.startswith('stormwater.'):
            raise AssertionError('Core imported jurisdiction package: '+fullname)
sys.meta_path.insert(0,DenyJurisdiction())
import drainage_core
loaded=[]
for module in pkgutil.iter_modules(drainage_core.__path__):
    if module.name=='__main__':continue
    importlib.import_module('drainage_core.'+module.name)
    loaded.append(module.name)
assert all(not key.startswith('stormwater') for key in sys.modules)
assert {'geometry','drainage','terrain','raster','sources','validation'}<=set(loaded)
if 'engine' in loaded:
    from drainage_core.engine import analyze,new_case
    case=new_case('Southern hemisphere pure GIS',crs='EPSG:32756')
    case['parcel']={'type':'Polygon','coordinates':[[[334000,6250000],[334003,6250000],[334003,6250001],[334000,6250001],[334000,6250000]]]}
    case['features']['features']=[{'id':'paving','type':'Feature','geometry':case['parcel'],'properties':{'layer':'surface','class':'pavement'}}]
    result=analyze(case)
    assert result['result_type']=='gis-analysis'
    assert abs(result['measurement']['ga_m2']-3)<1e-8
    assert 'billing' not in result and 'screens' not in result
assert all(not key.startswith('stormwater') for key in sys.modules)
print('isolated core modules:',','.join(sorted(loaded)))
'''
        result=subprocess.run([sys.executable,'-c',script],cwd=Path(__file__).resolve().parents[1],
                              capture_output=True,text=True)
        self.assertEqual(result.returncode,0,result.stdout+result.stderr)

    def test_non_philadelphia_metric_and_foot_inputs_have_same_known_area_and_outlet(self):
        # Synthetic sites in northern and southern UTM zones and California feet.
        for crs,unit,metres_per_unit,origin in [
            ('EPSG:32630','m',1.,[530000.,5700000.]),
            ('EPSG:32756','m',1.,[334000.,6250000.]),
            ('EPSG:2229','us-ft',1200/3937,[6300000.,1800000.])]:
            with self.subTest(crs=crs):
                size=1/metres_per_unit;x,y=origin
                geom=mapping(box(x,y-size,x+3*size,y))
                case={'crs':crs,'parcel':geom,'features':{'type':'FeatureCollection','features':[
                    {'id':'paving','type':'Feature','geometry':geom,'properties':{'layer':'surface','class':'pavement'}}]},
                    'baseline':{'invalid':'must never affect physical GIS'},
                    'benefits':[{'id':'unrecognized-policy','category':'not-a-core-concept','area_sqft':999999}]}
                measured=measure(case)
                self.assertAlmostEqual(measured['ga_sqft'],3*SQFT_PER_M2,places=6)
                self.assertAlmostEqual(measured['ia_sqft'],3*SQFT_PER_M2,places=6)
                self.assertAlmostEqual(measured['ga_m2'],3,places=7)
                self.assertAlmostEqual(measured['ia_m2'],3,places=7)
                for name,value in measured.items():
                    if name.endswith('_sqft'):
                        self.assertAlmostEqual(measured[name[:-5]+'_m2']*SQFT_PER_M2,value,places=7)
                self.assertTrue(measured['complete'])
                result=route_grid({'crs':crs,'origin':origin,'cell_size':size,'horizontal_unit':unit,
                    'vertical_unit':'m','elevations':[[3,2,1]],'inlets':[{'id':'collector','cell':[0,2]}],
                    'settings':{'extent_sufficient':True}})
                self.assertEqual(result['labels'],[['inlet:collector']*3])
                self.assertAlmostEqual(result['outlets'][0]['area_sqft'],3*SQFT_PER_M2)

    def test_si_area_helpers_respect_native_units_and_designated_area_crs(self):
        from drainage_core.geometry import reproject
        source=box(530000,5700000,530010,5700010)
        self.assertAlmostEqual(area_m2(source,'EPSG:32630'),100)
        california_foot=box(0,0,10/(1200/3937),10/(1200/3937))
        self.assertAlmostEqual(area_m2(california_foot,'EPSG:2229'),100)
        projected=reproject(source,'EPSG:32630','EPSG:3857')
        case={'crs':'EPSG:3857','area_crs':'EPSG:32630'}
        self.assertAlmostEqual(case_area_m2(projected,case),100,places=6)

    def test_declared_source_dependence_is_location_neutral_and_surface_specific(self):
        geom=mapping(box(0,0,10,10))
        case={'crs':'EPSG:32756','parcel':geom,'features':{'features':[
            {'id':'surface','geometry':geom,'properties':{'layer':'surface','class':'pavement',
                'source_family':'Council land cover','source_dependency':True}},
            {'id':'tree','geometry':geom,'properties':{'layer':'canopy','source_family':'Unrelated canopy','source_dependency':True}}]}}
        self.assertEqual(measure(case)['source_dependence'],['Council land cover'])
        self.assertTrue(all('PWD' not in warning for warning in measure(case)['warnings']))
        case['features']['features'][0]['properties'].pop('source_family')
        self.assertEqual(measure(case)['source_dependence'],['Unidentified declared dependency'])

    def test_generic_arcgis_defaults_to_wgs84_and_records_explicit_projected_units(self):
        cache=Mock();cache.fetch_json.return_value={'data':{'features':[]},'provenance':{}}
        result=arcgis_features('https://example.test/FeatureServer/0',cache)
        self.assertEqual(result['crs'],'EPSG:4326')
        self.assertEqual(cache.fetch_json.call_args.args[2]['horizontal_unit'],'degree')
        result=arcgis_features('https://example.test/FeatureServer/0',cache,params={'outSR':'32756'})
        self.assertEqual(result['crs'],'EPSG:32756')
        self.assertEqual(cache.fetch_json.call_args.args[2]['horizontal_unit'],'m')
        result=arcgis_features('https://example.test/FeatureServer/0',cache,params={'outSR':'EPSG:32756'})
        self.assertEqual(result['crs'],'EPSG:32756')
        self.assertIn('outSR=32756',cache.fetch_json.call_args.args[0])

    def test_legacy_modules_delegate_to_same_implementations_and_keep_query_default(self):
        from stormwater import drainage,raster,terrain,validation
        from drainage_core import drainage as generic_drainage,raster as generic_raster,terrain as generic_terrain,validation as generic_validation
        self.assertIs(drainage.route_grid,generic_drainage.route_grid)
        self.assertIs(raster._provenance,generic_raster._provenance)
        self.assertIs(terrain.prepare_terrain,generic_terrain.prepare_terrain)
        self.assertIs(validation.validate_case,generic_validation.validate_case)
        from stormwater.acquisition import arcgis_features as philly_features
        cache=Mock();cache.fetch_json.return_value={'data':{'features':[]},'provenance':{}}
        self.assertEqual(philly_features('https://example.test/layer',cache)['crs'],'EPSG:2272')

    def test_generic_cache_uses_neutral_client_and_preserves_replay(self):
        opener=Mock(return_value=io.BytesIO(b'{"value":3}'))
        with tempfile.TemporaryDirectory() as directory:
            cache=Cache(directory,opener=opener)
            first=cache.fetch_json('https://example.test/source')
            self.assertNotIn('Philadelphia',opener.call_args.args[0].get_header('User-agent'))
            opener.side_effect=AssertionError('Replay must not reacquire')
            self.assertEqual(cache.fetch_json('https://example.test/source'),first)


if __name__=='__main__':unittest.main()
