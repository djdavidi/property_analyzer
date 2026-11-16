"""Synthetic offline ArcGIS/PWD opener for prospect scans (no network)."""
import json, io
from urllib.parse import urlparse, parse_qs
from shapely.geometry import box, mapping, Point, shape
from stormwater import prospects as p

def sysf(sid, bounds, project, **extra):
    return {'type':'Feature','id':int(sid),'geometry':mapping(box(*bounds)),'properties':{'objectid':int(sid),'gsi_system_id':sid,'project_type':'Private - Retrofit','year_installed':2018,'status':'Complete','gsi_system_type':'Rain Garden','project_number':project,**extra}}
def parf(pid, bounds, owner='PRIVATE HOLDINGS LLC', **extra):
    return {'type':'Feature','id':int(pid),'geometry':mapping(box(*bounds)),'properties':{'objectid':int(pid),'parcelid':int(pid),'address':f'{pid} TEST ST','owner1':owner,'owner2':None,'gross_area':(bounds[2]-bounds[0])*(bounds[3]-bounds[1]),**extra}}
def bill(pid, charge=1000, owner='PRIVATE HOLDINGS LLC', **extra):
    return {'Parcel':{'ParcelID':int(pid),'Owner1':owner,'Owner2':None,'Address':f'{pid} TEST ST','GrossArea':100000,'ImpervArea':80000,'NPDESCredit':0,'BldgType':'NonRes',**extra},
        'ChargeSummary':{'GrossCreditSqFt':0,'ImpervCreditSqFt':0,'Errors':[],'ParcelTotals':[{'TotalStormwaterCharge':charge,'RateSchedule':{'IsCurrent':True,'StartDate':'2026-07-01T00:00:00','EndDate':'2027-06-30T00:00:00'}}]},'Pending':{'Expired':0,'Credits':0}}

class World:
    def __init__(self, systems, parcels, bills, parcel_error=None):
        self.systems=systems; self.parcels=parcels; self.bills=bills; self.calls=[]; self.parcel_error=parcel_error
    def opener(self, request, timeout=None):
        url=request.full_url; self.calls.append(url); u=urlparse(url); q={k:v[0] for k,v in parse_qs(u.query).items()}
        if 'GSI_SMP_TYPES' in url:
            body={'type':'FeatureCollection','features':self.systems}
        elif 'PWD_PARCELS' in url:
            if self.parcel_error:
                err=self.parcel_error; self.parcel_error=None
                body={'error':{'code':500,'message':err}}
            else:
                pts=json.loads(q['geometry'])['points']
                hits=[f for f in self.parcels if any(shape(f['geometry']).intersects(Point(*pt)) for pt in pts)]
                body={'type':'FeatureCollection','features':hits}
        elif '/PwdWebApi/' in url:
            pid=url.rstrip('/').split('/')[-2]; body=self.bills[pid]
        else: raise AssertionError(url)
        data=json.dumps(body).encode()
        class R(io.BytesIO):
            def __enter__(s):return s
            def __exit__(s,*a):return False
        return R(data)
