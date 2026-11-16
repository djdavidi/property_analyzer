"""Check semantic_cover's resampling: (a) valid==1 float equality, (b) bilinear bleed of transparent pixels into 'valid' samples."""
import numpy as np
from rasterio.io import MemoryFile
from rasterio.enums import Resampling
def rs(arr,count,shape,res,dtype='uint8',out_dtype=None):
    with MemoryFile() as mem:
        with mem.open(driver='GTiff',width=arr.shape[-1],height=arr.shape[-2],count=count,dtype=dtype) as ds:
            ds.write(arr if count>1 else arr[None]) 
            kw={'out_dtype':out_dtype} if out_dtype else {}
            return ds.read(out_shape=(count,)+shape,resampling=res,**kw)
# (a) all-opaque mask, non-integer ratios like the real pipeline (2048x2013 -> 556x547 etc.)
for W,H,w,h in [(2048,2013,556,547),(1024,1007,556,547),(2048,1593,611,476),(1777,2048,333,384)]:
    v=rs(np.ones((H,W),'uint8'),1,(h,w),Resampling.average,out_dtype='float32')[0]
    print('opaque',W,H,'->',w,h,'valid fraction',(v==1).mean(), 'min',v.min())
# (b) left 40% transparent black (ArcGIS outside-coverage), right opaque grey 200
W,H,w,h=2048,2013,556,547
rgb=np.zeros((3,H,W),'uint8'); rgb[:,:,int(W*.4):]=200
alpha=np.zeros((H,W),'uint8'); alpha[:,int(W*.4):]=1
out=rs(rgb,3,(h,w),Resampling.bilinear)
valid=rs(alpha,1,(h,w),Resampling.average,out_dtype='float32')[0]==1
row=out[0,h//2]; vrow=valid[h//2]
first=np.argmax(vrow)
print('first valid col',first,'RGB values at first valid cols:',row[first:first+4].tolist(),'(true value 200)')
