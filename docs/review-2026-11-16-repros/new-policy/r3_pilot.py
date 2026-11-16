"""Repros for management_pilot / runoff_capacity / warnings (synthetic only)."""
import sys
from copy import deepcopy
from datetime import date
from unittest.mock import patch
sys.path.insert(0, 'tests')
from tests.test_management_pilot_unit import pilot_fixture
from tests.test_management_estimates import fixture
from stormwater.management_pilot import estimate_property
from stormwater.management_estimates import estimate_management
from stormwater.portfolio_report import canopy_compatibility
from test_modeled_assessment_unit import fixture as mfixture

print('=== R7: garden-bed IA retained in non-01073 headline (same defect that superseded 01073) ===')
case, gis = pilot_fixture()
res = estimate_property(case, gis, ['62571'])
s = res['systems'][0]
run = s['physical']['runs'][0]
ce = s['policy']['current_estimate']
print(' 62571 within_system_footprint_sqft', round(run['within_system_footprint_sqft'], 2),
      '| policy basis', s['policy']['basis'], '| candidate', round(ce['candidate_ia_sqft'], 2), '| annual', ce['annual_savings'],
      '| superseded?', 'full_area_management_scenario' in s)
case, gis = pilot_fixture()
for f in case['features']['features']:
    if f['properties'].get('kind') == 'system_footprint':
        f['properties']['gsi_system_id'] = '01073'
gis['research_drainage']['primary']['catchments'][0]['gsi_id'] = '01073'
cap = {'system_id': '01073', 'status': 'estimated', 'surface_storage_volume_cuft': 1e6, 'source_lineage': {},
       'scenarios': [{'name': 'boundary_cell_minimum', 'status': 'estimated', 'volume_cuft': 1e6}]}
with patch('drainage_core.runoff_capacity.estimate_capacity', return_value=cap):
    s = estimate_property(case, gis, ['01073'])['systems'][0]
best = s['managed_runoff']['current_estimate']
print(' 01073 same geometry, unlimited storage: garden_ia_excluded', round(best['garden_ia_excluded_sqft'], 2),
      '| storage-limited annual', best['annual_savings'],
      '| superseded full-area annual', s['full_area_management_scenario']['current_estimate']['annual_savings'])

print('\n=== R8: as_of not normalized in pilot canopy path ===')
case, gis = pilot_fixture()
try:
    estimate_property(case, gis, ['62571'], as_of=date(2026, 11, 16))
    print(' no error')
except Exception as exc:
    print(' estimate_property(as_of=date) ->', type(exc).__name__, exc)
c, g, e = fixture()
print(' estimate_management(as_of=date) ->', estimate_management(c, g, e, date(2026, 11, 16))['status'])

print('\n=== R9: computed-vs-published baseline warning dropped from management output ===')
c, g, e = fixture()
c['baseline']['published_monthly_total'] = 10.00
r = estimate_management(c, g, e, '2026-11-16')
print(' baseline published_difference', r['baseline']['published_difference'], '| warnings', r['warnings'],
      '| status', r['status'], r['current_estimate']['annual_savings'])

print('\n=== R4b: canopy cap stacks on observed paved ground already under an existing award ===')
b = mfixture()['baseline']
b.update(ia_sqft=10000, existing_ga_credit_sqft=1600, existing_ia_credit_sqft=1600, existing_credits_spatially_reconciled=True)
v = canopy_compatibility(b, 6000, 9000, known_overlap=2000)
print(' known observed canopy-ground IA 2000 (may be the 2000 sqft management allocation): area', v['area_sqft'],
      'status', v['status'], 'annual', v['annual_change'])
