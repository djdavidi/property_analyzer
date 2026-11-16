# Repro: conservative routing rasterizes barriers all-touched (intersects cell box)
# and roofs by cell centre; overlapping designations make route_grid raise.
from copy import deepcopy
from shapely.geometry import box, mapping, Point, LineString
from drainage_core.engine import new_case, analyze
crs='EPSG:32618'; x,y=500000,4400000
def base():
    c=new_case('t',crs=crs); c['id']='t1'
    c['parcel']=mapping(box(x,y-20,x+20,y))
    c['terrain']={'crs':crs,'origin':[x,y],'cell_size':1,'horizontal_unit':'m','vertical_unit':'m',
        'elevations':[[10-0.05*r-0.01*cc for cc in range(20)] for r in range(20)],
        'settings':{'extent_sufficient':False,'required_buffer_native_units':0,'flat_tolerance':0,'max_flow_paths':5}}
    c['research_drainage']={'sensitivity':False}
    return c
F=lambda i,g,**p:{'type':'Feature','id':i,'geometry':mapping(g),'properties':p}
# Case A: garden wall abutting a house footprint (shares its edge at x+10)
c=base(); c['features']['features']=[F('house',box(x+2,y-10,x+10,y-2),layer='surface',**{'class':'roof'}),
   F('wall',LineString([(x+10,y-10),(x+10,y-18)]),layer='barrier')]
try: analyze(c); print('A ok')
except Exception as e: print('A wall abutting house ->',type(e).__name__,e)
# Case B: wall drawn 0.3 m inside the house edge (digitizing error/overhang)
c=base(); c['features']['features']=[F('house',box(x+2,y-10,x+10,y-2),layer='surface',**{'class':'roof'}),
   F('wall',LineString([(x+9.7,y-1),(x+9.7,y-18)]),layer='barrier')]
try: analyze(c); print('B ok')
except Exception as e: print('B ->',type(e).__name__,e)
# Case C: curb barrier along gutter line, inlet point 0.3 m from curb (same cell)
c=base(); c['features']['features']=[F('curb',LineString([(x,y-15),(x+20,y-15)]),layer='barrier'),
   F('inlet-1',Point(x+10.5,y-15.3),layer='inlet')]
try: analyze(c); print('C ok')
except Exception as e: print('C curb+inlet ->',type(e).__name__,e)
# Case D: inlet in features file but beyond terrain crop
c=base(); c['features']['features']=[F('inlet-far',Point(x+30,y-5),layer='inlet')]
try: analyze(c); print('D ok')
except Exception as e: print('D inlet outside DEM ->',type(e).__name__,e)
