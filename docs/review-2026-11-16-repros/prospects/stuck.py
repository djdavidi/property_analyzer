import tempfile, warnings
warnings.filterwarnings('ignore')
from unittest.mock import patch
from stormwater.cases import CaseStore
from stormwater.fixtures import synthetic_case
from drainage_core import quality
with tempfile.TemporaryDirectory() as d:
    store=CaseStore(d);case=synthetic_case();r0=store.save(case)
    print('initial:',r0['quality_review']['status'],'reuse' if r0.get('physical_reuse') else 'fresh GIS')
    with patch.object(quality,'processing_fingerprint',return_value='f'*64):   # simulate a GIS code/library update
        for route in ('analyze','save','analyze'):
            r=getattr(store,route)(case)
            print(f'after code change, {route}:',r['quality_review']['status'],'|',r.get('physical_reuse',{}).get('status','fresh GIS'),'| billing:',r['billing'].get('status'))
