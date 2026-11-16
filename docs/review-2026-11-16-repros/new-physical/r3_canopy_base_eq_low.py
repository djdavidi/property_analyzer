"""estimate_canopy 'base' (road under canopy) cannot differ from 'low' with AI-only canopy."""
import sys, os; sys.path.insert(0, os.getcwd())
from shapely.geometry import box
from tests.test_management_geometry_unit import fixture, candidate
from drainage_core.management_estimates import estimate_canopy

case, gis = fixture()
obs, road, dev, grass, fp = case['features']['features']
# canopy predicted over the whole road strip and half the parcel; road predicted under it too
case['features']['features'] = [obs, candidate('canopy', box(0, 0, 15.24, 30.48)), road, dev, grass, fp]
res = estimate_canopy(case, gis)
print({r['id']: round(r['area_sqft'], 2) for r in res['area_scenarios']},
      'canopy_area', round(res['canopy_area_sqft'], 2), 'status', res['status'])
