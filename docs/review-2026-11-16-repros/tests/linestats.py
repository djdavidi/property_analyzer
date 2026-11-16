import sys, glob, tokenize, io, os
root=__import__('os').getcwd()
files=[f for f in glob.glob(root+'/**/*.py',recursive=True) if '/.venv/' not in f]
tot=0; gt200=0; gt500=0; mx=(0,''); semis=0; stmtlines=0
per={}
for f in files:
    src=open(f).read().splitlines()
    for i,l in enumerate(src,1):
        tot+=1
        n=len(l)
        if n>200: gt200+=1; per.setdefault(os.path.relpath(f,root),[0,0])[0]+=1
        if n>500: gt500+=1; per.setdefault(os.path.relpath(f,root),[0,0])[1]+=1
        if n>mx[0]: mx=(n,f'{os.path.relpath(f,root)}:{i}')
    # count semicolon statement separators via tokens
    try:
        toks=list(tokenize.generate_tokens(io.StringIO(open(f).read()).readline))
        semis+=sum(1 for t in toks if t.type==tokenize.OP and t.string==';')
    except Exception as e: print('tokerr',f,e)
print('files',len(files),'lines',tot,'>200',gt200,'>500',gt500,'max',mx,'semicolons',semis)
for k,v in sorted(per.items(), key=lambda x:-x[1][0])[:15]: print(k,v)
