import sys; sys.path.insert(0,'tests')
from tests.test_management_estimates import fixture, rectangle
from stormwater.management_estimates import estimate_management
c,g,e=fixture()
# Unrelated public project point whose feature id (OBJECTID) happens to equal the SMP id digits.
c['features']['features'].append({'type':'Feature','id':62571,'geometry':{'type':'Point','coordinates':[500,500]},
    'properties':{'kind':'project_point','gsi_system_id':'99999','status':'In Design'}})
r=estimate_management(c,g,e,'2026-11-16')
print(r['status'], r['eligibility'])
