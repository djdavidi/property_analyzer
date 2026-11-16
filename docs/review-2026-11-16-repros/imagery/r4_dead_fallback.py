"""Repro: acquire_imagery's Esri World Imagery export and acquire_tile_imagery fallback are unreachable."""
import tempfile
from unittest.mock import patch
from drainage_core.sources import Cache, SourceError
import stormwater.acquisition as acq
urls=[]
def opener(req, timeout=None):
    urls.append(req.full_url); raise OSError('PASDA down')
parcel={'type':'Polygon','coordinates':[[[2691146,238552],[2691528,238552],[2691528,239087],[2691146,239087],[2691146,238552]]]}
with tempfile.TemporaryDirectory() as d, patch.object(acq,'acquire_tile_imagery',side_effect=AssertionError('tile fallback reached')) as tile:
    c=Cache(d,opener=opener)
    for pol in (None,):
        try: acq.acquire_imagery(parcel,c,freshness_policy=pol)
        except SourceError as e: print('freshness_policy=None ->',str(e)[:400])
    print('hosts contacted:',sorted({u.split('/')[2] for u in urls}),'| tile fallback called:',tile.called)
