# Repro: an explicit canopy_observation status 'unavailable'/partial coverage is
# overridden by the mere presence of any canopy polygon; the 'upper' bound then
# only counts observed canopy and the 'no absence established' warning vanishes.
from shapely.geometry import box, mapping
from drainage_core.engine import new_case
from drainage_core.geometry import measure
crs='EPSG:32618'; x,y=500000,4400000
F=lambda i,g,**p:{'type':'Feature','id':i,'geometry':mapping(g),'properties':p}
for status,cov in [('unavailable',None),('partial',box(x,y-20,x+5,y))]:
    c=new_case('t',crs=crs); c['id']='t6'; c['parcel']=mapping(box(x,y-20,x+20,y))
    c['features']['features']=[F('pave',box(x,y-20,x+20,y),layer='surface',**{'class':'pavement'}),
                               F('tree',box(x,y-5,x+5,y),layer='canopy')]
    c['canopy_observation']={'status':status,**({'coverage_geometry':mapping(cov)} if cov else {})}
    m=measure(c)
    print(f"status={status}: canopy_status={m['canopy_status']} canopy_ground_ia={m['canopy_ground_ia_sqft']:.0f} "
          f"upper={m['canopy_ground_ia_upper_sqft']:.0f} ground_ia={m['ground_ia_sqft']:.0f} "
          f"canopy-unavailable warning={'Canopy coverage unavailable' in ' '.join(m['warnings'])}")
c['features']['features']=c['features']['features'][:1]; m=measure(c)
print(f"no canopy polygons: upper={m['canopy_ground_ia_upper_sqft']:.0f}")
