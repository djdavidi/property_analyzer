import sys; sys.path.insert(0,'tests')
from drainage_core.freshness import age_policy
from drainage_core.management_estimates import estimate_system
from tests.test_management_geometry_unit import fixture
from stormwater.management_estimates import estimate_management
case,gis=fixture('G1'); case['imagery_age_policy']=age_policy('2025-06-01')
case['features']['features'][-1]['properties']['year_installed']=2026
case['baseline']={'ga_sqft':10000,'ia_sqft':10000,'bill_date':'2026-11-16','actual_bill_verified':False}
case['assessment']={'records':[]}
e=estimate_system(case,gis,'G1')
print('physical:',e['status'],e['installation_issues'])
r=estimate_management(case,gis,e,'2026-11-16')
print('policy:',r['status'],r['eligibility']['status'],[x['annual_savings'] for x in r['sensitivity_examples']])
