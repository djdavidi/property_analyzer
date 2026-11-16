import shapely
from shapely.geometry import box, mapping, Point
from drainage_core.engine import new_case
from drainage_core.geometry import measure
print('shapely',shapely.__version__, 'geos', shapely.geos_version)
crs='EPSG:32618'; x,y=500000,4400000
F=lambda i,g,**p:{'type':'Feature','id':i,'geometry':mapping(g),'properties':p}
for name,parcel,feats in [
  ('box parcel, one roof off-parcel, no pervious', box(x,y-10,x+10,y), [F('a',box(x+2,y-8,x+5,y-5),layer='surface',**{'class':'roof'}),F('b',box(x+50,y-8,x+55,y-5),layer='surface',**{'class':'roof'})]),
  ('box parcel, only roof on-parcel', box(x,y-10,x+10,y), [F('a',box(x+2,y-8,x+5,y-5),layer='surface',**{'class':'roof'})]),
  ('circle parcel, roof partly on', Point(x,y).buffer(10,64), [F('a',box(x-2,y-2,x+15,y+3),layer='surface',**{'class':'roof'})]),
  ('circle parcel, two roofs one off', Point(x,y).buffer(10,64), [F('a',box(x-2,y-2,x+15,y+3),layer='surface',**{'class':'roof'}),F('b',box(x+50,y,x+60,y+5),layer='surface',**{'class':'roof'})]),
]:
    c=new_case('t',crs=crs); c['id']='t14'; c['parcel']=mapping(parcel); c['features']['features']=feats
    try: m=measure(c); print(name,'-> ok ia_m2',round(m['ia_m2'],2))
    except Exception as e: print(name,'->',type(e).__name__,str(e)[:90])
