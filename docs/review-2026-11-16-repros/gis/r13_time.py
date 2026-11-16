import time, numpy as np
from shapely.geometry import box, mapping, Point
from drainage_core.engine import new_case, routing
from drainage_core.geometry import measure
crs='EPSG:32618'; x,y=500000,4400000; N=400
rng=np.random.default_rng(0)
c=new_case('t',crs=crs); c['id']='t13'; c['parcel']=mapping(Point(x+200,y-200).buffer(60,64))
c['terrain']={'crs':crs,'origin':[x,y],'cell_size':1,'horizontal_unit':'m','vertical_unit':'m',
  'elevations':(10-0.01*np.add.outer(np.arange(N),np.arange(N))+rng.normal(0,.05,(N,N))).tolist(),'settings':{}}
F=lambda i,g,**p:{'type':'Feature','id':i,'geometry':mapping(g),'properties':p}
c['features']['features']=[F('h%d'%i,box(x+20+i*30,y-200,x+40+i*30,y-180),layer='surface',**{'class':'roof'}) for i in range(10)]
m=measure(c)
import cProfile,pstats
t=time.perf_counter(); out,_=routing(c,m); total=time.perf_counter()-t
print('routing total s',round(total,2),'catchments',len(out['catchments']))
from drainage_core.drainage import route_grid
