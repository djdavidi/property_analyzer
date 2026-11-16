# Repro: validate_case only looks up references in the *conservative* terminal-region
# dict (keys like 'inlet:..', 'edge:r:c'); research GSI catchments, which are what the
# policy layer consumes, can never be measured against an independent reference.
from shapely.geometry import box, mapping
from drainage_core.engine import new_case, analyze
crs='EPSG:32618'; x,y=500000,4400000; N=20
c=new_case('t',crs=crs); c['id']='t4'
c['parcel']=mapping(box(x,y-N,x+N,y))
c['terrain']={'crs':crs,'origin':[x,y],'cell_size':1,'horizontal_unit':'m','vertical_unit':'m',
  'elevations':[[10-0.02*r-0.03*cc for cc in range(N)] for r in range(N)],'settings':{'extent_sufficient':False}}
F=lambda i,g,**p:{'type':'Feature','id':i,'geometry':mapping(g),'properties':p}
c['features']['features']=[F('pave',box(x,y-N,x+N,y),layer='surface',**{'class':'pavement'}),
                           F('rg',box(x+12,y-14,x+16,y-10),layer='gsi',gsi_system_id='G1')]
c['research_drainage']={'sensitivity':False}
ref=box(x+8,y-16,x+16,y-6)
c['references']=[{'id':'ref1','kind':'drainage','outlet':o,'geometry':mapping(ref),'crs':crs,'independent':True,
   'source_url':'https://example.org/survey','stable_site_verified':True} for o in ('G1','gsi:G1')]
c['references'][1]['id']='ref2'
r=analyze(c)
print('research GSI catchments:',[(k['gsi_id'],round(k['on_parcel_area_sqft'])) for k in r['research_drainage']['primary']['catchments']])
print('conservative outlet keys (sample):',sorted({k['outlet'].split(':')[0] for k in r['drainage']['catchments']}))
print('drainage validation:',r['validation']['drainage']['status'],r['validation']['drainage']['blockers'])
