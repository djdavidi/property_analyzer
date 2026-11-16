import sys, tempfile, json
sys.path.insert(0,__import__('os').path.dirname(__import__('os').path.abspath(__file__)))
from harness import *
from pathlib import Path
from threading import Event
from stormwater.record_cache import SharedCache
w=World([sysf('1',(10,10,90,90),'P1')],[parf('1',(0,0,100,100))],{'1':bill('1',1000)})
stop=Event();orig=p.save_result
def slow_save(root,result):orig(root,result);stop.set()   # user presses Cancel while results are being written
p.save_result=slow_save
with tempfile.TemporaryDirectory() as root:
    try:p.run_scan(root,cache=SharedCache(root+'/public',fallback_roots=[],opener=w.opener),cancel=stop);print('completed')
    except Exception as e:print('reported:',e)
    print('latest.json now points to new run:',json.loads((Path(root)/'latest.json').read_text())['id'][:8],'| runs saved:',len(list((Path(root)/'runs').iterdir())))
