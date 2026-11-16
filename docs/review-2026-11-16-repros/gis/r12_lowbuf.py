# low_offsets sensitivity uses a 0.305 m inlet/wall buffer with centre rasterization;
# on a 1 m grid most inlet points then rasterize to zero cells (vanish from the run).
import numpy as np
from shapely.geometry import Point, mapping
from drainage_core.research import _mask
for cell in (1.0, 0.9144, 2.0):
    grid={'cell_size':cell,'horizontal_unit':'m','origin':[0,20],'elevations':[[0]*20]*20}
    rng=np.random.default_rng(1); n=4000
    miss=sum(not _mask(mapping(Point(*rng.uniform(5,15,2))),grid,.305).any() for _ in range(n))
    print(f'grid {cell} m: inlets with zero cells in low_offsets run: {miss/n:.0%}')
