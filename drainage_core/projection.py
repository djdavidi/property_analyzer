"""Explicit vector and display reprojection while preserving native terrain grids."""
from copy import deepcopy
from hashlib import sha256
from pathlib import Path
from shapely.geometry import shape,mapping
from .geometry import reproject

def project_case(case,target_crs):
    """Transform all vector ledgers consistently; keep source records untouched."""
    out=deepcopy(case);source=case['crs']
    out['area_crs']=case.get('area_crs',source)
    def geom(value):return mapping(reproject(shape(value),source,target_crs))
    out['parcel']=geom(out['parcel'])
    for f in out['features']['features']:f['geometry']=geom(f['geometry'])
    for correction in out.get('corrections',[]):
        if correction.get('feature'):correction['feature']['geometry']=geom(correction['feature']['geometry'])
    for benefit in out.get('benefits',[]):
        if benefit.get('geometry'):benefit['geometry']=geom(benefit['geometry'])
    for feature in out.get('research_drainage',{}).get('features',[]):
        feature['geometry']=geom(feature['geometry'])
    for record in out.get('assessment',{}).get('records',[])+out.get('assessment',{}).get('existing_credit_allocations',[]):
        for key in ('geometry','footprint_geometry'):
            if record.get(key):record[key]=geom(record[key])
        if record.get('public_geometry') and record.get('source',{}).get('crs')==source:
            record['public_geometry']=geom(record['public_geometry'])
            record['source']={**record['source'],'crs':target_crs,'original_crs':source}
    if out.get('canopy_observation',{}).get('coverage_geometry'):
        out['canopy_observation']['coverage_geometry']=geom(out['canopy_observation']['coverage_geometry'])
    for reference in out.get('references',[]):
        if reference.get('crs')!=source:raise ValueError('Reference uses a different CRS; transform it explicitly before rerun')
        reference['geometry']=geom(reference['geometry']);reference['crs']=target_crs
    out['crs']=target_crs;out['terrain']=None
    out.pop('imagery',None) # A separately warped cached display is added below.
    out.setdefault('processing_history',[]).append({'operation':'Vector coordinate transformation',
        'source_crs':source,'target_crs':target_crs,'method':'pyproj always_xy; source observations retained in prior case revision'})
    return out


def warp_display(case,target_crs,root):
    """Reproject cached aerial pixels for display, never for terrain/classification."""
    import numpy as np
    from rasterio.io import MemoryFile
    from rasterio.transform import from_bounds
    from rasterio.warp import calculate_default_transform,reproject as warp,Resampling
    info=case.get('imagery')
    if not info:return None
    from .media import read_blob
    payload=read_blob(info,roots=[root])
    if sha256(payload).hexdigest()!=info['sha256']:raise ValueError('Aerial source hash mismatch')
    with MemoryFile(payload) as memory, memory.open() as image:
        from .remote_sensing import image_array
        source_pixels=np.moveaxis(image_array(payload),-1,0)
        source_transform=from_bounds(*info['bounds'],image.width,image.height)
        target_transform,width,height=calculate_default_transform(case['crs'],target_crs,image.width,image.height,*info['bounds'])
        output=np.zeros((source_pixels.shape[0],height,width),dtype='uint8')
        for band in range(source_pixels.shape[0]):
            warp(source_pixels[band],output[band],src_transform=source_transform,src_crs=case['crs'],
                 dst_transform=target_transform,dst_crs=target_crs,resampling=Resampling.bilinear)
        with MemoryFile() as result:
            with result.open(driver='PNG',width=width,height=height,count=output.shape[0],dtype='uint8') as out:out.write(output)
            png=result.read()
    digest=sha256(png).hexdigest();(root/'blobs').mkdir(parents=True,exist_ok=True);(root/'blobs'/digest).write_bytes(png)
    xmin=target_transform.c;ymax=target_transform.f
    return {**info,'sha256':digest,'blob_path':str(root/'blobs'/digest),'crs':target_crs,'width':width,'height':height,
            'bounds':[xmin,ymax+height*target_transform.e,xmin+width*target_transform.a,ymax],
            'processing':{'method':'bilinear aerial display-only reprojection','source_sha256':info['sha256'],
                          'source_crs':case['crs'],'target_crs':target_crs,'acquisition_date':None}}

