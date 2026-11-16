import sys; sys.path.insert(0,'tests')
from tests.test_management_estimates import fixture, rectangle
from stormwater.management_estimates import estimate_management
c,g,e=fixture()
c['parcel']=rectangle(1000); g['measurement']['geometries']['physical_ia']=c['parcel']
c['features']['features'][0]['geometry']=rectangle(100)
c['baseline'].update(ga_sqft=1000, ia_sqft=1000, accounts=[{'allocation':.5,'discount_factor':1},{'allocation':.5,'discount_factor':1}])
e['runs'][0]['area_scenarios']=[{'id':'base','area_sqft':500,'geometry':rectangle(500),'basis':'x'}]
r=estimate_management(c,g,e,'2026-11-16')
b=r['current_estimate']
print('baseline monthly',r['baseline']['monthly_total'],r['baseline']['minimum_mode'],'-> with credit',b['bill']['monthly_total'],b['bill']['minimum_mode'],'monthly_savings',b['monthly_savings'],'status',r['status'])
