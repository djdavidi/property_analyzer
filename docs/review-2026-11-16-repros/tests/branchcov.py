import sys,os,io,unittest,glob,types,dis,collections
R=os.path.realpath(sys.argv[1]); sys.path.insert(0,R+'/tests'); sys.path.insert(0,R); os.chdir(R)
mon=sys.monitoring; TID=mon.COVERAGE_ID; mon.use_tool_id(TID,'bcov')
taken=collections.defaultdict(set)
def ok(fn): fn=os.path.realpath(fn); return fn.startswith(R+'/') and not fn[len(R):].startswith('/tests/') and '/examples/' not in fn
okc={}
def br(code,src,dst):
    v=okc.get(code)
    if v is None: v=okc[code]=ok(code.co_filename)
    if v:
        k=(os.path.realpath(code.co_filename),code.co_qualname,code.co_firstlineno,src); t=taken[k]; t.add(dst)
        if len(t)>=2: return mon.DISABLE
    else: return mon.DISABLE
mon.register_callback(TID,mon.events.BRANCH,br); mon.set_events(TID,mon.events.BRANCH)
r=unittest.TextTestRunner(stream=io.StringIO()).run(unittest.defaultTestLoader.discover(R+'/tests'))
mon.set_events(TID,0)
print('ran',r.testsRun,'fail',len(r.failures))
def codes(co):
    yield co
    for c in co.co_consts:
        if isinstance(c,types.CodeType): yield from codes(c)
tot=hit=0; per={}
for f in glob.glob(R+'/stormwater/**/*.py',recursive=True)+glob.glob(R+'/drainage_core/*.py'):
    f=os.path.realpath(f); ft=fh=0
    for co in codes(compile(open(f).read(),f,'exec')):
        ins=list(dis.get_instructions(co))
        for i,x in enumerate(ins):
            if x.opname.startswith('POP_JUMP_IF') and i+1<len(ins):
                arcs={x.argval,ins[i+1].offset}
                got=taken.get((f,co.co_qualname,co.co_firstlineno,x.offset),set())
                ft+=2; fh+=len(got&arcs) if got else 0
    tot+=ft; hit+=fh; per[os.path.relpath(f,R)]=(fh,ft)
print('BRANCH arc coverage %.1f%% (%d/%d)'%(100*hit/tot,hit,tot))
for k in ['stormwater/billing.py','stormwater/assessment_policy.py','stormwater/assessment_workflow.py','stormwater/model_assessment.py','stormwater/curve_number.py','drainage_core/drainage.py','drainage_core/research.py','stormwater/acquisition.py']:
    h,t=per[k]; print('  %-34s %5.1f%% (%d/%d)'%(k,100*h/max(t,1),h,t))
