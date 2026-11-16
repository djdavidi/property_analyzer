import sys; sys.path.insert(0,'tests')
from shapely.geometry import box, mapping
from drainage_core.engine import analyze
from test_assessment_policy import fixture
from stormwater.jurisdictions.philadelphia import apply
c,g=fixture(); imp=mapping(box(0,0,24.384,30.48)); lawn=mapping(box(24.384,0,30.48,30.48))
c['baseline'].update(ia_sqft=8000,existing_ia_credit_sqft=800,existing_ga_credit_sqft=800,existing_credits_spatially_reconciled=True)
c['features']['features']=[{'id':'roof','geometry':imp,'properties':{'layer':'surface','class':'roof'}},
                           {'id':'lawn','geometry':lawn,'properties':{'layer':'surface','class':'pervious'}}]
c['benefits']=[{'id':'open','category':'open_space','geometry':lawn,'area_sqft':2000,'basis':'documented','existing_overlap_reconciled':True,
   'evidence':{'physical_area_confirmed':True,'parcel_allocation_confirmed':True,'account_current':True,'cover_confirmed':True,
               'soil_confirmed':True,'runoff_characteristics_confirmed':True,'non_impervious_confirmed':True,'curve_number':55}}]
g=analyze(c)
from unittest.mock import patch
import datetime
with patch('stormwater.renewals.today',lambda: datetime.date(2026,11,15)):
    out=apply(c,g)
b=out['billing']['documented_credit_only']; a=out['assessment']['economics']['documented']
print('legacy billing documented_credit_only:',b['status'],b.get('monthly_savings'))
print('assessment economics documented    :',a['status'],a.get('gross_monthly_reduction'),a.get('reasons'))
