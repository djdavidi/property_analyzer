"""Optional local semantic cover estimates, separate from physical observations."""
from hashlib import sha256
from pathlib import Path
import subprocess
import tempfile
import math
import numpy as np
from pyproj import CRS
from rasterio.io import MemoryFile
from rasterio.enums import Resampling
from .remote_sensing import image_array, classified_features

MODEL_SHA256='a10b97b4b0caeed02aa292e822e702d21f9b99aa0a3d1d759dba57e93cf5f3ea'
MODEL_URL='https://drive.usercontent.google.com/download?id=1j6Os_c4RmiJlJd6EsPTGhJizVlfLeiZv&export=download&confirm=t'
MODEL_PAGE='https://open-earth-map.org/code.html'


def _cached_labels(path,shape):
    """Verified cached prediction, or None (a cache miss) for absent or bad entries.

    A missing/mismatched checksum, unreadable array or wrong shape is never an
    error that forces a permanent fallback; the prediction is recomputed.
    """
    checksum=path.with_suffix('.sha256')
    try:
        content=path.read_bytes()
        if checksum.read_text().strip()!=sha256(content).hexdigest():return None
        import io
        labels=np.load(io.BytesIO(content),allow_pickle=False)
    except (OSError,ValueError,EOFError):
        return None
    if labels.shape!=shape or labels.dtype!=np.uint8:return None
    return labels


def _store_labels(path,labels):
    """Atomic array then checksum writes; a crash between them is a later cache miss."""
    import io
    from .saved import atomic_write
    path.parent.mkdir(parents=True,exist_ok=True)
    stream=io.BytesIO();np.save(stream,labels,allow_pickle=False);content=stream.getvalue()
    atomic_write(path,content)
    atomic_write(path.with_suffix('.sha256'),sha256(content).hexdigest()+'\n')


MAX_CELLS=1_000_000
FINEST_METRES=.5
COARSEST_METRES=1.0


def analysis_resolution(bounds,crs,native=None):
    """Model cell size (m) for an analysis box, chosen before imagery is requested.

    Uses 0.5 m when the box fits in 1,000,000 cells, otherwise coarsens just
    enough to fit, up to the model's 1 m limit. Imagery coarser than the result
    sets the floor. A box that cannot fit at 1 m raises ValueError naming why.
    """
    unit=CRS(crs).axis_info[0].unit_conversion_factor
    width_m,height_m=(bounds[2]-bounds[0])*unit,(bounds[3]-bounds[1])*unit
    if native is not None and native>COARSEST_METRES:
        raise ValueError(f'Imagery cells of {native:.2f} m are coarser than the semantic model\'s 1 m limit')
    target=max(FINEST_METRES,native or 0,math.sqrt(width_m*height_m/MAX_CELLS))
    while math.ceil(width_m/target)*math.ceil(height_m/target)>MAX_CELLS:target*=1.001
    if target>COARSEST_METRES+1e-9:
        raise ValueError(f'Analysis box {width_m:.0f} x {height_m:.0f} m needs {target:.2f} m cells to fit the '
                         f'{MAX_CELLS:,}-cell model limit; the model supports at most 1 m')
    return target


