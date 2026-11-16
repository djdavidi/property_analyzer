import ast,glob,re,os
root=__import__('os').getcwd()
mods=glob.glob(root+'/stormwater/**/*.py',recursive=True)+glob.glob(root+'/drainage_core/*.py')
tests=''.join(open(f).read() for f in glob.glob(root+'/tests/*.py'))+''.join(open(f).read() for f in glob.glob(root+'/tests/*.js'))
src_all={f:open(f).read() for f in mods+glob.glob(root+'/examples/**/*.py',recursive=True)}
allsrc=''.join(src_all.values())
res=[]
for f in sorted(mods):
    t=ast.parse(open(f).read())
    for n in t.body:
        if isinstance(n,(ast.FunctionDef,ast.ClassDef)):
            name=n.name
            in_tests=len(re.findall(r'\b'+re.escape(name)+r'\b',tests))
            uses=len(re.findall(r'\b'+re.escape(name)+r'\b',allsrc))-1  # minus def
            res.append((os.path.relpath(f,root),n.lineno,name,in_tests,uses))
dead=[r for r in res if r[4]==0 and r[3]==0 and not r[2].startswith('__')]
untested=[r for r in res if r[3]==0]
print('total defs',len(res),'never named in tests',len(untested),'never referenced anywhere (dead?)',len(dead))
print('DEAD:'); [print(' ',*r) for r in dead]
for m in ['stormwater/billing.py','stormwater/assessment_policy.py','stormwater/curve_number.py','drainage_core/drainage.py','drainage_core/research.py','stormwater/model_assessment.py','stormwater/assessment_workflow.py']:
    print('UNTESTED in',m,[ (r[2],r[1],r[4]) for r in untested if r[0]==m])
