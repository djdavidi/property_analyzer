"""Known-answer source interpretation and automatic property workflow; no accuracy claims."""
import base64
from copy import deepcopy
from hashlib import sha256
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock,patch
import numpy as np
import rasterio
from rasterio.io import MemoryFile
from shapely.geometry import box,mapping,shape
from drainage_core.geometry import measure,SQFT_PER_M2
from drainage_core.remote_sensing import decode_classification,classified_features,legend_palette,vegetation_candidates
from stormwater.automatic import acquire,enrich_candidates,lookup,landcover,LANDCOVER
from stormwater.cases import new_case,CaseStore,analyze


def png(pixels):
    a=np.array(pixels,dtype='uint8')
    with MemoryFile() as mem:
        with mem.open(driver='PNG',width=a.shape[1],height=a.shape[0],count=a.shape[2],dtype='uint8') as ds:ds.write(np.moveaxis(a,-1,0))
        return mem.read()


def fixture():
    c=new_case('Automatic source test');c.update(id='automatic-fixture',crs='EPSG:26918',parcel=mapping(box(0,0,4,2)))
    return c


def source():return {'family':'Invented classified source','vintage':'2025','sha256':'a'*64,'url':'https://example.test/source'}


def lc(c):return classified_features(np.array([[1,2,5,7],[1,2,5,7]],dtype='uint8'),[0,0,4,2],c,source())


class RemoteSensingTests(unittest.TestCase):
    def test_classified_canopy_is_measured_without_calling_hidden_ground_pervious(self):
        c=fixture();r=lc(c);c['features']['features']=r['features'];c['canopy_observation']={'status':'complete'}
        m=measure(c)
        self.assertAlmostEqual(m['canopy_sqft'],2*SQFT_PER_M2)
        self.assertAlmostEqual(m['ia_sqft'],4*SQFT_PER_M2)
        self.assertAlmostEqual(m['pervious_sqft'],2*SQFT_PER_M2)
        self.assertAlmostEqual(m['unknown_sqft'],2*SQFT_PER_M2)
        self.assertAlmostEqual(m['canopy_ground_ia_upper_sqft'],2*SQFT_PER_M2)
        self.assertFalse(m['complete'])
        self.assertEqual(sum(x['area_sqft'] for x in r['estimates']),m['ga_sqft'])

    def test_missing_canopy_vs_explicit_zero_are_distinct(self):
        c=fixture();m=measure(c);self.assertIsNone(m['canopy_sqft']);self.assertIsNone(m['canopy_ground_ia_sqft'])
        c['canopy_observation']={'status':'complete'};m=measure(c)
        self.assertEqual(m['canopy_sqft'],0)
        c['canopy_observation']={'status':'partial'};self.assertIsNone(measure(c)['canopy_sqft'])

    def test_transparency_and_unknown_colors_do_not_become_classes(self):
        content=png([[[10,20,30,255],[10,20,30,0],[11,20,30,255]]])
        a=decode_classification(content,{(10,20,30):1})
        np.testing.assert_array_equal(a,[[1,0,0]])

    def test_legend_is_checked_instead_of_assuming_display_colors(self):
        items=[{'label':str(i),'imageData':base64.b64encode(png([[[i,20,30,255]]])).decode()} for i in range(1,8)]
        palette=legend_palette({'layers':[{'layerId':2,'legend':items}]},2)
        self.assertEqual(palette[(1,20,30)],1)
        with self.assertRaises(ValueError):legend_palette({'layers':[{'layerId':2,'legend':items[:-1]}]},2)

    def test_edge_ranges_clip_to_parcel_and_keep_missing_coverage_in_upper(self):
        c=fixture();r=classified_features(np.array([[1,0],[2,0]],dtype='uint8'),[0,0,4,2],c,source())
        self.assertAlmostEqual(r['unclassified_sqft'],4*SQFT_PER_M2)
        canopy=r['estimates'][0]
        self.assertLessEqual(canopy['edge_lower_sqft'],canopy['area_sqft'])
        self.assertGreater(canopy['edge_upper_sqft'],canopy['area_sqft'])
        self.assertLessEqual(canopy['edge_upper_sqft'],8*SQFT_PER_M2+1e-8)
        self.assertIn('not a statistical',canopy['uncertainty'])

    def test_rgb_green_candidate_is_not_a_canopy_classifier(self):
        c=fixture();g=vegetation_candidates(png([[[30,130,30],[100,100,100]],[[30,130,30],[5,5,5]]]),[0,0,4,2],c,minimum_area_sqft=1)
        self.assertAlmostEqual(g.area,4)


