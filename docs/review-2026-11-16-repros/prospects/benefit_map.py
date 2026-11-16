import tempfile, warnings
warnings.filterwarnings('ignore')
from copy import deepcopy
from shapely.geometry import box, mapping, shape
from stormwater.cases import CaseStore
from stormwater.fixtures import synthetic_case
with tempfile.TemporaryDirectory() as d:
    store=CaseStore(d);case=synthetic_case();store.save(case)
    edited=deepcopy(case);x,y=2690000,250000
    edited['benefits'][0]['geometry']=mapping(box(x+80,y-95,x+95,y-80))     # move canopy hypothesis
    r=store.analyze(edited)
    mf=next(f for f in r['map_features'] if f['id']=='canopy-hypothesis')
    print('reuse:',r.get('physical_reuse',{}).get('status'))
    print('map_features benefit bounds:',shape(mf['geometry']).bounds)
    print('current case benefit bounds:',shape(edited['benefits'][0]['geometry']).bounds)
    print('screened benefit area used by policy:',[s for s in r['screens'] if s['id']=='canopy-hypothesis'][0].get('area_sqft'))
