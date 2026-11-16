"""Diagonal footprint edge through grid vertices: zero-length vertex contacts are not rim,
so a low cell touching the perimeter only at a point is ignored; a 1e-6 m nudge flips it."""
import sys, os; sys.path.insert(0, os.getcwd())
from copy import deepcopy
import numpy as np
from shapely.geometry import Polygon, box, mapping
from shapely.affinity import translate
from tests.test_runoff_capacity_unit import fixture, CUFT_PER_M3
from drainage_core.runoff_capacity import estimate_capacity

case, gis = fixture()
n = 12
case['parcel'] = mapping(box(0, 0, n, n))
diamond = Polygon([(6, 2), (10, 6), (6, 10), (2, 6)])
el = np.zeros((n, n))
# cells with positive-length exterior intersection = 10 (a one-cell berm); all else 0
for r in range(n):
    for c in range(n):
        cell = box(c, n-(r+1), c+1, n-r)
        if diamond.exterior.intersection(cell).length > 1e-10 and cell.intersection(diamond).area > 1e-12:
            el[r, c] = 10.
case['terrain'].update(origin=[0, n], elevations=el.tolist())
for dx in (0., 1e-6):
    k = deepcopy(case); k['features']['features'][0]['geometry'] = mapping(translate(diamond, dx, 0))
    res = estimate_capacity(k, gis, '01073')
    print(f'dx={dx:g}', [(s['name'], s['component_spill_elevations_m'][0] if s['status']=='estimated' else None,
          round(s['volume_cuft']/CUFT_PER_M3, 2) if s['volume_cuft'] is not None else None) for s in res['scenarios']])
