"""Native-grid DEM preparation with explicit source-evidence and crop provenance."""
from hashlib import sha256
import math
from pathlib import Path

import rasterio
from rasterio.windows import Window, from_bounds
from shapely.geometry import shape, box

from .raster import import_dem


def crop_dem(source, parcel, destination, *, crs, buffer_native_units=150, max_cells=250000):
    """Crop outward on the source grid, preserving resolution and GDAL georeference.

    Rasterio already accounts for GeoTIFF PixelIsPoint. Applying another half-cell
    shift would misalign the crop. Require full requested coverage rather than
    silently reducing the buffer at source edges.
    """
    if not math.isfinite(buffer_native_units) or buffer_native_units < 0:
        raise ValueError('Crop buffer must be finite and nonnegative')
    source=Path(source);destination=Path(destination)
    if source.resolve()==destination.resolve():raise ValueError('Crop must preserve original source')
    region=shape(parcel).buffer(buffer_native_units,join_style='mitre')
    with rasterio.open(source) as ds:
        if ds.crs != rasterio.crs.CRS.from_user_input(crs):
            raise ValueError('Parcel/source CRS mismatch; explicit coordinate operation required')
        t=ds.transform
        if t.b or t.d or t.a<=0 or t.e>=0:
            raise ValueError('Crop requires native north-up source grid')
        if not box(*ds.bounds).covers(region):
            raise ValueError('Source does not cover parcel and requested crop buffer')
        win=from_bounds(*region.bounds,transform=t)
        left,top=math.floor(win.col_off),math.floor(win.row_off)
        right,bottom=math.ceil(win.col_off+win.width),math.ceil(win.row_off+win.height)
        window=Window(left,top,right-left,bottom-top)
        if window.width*window.height>max_cells:
            raise ValueError('Native crop exceeds property cell limit; do not silently resample')
        profile=ds.profile.copy()
        profile.update(driver='GTiff',width=int(window.width),height=int(window.height),
                       transform=ds.window_transform(window),compress='deflate')
        destination.parent.mkdir(parents=True,exist_ok=True)
        with rasterio.open(destination,'w',**profile) as out:
            out.write(ds.read(window=window))
            out.update_tags(**ds.tags())
        return {'operation':'native grid crop; no resampling or elevation conversion',
                'source_sha256':sha256(source.read_bytes()).hexdigest(),
                'crop_sha256':sha256(destination.read_bytes()).hexdigest(),
                'window':{'col_off':left,'row_off':top,'width':right-left,'height':bottom-top},
                'buffer_native_units':buffer_native_units,'crs':crs,
                'source_pixel_interpretation':ds.tags().get('AREA_OR_POINT'),
                'half_pixel_adjustment':'GDAL native transform retained; no additional shift'}


def prepare_terrain(source, parcel, destination, *, crs, vertical_unit, unit_evidence,
                    acquisition_date=None, buffer_native_units=150):
    """Require provenance for verified units; permit clearly labelled assumptions.

    unit_evidence status is verified or assumed, with a source URL and explanation.
    An assumed unit remains a scenario even when a caller uses a valid unit code.
    """
    if unit_evidence.get('status') not in ('verified','assumed') or not unit_evidence.get('source_url') or not unit_evidence.get('explanation'):
        raise ValueError('Explicit vertical-unit evidence or labelled assumption is required')
    crop=crop_dem(source,parcel,destination,crs=crs,buffer_native_units=buffer_native_units)
    item=import_dem(destination,vertical_unit=vertical_unit,acquisition_date=acquisition_date)
    item['provenance'].update(processing=crop,vertical_unit_evidence=unit_evidence)
    item['grid']['settings']={'extent_sufficient':False,'required_buffer_native_units':buffer_native_units,
                              'flat_tolerance':0,'max_flow_paths':40}
    item['grid']['source_quality']={'vertical_units':unit_evidence['status'],
                                  'hydrologic_extent':'Unverified; geometric buffer is not proof of sufficient watershed extent'}
    if unit_evidence['status']=='assumed':item['warnings'].append('Vertical units assumed for this scenario; not verified source metadata')
    item['warnings'].append('No depression filling, inferred inlets or private conveyance applied; surrounding watershed sufficiency unverified')
    return item
