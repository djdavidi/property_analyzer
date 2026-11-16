# Run from repo root: PYTHONPATH=tests:. .venv/bin/python docs/review-2026-11-16-repros/second/account_and_rejection.py
import sys, warnings; warnings.filterwarnings('ignore'); sys.path.insert(0,'tests')
from shapely.geometry import box
from test_modeled_assessment_unit import fixture, candidate, record, fake_research, frozen_gis, assess, rec_info

def money(rows): return [(r.get('receiver_id', r.get('name')), r.get('bound', ''), r['status'], r.get('gross_annual_reduction')) for r in rows]

# Finding 1: known failed account standing
c = fixture(); c['baseline']['account_current'] = False
c['features']['features'] = [candidate('canopy', box(0, 0, 30.48, 30.48))]
r = assess(c)
print('#1 canopy, baseline.account_current=False:', money(r['modeled_integration']['canopy_scenarios']))
c = fixture(); c['baseline']['account_current'] = False
r = assess(c, frozen_gis(c, fake_research(c)))
print('#1 generic GSI, baseline.account_current=False:', money(r['modeled_integration']['catchment_scenarios'])[:3])
# record-level explicit false on the only installed-system record does not reach the generic path either
c = fixture(); c['assessment']['records'] = [record(category='green_roof', facts={'account_current': False})]
r = assess(c, frozen_gis(c, fake_research(c)))
print('   record-level account_current=False, record status:', rec_info(r)['status'], rec_info(r).get('known_failed_prerequisites'))

# Finding 2: rejected record re-priced as unassigned receiver
c = fixture(); c['assessment']['records'] = [record(gsi_id='G1', decision='rejected', facts={'existing_installation': False})]
r = assess(c, frozen_gis(c, fake_research(c)))
print('#2 rejected record context:', rec_info(r)['status'])
print('#2 generic scenarios for same receiver:', money(r['modeled_integration']['catchment_scenarios']))
# control: same record as candidate is not recounted
c = fixture(); c['assessment']['records'] = [record(gsi_id='G1')]
r = assess(c, frozen_gis(c, fake_research(c)))
print('   control (candidate record linked to G1):', money(r['modeled_integration']['catchment_scenarios']))