class AutomaticWorkflowTests(unittest.TestCase):
    def test_address_lookup_does_not_silently_choose_ambiguous_match(self):
        cache=Mock();cache.fetch_json.return_value={'data':{'features':[
            {'id':1,'properties':{'parcelid':1,'address':'5300 TEST AVE A'}},
            {'id':2,'properties':{'parcelid':2,'address':'5300 TEST AVE B'}}]},'provenance':{}}
        matches=lookup('5300 Test Ave',cache)['matches'];self.assertEqual(len(matches),2)
        self.assertEqual(lookup('98627',cache)['matches'][0]['parcel_id'],98627)
        with self.assertRaises(ValueError):lookup('Philadelphia',cache)
        self.assertIn('outFields=parcelid%2Caddress',cache.fetch_json.call_args.args[0])

    def test_acquisition_populates_features_and_keeps_manual_corrections(self):
        c=fixture();r=lc(c);r.update(source_snapshots=[],status='source_estimate',source_vintage='2025',retrieved_at='2020-01-01')
        c['corrections']=[{'id':'review','at':'2026-11-15','reason':'Known lawn review','action':'add',
            'feature':{'id':'manual','geometry':mapping(box(0,0,1,1)),'properties':{'layer':'surface','class':'pervious'}}}]
        original=deepcopy(c)
        with patch('stormwater.acquisition.acquire_imagery',side_effect=OSError('offline image')),patch('stormwater.automatic.landcover',return_value=r),patch('stormwater.automatic_terrain.acquire',side_effect=OSError('no terrain')):
            out=acquire(c,Mock());again=acquire(out,Mock())
        self.assertEqual(c,original);self.assertEqual(out['corrections'],c['corrections'])
        self.assertTrue(any(f['properties'].get('layer')=='canopy' for f in out['features']['features']))
        self.assertEqual(len(out['features']['features']),len(again['features']['features']))
        self.assertEqual(len(again['automatic_runs']),2)
        self.assertEqual(measure(out)['canopy_status'],'complete')
        self.assertIn('unavailable',[s['status'] for s in out['automatic']['source_status']])

    def test_total_outage_retains_dated_source_or_unknown_without_zero(self):
        c=fixture()
        with patch('stormwater.acquisition.acquire_imagery',side_effect=OSError('offline')),patch('stormwater.automatic.landcover',side_effect=OSError('offline')),patch('stormwater.automatic_terrain.acquire',side_effect=OSError('offline')):
            out=acquire(c,Mock());self.assertIsNone(measure(out)['canopy_sqft'])
            c['automatic']={'landcover':{'retrieved_at':'2020-01-01'},'estimates':[{'feature':'canopy','area_sqft':99}]}
            out=acquire(c,Mock())
        self.assertEqual(out['automatic']['estimates'],[])
        self.assertEqual(out['automatic_history'][-1]['estimates'][0]['area_sqft'],99)
        self.assertEqual(next(s for s in out['automatic']['source_status'] if s['provider']=='Recent imagery cover candidates')['status'],'unavailable')

    def test_public_footprint_automatically_measured_without_managed_area_or_confirmation(self):
        c=fixture();c['assessment']={'records':[{'id':'public-roof','category':'green_roof','decision':'candidate','basis':'public_candidate',
            'public_geometry':mapping(box(0,0,1,1)),'public_geometry_role':'system footprint, not managed catchment',
            'source':{'url':'https://example.test/system','crs':c['crs']},'facts':{},'evidence_refs':[]}]}
        out=enrich_candidates(c);record=out['assessment']['records'][0]
        self.assertAlmostEqual(record['automatic_footprint']['area_sqft'],SQFT_PER_M2)
        self.assertNotIn('geometry',record);self.assertEqual(record['decision'],'candidate')
        result=analyze(out)['assessment']['categories'][0]['records'][0]
        self.assertAlmostEqual(result['footprint_area_sqft'],SQFT_PER_M2);self.assertIsNone(result['managed_area_sqft'])

    def test_coordinate_change_preserves_candidate_geometry_and_manual_sources(self):
        from drainage_core.projection import project_case
        c=fixture();c['assessment']={'records':[{'geometry':c['parcel'],'footprint_geometry':c['parcel'],
            'public_geometry':c['parcel'],'source':{'crs':c['crs'],'url':'https://example.test/system'}}]}
        before=deepcopy(c);out=project_case(c,'EPSG:2272')
        self.assertEqual(c,before);record=out['assessment']['records'][0]
        self.assertEqual(record['source']['original_crs'],c['crs']);self.assertEqual(record['source']['crs'],'EPSG:2272')
        self.assertEqual(record['geometry'],record['public_geometry'])

