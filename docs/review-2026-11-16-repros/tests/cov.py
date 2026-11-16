import sys, os, io, unittest, json, glob, types
R=os.path.realpath(sys.argv[1])
sys.path.insert(0,R+'/tests'); sys.path.insert(0,R); os.chdir(R)
mon=sys.monitoring; TID=mon.COVERAGE_ID
mon.use_tool_id(TID,'cov')
hit=set()
def line(code,ln):
    fn=os.path.realpath(code.co_filename)
    if fn.startswith(R+'/') and not fn[len(R):].startswith('/tests/'): hit.add((fn,ln))
    return mon.DISABLE
mon.register_callback(TID,mon.events.LINE,line)
mon.set_events(TID,mon.events.LINE)
suite=unittest.defaultTestLoader.discover(R+'/tests')
r=unittest.TextTestRunner(stream=io.StringIO()).run(suite)
mon.set_events(TID,0)
print('ran',r.testsRun,'fail',len(r.failures),'err',len(r.errors),'skip',len(r.skipped))
def lines_of(co):
    s=set(l for _,_,l in co.co_lines() if l is not None)
    for c in co.co_consts:
        if isinstance(c,types.CodeType): s|=lines_of(c)
    return s
def funcs(co,out):
    for c in co.co_consts:
        if isinstance(c,types.CodeType):
            out.append(c); funcs(c,out)
    return out
tot_e=tot_h=0; rows=[]; unhit_funcs={}
for f in sorted(glob.glob(R+'/stormwater/**/*.py',recursive=True)+glob.glob(R+'/drainage_core/*.py')):
    co=compile(open(f).read(),f,'exec')
    ex=lines_of(co); h={l for (ff,l) in hit if ff==f}&ex
    tot_e+=len(ex); tot_h+=len(h)
    rows.append((len(h)/max(1,len(ex)),len(ex),len(h),os.path.relpath(f,R)))
    uf=[c.co_name+':'+str(c.co_firstlineno) for c in funcs(co,[]) if not (lines_of(c) & h) and c.co_name not in ('<lambda>','<genexpr>','<listcomp>','<dictcomp>','<setcomp>')]
    if uf: unhit_funcs[os.path.relpath(f,R)]=uf
print('TOTAL line coverage %.1f%% (%d/%d)'%(100*tot_h/tot_e,tot_h,tot_e))
for p,e,h,f in sorted(rows): print('%5.1f%% %4d/%4d %s'%(100*p,h,e,f))
json.dump(unhit_funcs,open(os.path.dirname(__file__)+'/unhit_funcs.json','w'),indent=1)
miss={}
for f in sorted(glob.glob(R+'/stormwater/**/*.py',recursive=True)+glob.glob(R+'/drainage_core/*.py')):
    co=compile(open(f).read(),f,'exec'); ex=lines_of(co); h={l for (ff,l) in hit if ff==f}
    miss[os.path.relpath(f,R)]=sorted(ex-h)
json.dump(miss,open(os.path.dirname(os.path.abspath(__file__))+'/missed_lines.json','w'))
