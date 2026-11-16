# Conservative engine: roof cells are centre-rasterized, but catchment IA is an exact
# polygon intersection, so roof-polygon slivers inside ground cells are credited to the
# ground terminal (here a documented inlet) although roof routing is 'unresolved'.
from shapely.geometry import box, mapping, Point
from drainage_core.engine import new_case, analyze
crs='EPSG:32618'; x,y=500000,4400000; N=20
c=new_case('t',crs=crs); c['id']='t10'; c['parcel']=mapping(box(x,y-N,x+N,y))
c['terrain']={'crs':crs,'origin':[x,y],'cell_size':1,'horizontal_unit':'m','vertical_unit':'m',
  'elevations':[[10-0.02*r-0.03*cc for cc in range(N)] for r in range(N)],'settings':{}}
F=lambda i,g,**p:{'type':'Feature','id':i,'geometry':mapping(g),'properties':p}
house=box(x+2.6,y-12.4,x+12.4,y-2.6)      # 9.8 m x 9.8 m roof, edges 0.4 m into ground cells
c['features']['features']=[F('house',house,layer='surface',**{'class':'roof'}),
   F('lawn',box(x,y-N,x+N,y).difference(house),layer='surface',**{'class':'pervious'}),
   F('in1',Point(x+19.5,y-19.5),layer='inlet')]
c['research_drainage']={'enabled':False}
r=analyze(c)
for k in r['drainage']['catchments']:
    if k['on_parcel_physical_ia_sqft']>0.01: print(k['outlet'],'physical IA m2 =',round(k['on_parcel_physical_ia_m2'],2))
print('true roof m2',round(house.area,2),'| only IA on parcel is roof; inlet has no documented roof connection')
