"""Exercise the untested micro-basin terminal-hypothesis branch."""
import sys, os; sys.path.insert(0, os.getcwd())
from shapely.geometry import box, mapping
from tests.test_management_geometry_unit import fixture
from drainage_core.management_estimates import estimate_system
case, gis = fixture('01074', 'Subsurface Basin')
run = gis['research_drainage']['primary']; run['catchments'] = []
grid = {'origin': [0, 30.48], 'cell_size': 3.048, 'crs': case['crs'], 'horizontal_unit': 'm', 'vertical_unit': 'm'}
basins = [[1]*5 + [2]*5 for _ in range(10)]
run.update(grid=grid, rasters={'micro_basins': basins}, micro_basins=[
    {'id': 1, 'terminal': 'unresolved:depression:9:0', 'sink_cell': [9, 0], 'gsi_id': None, 'outlet_id': None},
    {'id': 2, 'terminal': 'unresolved:flat:9:9', 'sink_cell': [9, 9], 'gsi_id': None, 'outlet_id': None}])
res = estimate_system(case, gis, '01074')
print(res['status'], [(r['name'], round(r['on_parcel_area_sqft'], 1), {s['id']: round(s['area_sqft'], 1) for s in r['area_scenarios']}) for r in res['runs']])
print(res['scenario_envelope_sqft'])
