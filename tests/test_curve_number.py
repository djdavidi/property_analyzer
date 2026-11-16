"""Known-answer PWD worksheets and public-source failures; no site accuracy claim."""
from copy import deepcopy
from hashlib import sha256
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import Mock,patch
import io
import json
import unittest
from shapely.geometry import box,mapping,shape
from drainage_core.engine import analyze as analyze_gis,canonical
from drainage_core.geometry import reproject,measure,SQFT_PER_M2
from drainage_core.sources import Cache,SourceError
from stormwater.cases import new_case,CaseStore
from stormwater.curve_number import worksheet,review_inputs,soil_groups,TABLE
from stormwater.soil_sources import acquire,parse,query,boundary_hash,COLUMNS,MAX_ROWS


def feature(id,geometry,**properties):
    return {'id':id,'type':'Feature','geometry':mapping(geometry),'properties':{'layer':'surface','class':'pervious',**properties}}


def soil(c,g,group='B',id='soil',pct=100):
    return {'id':id,'type':'Feature','geometry':mapping(reproject(g,c['crs'],'EPSG:4326')),
            'properties':{'mukey':'1','mapunit_name':'Invented soil','components':[{'cokey':id,'compname':'Invented component','comppct_r':pct,'hydgrp':group}]}}


def attach(c,features):
    c.setdefault('assessment',{})['soil_snapshot']={'status':'retrieved','crs':'EPSG:4326',
        'boundary_sha256':boundary_hash(c),'features':features,'sources':[{'url':'https://example.test/soil','sha256':'a'*64}]}
    return c


def fixture():
    c=new_case('Synthetic CN worksheet');c['crs']='EPSG:26918'
    c['parcel']=mapping(box(500000,4420000,500100,4420100))
    c['features']['features']=[feature('lawn',box(500000,4420000,500060,4420100),cn_cover='lawn',cn_condition='good'),
                               feature('woods',box(500060,4420000,500100,4420100),cn_cover='woods',cn_condition='good')]
    attach(c,[soil(c,shape(c['parcel']))]);return c


def run(c):return worksheet(c,analyze_gis(c))


