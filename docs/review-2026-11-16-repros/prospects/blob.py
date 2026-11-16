import tempfile, hashlib, io
from pathlib import Path
from drainage_core.sources import Cache, SourceError
body=b'{"Parcel":{"ParcelID":1}}'
class R(io.BytesIO):
    def __enter__(s):return s
    def __exit__(s,*a):return False
with tempfile.TemporaryDirectory() as d:
    c=Cache(d,opener=lambda req,timeout=None:R(body))
    sha=hashlib.sha256(body).hexdigest()
    (Path(d)/'blobs'/sha).write_bytes(body[:7])   # simulate crash/concurrent partial write of the blob
    for refresh in (False,True,True):
        try:c.fetch_json('https://x.example/a',refresh);print('refresh',refresh,'ok')
        except SourceError as e:print('refresh',refresh,'->',e)
    try:c._read('https://x.example/a');print('read ok')
    except SourceError as e:print('subsequent cached read ->',e)
    from stormwater.prospects import CappedCache
    try:CappedCache(c,max_requests=80,refresh_stale=True).fetch_json('https://x.example/a');print('capped ok')
    except Exception as e:print('CappedCache(refresh_stale) ->',type(e).__name__,e)
    c2=Cache(d,opener=lambda req,timeout=None:R(body))
    try:c2.fetch_json('https://x.example/a',True);c2._read('https://x.example/a');print('refetch heals')
    except SourceError as e:print('after another forced refetch, read still ->',e)
