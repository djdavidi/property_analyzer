import sys; sys.path.insert(0,'tests')
from copy import deepcopy
from tests.test_runoff_capacity_policy_unit import setup
from tests.test_management_estimates import rectangle, add_existing
from stormwater.runoff_capacity import estimate_capacity_management
case,gis,e,cap=setup(); add_existing(case,gis)
nom=deepcopy(e['runs'][0]); nom['name']='nominal'
sen=deepcopy(e['runs'][0]); sen['name']='sens'
sen['area_scenarios'][1].update(geometry=rectangle(2000,start=3.048))
e['runs']=[sen,nom]
r=estimate_capacity_management(case,gis,e,cap,'2026-11-16')
print('capacity adapter:',r['status'],'current run',r['current_estimate']['run'],r['current_estimate']['status'],
      [(x['name'],[(s['name'],s['status'],s['annual_savings']) for s in x['scenarios'][:1]]) for x in r['runs']])
