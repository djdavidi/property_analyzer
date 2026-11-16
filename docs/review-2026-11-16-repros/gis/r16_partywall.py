# Rowhouse: the neighbour's roof footprint shares the parcel line (party wall).
# polygon.intersection(parcel) yields a LineString; measure() then unions mixed
# dimensions and calls overlay ops on a GeometryCollection.
from shapely.geometry import box, mapping
from drainage_core.engine import new_case, analyze
from drainage_core.geometry import measure
crs='EPSG:2272'; x,y=2690000,240000   # PA South ftUS
F=lambda i,g,**p:{'type':'Feature','id':i,'geometry':mapping(g),'properties':p}
parcel=box(x,y-100,x+16,y)            # 16 ft x 100 ft rowhouse lot
own=box(x,y-60,x+16,y); nb_roof=box(x+16,y-60,x+32,y)   # neighbour shares x+16 line
nb_yard_tree=box(x+16,y-80,x+30,y-60)
cases={'own roof + pavement + neighbour roof (shared edge)':[F('r',own,layer='surface',**{'class':'roof'}),F('p',box(x,y-100,x+16,y-60),layer='surface',**{'class':'pavement'}),F('n',nb_roof,layer='surface',**{'class':'roof'})],
       'own roof + yard pervious + neighbour roof':[F('r',own,layer='surface',**{'class':'roof'}),F('g',box(x,y-100,x+16,y-60),layer='surface',**{'class':'pervious'}),F('n',nb_roof,layer='surface',**{'class':'roof'})],
       'own roof + neighbour tree canopy touching line':[F('r',own,layer='surface',**{'class':'roof'}),F('t',nb_yard_tree,layer='canopy')],
       'no neighbour features':[F('r',own,layer='surface',**{'class':'roof'}),F('p',box(x,y-100,x+16,y-60),layer='surface',**{'class':'pavement'})]}
for name,feats in cases.items():
    c=new_case('t',crs=crs); c['id']='t16'; c['parcel']=mapping(parcel); c['features']['features']=feats
    try: m=measure(c); print(f'{name}: ok ia={m["ia_sqft"]:.0f} sqft')
    except Exception as e: print(f'{name}: {type(e).__name__}: {str(e)[:80]}')
