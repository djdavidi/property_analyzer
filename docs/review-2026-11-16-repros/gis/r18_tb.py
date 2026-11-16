import traceback
from shapely.geometry import box, mapping
from drainage_core.engine import new_case, analyze
crs='EPSG:2272'; x,y=2690000,240000
F=lambda i,g,**p:{'type':'Feature','id':i,'geometry':mapping(g),'properties':p}
c=new_case('t',crs=crs); c['id']='t18'; c['parcel']=mapping(box(x,y-100,x+30,y))
c['features']['features']=[F('r',box(x,y-60,x+20,y),layer='surface',**{'class':'roof'}),F('n',box(x+30,y-60,x+50,y),layer='surface',**{'class':'roof'}),
   F('s',box(x+20,y-60,x+30,y),layer='surface',**{'class':'pervious'})]
try: analyze(c)
except Exception as e: print(''.join(traceback.format_exc().splitlines(True)[-14:-5]))
