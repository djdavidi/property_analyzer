import sys; sys.path.insert(0,'tests')
from copy import deepcopy
from shapely.geometry import box, mapping
from drainage_core.engine import analyze
from test_assessment_policy import fixture, record, run
def base():
    c,g=fixture(); imp=mapping(box(0,0,24.384,30.48)); lawn=mapping(box(24.384,0,30.48,30.48))
    c['baseline']['ia_sqft']=8000
    c['features']['features']=[{'id':'roof','geometry':imp,'properties':{'layer':'surface','class':'roof'}},
                               {'id':'lawn','geometry':lawn,'properties':{'layer':'surface','class':'pervious'}}]
    return c,analyze(c),lawn
def show(tag,c,g):
    s=run(c,g)['economics']['documented']
    print(f"{tag:45s} status={s['status']:10s} GAcr={s['ledger']['new_ga_credit_sqft'] if s.get('ledger') else None} IAcr={s['ledger']['new_ia_credit_sqft'] if s.get('ledger') else None} bill={s['bill']['monthly_total'] if s.get('bill') else None} reduction={s['gross_monthly_reduction']} reasons={s.get('reasons')}")
# A: NPDES alone
c,g,lawn=base(); c['assessment']['records']=[record('industrial_npdes')]; show('A NPDES alone',c,g)
# B: NPDES + qualifying 100 sqft management on roof
c,g,lawn=base(); m=record(); m['geometry']=m['footprint_geometry']=mapping(box(0,0,0.3048,30.48)); m['managed_area_sqft']=100
c['assessment']['records']=[m,record('industrial_npdes','permit')]; show('B NPDES + 100 sqft managed SMP',c,g)
# C: NPDES + open space CN74 over the lawn (documented legacy benefit)
for cn in (74,70):
    c,g,lawn=base(); c['assessment']['records']=[record('industrial_npdes')]
    c['benefits']=[{'id':'open','category':'open_space','geometry':lawn,'area_sqft':2000,'basis':'documented',
       'evidence':{'physical_area_confirmed':True,'parcel_allocation_confirmed':True,'account_current':True,'cover_confirmed':True,
                   'soil_confirmed':True,'runoff_characteristics_confirmed':True,'non_impervious_confirmed':True,'curve_number':cn}}]
    show(f'C NPDES + open space CN{cn}',c,g)
