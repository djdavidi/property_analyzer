import sys; sys.path.insert(0,'tests')
from test_modeled_assessment_unit import fixture, frozen_gis, assess, candidate
from shapely.geometry import box
from stormwater.portfolio_report import parcel_view
from stormwater.billing import calculate_scenarios
c=fixture(); c['features']['features']=[candidate('canopy',box(0,0,30.48,30.48))]
c['baseline'].pop('bill_date',None)
c['assessment']['baseline_refresh']={'status':'pending_review'}
g=frozen_gis(c); a=assess(c,g)
r={**g,'assessment':a,'billing':{'baseline':calculate_scenarios(c['baseline'])['baseline']}}
m=parcel_view(c,r,{'parcel_id':'1','address':'Invented','systems':[]})
cap=next(x for x in m['categories'] if x['category']=='canopy')['scenarios'][0]
print('baseline_refresh pending, no bill_date -> canopy cap',cap['status'],cap['annual_change'],'| assessment economics modeled:',a['economics']['modeled']['status'])
