"""Same case: estimate_system's 'modeled' surface_storage_diagnostic vs estimate_capacity."""
import sys, os; sys.path.insert(0, os.getcwd())
from shapely.geometry import box, mapping
from tests.test_management_geometry_unit import fixture
from drainage_core.management_estimates import estimate_system
from drainage_core.runoff_capacity import estimate_capacity
from drainage_core.research import digest, fill_dem
from drainage_core.geometry import SQFT_PER_M2

CUFT_PER_M3 = SQFT_PER_M2/.3048
case, gis = fixture()
n = 31
el = [[10.]*n for _ in range(n)]
for i in range(n):
    el[0][i] = el[n-1][i] = el[i][0] = el[i][n-1] = 20.   # larger enclosing depression (e.g. lot)
for r in range(17, 20):
    for c in range(11, 14):
        el[r][c] = 0.                                       # garden bowl
grid = {'origin': [0, 31], 'cell_size': 1., 'crs': case['crs'], 'horizontal_unit': 'm', 'vertical_unit': 'm'}
case['terrain'] = {**grid, 'elevations': el}
case['features']['features'][-1]['geometry'] = mapping(box(10, 10, 15, 15))  # rows 16..20, cols 10..14
import numpy as np
filled = fill_dem(el); depth = (filled - np.asarray(el)).tolist()
run = gis['research_drainage']['primary']
run.update(grid=grid, input_dem_sha256=digest(el), rasters={'fill_depth': depth})
sd = estimate_system(case, gis, 'G1')['surface_storage_diagnostic']
cap = estimate_capacity(case, gis, 'G1')
print('estimate_system diagnostic:', sd['status'], round(sd['volume_cuft']/CUFT_PER_M3, 3), 'm3', round(sd['volume_cuft'], 1), 'cuft')
print('estimate_capacity primary  :', cap['status'], round(cap['surface_storage_volume_cuft']/CUFT_PER_M3, 3), 'm3', round(cap['surface_storage_volume_cuft'], 1), 'cuft')
