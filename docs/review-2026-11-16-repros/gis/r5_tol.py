# Repro: with flat_tolerance>0 the flat BFS joins a cell that already has a D8 exit
# with a lower "flat" cell, then points the lower cell back uphill -> 2-cycle.
from drainage_core.drainage import route_grid
g={'elevations':[[5.0,5.9,4.5]],'cell_size':1,'horizontal_unit':'m','vertical_unit':'m',
   'settings':{'flat_tolerance':1.0}}
o=route_grid(g)
print('next_cells:',o['next_cells'][0]); print('labels:',o['labels'][0])
# Smaller, realistic tolerance (5 cm) on a 1 m grid
g={'elevations':[[10.00,10.04,9.98,10.2],[10.3,10.3,10.3,10.3]],'cell_size':1,'horizontal_unit':'m','vertical_unit':'m',
   'settings':{'flat_tolerance':0.05}}
o=route_grid(g); print('5cm tol labels:',o['labels'][0],'next:',o['next_cells'][0])
# Research path on the same kind of terrain crashes the whole engine.analyze
from shapely.geometry import box,mapping
from drainage_core.engine import new_case, analyze
crs='EPSG:32618';x,y=500000,4400000
c=new_case('t',crs=crs);c['id']='t5';c['parcel']=mapping(box(x,y-2,x+4,y))
c['terrain']={'crs':crs,'origin':[x,y],'cell_size':1,'horizontal_unit':'m','vertical_unit':'m',
  'elevations':[[10.00,10.04,9.98,10.2],[10.3,10.3,10.3,10.3]],'settings':{'flat_tolerance':0.05}}
try: analyze(c); print('analyze ok')
except Exception as e: print('analyze ->',type(e).__name__,e)
