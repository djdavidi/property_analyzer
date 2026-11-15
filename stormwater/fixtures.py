"""Reproducible invented property for local workflow and known-answer checks.

This is not a Philadelphia parcel or an independent real-site benchmark.
"""
from shapely.geometry import Point, LineString, box, mapping
from .cases import new_case
from .geometry import area_sqft


def synthetic_case():
    x,y=2690000,250000
    crs='EPSG:2272'
    parcel=box(x+20,y-100,x+100,y-20)
    def feature(id,geometry,layer,cls=None,**properties):
        props={'layer':layer,'source_kind':'synthetic','source_family':'invented fixture',
               'acquisition_date':None,**properties}
        if cls is not None:props['class']=cls
        return {'type':'Feature','id':id,'geometry':mapping(geometry),'properties':props}
    roof=box(x+20,y-50,x+50,y-20)
    canopy_credit=box(x+55,y-45,x+70,y-30)
    case=new_case('Synthetic workflow example — invented property')
    case.update(id='synthetic-demo',crs=crs,parcel=mapping(parcel),synthetic_case=True,
                created_at='2026-11-15T00:00:00+00:00')
    case['features']['features']=[
        feature('roof-west',roof,'surface','roof'),
        feature('paving-east',box(x+50,y-100,x+100,y-20),'surface','pavement'),
        feature('paving-southwest',box(x+20,y-100,x+50,y-60),'surface','pavement'),
        feature('receiving-lawn',box(x+20,y-60,x+50,y-50),'surface','pervious'),
        feature('canopy',box(x+45,y-70,x+75,y-30),'canopy'),
        feature('drain-A',Point(x+92.5,y-92.5),'inlet',evidence='documented'),
        feature('pipe-A',LineString([(x+92.5,y-92.5),(x+110,y-105)]),'connection',
                **{'from':'drain-A','to':'garden-outlet','evidence':'documented'}),
        feature('garden-footprint',box(x+105,y-110,x+115,y-100),'footprint')]
    case['terrain']={'crs':crs,'elevations':[[12-.05*c-.03*r for c in range(24)] for r in range(24)],
                     'origin':[x,y],'cell_size':5,'horizontal_unit':'us-ft','vertical_unit':'ft',
                     'settings':{'extent_sufficient':False,'max_flow_paths':30}}
    case['baseline']={'ga_sqft':6800,'ia_sqft':6500,'existing_ga_credit_sqft':0,
                      'existing_ia_credit_sqft':0,'existing_iar_sqft':0,'npdes_fraction':0,
                      'property_type':'NonRes','accounts':[{'allocation':1,'discount_factor':1}],
                      'bill_date':'2026-11-15','actual_bill_verified':False,
                      'source':'Invented baseline for calculation exercise; not a PWD invoice'}
    common={'physical_area_confirmed':True,'parcel_allocation_confirmed':True,'account_current':True}
    case['benefits']=[
        {'id':'canopy-hypothesis','category':'canopy','geometry':mapping(canopy_credit),
         'area_sqft':area_sqft(canopy_credit,crs),'basis':'modeled',
         'evidence':{**common,'ground_impervious_overlap_confirmed':True}},
        {'id':'roof-disconnection-unresolved','category':'roof_disconnection','geometry':mapping(roof),
         'area_sqft':area_sqft(roof,crs),'basis':'modeled',
         'evidence':{**common,'account_current':None,'routing_confirmed':None,'soil_group':None}}]
    case['sources']=[{'url':'synthetic://drainage-v1/known-answer-property','source_kind':'synthetic',
                      'acquisition_date':None,'retrieved_at':'2026-11-15T00:00:00+00:00',
                      'crs':crs,'horizontal_unit':'us-ft','vertical_unit':'ft','resolution':5,
                      'processing':'Analytic vector rectangles and invented sloping plane; no real survey'}]
    case['assumptions']=[
        'All geometry, elevations, connections and billing quantities are invented synthetic inputs.',
        'The documented connection evidence label is part of the invented fixture, not a real engineering document.',
        'The roof has no known downspout connection and must remain unresolved in drainage routing.',
        'Canopy credit is a modeled technical screening example. The roof-disconnection example lacks prerequisites.',
        'The terrain has a surrounding buffer, but its hydrologic sufficiency has not been verified.',
        'Synthetic known-answer comparisons cannot establish independent real-site accuracy.']
    case['warnings']=['SYNTHETIC EXAMPLE: no actual property, approved drawing, invoice or eligible savings is represented.']
    case['references']=[]
    case['synthetic_known_answers']={'parcel_area_native_square_units':6400,
        'impervious_area_native_square_units':6100,'pervious_area_native_square_units':300,
        'roof_area_native_square_units':900,'canopy_ground_overlap_native_square_units':1050,
        'reference_purpose':'Known-answer synthetic checks only; not independent real-site validation'}
    return case
