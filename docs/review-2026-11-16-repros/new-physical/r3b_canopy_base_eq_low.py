"""estimate_canopy: 'base' = low + (hidden ∩ AI road); AI classes are made disjoint, so with
AI-only canopy base==low always. Only an observed canopy polygon can make base differ."""
import sys, os; sys.path.insert(0, os.getcwd())
from shapely.geometry import box, mapping
from tests.test_management_geometry_unit import fixture, candidate
from drainage_core.management_estimates import estimate_canopy
for label, extra in [('AI canopy over grass strip, beside AI road', []),
                     ('AI canopy + observed canopy polygon over road strip',
                      [{'id': 'obs-canopy', 'geometry': mapping(box(3.048, 0, 9.144, 30.48)), 'properties': {'layer': 'canopy'}}])]:
    case, gis = fixture()
    obs, road, dev, grass, fp = case['features']['features']
    case['features']['features'] = [obs, road, dev, candidate('canopy', box(18.288, 0, 30.48, 30.48)), fp] + extra
    res = estimate_canopy(case, gis)
    print(label, {r['id']: round(r['area_sqft'], 1) for r in res['area_scenarios']})
