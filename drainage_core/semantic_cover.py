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


def semantic_cover(content,bounds,case,source,*,runtime,weights,cache=None):
    runtime=Path(runtime);weights=Path(weights)
    if not runtime.is_file() or not weights.is_file():
        raise FileNotFoundError('Local semantic classifier is not installed; see SETUP.md')
    if sha256(weights.read_bytes()).hexdigest()!=MODEL_SHA256:
        raise ValueError('Semantic model weight hash mismatch')
    pixels=image_array(content)
    unit=CRS(case['crs']).axis_info[0].unit_conversion_factor
    native=max((bounds[2]-bounds[0])*unit/pixels.shape[1],(bounds[3]-bounds[1])*unit/pixels.shape[0])
    if native>1:raise ValueError('Imagery coarser than 1 m is unsuitable for this semantic model')
    target=max(.5,native)
    width=max(1,math.ceil((bounds[2]-bounds[0])*unit/target));height=max(1,math.ceil((bounds[3]-bounds[1])*unit/target))
    if width*height>1_000_000:raise ValueError('Semantic image window exceeds 1,000,000-cell limit')
    # Palette images are decoded before resampling. Alpha is never interpolated
    # into valid evidence; any nonopaque original pixel makes its sample unknown.
    with MemoryFile() as mem:
        with mem.open(driver='GTiff',width=pixels.shape[1],height=pixels.shape[0],count=3,dtype='uint8') as ds:
            ds.write(np.moveaxis(pixels[:,:,:3],-1,0))
            rgb=np.moveaxis(ds.read(out_shape=(3,height,width),resampling=Resampling.bilinear),0,-1)
    valid=np.ones((height,width),dtype=bool)
    if pixels.shape[2]>3:
        with MemoryFile() as mem:
            with mem.open(driver='GTiff',width=pixels.shape[1],height=pixels.shape[0],count=1,dtype='uint8') as ds:
                ds.write((pixels[:,:,3]==255).astype('uint8'),1)
                valid=ds.read(1,out_shape=(height,width),out_dtype='float32',resampling=Resampling.average)==1
    settings={'algorithm':'OpenEarthMap U-Net EfficientNet-B4 SCSE v1','model_sha256':MODEL_SHA256,
        'model_url':MODEL_URL,'model_reference':MODEL_PAGE,'device':'CPU','torch':'2.9.1',
        'segmentation_models_pytorch':'0.3.3','input_scaling':'RGB / 255; no ImageNet normalization',
        'pixel_dimensions':[width,height],'rendered_bounds':list(bounds),'rendered_crs':case['crs'],
        'original_pixel_dimensions':[pixels.shape[1],pixels.shape[0]],'target_pixel_metres':target,
        'tile_size':512,'stride':384,'minimum_top_score':.60,'minimum_score_margin':.15,
        'source_sha256':source['sha256'],'class_mapping':{'1':'bare_soil','2':'grass_shrub','3':'other_pavement',
        '4':'road','5':'canopy','6':'water','7':'grass_shrub (cropland grouped)','8':'roof'}}
    settings['worker_sha256']=sha256(Path(__file__).with_name('model_worker.py').read_bytes()).hexdigest()
    key=sha256(__import__('json').dumps(settings,sort_keys=True).encode()).hexdigest()
    prediction_path=Path(cache)/('semantic-'+key+'.npy') if cache else None
    if prediction_path and prediction_path.exists():
        checksum=prediction_path.with_suffix('.sha256')
        if not checksum.exists() or checksum.read_text().strip()!=sha256(prediction_path.read_bytes()).hexdigest():
            raise ValueError('Cached semantic prediction hash mismatch')
        labels=np.load(prediction_path,allow_pickle=False)
    else:
        with tempfile.TemporaryDirectory() as temporary:
            folder=Path(temporary);np.save(folder/'input.npy',rgb,allow_pickle=False)
            try:
                run=subprocess.run([str(runtime.absolute()),str(Path(__file__).with_name('model_worker.py')),str(weights.resolve()),
                                    str(folder/'input.npy'),str(folder/'labels.npy')],capture_output=True,text=True,timeout=180)
            except subprocess.TimeoutExpired as exc:
                raise ValueError('Local classifier exceeded 180-second processing limit') from exc
            if run.returncode:raise ValueError('Local classifier failed: '+run.stderr[-1500:])
            labels=np.load(folder/'labels.npy',allow_pickle=False)
        if prediction_path:
            prediction_path.parent.mkdir(parents=True,exist_ok=True)
            np.save(prediction_path,labels,allow_pickle=False)
            prediction_path.with_suffix('.sha256').write_text(sha256(prediction_path.read_bytes()).hexdigest()+'\n')
    if labels.shape!=(height,width) or labels.dtype!=np.uint8 or labels.max()>8:
        raise ValueError('Invalid semantic prediction raster')
    labels=labels.copy();labels[~valid]=0
    # Map OEM's eight classes into the established reporting vocabulary.
    remap=np.array([0,3,2,7,6,1,4,2,5],dtype='uint8')
    classes=remap[labels]
    result=classified_features(classes,bounds,case,{'family':'Local OpenEarthMap modeled cover',
        'url':MODEL_PAGE,'sha256':source['sha256'],'vintage':source.get('source_vintage')})
    result['model_coverage_complete']=result['coverage_complete'];result['coverage_complete']=False
    result['candidate_sqft']=result['classified_sqft'];result['classified_sqft']=None
    for feature in result['features']:
        props=feature['properties'];name=props['classification']
        feature['id']='auto-semantic-'+name
        props.update(layer='canopy_candidate' if name=='canopy' else 'vegetation_candidate' if name=='grass_shrub' else 'surface_candidate',
            source_kind='modeled semantic estimate',model_sha256=MODEL_SHA256,physical_class_unverified=True)
        props.pop('class',None)
    for row in result['estimates']:
        row['basis']='Modeled semantic image estimate; not a reviewed physical observation'
        row['uncertainty']='Pixel-edge/unknown-coverage sensitivity only. Model scores are uncalibrated; local classification accuracy is unverified.'
    result.update(status='modeled_semantic_estimates',settings=settings,
        prediction_sha256=sha256(classes.tobytes()).hexdigest(),
        claim='Modeled canopy and surface areas from recent imagery; independent local accuracy unverified.',
        coverage_warning='Tree/grass and roof/pavement classes are model predictions. Low-score pixels and ground hidden by trees remain unknown. Grass/soil appearance does not establish infiltration or eligibility.')
    return result
