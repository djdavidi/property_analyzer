"""Repros for stormwater/management_estimates.py (synthetic fixtures only)."""
import sys
from copy import deepcopy
sys.path.insert(0, 'tests')
from tests.test_management_estimates import fixture, rectangle, add_existing
from stormwater.management_estimates import estimate_management
from stormwater.model_assessment import match

DAY = '2026-11-16'

print('=== R1: current_estimate run selection (production run names are nominal + sensitivity names) ===')
c, g, e = fixture()
add_existing(c, g)  # prior award occupies rectangle(1000) at x=0
nominal = deepcopy(e['runs'][0]); nominal['name'] = 'nominal'      # base overlaps prior award -> blocked
sens = deepcopy(e['runs'][0]); sens['name'] = 'sensitivity_dem_plus'
for s in sens['area_scenarios']:
    s['geometry'] = rectangle(s['area_sqft'], start=3.048)        # disjoint -> calculated
for s in nominal['area_scenarios']:
    if s['id'] != 'base':
        s['geometry'] = rectangle(s['area_sqft'], start=3.048)
e['runs'] = [nominal, sens]
r = estimate_management(c, g, e, DAY)
print('status', r['status'])
for run in r['runs']:
    print(' run', run['name'], [(s['id'], s['status'], s['annual_savings']) for s in run['scenarios']])
print('current_estimate run:', r['current_estimate']['run'], 'annual', r['current_estimate']['annual_savings'])
print('top-level reasons:', r['reasons'])

print('\n--- R1b: both calculated; order [sensitivity, nominal] ---')
c, g, e = fixture()
a = deepcopy(e['runs'][0]); a['name'] = 'high_terrain'
b = deepcopy(e['runs'][0]); b['name'] = 'nominal'
b['area_scenarios'][1].update(area_sqft=500, geometry=rectangle(500))
e['runs'] = [a, b]
r = estimate_management(c, g, e, DAY)
print('current_estimate run:', r['current_estimate']['run'], r['current_estimate']['annual_savings'])

print('\n=== R2: _known_failures misses record identities that model_assessment.match accepts ===')
for label, rec in [
    ('gsi_id rejected', {'id': 'r1', 'category': 'management', 'decision': 'rejected', 'gsi_id': '62571', 'facts': {}}),
    ('raw_record rejected', {'id': 'public-abc', 'category': 'management', 'decision': 'rejected', 'facts': {},
                             'source': {'url': 'u', 'record_id': '991'}, 'raw_record': {'gsi_system_id': '62571'}}),
    ('raw_record routing False', {'id': 'public-abc', 'category': 'management', 'decision': 'candidate',
                                  'facts': {'routing_confirmed': False, 'treatment_depth_inches': 0.5},
                                  'source': {'url': 'u', 'record_id': '991'}, 'raw_record': {'gsi_system_id': '62571'}}),
    ('facts.gsi_id treatment 0.5in', {'id': 'r3', 'category': 'management', 'decision': 'candidate',
                                      'facts': {'gsi_id': '62571', 'treatment_depth_inches': 0.5}}),
]:
    c, g, e = fixture()
    c['assessment']['records'] = [rec]
    r = estimate_management(c, g, e, DAY)
    run = {'catchments': [{'kind': 'gsi', 'receiver_id': '62571'}]}
    m = match(rec, c, {}, run)['status']
    print(f' {label:32s} match()={m:7s} eligibility={r["eligibility"]["status"]:12s} base={r["runs"][0]["scenarios"][1]["status"]} annual={r["runs"][0]["scenarios"][1]["annual_savings"]}')

print('\n=== R3: lineage binding bypassed when keys absent / differently named ===')
c, g, e = fixture()
print(' fixture lineage', e['source_lineage'], '-> status', estimate_management(c, g, e, DAY)['status'])
# Engineering computed for a different property, lineage stripped, GIS unhashed
c2 = deepcopy(c); c2['parcel'] = rectangle(12000); c2['baseline']['ga_sqft'] = 12000; c2['baseline']['ia_sqft'] = 12000
e2 = deepcopy(e); e2['source_lineage'] = {'case_sha256': None, 'gis_analysis_sha256': None}
r = estimate_management(c2, g, e2, DAY)
print(' foreign engineering w/ null lineage -> status', r['status'], 'annual', r['current_estimate']['annual_savings'])
