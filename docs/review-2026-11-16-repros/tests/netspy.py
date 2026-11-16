import sys, unittest, traceback, socket, urllib.request, collections
sys.path.insert(0,'./tests'); sys.path.insert(0,__import__('os').getcwd())
hits=collections.Counter()
cur=[None]
orig=socket.socket.connect
def connect(self, addr, *a, **k):
    host=addr[0] if isinstance(addr,tuple) else addr
    if True:
        hits[(cur[0], str(addr))]+=1
    return orig(self, addr, *a, **k)
socket.socket.connect=connect
class R(unittest.TextTestResult):
    def startTest(self,t):
        cur[0]=t.id(); super().startTest(t)
suite=unittest.defaultTestLoader.discover('./tests')
import io
r=unittest.TextTestRunner(stream=io.StringIO(),resultclass=R).run(suite)
print("ran",r.testsRun,"fail",len(r.failures),"err",len(r.errors),"skip",len(r.skipped)); [print(t.id(), tb[-600:]) for t,tb in r.failures]
for k,v in hits.items(): print(v,k)
