from contextlib import redirect_stdout
from io import StringIO
import json
from pathlib import Path
import tempfile
import unittest
import subprocess
import sys

import numpy as np
import rasterio
from rasterio.transform import from_origin
from shapely.geometry import box,mapping

from drainage_core.cli import main,parser,build_project,_automatic_utm
from drainage_core.geometry import reproject


class GenericCliTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name)

    def call(self,args):
        capture=StringIO()
        with redirect_stdout(capture):code=main(args)
        return code,json.loads(capture.getvalue())

    def write_boundary(self,geometry,crs=None):
        p=self.root/'boundary.geojson';data={'type':'Feature','properties':{},'geometry':mapping(geometry)}
        if crs:data['crs']={'type':'name','properties':{'name':crs}}
        p.write_text(json.dumps(data));return p

    def test_non_us_demo_and_frozen_rerun_have_no_credit_or_billing_layer(self):
        output=self.root/'demo';code,summary=self.call(['demo','--output',str(output)])
        self.assertEqual(code,0);self.assertEqual(summary['crs'],'EPSG:32756')
        self.assertAlmostEqual(summary['gross_area_m2'],900,places=6)
        self.assertAlmostEqual(summary['known_impervious_area_m2'],700,places=6)
        for name in ['case.json','analysis.json','measurements.geojson','report.html']:
            self.assertTrue((output/name).is_file(),name)
        result=json.loads((output/'analysis.json').read_text())
        for field in ['billing','screens','surface_assumption_scenarios']:
            self.assertNotIn(field,result)
        self.assertNotIn('PWD',json.dumps(result));self.assertNotIn('Philadelphia',json.dumps(result))
        self.assertEqual(result['validation']['ia']['status'],'incomplete')
        saved_hash=summary['input_sha256']
        code,next_summary=self.call(['analyze',str(output/'case.json'),'--output',str(self.root/'rerun')])
        self.assertEqual(code,0);self.assertEqual(saved_hash,next_summary['input_sha256'])

    def test_native_metric_dem_with_wgs84_vectors_keeps_units_as_explicit_assumption(self):
        crs='EPSG:32756';local=box(334008,6250968,334022,6250982)
        boundary=self.write_boundary(reproject(local,crs,'EPSG:4326'))
        features=self.root/'surfaces.geojson'
        features.write_text(json.dumps({'type':'FeatureCollection','features':[
            {'type':'Feature','id':'paving','properties':{'layer':'surface','class':'pavement'},
             'geometry':mapping(reproject(local,crs,'EPSG:4326'))}]}))
        source=self.root/'dem.tif'
        with rasterio.open(source,'w',driver='GTiff',count=1,width=32,height=32,dtype='float32',
                           crs=crs,transform=from_origin(334000,6250990,1,1),nodata=-9999) as ds:
            ds.write(np.array([[40-r*.1-c*.2 for c in range(32)] for r in range(32)],dtype='float32'),1)
        output=self.root/'terrain-project'
        code,summary=self.call(['run','--boundary',str(boundary),'--features',str(features),'--dem',str(source),
                                '--vertical-unit','m','--buffer','2','--output',str(output)])
        self.assertEqual(code,0,summary)
        c=json.loads((output/'case.json').read_text())
        self.assertEqual(c['crs'],crs);self.assertEqual(c['terrain']['cell_size'],1)
        self.assertEqual(c['terrain']['vertical_unit'],'m')
        self.assertEqual(c['terrain']['source_quality']['vertical_units'],'assumed')
        self.assertEqual(len(list((output/'inputs').glob('terrain-*.tif'))),1)
        self.assertAlmostEqual(summary['gross_area_m2'],196,places=3)
        self.assertFalse(c['terrain']['settings']['extent_sufficient'])

    def test_global_boundary_without_dem_selects_southern_utm_and_reports_routing_unavailable(self):
        boundary=self.write_boundary(box(151.20,-33.87,151.201,-33.869))
        code,summary=self.call(['run','--boundary',str(boundary),'--output',str(self.root/'boundary-only')])
        self.assertEqual(code,0);self.assertEqual(summary['crs'],'EPSG:32756')
        self.assertEqual(summary['drainage_status'],'unavailable')
        self.assertGreater(summary['unknown_surface_area_m2'],0)
        self.assertAlmostEqual(summary['gross_area_m2'],summary['unknown_surface_area_m2'])

    def test_projected_coordinates_without_crs_are_rejected_instead_of_assumed_geographic(self):
        boundary=self.write_boundary(box(334000,6251000,334010,6251010))
        code,out=self.call(['run','--boundary',str(boundary),'--output',str(self.root/'bad')])
        self.assertEqual(code,1);self.assertIn('correct input CRS',out['error'])

    def test_explicit_and_embedded_crs_conflict_is_rejected(self):
        boundary=self.write_boundary(box(334000,6251000,334010,6251010),'EPSG:32756')
        code,out=self.call(['run','--boundary',str(boundary),'--boundary-crs','EPSG:26918','--output',str(self.root/'bad')])
        self.assertEqual(code,1);self.assertIn('conflicts',out['error'])

    def test_dem_requires_vertical_units_and_cannot_be_reprojected_silently(self):
        boundary=self.write_boundary(box(334008,6250968,334022,6250982),'EPSG:32756')
        source=self.root/'dem.tif'
        with rasterio.open(source,'w',driver='GTiff',count=1,width=32,height=32,dtype='float32',
                           crs='EPSG:32756',transform=from_origin(334000,6250990,1,1)) as ds:ds.write(np.ones((32,32),dtype='float32'),1)
        base=['run','--boundary',str(boundary),'--dem',str(source),'--buffer','0','--output',str(self.root/'bad')]
        code,out=self.call(base);self.assertEqual(code,1);self.assertIn('--vertical-unit',out['error'])
        code,out=self.call(base+['--vertical-unit','m','--crs','EPSG:26918'])
        self.assertEqual(code,1);self.assertIn('native projected CRS',out['error'])

    def test_verified_unit_status_requires_reviewed_evidence_not_only_a_label(self):
        boundary=self.write_boundary(box(334008,6250968,334022,6250982),'EPSG:32756')
        source=self.root/'dem.tif'
        with rasterio.open(source,'w',driver='GTiff',count=1,width=32,height=32,dtype='float32',
                           crs='EPSG:32756',transform=from_origin(334000,6250990,1,1)) as ds:ds.write(np.ones((32,32),dtype='float32'),1)
        code,out=self.call(['run','--boundary',str(boundary),'--dem',str(source),'--vertical-unit','m',
                           '--unit-status','verified','--buffer','0','--output',str(self.root/'bad')])
        self.assertEqual(code,1);self.assertIn('--unit-evidence',out['error'])

    def test_auto_projection_polar_boundary_requires_explicit_suitable_projection(self):
        with self.assertRaises(ValueError):_automatic_utm(box(10,86,11,87),'EPSG:4326')
        self.assertEqual(_automatic_utm(box(-73,40,-72.9,40.1),'EPSG:4326').to_epsg(),32618)

    def test_fresh_cli_process_cannot_import_the_jurisdiction_package(self):
        code='''import importlib.abc,sys
class BlockJurisdiction(importlib.abc.MetaPathFinder):
    def find_spec(self,fullname,path=None,target=None):
        if fullname=='stormwater' or fullname.startswith('stormwater.'):
            raise RuntimeError('Generic CLI imported jurisdiction: '+fullname)
sys.meta_path.insert(0,BlockJurisdiction())
from drainage_core.cli import main
raise SystemExit(main(['demo','--output',sys.argv[1]]))
'''
        process=subprocess.run([sys.executable,'-c',code,str(self.root/'isolated')],
                               cwd=Path(__file__).resolve().parents[1],capture_output=True,text=True,timeout=20)
        self.assertEqual(process.returncode,0,process.stderr)
        self.assertEqual(json.loads(process.stdout)['crs'],'EPSG:32756')

if __name__=='__main__':unittest.main()
