import sys,os,io,unittest,datetime
R=os.path.realpath(sys.argv[1]); D=datetime.date.fromisoformat(sys.argv[2])
sys.path.insert(0,R+'/tests'); sys.path.insert(0,R); os.chdir(R)
class FD(datetime.date):
    @classmethod
    def today(cls): return cls(D.year,D.month,D.day)
import stormwater.renewals as rn, stormwater.assessment_policy as ap
rn.today=lambda: D
ap.date=FD
import stormwater.jurisdictions.philadelphia as ph
if hasattr(ph,'today'): ph.today=lambda: D
suite=unittest.defaultTestLoader.discover(R+'/tests')
r=unittest.TextTestRunner(stream=io.StringIO()).run(suite)
print(D,'ran',r.testsRun,'fail',len(r.failures),'err',len(r.errors),'skip',len(r.skipped))
for t,_ in r.failures+r.errors: print('  ',t.id())
