import tempfile, threading, json, time
from copy import deepcopy
from stormwater.cases import CaseStore, input_hash
from stormwater.fixtures import synthetic_case
from drainage_core.engine import input_hash
with tempfile.TemporaryDirectory() as d:
    store=CaseStore(d);base=synthetic_case()
    t=time.perf_counter();store.save(base);print('one save s',round(time.perf_counter()-t,2))
    errors=[]
    def go(i):
        c=deepcopy(base);c['name']=f'edit {i}'
        try:store.save(c)
        except Exception as e:errors.append(f'{type(e).__name__}: {e}')
    for trial in range(5):
        ts=[threading.Thread(target=go,args=(trial*10+i,)) for i in range(4)]
        [x.start() for x in ts];[x.join() for x in ts]
        case=json.loads((store.root/'synthetic-demo'/'case.json').read_text())
        an=json.loads((store.root/'synthetic-demo'/'analysis.json').read_text())
        if an['input_sha256']!=input_hash(case):errors.append(f'trial {trial}: case.json/analysis.json from different saves')
    print(len(errors),'errors');print('\n'.join(sorted(set(errors))[:6]))
