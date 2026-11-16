from shapely.geometry import box, mapping
from drainage_core.engine import new_case
from drainage_core.geometry import measure
crs='EPSG:2272'; x,y=2690000,240000
F=lambda i,g,**p:{'type':'Feature','id':i,'geometry':mapping(g),'properties':p}
parcel=box(x,y-100,x+30,y)
own=box(x,y-60,x+20,y)                     # 10 ft side yard on the east
nb=box(x+30,y-60,x+50,y)                   # neighbour roof touches parcel line x+30
side_yard=box(x+20,y-60,x+30,y)
for name,feats in {
  'neighbour roof touches line; side yard pervious':[F('r',own,layer='surface',**{'class':'roof'}),F('n',nb,layer='surface',**{'class':'roof'}),F('s',side_yard,layer='surface',**{'class':'pervious'})],
  'neighbour roof touches line; side yard unmapped':[F('r',own,layer='surface',**{'class':'roof'}),F('n',nb,layer='surface',**{'class':'roof'})],
  'neighbour driveway touches line; own lawn':[F('r',own,layer='surface',**{'class':'roof'}),F('d',box(x+30,y-100,x+40,y),layer='surface',**{'class':'pavement'}),F('s',box(x,y-100,x+30,y-60),layer='surface',**{'class':'pervious'})],
  'neighbour roof touches only a corner':[F('r',own,layer='surface',**{'class':'roof'}),F('n',box(x+30,y,x+40,y+10),layer='surface',**{'class':'roof'})],
}.items():
    c=new_case('t',crs=crs); c['id']='t17'; c['parcel']=mapping(parcel); c['features']['features']=feats
    try: m=measure(c); print(f'{name}: ok ia={m["ia_sqft"]:.0f}')
    except Exception as e: print(f'{name}: {type(e).__name__}: {str(e)[:70]}')