class PaletteAndPublicReplayTests(unittest.TestCase):
    def test_indexed_aerial_colors_are_decoded_before_candidate_analysis_and_warp(self):
        from drainage_core.remote_sensing import image_array
        from drainage_core.projection import warp_display
        with MemoryFile() as mem:
            with mem.open(driver='PNG',width=2,height=2,count=1,dtype='uint8') as ds:
                ds.write(np.array([[0,1],[0,1]],dtype='uint8'),1)
                ds.write_colormap(1,{0:(30,130,30,255),1:(100,100,100,255)})
            raw=mem.read()
        np.testing.assert_array_equal(image_array(raw)[0,0,:3],[30,130,30])
        c=fixture();self.assertAlmostEqual(vegetation_candidates(raw,[0,0,4,2],c,minimum_area_sqft=1).area,4)
        with tempfile.TemporaryDirectory() as root:
            root=Path(root);(root/'blobs').mkdir();digest=sha256(raw).hexdigest();(root/'blobs'/digest).write_bytes(raw)
            c['imagery']={'sha256':digest,'blob_path':str(root/'blobs'/digest),'bounds':[0,0,4,2],'width':2,'height':2,'crs':c['crs']}
            warped=warp_display(c,c['crs'],root)
            output=image_array((root/'blobs'/warped['sha256']).read_bytes())
            np.testing.assert_array_equal(output[0,0,:3],[30,130,30])

    def test_original_public_renderings_replay_offline_without_accuracy_claim(self):
        import subprocess,sys
        script=Path(__file__).resolve().parents[1]/'examples'/'automatic-public'/'replay.py'
        result=subprocess.run([sys.executable,str(script)],capture_output=True,text=True)
        self.assertEqual(result.returncode,0,result.stderr)
        rows=[json.loads(line) for line in result.stdout.splitlines()]
        self.assertEqual(len(rows),2)
        self.assertGreater(rows[0]['areas_sqft']['canopy'],20000)
        self.assertGreater(rows[1]['areas_sqft']['canopy'],2000)
        self.assertTrue(all('not independent' in r['claim'] for r in rows))

class AutomaticTerrainEvidenceTests(unittest.TestCase):
    def test_saved_native_grid_is_retained_without_silent_source_replacement(self):
        from stormwater.automatic_terrain import acquire as terrain_acquire
        c=fixture();c['terrain']={'source':'saved user-reviewed grid'};cache=Mock()
        out,status=terrain_acquire(c,cache)
        self.assertEqual(out['terrain'],c['terrain']);self.assertEqual(status['status'],'saved_native_grid')
        cache.fetch_json.assert_not_called()

    def test_unknown_vertical_units_cannot_activate_routing(self):
        from stormwater.automatic_terrain import acquire as terrain_acquire
        cache=Mock();cache.fetch_json.return_value={'data':{'items':[{'downloadURL':
            'https://prd-tnm.s3.amazonaws.com/StagedProducts/Elevation/1m/Projects/test/TIFF/tile.tif'}]},'provenance':{}}
        cache.fetch_bytes.return_value={'content':b'<metadata><abstract>Elevation units unspecified. NAVD88.</abstract></metadata>','provenance':{'sha256':'a'*64}}
        with patch('rasterio.open',side_effect=AssertionError('Do not open DEM before unit verification')) as raster:
            with self.assertRaisesRegex(ValueError,'metre elevations'):
                terrain_acquire(fixture(),cache)
            raster.assert_not_called()

