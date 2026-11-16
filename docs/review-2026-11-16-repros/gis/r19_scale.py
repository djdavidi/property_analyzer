# The 'm vs us-ft vertical unit' diagnostic cannot change conservative D8: argmax of
# (dz*k)/d is invariant to k>0 and flat_tolerance=0. Random DEMs, 200 trials.
import numpy as np
from drainage_core.drainage import route_grid
rng=np.random.default_rng(3); diff=0
for t in range(200):
    z=np.round(rng.normal(10,1,(25,25)),2).tolist()   # rounded -> many exact ties/flats
    a=route_grid({'elevations':z,'cell_size':1,'horizontal_unit':'m','vertical_unit':'m'})
    b=route_grid({'elevations':z,'cell_size':1,'horizontal_unit':'m','vertical_unit':'us-ft'})
    diff+=a['next_cells']!=b['next_cells'] or a['labels']!=b['labels']
print('trials with any changed direction/label:',diff,'/ 200')
