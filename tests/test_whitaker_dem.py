from copy import deepcopy
import unittest
from shapely.geometry import shape,box,mapping

from stormwater.cases import analyze
from stormwater.fixtures import synthetic_case
from stormwater.geometry import reproject,area_sqft,measure
from stormwater.whitaker_usgs import project_case


class NativeTerrainCaseTests(unittest.TestCase):
    def test_coordinate_change_transforms_every_vector_ledger_and_preserves_observations(self):
        original=synthetic_case();before=deepcopy(original)
        original['references']=[{'id':'r','kind':'ia','crs':original['crs'],'geometry':original['parcel']}]
        original['corrections']=[{'id':'e','action':'add','at':'2026-11-15','reason':'Survey evidence',
            'feature':{'type':'Feature','id':'review','geometry':mapping(box(2690060,249920,2690070,249930)),
                       'properties':{'layer':'surface','class':'pavement'}}}]
        c=project_case(original,'EPSG:26918')
        pairs=[(original['parcel'],c['parcel'])]
        pairs.extend((a['geometry'],b['geometry']) for a,b in zip(original['features']['features'],c['features']['features']))
        pairs.append((original['corrections'][0]['feature']['geometry'],c['corrections'][0]['feature']['geometry']))
        pairs.extend((a['geometry'],b['geometry']) for a,b in zip(original['benefits'],c['benefits']))
        pairs.append((original['references'][0]['geometry'],c['references'][0]['geometry']))
        for source,target in pairs:
            restored=reproject(shape(target),'EPSG:26918',original['crs'])
            self.assertLess(shape(source).hausdorff_distance(restored),1e-5)
        self.assertEqual(c['references'][0]['crs'],'EPSG:26918')
        self.assertIsNone(c['terrain'])
        self.assertEqual(original['features'],before['features'])
        self.assertEqual(c['sources'],original['sources'])
        self.assertEqual(c['area_crs'],original['crs'])
        a,b=measure(original),measure(c)
        for field in ('ga_sqft','ia_sqft','canopy_ground_ia_sqft'):
            self.assertAlmostEqual(a[field],b[field],places=4)

    def test_incompatible_reference_crs_cannot_be_silently_relabelled(self):
        c=synthetic_case();c['references']=[{'crs':'EPSG:4326','geometry':mapping(box(-75,40,-74,41))}]
        with self.assertRaises(ValueError):project_case(c,'EPSG:26918')

    def test_unresolved_roof_display_aggregation_preserves_detailed_routing_labels(self):
        c=synthetic_case();r=analyze(c)
        roof_cells=[x for row in r['drainage']['labels'] for x in row if x and x.startswith('unresolved:roof:')]
        groups=[x for x in r['drainage']['catchments'] if x['outlet']=='unresolved:roof']
        self.assertGreater(len(roof_cells),1);self.assertEqual(len(groups),1)
        size=c['terrain']['cell_size']
        self.assertAlmostEqual(groups[0]['contributing_area_sqft'],len(roof_cells)*area_sqft(box(0,0,size,size),c['crs']),places=5)

if __name__=='__main__':unittest.main()
