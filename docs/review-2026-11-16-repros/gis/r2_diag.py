# Repro: research walls/berms are raised (not 'closed'), so route_grid's
# no-corner-crossing rule does not apply; D8 crosses a diagonal wall between
# two raised cells that touch only at a corner.
from shapely.geometry import box, mapping, LineString, Polygon
from drainage_core.engine import new_case
from drainage_core.geometry import measure
from drainage_core.research import feature_inputs, run_model
import numpy as np
crs='EPSG:32618'; x,y=500000,4400000; N=20
def case(feats):
    c=new_case('t',crs=crs); c['id']='t2'
    c['parcel']=mapping(box(x,y-N,x+N,y))
    c['terrain']={'crs':crs,'origin':[x,y],'cell_size':1,'horizontal_unit':'m','vertical_unit':'m',
      'elevations':[[10+0.05*(cc-r)+0.001*r for cc in range(N)] for r in range(N)],
      'settings':{'extent_sufficient':False}}
    c['features']['features']=feats; return c
F=lambda i,g,**p:{'type':'Feature','id':i,'geometry':mapping(g),'properties':p}
line=LineString([(x,y),(x+N,y-N)])  # main diagonal, separates NE (high) from SW (low)
gsi=box(x+2,y-18,x+6,y-14)          # GSI in SW (downhill) triangle
for label,feat,kw in [('berm nominal',F('b',line,layer='berm'),{}),
                      ('wall low_offsets',F('w',line,layer='wall'),dict(offset_scale=.5,inlet_buffer_m=.305)),
                      ('wall nominal',F('w',line,layer='wall'),{})]:
    c=case([feat,F('g',gsi,layer='gsi',gsi_system_id='G1')])
    m=measure(c); fs,_=feature_inputs(c); out=run_model(c,m,fs,**kw)
    d=np.array(out['rasters']['direction_d8'],dtype=object)
    wallcells=next(f for f in out['feature_audit'] if f['id'] in('b','w'))['raster_cells']
    inv={1:(0,1),2:(1,1),4:(1,0),8:(1,-1),16:(0,-1),32:(-1,-1),64:(-1,0),128:(-1,1)}
    cross=0
    for r in range(N):
        for cc in range(N):
            v=d[r,cc]
            if v in inv:
                dr,dc=inv[v]; a=cc-r; b=(cc+dc)-(r+dr)
                if a>0 and b<0: cross+=1   # NE side straight to SW side, skipping the wall diagonal
    ne=sum(1 for r in range(N) for cc in range(N) if cc>r)
    gc=out['catchments'][0] if out['catchments'] else None
    ne_area=gc and shape_area_ne(gc) if False else None
    from shapely.geometry import shape
    tri_ne=Polygon([(x,y),(x+N,y),(x+N,y-N)])
    print(f"{label}: wall cells={wallcells}, D8 pointers jumping NE->SW across wall={cross}, "
          f"GSI catchment area from NE (walled-off) side={shape(gc['geometry']).intersection(tri_ne).area if gc else 0:.1f} m2")