def semantic_cover(content,bounds,case,source,*,runtime,weights,cache=None):
    runtime=Path(runtime);weights=Path(weights)
    if not runtime.is_file() or not weights.is_file():
        raise FileNotFoundError('Local semantic classifier is not installed; see SETUP.md')
    if sha256(weights.read_bytes()).hexdigest()!=MODEL_SHA256:
        raise ValueError('Semantic model weight hash mismatch')
    pixels=image_array(content)
    unit=CRS(case['crs']).axis_info[0].unit_conversion_factor
    native=max((bounds[2]-bounds[0])*unit/pixels.shape[1],(bounds[3]-bounds[1])*unit/pixels.shape[0])
    # Coarsen within the model's 1 m limit instead of rejecting a large box.
    target=analysis_resolution(bounds,case['crs'],native)
    width=max(1,math.ceil((bounds[2]-bounds[0])*unit/target));height=max(1,math.ceil((bounds[3]-bounds[1])*unit/target))
    if width*height>MAX_CELLS:raise ValueError('Semantic image window exceeds 1,000,000-cell limit')
    # Palette images are decoded before resampling. Alpha is never interpolated
    # into valid evidence; any nonopaque original pixel makes its sample unknown.
    with MemoryFile() as mem:
        with mem.open(driver='GTiff',width=pixels.shape[1],height=pixels.shape[0],count=3,dtype='uint8') as ds:
            ds.write(np.moveaxis(pixels[:,:,:3],-1,0))
            rgb=np.moveaxis(ds.read(out_shape=(3,height,width),resampling=Resampling.bilinear),0,-1)
    valid=np.ones((height,width),dtype=bool)
    transparent=pixels.shape[2]>3 and bool((pixels[:,:,3]!=255).any())
    if pixels.shape[2]>3:
        with MemoryFile() as mem:
            with mem.open(driver='GTiff',width=pixels.shape[1],height=pixels.shape[0],count=1,dtype='uint8') as ds:
                ds.write((pixels[:,:,3]==255).astype('uint8'),1)
                valid=ds.read(1,out_shape=(height,width),out_dtype='float32',resampling=Resampling.average)==1
    if transparent:
        # Transparent NoData (png32 exports) must not darken valid samples through
        # the bilinear kernel: weight colours by opacity and renormalize.
        weight=(pixels[:,:,3]==255).astype('float32')
        stack=np.concatenate([pixels[:,:,:3].astype('float32')*weight[:,:,None],weight[:,:,None]],axis=2)
        with MemoryFile() as mem:
            with mem.open(driver='GTiff',width=pixels.shape[1],height=pixels.shape[0],count=4,dtype='float32') as ds:
                ds.write(np.moveaxis(stack,-1,0))
                sampled=np.moveaxis(ds.read(out_shape=(4,height,width),resampling=Resampling.bilinear),0,-1)
        total=sampled[:,:,3:]
        rgb=np.where(total>0,np.clip(np.rint(sampled[:,:,:3]/np.where(total>0,total,1)),0,255),0).astype('uint8')
    settings={'algorithm':'OpenEarthMap U-Net EfficientNet-B4 SCSE v1','model_sha256':MODEL_SHA256,
        'model_url':MODEL_URL,'model_reference':MODEL_PAGE,'device':'CPU','torch':'2.9.1',
        'segmentation_models_pytorch':'0.3.3','input_scaling':'RGB / 255; no ImageNet normalization',
        'pixel_dimensions':[width,height],'rendered_bounds':list(bounds),'rendered_crs':case['crs'],
        'original_pixel_dimensions':[pixels.shape[1],pixels.shape[0]],'target_pixel_metres':target,
        'tile_size':512,'stride':384,'minimum_top_score':.60,'minimum_score_margin':.15,
        'source_sha256':source['sha256'],'interpretation_version':'oem-appearance-v2','class_mapping':{'1':'bare_soil','2':'grass_shrub','3':'developed_space',
        '4':'road','5':'canopy','6':'water','7':'grass_shrub (cropland grouped)','8':'roof'}}
    settings['worker_sha256']=sha256(Path(__file__).with_name('model_worker.py').read_bytes()).hexdigest()
    if transparent:settings['nodata_resampling']='opacity-weighted bilinear; transparent pixels excluded'
    key=sha256(__import__('json').dumps(settings,sort_keys=True).encode()).hexdigest()
    prediction_path=Path(cache)/('semantic-'+key+'.npy') if cache else None
    labels=_cached_labels(prediction_path,(height,width)) if prediction_path else None
    if labels is None:
        with tempfile.TemporaryDirectory() as temporary:
            folder=Path(temporary);np.save(folder/'input.npy',rgb,allow_pickle=False)
            try:
                run=subprocess.run([str(runtime.absolute()),str(Path(__file__).with_name('model_worker.py')),str(weights.resolve()),
                                    str(folder/'input.npy'),str(folder/'labels.npy')],capture_output=True,text=True,timeout=180)
            except subprocess.TimeoutExpired as exc:
                raise ValueError('Local classifier exceeded 180-second processing limit') from exc
            if run.returncode:raise ValueError('Local classifier failed: '+run.stderr[-1500:])
            labels=np.load(folder/'labels.npy',allow_pickle=False)
        if prediction_path:_store_labels(prediction_path,labels)
    if labels.shape!=(height,width) or labels.dtype!=np.uint8 or labels.max()>8:
        raise ValueError('Invalid semantic prediction raster')
    labels=labels.copy();labels[~valid]=0
    # Map OEM's eight classes into the established reporting vocabulary.
    remap=np.array([0,3,2,7,6,1,4,2,5],dtype='uint8')
    classes=remap[labels]
    from .remote_sensing import CLASS_NAMES
    result=classified_features(classes,bounds,case,{'family':'Local OpenEarthMap modeled cover',
        'url':MODEL_PAGE,'sha256':source['sha256'],'vintage':source.get('source_vintage')},
        class_names={**CLASS_NAMES,7:'developed_space'})
    result['model_coverage_complete']=result['coverage_complete'];result['coverage_complete']=False
    result['candidate_sqft']=result['classified_sqft'];result['classified_sqft']=None
    for feature in result['features']:
        props=feature['properties'];name=props['classification']
        feature['id']='auto-semantic-'+name
        props.update(layer='canopy_candidate' if name=='canopy' else 'vegetation_candidate' if name=='grass_shrub' else 'surface_candidate',
            source_kind='modeled semantic estimate',model_sha256=MODEL_SHA256,physical_class_unverified=True,
            interpretation_version='oem-appearance-v2')
        props.pop('class',None)
    for row in result['estimates']:
        row['basis']='Modeled semantic image estimate; not a reviewed physical observation'
        row['uncertainty']='Pixel-edge/unknown-coverage sensitivity only. Model scores are uncalibrated; local classification accuracy is unverified.'
    result.update(status='modeled_semantic_estimates',settings=settings,
        prediction_sha256=sha256(classes.tobytes()).hexdigest(),
        claim='Modeled canopy and surface areas from recent imagery; independent local accuracy unverified.',
        coverage_warning='Tree/grass and roof/pavement classes are model predictions. Low-score pixels and ground hidden by trees remain unknown. Grass/soil appearance does not establish infiltration or eligibility.')
    return result
