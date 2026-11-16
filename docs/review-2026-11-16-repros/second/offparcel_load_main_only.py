# Requires origin/main (a11f4db) code: run from a checkout of main with PYTHONPATH=.
import warnings; warnings.filterwarnings('ignore')
from tests.test_runoff_capacity_policy_unit import setup, run
case, gis, e, cap = setup()
base = run(case, gis, e, cap)['current_estimate']
print('#6 baseline: off_parcel', e['runs'][0].get('off_parcel_area_sqft'), '-> annual', base['annual_savings'])
case, gis, e, cap = setup(); e['runs'][0]['off_parcel_area_sqft'] = 1_000_000
r = run(case, gis, e, cap)['current_estimate']
print('#6 with 1,000,000 sq ft reported off-parcel contribution -> annual', r['annual_savings'], '| other_ground', r['other_ground_area_sqft'])
