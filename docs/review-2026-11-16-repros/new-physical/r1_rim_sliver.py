"""Sub-mm footprint shift flips the boundary_cell_minimum spill to outside terrain."""
import sys, os; sys.path.insert(0, os.getcwd())
from copy import deepcopy
from shapely.geometry import box, mapping
from tests.test_runoff_capacity_unit import fixture, CUFT_PER_M3
from drainage_core.runoff_capacity import estimate_capacity

case, gis = fixture()
# outer ring (outside the 5x5 garden) is lower than the garden's own berm cells
el = case['terrain']['elevations']
for r in range(7):
    for c in range(7):
        if r in (0, 6) or c in (0, 6):
            el[r][c] = 5.
for eps in (0., 1e-4, 1e-6):
    k = deepcopy(case)
    k['features']['features'][0]['geometry'] = mapping(box(1-eps, 1, 6, 6))
    res = estimate_capacity(k, gis, '01073')
    print(f'shift={eps:g} m  area_sqft={res["footprint_area_sqft"]:.6f}  '
          f'spill_m={[s["component_spill_elevations_m"] for s in res["scenarios"]]}  '
          f'vol_m3={[round(s["volume_cuft"]/CUFT_PER_M3,3) if s["volume_cuft"] is not None else None for s in res["scenarios"]]}')
