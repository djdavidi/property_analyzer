import sys; sys.path.insert(0,'tests')
from shapely.geometry import box, mapping
from drainage_core.engine import analyze
from test_assessment_policy import fixture, record, run
def base():
    c,g=fixture(); c['parcel']=mapping(box(0,0,30.48,304.8))  # 100,000 sq ft
    imp=mapping(box(0,0,30.48,60.96)); lawn=mapping(box(0,60.96,30.48,304.8))  # 20,000 IA, 80,000 lawn
    c['baseline'].update(ga_sqft=100000,ia_sqft=20000)
    c['features']['features']=[{'id':'roof','geometry':imp,'properties':{'layer':'surface','class':'roof'}},
                               {'id':'lawn','geometry':lawn,'properties':{'layer':'surface','class':'pervious'}}]
    return c,analyze(c)
def show(tag,c,g):
    s=run(c,g)['economics']['documented']; b=s.get('bill') or {}
    print(f"{tag:34s} {s['status']} GAcr={s['ledger']['new_ga_credit_sqft'] if s.get('ledger') else None} IAcr={s['ledger']['new_ia_credit_sqft'] if s.get('ledger') else None} billedGA={b.get('billed_ga_sqft')} bill={b.get('monthly_total')} reduction={s['gross_monthly_reduction']} {s.get('reasons','')}")
c,g=base(); print('baseline', run(c,g)['economics']['baseline']['monthly_total'])
c['assessment']['records']=[record('industrial_npdes')]; show('A NPDES alone',c,g)
c,g=base(); m=record(); m['geometry']=m['footprint_geometry']=mapping(box(0,0,0.3048,30.48)); m['managed_area_sqft']=100
c['assessment']['records']=[m,record('industrial_npdes','permit')]; show('B NPDES + 100 sqft managed SMP',c,g)
c,g=base(); c['assessment']['records']=[m]; show('B0 100 sqft managed SMP alone',c,g)
