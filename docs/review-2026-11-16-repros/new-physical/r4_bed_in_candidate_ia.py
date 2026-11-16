"""estimate_system area scenarios include the system's own bed; no IA-in-bed field exists."""
import sys, os; sys.path.insert(0, os.getcwd())
from shapely.geometry import box, shape
from tests.test_management_geometry_unit import fixture
from drainage_core.management_estimates import estimate_system
from drainage_core.geometry import case_area_sqft

case, gis = fixture()           # rain garden footprint = box(0,0,3.048,3.048), 100 sqft of observed pavement
res = estimate_system(case, gis, 'G1'); run = res['runs'][0]
fp = shape(res['footprint_geometry'])
for s in run['area_scenarios']:
    print(s['id'], round(s['area_sqft'], 2), 'of which inside system bed:',
          round(case_area_sqft(shape(s['geometry']).intersection(fp), case), 2))
print('reported fields:', {k: round(v, 2) for k, v in run.items() if k.endswith('footprint_sqft')})
