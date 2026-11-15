"""Contract checks for the GIS evidence → jurisdiction boundary."""
from copy import deepcopy
import unittest
from unittest.mock import patch

from shapely.geometry import box,mapping

from stormwater.jurisdictions import get_profile
from stormwater.jurisdictions.philadelphia import apply,PROFILE_ID


def fixture():
    """Independent rectangles with known physical areas; no real-site claim."""
    from drainage_core.engine import input_hash,result_hash
    parcel=mapping(box(500000,6200000,500030.48,6200030.48))
    canopy=mapping(box(500000,6200000,500003.3528,6200030.48))
    case={'schema_version':1,'id':'policy-fixture','name':'Invented nonlocal fixture','crs':'EPSG:26918',
          'parcel':parcel,'features':{'type':'FeatureCollection','features':[]},
          'corrections':[],'sources':[],'benefits':[]}
    measurement={'ga_sqft':10000.,'ia_sqft':10000.,'ia_min_sqft':10000.,'ia_max_sqft':10000.,
                 'unknown_sqft':0.,'complete':True,
                 'geometries':{'physical_ia':parcel,'pervious':{'type':'GeometryCollection','geometries':[]},
                               'canopy_ground_ia':canopy,'unknown':{'type':'GeometryCollection','geometries':[]}}}
    gis={'schema_version':1,'result_type':'gis-analysis','input_sha256':input_hash(case),'measurement':measurement,
         'drainage':{'status':'unavailable'},'warnings':['Independent references are missing'],
         'validation':{'ia':{'status':'incomplete'},'drainage':{'status':'incomplete'}},
         'processing_seconds':0.01}
    gis['analysis_sha256']=result_hash(gis)
    baseline={'ga_sqft':10000,'ia_sqft':10000,'existing_ga_credit_sqft':0,
              'existing_ia_credit_sqft':0,'existing_iar_sqft':0,'npdes_fraction':0,
              'accounts':[{'allocation':1,'discount_factor':1}],
              'property_type':'NonRes','bill_date':'2026-11-15','actual_bill_verified':False}
    benefit={'id':'canopy-credit','category':'canopy','geometry':canopy,'area_sqft':1100,
             'basis':'modeled','evidence':{'physical_area_confirmed':True,
                 'ground_impervious_overlap_confirmed':True,'parcel_allocation_confirmed':True,
                 'account_current':True}}
    return case,gis,{'baseline':baseline,'benefits':[benefit]}


class JurisdictionAdapterTests(unittest.TestCase):
    def test_known_bill_and_spatial_credit_without_mutating_gis_or_case(self):
        case,gis,policy=fixture();frozen=deepcopy((case,gis,policy))
        result=apply(case,gis,policy)
        self.assertEqual(result['jurisdiction'],PROFILE_ID)
        self.assertEqual(result['billing']['baseline']['monthly_total'],163.83)
        self.assertEqual(result['billing']['credit_only']['monthly_total'],156.78)
        self.assertEqual(result['billing']['credit_only']['monthly_savings'],7.05)
        self.assertEqual((case,gis,policy),frozen)
        self.assertNotIn('measurement',result);self.assertNotIn('drainage',result)

    def test_policy_reuse_does_not_reroute_and_records_different_policy_hash(self):
        case,gis,policy=fixture();other=deepcopy(policy);other['benefits']=[]
        with patch('drainage_core.engine.analyze',side_effect=AssertionError('GIS must not rerun')):
            first=apply(case,gis,policy);second=apply(case,gis,other)
        self.assertEqual(first['gis_input_sha256'],second['gis_input_sha256'])
        self.assertEqual(first['gis_artifact_sha256'],second['gis_artifact_sha256'])
        self.assertNotEqual(first['policy_input_sha256'],second['policy_input_sha256'])
        self.assertEqual(second['billing']['credit_only']['monthly_savings'],0)

    def test_changed_physical_case_is_rejected_as_stale(self):
        case,gis,policy=fixture();case['parcel']=mapping(box(0,0,20,20))
        with self.assertRaisesRegex(ValueError,'does not match'):
            apply(case,gis,policy)

    def test_source_metadata_change_requires_matching_gis_artifact(self):
        case,gis,policy=fixture()
        case['sources'].append({'url':'local:survey-fixture','acquisition_date':'2025-04-01'})
        with self.assertRaisesRegex(ValueError,'does not match'):
            apply(case,gis,policy)

    def test_account_policy_changes_reuse_same_physical_analysis(self):
        case,gis,policy=fixture();discounted=deepcopy(policy)
        discounted['baseline']['accounts'][0].update(discount_factor=.75,discount_verified=True)
        with patch('drainage_core.engine.analyze',side_effect=AssertionError('No GIS rerun')):
            standard=apply(case,gis,policy);reduced=apply(case,gis,discounted)
        self.assertEqual(reduced['billing']['baseline']['monthly_total'],122.87)
        self.assertEqual(reduced['billing']['credit_only']['monthly_total'],117.59)
        self.assertEqual(standard['gis_analysis_sha256'],reduced['gis_analysis_sha256'])
        self.assertNotEqual(standard['policy_input_sha256'],reduced['policy_input_sha256'])
        self.assertEqual(gis['measurement']['ia_sqft'],10000)

    def test_modified_measurements_or_composed_policy_results_cannot_be_reused_as_gis(self):
        case,gis,policy=fixture();gis['measurement']['ia_sqft']=0
        with self.assertRaisesRegex(ValueError,'content digest'):
            apply(case,gis,policy)
        case,gis,policy=fixture();gis['result_type']='jurisdiction-analysis'
        with self.assertRaisesRegex(ValueError,'supported saved GIS'):
            apply(case,gis,policy)

    def test_missing_baseline_is_policy_blocker_not_physical_zero(self):
        case,gis,_=fixture();result=apply(case,gis)
        self.assertEqual(result['billing']['status'],'blocked')
        self.assertEqual(gis['measurement']['ia_sqft'],10000)
        self.assertIn('Actual billing baseline unavailable',result['warnings'])

    def test_benefit_outside_measured_eligible_region_fails(self):
        case,gis,policy=fixture()
        policy['benefits'][0]['geometry']=mapping(box(500010,6200000,500020,6200030.48))
        result=apply(case,gis,policy)
        self.assertEqual(result['screens'][0]['status'],'requirements_failed')
        self.assertIn('physical_area_confirmed',result['screens'][0]['failed'])
        self.assertEqual(result['billing']['credit_only']['status'],'blocked')

    def test_explicit_profile_dispatch_and_invalid_policy_rejected(self):
        self.assertEqual(get_profile(PROFILE_ID).PROFILE_ID,PROFILE_ID)
        with self.assertRaises(ValueError):get_profile('unimplemented-city')
        case,gis,policy=fixture()
        for overlay in [{**policy,'jurisdiction':'unimplemented-city'}, {**policy,'new_physical_ia':0}]:
            with self.assertRaises(ValueError):apply(case,gis,overlay)
        with self.assertRaises(ValueError):apply(case,{**gis,'schema_version':99},policy)

if __name__=='__main__':unittest.main()
