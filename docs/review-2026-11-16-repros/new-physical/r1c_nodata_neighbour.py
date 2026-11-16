"""NoData just outside an aligned edge does not block the primary; a 1e-6 m outward nudge does."""
import sys, os; sys.path.insert(0, os.getcwd())
from copy import deepcopy
from shapely.geometry import box, mapping
from tests.test_runoff_capacity_unit import fixture
from drainage_core.runoff_capacity import estimate_capacity
case, gis = fixture(); case['terrain']['elevations'][0][3] = None   # cell directly north of garden edge
for eps in (0., 1e-6):
    k = deepcopy(case); k['features']['features'][0]['geometry'] = mapping(box(1, 1, 6, 6+eps))
    r = estimate_capacity(k, gis, '01073')
    print(f'eps={eps:g}', r['status'], r['surface_storage_volume_cuft'], [(s['name'], s['status']) for s in r['scenarios']], r.get('reason'))
