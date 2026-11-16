# How often does a nominal curb cut (0.152 m buffer, centre rasterization) vanish on a 1 m grid?
import numpy as np
from shapely.geometry import LineString, mapping
from drainage_core.research import _mask
grid={'cell_size':1,'horizontal_unit':'m','origin':[0,10],'elevations':[[0]*10]*10}
rng=np.random.default_rng(0); miss=0; n=2000
for _ in range(n):
    x0,y0=rng.uniform(3,6,2); a=rng.uniform(0,np.pi); L=rng.uniform(1.5,3.0)  # 1.5-3 m curb cut
    g=LineString([(x0,y0),(x0+L*np.cos(a),y0+L*np.sin(a))])
    if not _mask(mapping(g),grid,.152).any(): miss+=1
print(f'curb cuts with zero nominal cells: {miss}/{n} = {miss/n:.0%}')
