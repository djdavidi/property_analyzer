import ast,glob,os
R='./tests/'
weak=[];total=0
for f in sorted(glob.glob(R+'test_*.py')):
    src=open(f).read(); t=ast.parse(src)
    for n in ast.walk(t):
        if isinstance(n,ast.FunctionDef) and n.name.startswith('test'):
            total+=1
            calls=[c for c in ast.walk(n) if isinstance(c,ast.Call)]
            names=[getattr(c.func,'attr',getattr(c.func,'id','')) for c in calls]
            asserts=[x for x in names if x.startswith('assert')]+[1 for c in ast.walk(n) if isinstance(c,ast.Assert)]
            strong=[x for x in names if x in('assertEqual','assertAlmostEqual','assertRaises','assertRaisesRegex','assertIsNone','assertIs','assertNotEqual','assertLess','assertGreater','assertFalse')]
            if len(strong)==0:
                weak.append((os.path.basename(f),n.lineno,n.name,sorted(set(x for x in names if isinstance(x,str) and x.startswith('assert')))))
print('total test fns',total,'with no equality/raises/None/false assertions:',len(weak))
for w in weak: print(*w)
