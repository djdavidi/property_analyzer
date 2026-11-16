"""A mapped inlet/overflow inside the garden bowl does not change or flag capacity."""
import sys, os; sys.path.insert(0, os.getcwd())
from shapely.geometry import box, mapping, Point
from tests.test_runoff_capacity_unit import fixture, CUFT_PER_M3
from drainage_core.runoff_capacity import estimate_capacity

case, gis = fixture()
a = estimate_capacity(case, gis, '01073')
case['features']['features'].append({'id': 'overflow', 'geometry': mapping(Point(3.5, 3.5).buffer(.3)),
    'properties': {'layer': 'inlet', 'drainage_role': 'inlet', 'rim_elevation_m': 0.3}})
case['features']['features'].append({'id': 'curbcut', 'geometry': mapping(box(1, 3, 1.2, 4)),
    'properties': {'layer': 'curb_cut'}})
b = estimate_capacity(case, gis, '01073')
print('without inlet:', a['status'], round(a['surface_storage_volume_cuft']/CUFT_PER_M3, 2), 'm3')
print('with inlet+curb cut:', b['status'], round(b['surface_storage_volume_cuft']/CUFT_PER_M3, 2), 'm3',
      'mentions inlet:', 'inlet' in str({k: v for k, v in b.items() if k not in ('limitations',)}).lower())
print('max ponding depth implied (m):', max(r['spill_elevation_m'] for r in [{'spill_elevation_m': b['scenarios'][0]['component_spill_elevations_m'][0]}]) - 0.0)
