"""Explicitly georeferenced raster import; no resampling creates source detail."""
from __future__ import annotations
import hashlib
from pathlib import Path
import math


def _provenance(path, dataset, acquisition_date=None):
    from pyproj import CRS
    crs=CRS(dataset.crs)
    unit=crs.axis_info[0].unit_name if crs.axis_info else None
    horizontal={'metre':'m','foot':'ft','US survey foot':'us-ft'}.get(unit,unit)
    return {'path':str(Path(path).resolve()),'url':None,
            'sha256':hashlib.sha256(Path(path).read_bytes()).hexdigest(),
            'acquisition_date':acquisition_date,'crs':crs.to_string(),
            'horizontal_unit':horizontal,'vertical_unit':None,
            'resolution':[abs(dataset.transform.a),abs(dataset.transform.e)],
            'bounds':list(dataset.bounds),'width':dataset.width,'height':dataset.height,
            'nodata':dataset.nodata,'processing':'native grid; no resampling'}


def _open(path, max_cells):
    import rasterio
    from pyproj import CRS
    dataset=rasterio.open(path)
    if not dataset.crs or not CRS(dataset.crs).is_projected:
        dataset.close();raise ValueError('Raster must have a projected coordinate system')
    t=dataset.transform
    if abs(t.b)>1e-10 or abs(t.d)>1e-10 or t.a<=0 or t.e>=0:
        dataset.close();raise ValueError('Import requires a north-up, unrotated raster; reproject explicitly first')
    if dataset.width*dataset.height>max_cells:
        dataset.close();raise ValueError(f'Raster exceeds {max_cells} cells; crop to property and routing buffer first')
    return dataset


def import_dem(path, *, vertical_unit, acquisition_date=None, max_cells=250000):
    """Return route_grid input and complete source metadata; retain NoData as None.

    Elevation units are mandatory and independent of horizontal CRS units. The
    file's top-left corner is returned as origin; row numbers increase southward.
    """
    import numpy as np
    if vertical_unit not in ('m','ft','us-ft'):
        raise ValueError('Explicit vertical_unit m, ft or us-ft is required')
    with _open(path,max_cells) as ds:
        if ds.count != 1:
            raise ValueError('DEM must contain exactly one elevation band')
        if not math.isclose(abs(ds.transform.a),abs(ds.transform.e),rel_tol=1e-9):
            raise ValueError('DEM requires square cells; resample explicitly and preserve processing settings')
        values=ds.read(1,masked=True)
        missing=np.ma.getmaskarray(values) | ~np.isfinite(values.data)
        elevations=[[None if missing[r,c] else float(values[r,c]) for c in range(ds.width)] for r in range(ds.height)]
        source=_provenance(path,ds,acquisition_date)
        if source['horizontal_unit'] not in ('m','ft','us-ft'):
            raise ValueError('Unsupported horizontal raster units')
        source['vertical_unit']=vertical_unit
        warnings=[]
        if missing.any():
            warnings.append(f'{int(missing.sum())} NoData cells remain unresolved; no terrain fill performed')
        if acquisition_date is None:
            warnings.append('Elevation acquisition date unknown; final grading compatibility unverified')
        return {'grid':{'elevations':elevations,'origin':[ds.transform.c,ds.transform.f],
                        'cell_size':abs(ds.transform.a),'horizontal_unit':source['horizontal_unit'],
                        'vertical_unit':vertical_unit,'crs':source['crs']},
                'provenance':source,'warnings':warnings}


def classify_raster(path, class_map, *, acquisition_date=None, max_cells=250000):
    """Polygonize a categorical surface raster. Unknown/NoData stays unknown.

    ``class_map`` maps integer classes to roof/pavement/pervious/unknown. A canopy
    raster cannot establish the hidden ground material; import it separately.
    Returned vectors retain all cells, so missing tiles cannot count as pervious.
    """
    import numpy as np
    from rasterio.features import shapes
    allowed={'roof','pavement','pervious','unknown'}
    mapping={int(k):v for k,v in class_map.items()}
    if any(v not in allowed for v in mapping.values()):
        raise ValueError('Unsupported surface class')
    codes={name:i for i,name in enumerate(['unknown','roof','pavement','pervious'])}
    with _open(path,max_cells) as ds:
        if ds.count!=1:
            raise ValueError('Categorical surface raster requires one band and an explicit class map')
        values=ds.read(1,masked=True)
        result=np.zeros(values.shape,dtype=np.uint8)
        for value,name in mapping.items():
            result[(values.data==value)&~np.ma.getmaskarray(values)]=codes[name]
        names={value:key for key,value in codes.items()}
        features=[]
        for geo,value in shapes(result,transform=ds.transform):
            features.append({'type':'Feature','geometry':geo,
                             'properties':{'layer':'surface','class':names[int(value)],
                                           'source_kind':'observation','source_method':'categorical raster import',
                                           'reviewed':False}})
        source=_provenance(path,ds,acquisition_date)
        source['class_map']=mapping
        source['unknown_cells']=int((result==0).sum())
        return {'features':{'type':'FeatureCollection','features':features},
                'crs':source['crs'],'provenance':source,
                'warnings':['Categorical source dependency must be disclosed; billing-derived maps are not independent validation.',
                            f'{source["unknown_cells"]} cells remain unknown.']}


def check_alignment(sources, *, parcel_bounds=None, routing_buffer=0):
    """Check CRS, pixel size, grid alignment, seams and routing extent explicitly."""
    warnings=[]
    if not sources:
        return ['No raster sources supplied']
    reference=sources[0]
    for item in sources:
        if item.get('crs')!=reference.get('crs'):
            warnings.append('Raster CRS mismatch; explicit reprojection required')
            continue
        if item.get('resolution')!=reference.get('resolution'):
            warnings.append('Raster resolution mismatch; explicit resampling required')
            continue
        bounds=item.get('bounds'); refbounds=reference.get('bounds'); res=item.get('resolution')
        if bounds and refbounds and res:
            for axis in range(2):
                offset=(bounds[axis]-refbounds[axis])/res[axis]
                if not math.isclose(offset,round(offset),abs_tol=1e-7):
                    warnings.append('Raster tile grid origins misaligned; seam can change routing')
                    break
    if parcel_bounds:
        bounds=[item.get('bounds') for item in sources if item.get('bounds')]
        if not bounds:
            warnings.append('Routing extent unknown')
        else:
            # Full coverage requires union coverage, not merely the combined envelope.
            from shapely.geometry import box
            from shapely.ops import unary_union
            extent=box(*parcel_bounds).buffer(routing_buffer,join_style='mitre')
            covered=unary_union([box(*b) for b in bounds])
            if not covered.covers(extent):
                warnings.append('Insufficient raster coverage for parcel and requested routing buffer; gaps/seams remain unresolved')
    return warnings
