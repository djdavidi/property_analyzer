# Repro: engine.routing downgrades extent_sufficient when the DEM does not cover the
# parcel+buffer, but research/model_integration read the raw terrain setting, so the
# finance gate (run['extent_sufficient'] is True) still passes. Boundary/nodata
# basins also do not affect the research flag.
from shapely.geometry import box, mapping
from drainage_core.engine import new_case, analyze
crs='EPSG:32618'; x,y=500000,4400000; N=20
c=new_case('t',crs=crs); c['id']='t7'
c['parcel']=mapping(box(x,y-30,x+30,y))      # parcel extends 10 m beyond the 20x20 DEM
el=[[10-0.02*r-0.03*cc for cc in range(N)] for r in range(N)]
for r in range(15,20):
    for cc in range(5): el[r][cc]=None          # NoData hole too
c['terrain']={'crs':crs,'origin':[x,y],'cell_size':1,'horizontal_unit':'m','vertical_unit':'m','elevations':el,
  'settings':{'extent_sufficient':True,'required_buffer_native_units':45}}
F=lambda i,g,**p:{'type':'Feature','id':i,'geometry':mapping(g),'properties':p}
c['features']['features']=[F('pave',box(x,y-30,x+30,y),layer='surface',**{'class':'pavement'}),
                           F('rg',box(x+12,y-14,x+16,y-10),layer='gsi',gsi_system_id='G1')]
c['research_drainage']={'sensitivity':False}
r=analyze(c)
print('conservative: status',r['drainage']['status'],'extent_sufficient',r['drainage']['extent_sufficient'],
      '| warnings has partial extent:',any('Partial routing extent' in w for w in r['drainage']['warnings']))
p=r['research_drainage']['primary']
print('research primary: extent_sufficient',p['extent_sufficient'],'nodata',p['nodata_cells'],'boundary_basins',p['boundary_basins'])
print('modeled_integration runs extent flags:',[run['extent_sufficient'] for run in r['modeled_integration']['runs']])
