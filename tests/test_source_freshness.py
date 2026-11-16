"""Age boundaries, stale-cache rejection and measurement/policy separation."""
from copy import deepcopy
from pathlib import Path
from hashlib import sha256
import tempfile
import unittest
from unittest.mock import Mock, patch
from drainage_core.freshness import age_policy, freshness
from drainage_core.geometry import measure, effective_features, SQFT_PER_M2
from drainage_core.sources import SourceError
from stormwater.automatic import acquire, landcover
from stormwater.acquisition import acquire_imagery
from test_automatic_site import fixture, lc, png


class SourceFreshnessTests(unittest.TestCase):
    def test_other_automatic_datasets_and_documented_canopy_absence_survive_image_outage(self):
        c=fixture();features=lc(c)['features']
        for index,f in enumerate(features):f['id']='other-dataset-'+str(index)
        c['features']['features']=features[1:]
        c['canopy_observation']={'status':'complete','source_vintage':'2018','reviewed':True}
        with patch('stormwater.automatic.buildings',side_effect=SourceError('offline')), \
             patch('stormwater.acquisition.acquire_imagery',side_effect=SourceError('offline')), \
             patch('stormwater.automatic_terrain.acquire',side_effect=SourceError('offline')):
            out=acquire(c,Mock())
        self.assertEqual(out['features'],c['features'])
        self.assertEqual(measure(out)['canopy_sqft'],0)
        self.assertGreater(measure(out)['ia_sqft'],0)

    def test_missing_image_coverage_cannot_create_zero_candidate_measurements(self):
        from drainage_core.remote_sensing import rgb_cover_candidates
        with self.assertRaisesRegex(ValueError,'No usable imagery coverage'):
            rgb_cover_candidates(png([[[30,130,30,0]]]),[0,0,4,2],fixture(),
                                 {'family':'fixture','sha256':'a'*64,'source_vintage':'2025'})

    def test_display_projection_does_not_change_original_image_mask_measurements(self):
        from drainage_core.projection import project_case
        c=fixture();c['imagery_age_policy']=age_policy('2026-11-15')
        raw=png([[[30,130,30],[100,100,100]]]*2)
        with tempfile.TemporaryDirectory() as root:
            path=Path(root)/'image';path.write_bytes(raw)
            c['measurement_imagery']={'source_vintage':'2025','sha256':sha256(raw).hexdigest(),
                'blob_path':str(path),'bounds':[0,0,4,2],'crs':c['crs'],'sources':[]}
            one=landcover(c,Mock(),False)
            projected=project_case(c,'EPSG:2272');two=landcover(projected,Mock(),False)
        self.assertEqual(one['settings'],two['settings'])
        self.assertEqual(two['pixel_crs'],c['crs'])
        for a,b in zip(one['estimates'][:2],two['estimates'][:2]):
            self.assertAlmostEqual(a['area_sqft'],b['area_sqft'],places=4)

    def test_exact_calendar_boundary_future_unknown_and_year_only(self):
        policy=age_policy('2026-11-15')
        for value,status in [('2023-11-15','within_age_limit'),('2023-11-14','too_old'),
                             ('2026-11-16','future_capture_date'),('bad','unknown_capture_date')]:
            self.assertEqual(freshness({'acquisition_date':value},policy)['status'],status)
        self.assertTrue(freshness({'source_vintage':'2025'},policy)['eligible'])
        self.assertFalse(freshness({'source_vintage':'2023'},policy)['eligible'])
        self.assertFalse(freshness({'retrieved_at':'2026-11-15','reviewed_at':'2026-11-15'},policy)['eligible'])
        self.assertEqual(age_policy('2028-02-29')['cutoff'],'2025-02-28')
        self.assertFalse(freshness({'acquisition_date':'bad','source_vintage':'2025'},policy)['eligible'])

    def test_imagery_rule_does_not_expire_other_datasets_or_manual_observations(self):
        c=fixture();c['imagery_age_policy']=age_policy('2026-11-15')
        c['features']['features']=lc(c)['features']
        for f in c['features']['features']:
            f['properties'].pop('automatic',None)
            f['properties']['source_vintage']='2018'
        c['canopy_observation']={'status':'complete','source_vintage':'2018'}
        original=deepcopy(c);m=measure(c)
        self.assertAlmostEqual(m['canopy_sqft'],2*SQFT_PER_M2)
        self.assertAlmostEqual(m['ia_sqft'],4*SQFT_PER_M2)
        self.assertEqual(c,original)
        for f in c['features']['features']:f['properties'].pop('source_vintage',None)
        self.assertEqual(len(effective_features(c)),4)

    def test_dated_manual_correction_remains_usable_without_redating_original(self):
        c=fixture();c['imagery_age_policy']=age_policy('2026-11-15');c['features']['features']=lc(c)['features']
        for f in c['features']['features']:f['properties']['source_vintage']='2018'
        c['corrections']=[{'id':'review','at':'2026-11-15','reason':'Dated site observation',
            'action':'replace','target':'auto-lc-5','feature':{'id':'reviewed-roof','geometry':c['parcel'],
            'properties':{'layer':'surface','class':'roof','observation_date':'2025-05-01'}}}]
        self.assertAlmostEqual(measure(c)['ia_sqft'],8*SQFT_PER_M2)
        self.assertEqual(c['features']['features'][2]['properties']['source_vintage'],'2018')

    def test_export_fails_closed_without_falling_back_to_undated_world_tiles(self):
        import stormwater.acquisition as acquisition
        self.assertFalse(hasattr(acquisition,'acquire_tile_imagery'))
        cache=Mock();cache.fetch_json.side_effect=SourceError('PASDA offline')
        # An outage is reported as an outage, never as "no recent imagery".
        with self.assertRaisesRegex(SourceError,'outage'):
            acquire_imagery(fixture()['parcel'],cache,freshness_policy=age_policy('2026-11-15'))
        self.assertEqual(cache.fetch_json.call_count,1)
        self.assertNotIn('arcgisonline',str(cache.fetch_json.call_args_list))
        cache.reset_mock();cache.fetch_json.side_effect=None
        cache.fetch_json.return_value={'data':{'services':[{'name':'pasda/PhiladelphiaImagery2025','type':'MapServer'}]},'provenance':{}}
        with self.assertRaisesRegex(SourceError,'three-year'):
            acquire_imagery(fixture()['parcel'],cache,freshness_policy=age_policy('2029-01-02'))
        self.assertEqual(cache.fetch_json.call_count,1)  # catalog only; no export of an ineligible vintage

    def test_outage_does_not_reactivate_old_image_or_estimates(self):
        c=fixture();c['features']['features']=lc(c)['features']
        for f in c['features']['features']:f['properties']['source_vintage']='2018'
        c['imagery']={'source_vintage':'2018','sha256':'a'*64}
        c['automatic']={'landcover':{'source_vintage':'2018'},'estimates':[{'area_sqft':99}]}
        before=deepcopy(c)
        with patch('stormwater.automatic.now',return_value='2026-11-15T12:00:00Z'), \
             patch('stormwater.automatic.buildings',side_effect=SourceError('offline')), \
             patch('stormwater.acquisition.acquire_imagery',side_effect=SourceError('offline')), \
             patch('stormwater.automatic_terrain.acquire',side_effect=SourceError('offline')):
            out=acquire(c,Mock())
        self.assertEqual(c,before);self.assertNotIn('imagery',out)
        self.assertEqual(out['historical_imagery'][0],c['imagery'])
        self.assertEqual(out['automatic']['estimates'],[])
        self.assertEqual(out['automatic_history'][0],c['automatic'])
        self.assertIsNone(measure(out)['canopy_sqft'])
        self.assertEqual(len(out['historical_automatic_features'][0]['features']),4)

    def test_saved_recent_image_reprocessed_during_outage_and_hash_checked(self):
        c=fixture();raw=png([[[30,130,30],[100,100,100]]]*2)
        with tempfile.TemporaryDirectory() as root:
            path=Path(root)/'image';path.write_bytes(raw)
            c['imagery']={'source_vintage':'2025','sha256':sha256(raw).hexdigest(),
                          'blob_path':str(path),'bounds':[0,0,4,2],'sources':[]}
            with patch('stormwater.automatic.now',return_value='2026-11-15T12:00:00Z'), \
                 patch('stormwater.automatic.buildings',side_effect=SourceError('offline')), \
                 patch('stormwater.acquisition.acquire_imagery',side_effect=SourceError('offline')), \
                 patch('stormwater.automatic_terrain.acquire',side_effect=SourceError('offline')):
                out=acquire(c,Mock())
            self.assertEqual(out['automatic']['landcover']['source_vintage'],'2025')
            self.assertTrue(out['automatic']['landcover']['freshness']['eligible'])
            self.assertIsNone(measure(out)['canopy_sqft'])
            path.write_bytes(b'tampered')
            with self.assertRaises(ValueError):landcover(out,Mock(),False)

    def test_stale_classifier_cannot_be_injected_even_when_downloaded_today(self):
        c=fixture();r=lc(c);r.update(source_vintage='2018',retrieved_at='2026-11-15',source_snapshots=[])
        with patch('stormwater.automatic.buildings',side_effect=SourceError('offline')), \
             patch('stormwater.acquisition.acquire_imagery',side_effect=SourceError('offline')), \
             patch('stormwater.automatic.landcover',return_value=r), \
             patch('stormwater.automatic_terrain.acquire',side_effect=SourceError('offline')):
            out=acquire(c,Mock())
        self.assertEqual(out['automatic']['estimates'],[])
        self.assertIsNone(measure(out)['canopy_sqft'])
