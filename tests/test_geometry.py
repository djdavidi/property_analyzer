import unittest
from shapely.geometry import box, Polygon, mapping
from stormwater.geometry import measure, area_sqft, reproject, effective_features


def feature(id, geom, cls, layer='surface'):
    return dict(type='Feature', id=id, geometry=mapping(geom), properties={'layer':layer,'class':cls})


def case(features, parcel=None, crs='EPSG:2272'):
    return {'crs':crs,'parcel':mapping(parcel if parcel is not None else box(0,0,100,100)),
            'features':{'type':'FeatureCollection','features':features}, 'corrections':[]}


class GeometryTests(unittest.TestCase):
    def test_union_clip_hole(self):
        parcel=Polygon([(0,0),(100,0),(100,100),(0,100)], [[(10,10),(20,10),(20,20),(10,20)]])
        c=case([feature('r',box(-10,0,60,100),'roof'),feature('p',box(40,0,110,100),'pavement')],parcel)
        m=measure(c)
        self.assertAlmostEqual(m['ia_sqft'],9900*(1200/3937/.3048)**2,places=4)
        self.assertAlmostEqual(m['ia_sqft'],m['ga_sqft'])

    def test_canopy_keeps_physical_ia_and_only_ground_overlap(self):
        c=case([feature('r',box(0,0,40,100),'roof'),feature('p',box(40,0,70,100),'pavement'),
                feature('l',box(70,0,100,100),'pervious'),feature('t',box(0,0,100,100),'canopy','canopy')])
        m=measure(c); factor=(1200/3937/.3048)**2
        self.assertAlmostEqual(m['ia_sqft'],7000*factor)
        self.assertAlmostEqual(m['canopy_ground_ia_sqft'],3000*factor)
        self.assertTrue(m['complete'])

    def test_unknown_and_conflict_not_pervious(self):
        c=case([feature('r',box(0,0,50,100),'roof'),feature('g',box(40,0,60,100),'pervious')])
        m=measure(c)
        self.assertFalse(m['complete']); self.assertGreater(m['unknown_sqft'],4999)
        self.assertGreater(m['ia_max_sqft'],m['ia_sqft'])

    def test_correction_is_replayable_and_observation_preserved(self):
        c=case([feature('r',box(0,0,100,100),'pavement')])
        c['corrections']=[{'id':'e','at':'2026-11-15','action':'add','reason':'Reviewed lawn',
                           'feature':feature('l',box(0,0,50,100),'pervious')}]
        self.assertAlmostEqual(measure(c)['ia_sqft']/measure(c)['ga_sqft'],.5)
        self.assertEqual(c['features']['features'][0]['geometry'],mapping(box(0,0,100,100)))
        c['corrections']=[]; self.assertEqual(measure(c)['ia_sqft'],measure(c)['ga_sqft'])

    def test_metre_foot_equivalence_and_geographic_rejected(self):
        m=area_sqft(box(0,0,30.48,30.48),'EPSG:26918')
        self.assertAlmostEqual(m,10000,places=6)
        foot=area_sqft(box(0,0,100*.3048/(1200/3937),100*.3048/(1200/3937)),'EPSG:2272')
        self.assertAlmostEqual(m,foot,places=6)
        with self.assertRaises(ValueError): area_sqft(box(0,0,1,1),'EPSG:4326')

    def test_invalid_geometry_rejected(self):
        with self.assertRaises(ValueError): measure(case([feature('x',Polygon([(0,0),(100,100),(0,100),(100,0)]),'roof')]))

if __name__ == '__main__': unittest.main()