class ImageCandidateIntegrationTests(unittest.TestCase):
    def test_current_image_candidates_are_measured_and_mapped_without_credit_confirmation(self):
        c=fixture();c['parcel']=mapping(box(0,0,10,10));c['features']['features']=[{
            'id':'roof','geometry':c['parcel'],'properties':{'layer':'surface','class':'roof'}}]
        raw=png([[[30,130,30],[100,100,100]],[[30,130,30],[100,100,100]]])
        with tempfile.TemporaryDirectory() as root:
            path=Path(root)/'image';path.write_bytes(raw)
            c['imagery']={'sha256':sha256(raw).hexdigest(),'blob_path':str(path),'bounds':[0,0,10,10]}
            out=enrich_candidates(c);again=enrich_candidates(out)
        self.assertAlmostEqual(out['automatic']['image_vegetation_candidate_sqft'],50*SQFT_PER_M2)
        self.assertAlmostEqual(out['automatic']['roof_vegetation_candidate_sqft'],50*SQFT_PER_M2)
        candidates=out['assessment']['records'];self.assertEqual(len(candidates),1)
        self.assertEqual(candidates[0]['decision'],'candidate');self.assertIsNone(candidates[0]['facts']['existing_installation'])
        self.assertNotIn('geometry',candidates[0]);self.assertEqual(len(again['assessment']['records']),1)
        self.assertAlmostEqual(measure(out)['ia_sqft'],100*SQFT_PER_M2)
        self.assertEqual(sum(f['id']=='auto-image-vegetation' for f in again['features']['features']),1)

class BadPublicGeometryTests(unittest.TestCase):
    def test_bad_public_polygon_leaves_other_estimates_usable(self):
        c=fixture();c['assessment']={'records':[{'id':'bad-public','category':'green_roof',
            'public_geometry':{'type':'Polygon','coordinates':[[[0,0],[1,1],[1,0],[0,1],[0,0]]]},
            'public_geometry_role':'system footprint','source':{'crs':c['crs']}}]}
        original=deepcopy(c);out=enrich_candidates(c)
        self.assertEqual(c,original);self.assertIn('automatic_footprint_error',out['assessment']['records'][0])
        self.assertNotIn('automatic_footprint',out['assessment']['records'][0])
        self.assertEqual(out['automatic']['system_footprints'],[])

class CurrentImageClassificationTests(unittest.TestCase):
    def setUp(self):
        model=patch('drainage_core.semantic_cover.semantic_cover',side_effect=FileNotFoundError('Explicit RGB-only fixture'))
        model.start();self.addCleanup(model.stop)

    def test_image_masks_use_frozen_pixels_without_requesting_2018_classification(self):
        from drainage_core.freshness import age_policy
        c=fixture();c['imagery_age_policy']=age_policy('2026-11-15')
        raw=png([[[30,130,30,255],[100,100,100,255],[5,5,5,255],[0,0,0,0]]]*2)
        with tempfile.TemporaryDirectory() as root:
            path=Path(root)/'image';path.write_bytes(raw)
            c['imagery']={'sha256':sha256(raw).hexdigest(),'blob_path':str(path),'bounds':[0,0,4,2],
                          'source_vintage':'2025','sources':[]}
            cache=Mock();r=landcover(c,cache,False)
            cache.fetch_json.assert_not_called();cache.fetch_bytes.assert_not_called()
        rows={x['feature']:x for x in r['estimates']}
        self.assertAlmostEqual(rows['vegetation_candidate']['area_sqft'],2*SQFT_PER_M2)
        self.assertAlmostEqual(rows['hard_surface_candidate']['area_sqft'],2*SQFT_PER_M2)
        self.assertAlmostEqual(r['unclassified_sqft'],4*SQFT_PER_M2)
        self.assertIsNone(rows['canopy']['area_sqft']);self.assertIsNone(rows['other_pavement']['area_sqft'])
        self.assertFalse(r['coverage_complete'])
        c['features']['features']=r['features']
        self.assertIsNone(measure(c)['canopy_sqft'])
        self.assertAlmostEqual(measure(c)['unknown_sqft'],8*SQFT_PER_M2)
