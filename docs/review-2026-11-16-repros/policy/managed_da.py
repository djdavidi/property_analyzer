import sys; sys.path.insert(0,'tests')
from shapely.geometry import box, mapping
from drainage_core.engine import analyze
from test_assessment_policy import fixture, record, run
c,g=fixture(); imp=mapping(box(0,0,24.384,30.48)); lawn=mapping(box(24.384,0,30.48,30.48))
c['baseline']['ia_sqft']=8000
c['features']['features']=[{'id':'roof','geometry':imp,'properties':{'layer':'surface','class':'roof'}},
                           {'id':'lawn','geometry':lawn,'properties':{'layer':'surface','class':'pervious'}}]
g=analyze(c)
r=record(start=21.336)   # 1,000 sqft drainage area: 3.048 m wide strip straddling roof edge (24.384)
r['geometry']=mapping(box(21.336,0,27.432,30.48)); r['managed_area_sqft']=2000  # 1,000 IA + 1,000 lawn
c['assessment']['records']=[r]
out=run(c,g); e=out['categories'][0]['records'][0]
print('SMP drainage area 1,000 IA + 1,000 lawn ->',e['status'],'failed=',e['failed'])
print('economics documented:',out['economics']['documented']['status'],out['economics']['documented'].get('gross_monthly_reduction'))