class CurveNumberTests(unittest.TestCase):
    def test_known_weighted_cn_and_ceil_factor_without_mutation(self):
        c=fixture();before=deepcopy(c);g=analyze_gis(c);frozen=deepcopy(g);w=worksheet(c,g)
        self.assertAlmostEqual(w['average_cn'],58.6,places=6)
        self.assertAlmostEqual(w['credit_factor'],.64)
        self.assertAlmostEqual(w['total_area_times_cn']/w['mapped_open_space_sqft'],58.6)
        self.assertEqual(c,before);self.assertEqual(g,frozen)
        self.assertFalse(c.get('benefits'));self.assertEqual(w['status'],'calculated_conditional')
        self.assertIsNone(w['image_candidate_area_sqft'],'No semantic model must not imply zero candidate area')

    def test_missing_condition_never_defaults_good_or_partial_average(self):
        c=fixture();del c['features']['features'][0]['properties']['cn_condition'];w=run(c)
        self.assertIsNone(w['average_cn']);self.assertIsNone(w['credit_factor'])
        self.assertIsNone(w['mapped_open_space_average_cn']);self.assertAlmostEqual(w['known_portion_average_cn'],55)
        row=next(r for r in w['rows'] if r['feature_id']=='lawn')
        self.assertIn('Cover condition unknown',row['missing']);self.assertEqual((row['candidate_cn_min'],row['candidate_cn_max']),(61,79))
        self.assertGreater(w['unknown_cn_area_sqft'],0)

    def test_unknown_soil_and_no_map_coverage_are_not_zero_cn(self):
        c=fixture();c['assessment']['soil_snapshot']['features']=[];w=run(c)
        self.assertIsNone(w['average_cn']);self.assertIsNone(w['known_portion_average_cn'])
        self.assertTrue(all(r['curve_number'] is None for r in w['rows']))
        self.assertTrue(all('Soil polygon coverage missing' in r['missing'] for r in w['rows']))

    def test_partial_soil_coverage_retains_uncovered_rows(self):
        c=fixture();attach(c,[soil(c,box(500000,4420000,500050,4420100))]);w=run(c)
        self.assertAlmostEqual(w['known_cn_area_sqft'],5000*SQFT_PER_M2,places=1)
        self.assertAlmostEqual(w['unknown_cn_area_sqft'],5000*SQFT_PER_M2,places=1)
        self.assertIsNone(w['average_cn'])

    def test_soil_group_ambiguity_dual_and_missing_components(self):
        c=fixture();p=c['assessment']['soil_snapshot']['features'][0]['properties']
        p['components']=[{'hydgrp':'B','comppct_r':60},{'hydgrp':'C','comppct_r':40}]
        w=run(c);self.assertIsNone(w['average_cn']);self.assertTrue(all(r['soil_group'] is None for r in w['rows']))
        for parts in ([{'hydgrp':'B/D','comppct_r':100}],[{'hydgrp':None,'comppct_r':100}],
                      [{'hydgrp':'B','comppct_r':60}],[],[{'hydgrp':'B','comppct_r':True}]):
            exact,_,missing=soil_groups({'components':parts});self.assertIsNone(exact);self.assertTrue(missing)
        self.assertEqual(soil_groups({'components':[{'hydgrp':'B','comppct_r':60},{'hydgrp':'B','comppct_r':40}]})[0],'B')

    def test_overlap_soils_are_unknown_and_not_double_counted(self):
        c=fixture();c['assessment']['soil_snapshot']['features'].append(soil(c,shape(c['parcel']),'C','other'))
        w=run(c);self.assertIsNone(w['average_cn'])
        self.assertAlmostEqual(sum(r['area_sqft'] for r in w['rows']),10000*SQFT_PER_M2,places=5)
        self.assertTrue(all('Overlapping soil polygons' in '; '.join(r['missing']) for r in w['rows']))

    def test_overlap_cover_is_unknown_and_not_double_counted(self):
        c=fixture();c['features']['features'].append(feature('duplicate',shape(c['parcel']),cn_cover='lawn',cn_condition='poor'))
        w=run(c);self.assertIsNone(w['average_cn'])
        self.assertAlmostEqual(sum(r['area_sqft'] for r in w['rows']),10000*SQFT_PER_M2,places=5)

    def test_unknown_ground_blocks_property_cn_but_keeps_subset(self):
        c=fixture();c['features']['features'].pop();w=run(c)
        self.assertAlmostEqual(w['mapped_open_space_average_cn'],61,places=6);self.assertIsNone(w['average_cn'])
        self.assertGreater(w['unresolved_ground_sqft'],0)

    def test_impervious_excluded_and_boundary_changes_invalidate_soils(self):
        c=fixture();c['features']['features'][1]['properties']['class']='pavement';w=run(c)
        self.assertAlmostEqual(w['average_cn'],61,places=6)
        self.assertAlmostEqual(w['mapped_open_space_sqft'],6000*SQFT_PER_M2,places=5)
        c['parcel']=mapping(box(500000,4420000,500090,4420100));w=run(c)
        self.assertIsNone(w['average_cn']);self.assertIn('does not match','; '.join(w['issues']))

    def test_image_candidates_remain_separate_and_do_not_infer_condition(self):
        c=fixture();c['features']['features']=[];g=analyze_gis(c)
        g['modeled_integration']['ai']={'status':'modeled','geometries':{'grass_shrub':c['parcel']}}
        w=worksheet(c,g);self.assertIsNone(w['average_cn']);self.assertIsNone(w['mapped_open_space_sqft'])
        self.assertGreater(w['image_candidate_area_sqft'],0)
        self.assertTrue(all(r['basis']=='image_candidate' and r['curve_number'] is None for r in w['rows']))
        updated=review_inputs(c,'image-grass_shrub','lawn','good','Synthetic manual interpretation')
        reviewed=worksheet(updated,g);self.assertIsNone(reviewed['average_cn'])
        self.assertTrue(all(r['curve_number']==61 for r in reviewed['rows']))

    def test_manual_reviews_append_history_and_do_not_overwrite_benefits(self):
        c=fixture();c['benefits']=[{'id':'manual','category':'open_space','area_sqft':1,'evidence':{'curve_number':55}}]
        r=review_inputs(c,'lawn','lawn','fair','Synthetic review');s=review_inputs(r,'lawn','meadow',None,'Correction')
        self.assertEqual(len(s['assessment']['open_space_reviews']),2)
        self.assertEqual(s['assessment']['open_space_reviews'][1]['before']['condition'],'fair')
        self.assertEqual(s['benefits'],c['benefits']);self.assertNotIn('open_space_inputs',c['assessment'])
        for args in [('bad','lawn','good','why'),('lawn','lawn','bad','why'),('lawn','lawn','good','')]:
            with self.assertRaises(ValueError):review_inputs(c,*args)

    def test_browser_integral_coordinate_json_does_not_invalidate_soil_or_review(self):
        c=fixture();reviewed=review_inputs(c,'lawn','lawn','fair','Synthetic review')
        def browser_json(v):
            if isinstance(v,bool):return v
            if isinstance(v,float) and v.is_integer():return int(v)
            if isinstance(v,dict):return {k:browser_json(x) for k,x in v.items()}
            if isinstance(v,(list,tuple)):return [browser_json(x) for x in v]
            return v
        client=browser_json(reviewed);w=run(client)
        self.assertAlmostEqual(w['average_cn'],63.4,places=6)
        self.assertFalse(any(r['review_stale'] for r in w['rows']))
        self.assertEqual(boundary_hash(c),boundary_hash(client))
        with TemporaryDirectory() as root:
            store=CaseStore(root);store.save(c)
            with patch('stormwater.cases.analyze_gis',side_effect=AssertionError('Browser policy edit must not reroute')):
                result=store.save(client)
            self.assertEqual(result['physical_reuse']['status'],'reused_frozen_gis')
            self.assertAlmostEqual(result['assessment']['open_space_curve_number']['average_cn'],63.4,places=6)


    def test_changed_mapping_makes_old_cover_review_stale(self):
        c=fixture();p=c['features']['features'][0]['properties'];p.pop('cn_condition')
        reviewed=review_inputs(c,'lawn','lawn','good','Synthetic manual input')
        self.assertIsNotNone(run(reviewed)['average_cn'])
        reviewed['features']['features'][0]['properties']['source_sha256']='new image'
        w=run(reviewed);self.assertIsNone(w['average_cn'])
        self.assertTrue(any(r['review_stale'] for r in w['rows']))
        self.assertIn('stale','; '.join(r['missing'][0] for r in w['rows'] if r['missing']))

    def test_corrupted_soil_snapshot_does_not_calculate(self):
        c=fixture();s=c['assessment']['soil_snapshot']
        s['snapshot_sha256']=sha256(__import__('drainage_core.sources',fromlist=['canonical']).canonical(s)).hexdigest()
        self.assertIsNotNone(run(c)['average_cn'])
        s['features'][0]['properties']['components'][0]['hydgrp']='A'
        self.assertIsNone(run(c)['average_cn']);self.assertIn('hash mismatch','; '.join(run(c)['issues']))

    def test_all_pwd_lookup_rows_and_group_d_effect(self):
        # Cover-specific entries matter: good lawn on D has CN80, not eligible
        # for standard open-space factor; woods B has CN55, maximum factor.
        c=fixture();c['assessment']['soil_snapshot']['features'][0]['properties']['components'][0]['hydgrp']='D'
        w=run(c);self.assertGreaterEqual(w['average_cn'],75);self.assertEqual(w['credit_factor'],0)
        self.assertEqual(TABLE['lawn']['good'],[39,61,74,80,61])
        self.assertEqual(TABLE['woods']['good'],[30,55,70,77,55])
        self.assertEqual(TABLE['porous_turf']['na'],[70,70,79,84,69])
        for entries in TABLE.values():
            for values in entries.values():self.assertEqual(len(values),5)

    def test_mapped_grass_percentage_boundaries(self):
        for pct,expected in [(49,'poor'),(50,'fair'),(75,'fair'),(76,'good')]:
            c=fixture();p=c['features']['features'][0]['properties'];p.pop('cn_condition');p['grass_cover_percent']=pct
            self.assertEqual(next(r for r in run(c)['rows'] if r['feature_id']=='lawn')['condition'],expected)

    def test_outside_verified_period_keeps_physical_worksheet_but_blocks_factor(self):
        from stormwater.assessment_policy import evaluate_assessment
        c=fixture();r=evaluate_assessment(c,analyze_gis(c),as_of='2030-01-01')['open_space_curve_number']
        self.assertAlmostEqual(r['average_cn'],58.6,places=6);self.assertIsNone(r['credit_factor'])
        self.assertIn('Outside verified','; '.join(r['issues']))

    def test_worksheet_html_escaping_and_unknowns(self):
        from stormwater.assessment_report import curve_number_section
        c=fixture();c['assessment']['soil_snapshot']['features'][0]['properties']['mapunit_name']='<script>bad</script>'
        w=run(c);html=curve_number_section(w)
        self.assertIn('Open-space curve-number worksheet',html);self.assertIn('58.60',html)
        self.assertIn('&lt;script&gt;',html);self.assertNotIn('<script>bad',html)
        c['assessment']['soil_snapshot']['features']=[];self.assertIn('Unknown',curve_number_section(run(c)))

    def test_policy_only_review_reuses_exact_frozen_gis(self):
        c=fixture()
        with TemporaryDirectory() as root:
            store=CaseStore(root);first=store.save(c);file=store.directory(c['id'])/'gis-analysis.json';before=file.read_bytes()
            updated=review_inputs(c,'lawn','lawn','fair','Synthetic condition correction')
            with patch('stormwater.cases.analyze_gis',side_effect=AssertionError('Must not reroute')):
                result=store.save(updated)
            self.assertEqual(result['physical_reuse']['status'],'reused_frozen_gis')
            self.assertEqual(file.read_bytes(),before)
            self.assertNotEqual(result['assessment']['open_space_curve_number']['average_cn'],first['assessment']['open_space_curve_number']['average_cn'])
            self.assertIn('worksheet', (file.parent/'report.html').read_text())


