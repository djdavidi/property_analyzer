# Adding a curb cut that feeds the GSI (default connection_evidence 'unknown'), or an
# overflow inlet inside the GSI, makes the GSI's own sink 'unresolved' and deletes the
# whole GSI catchment: more entrance evidence -> zero modeled catchment.
from shapely.geometry import box, mapping, Point, LineString
from drainage_core.engine import new_case
from drainage_core.geometry import measure
from drainage_core.research import feature_inputs, run_model
crs='EPSG:32618'; x,y=500000,4400000; N=24
F=lambda i,g,**p:{'type':'Feature','id':i,'geometry':mapping(g),'properties':p}
def run(extra):
    c=new_case('t',crs=crs); c['id']='t11'; c['parcel']=mapping(box(x,y-N,x+N,y))
    c['terrain']={'crs':crs,'origin':[x,y],'cell_size':1,'horizontal_unit':'m','vertical_unit':'m',
      'elevations':[[10-0.02*r-0.03*cc for cc in range(N)] for r in range(N)],'settings':{}}
    c['features']['features']=[F('pave',box(x,y-N,x+N,y),layer='surface',**{'class':'pavement'}),
                               F('rg',box(x+12,y-16,x+16,y-12),layer='gsi',gsi_system_id='G1')]+extra
    m=measure(c); fs,_=feature_inputs(c); o=run_model(c,m,fs)
    reasons={b['reason'] for b in o['micro_basins'] if b['candidate_gsi_ids'] or 'connection' in b['reason']}
    return round(o['known_ia_union_sqft']), reasons
print('GSI alone:', run([]))
print('+ curb cut into GSI (gsi_id=G1, evidence default):', run([F('cc',LineString([(x+12,y-12.2),(x+16,y-12.2)]),layer='curb_cut',gsi_id='G1')]))
print('+ overflow inlet inside GSI (no pipe record):', run([F('ovf',Point(x+15.5,y-15.5),layer='inlet')]))
