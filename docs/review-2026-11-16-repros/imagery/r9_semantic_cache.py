"""Repro: an interrupted semantic-cache write (labels .npy written, .sha256 not yet) makes every later
run raise ValueError -> landcover silently degrades to RGB candidates for that image forever."""
import tempfile, numpy as np, subprocess
from hashlib import sha256
from pathlib import Path
from unittest.mock import patch
from rasterio.io import MemoryFile
import drainage_core.semantic_cover as sc
d=Path(tempfile.mkdtemp()); weights=d/'w.pth'; weights.write_bytes(b'fake'); runtime=d/'python'; runtime.write_text('#!/bin/sh\n')
img=np.full((3,200,200),120,'uint8')
with MemoryFile() as m:
    with m.open(driver='PNG',width=200,height=200,count=3,dtype='uint8') as ds: ds.write(img)
    png=m.read()
case={'crs':'EPSG:2272','parcel':{'type':'Polygon','coordinates':[[[50,50],[150,50],[150,150],[50,150],[50,50]]]}}
calls=[]
def fake_run(cmd,**kw):
    calls.append(1); inp=np.load(cmd[3]); np.save(cmd[4],np.full(inp.shape[:2],8,'uint8'))
    if len(calls)==1: raise KeyboardInterrupt  # simulate kill right after worker wrote output
    return subprocess.CompletedProcess(cmd,0,'','')
cache=d/'semantic'
with patch.object(sc,'MODEL_SHA256',sha256(b'fake').hexdigest()), patch.object(sc.subprocess,'run',fake_run):
    # first run completes normally and populates cache
    def ok_run(cmd,**kw):
        inp=np.load(cmd[3]); np.save(cmd[4],np.full(inp.shape[:2],8,'uint8')); return subprocess.CompletedProcess(cmd,0,'','')
    with patch.object(sc.subprocess,'run',ok_run):
        r=sc.semantic_cover(png,[0,0,200,200],case,{'sha256':'a'*64},runtime=runtime,weights=weights,cache=cache)
    files=sorted(p.name for p in cache.iterdir()); print('cache files',files)
    # simulate a crash between np.save and checksum write: delete checksum
    next(cache.glob('*.sha256')).unlink()
    try:
        with patch.object(sc.subprocess,'run',ok_run):
            sc.semantic_cover(png,[0,0,200,200],case,{'sha256':'a'*64},runtime=runtime,weights=weights,cache=cache)
    except ValueError as e: print('every later run ->',e,'(landcover() catches ValueError and falls back to RGB masks)')