class SoilSourceTests(unittest.TestCase):
    def test_parse_schema_first_data_row_not_dropped_and_components_grouped(self):
        row=['p','m',box(-75,40,-74.999,40.001).wkt,'Invented','a','A',60,'B']
        other=[*row];other[4:]=['b','B',40,'C']
        r=parse({'Table':[COLUMNS,row,other]});self.assertEqual(len(r),1)
        self.assertEqual(len(r[0]['properties']['components']),2)
        self.assertEqual(parse({}),[])
        for data in ({'Table':[]},{'Table':[['wrong']]},{'Table':[COLUMNS,['bad']]},{'Table':[COLUMNS]+[row]*(MAX_ROWS+1)}):
            with self.assertRaises(SourceError):parse(data)

    def test_public_post_cache_preserves_bytes_request_identity_and_failure_fallback(self):
        raw=b'{ "Table": [["value"], [3]] }';opener=Mock(return_value=io.BytesIO(raw))
        with TemporaryDirectory() as root:
            cache=Cache(root,opener=opener);payload={'query':'SELECT 3','format':'JSON+COLUMNNAME'}
            first=cache.post_json('https://example.test/query',payload)
            self.assertEqual((Path(root)/'blobs'/first['provenance']['sha256']).read_bytes(),raw)
            self.assertEqual(opener.call_args.args[0].get_method(),'POST')
            self.assertEqual(first['provenance']['request'],payload)
            opener.side_effect=OSError('offline');self.assertEqual(cache.post_json('https://example.test/query',payload),first)
            dated=cache.post_json('https://example.test/query',payload,True)
            self.assertTrue(dated['provenance']['cache_reused_after_failure'])
            self.assertEqual(dated['provenance']['retrieved_at'],first['provenance']['retrieved_at'])
            with self.assertRaises(SourceError):cache.post_json('https://example.test/query',{'query':'other'})
            with self.assertRaises(SourceError):cache.post_json('http://example.test/query',payload)
            (Path(root)/'blobs'/first['provenance']['sha256']).write_bytes(b'bad')
            with self.assertRaises(SourceError):cache.post_json('https://example.test/query',payload)

    def test_acquisition_outage_invalid_data_history_and_physical_preservation(self):
        c=fixture();before=deepcopy(c);cache=Mock();cache.post_json.side_effect=SourceError('offline')
        out=acquire(c,cache);self.assertEqual(out['assessment']['soil_snapshot']['status'],'unavailable')
        self.assertEqual(out['assessment']['soil_history'][-1],c['assessment']['soil_snapshot'])
        self.assertEqual(out['features'],c['features']);self.assertEqual(out['sources'],c['sources']);self.assertEqual(c,before)
        self.assertIsNone(run(out)['average_cn'])
        cache.post_json.side_effect=None;cache.post_json.return_value={'data':{'Table':[['bad']]},'provenance':{'sha256':'b'*64}}
        out=acquire(c,cache);self.assertEqual(out['assessment']['soil_snapshot']['status'],'unavailable')
        self.assertEqual(out['assessment']['soil_snapshot']['sources'][0]['sha256'],'b'*64)

    def test_soil_raw_bytes_and_history_portable_without_physical_source_edits(self):
        import base64
        from stormwater.cases import CaseStore
        c=fixture();g=shape(c['assessment']['soil_snapshot']['features'][0]['geometry'])
        row=['p','m',g.wkt,'Synthetic mapunit','a','Synthetic component','100','B']
        raw=json.dumps({'Table':[COLUMNS,row]},separators=(',',':')).encode()
        with TemporaryDirectory() as public,TemporaryDirectory() as first,TemporaryDirectory() as second:
            root=Path(public);cache=Cache(root/'data/public',opener=Mock(return_value=io.BytesIO(raw)))
            updated=acquire(c,cache)
            self.assertEqual(updated['sources'],c['sources'])
            # Both stores share the temporary public cache, as data/public would locally.
            source=CaseStore(first,data_root=root/'data');result=source.save(updated);bundle=source.portable_bundle(c['id'])
            digest=sha256(raw).hexdigest();blob=next(b for b in bundle['public_blobs'] if b['sha256']==digest)
            self.assertEqual(base64.b64decode(blob['content_base64']),raw)
            imported=CaseStore(second,data_root=root/'data').import_bundle(bundle)
            self.assertEqual(imported['case']['assessment']['soil_snapshot'],json.loads(json.dumps(updated['assessment']['soil_snapshot'])))
            self.assertAlmostEqual(imported['analysis']['assessment']['open_space_curve_number']['average_cn'],58.6,places=5)
            self.assertEqual(result['assessment']['open_space_curve_number']['soil_snapshot_sha256'],updated['assessment']['soil_snapshot']['snapshot_sha256'])

    def test_query_bounded_projected_reprojection_and_no_persistent_aoi(self):
        c=fixture();sql=query(c);self.assertIn('TOP 1001',sql);self.assertIn('STIntersection',sql)
        self.assertIn('-75',sql);self.assertNotIn('500000',sql)
        c['crs']='EPSG:4326';c['parcel']=mapping(box(-75,40,-74,41))
        with self.assertRaises(SourceError):query(c)


if __name__=='__main__':unittest.main()
