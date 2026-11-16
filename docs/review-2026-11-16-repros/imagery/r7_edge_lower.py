"""Repro: 'pixel-edge' lower bound erodes the legal parcel line, not just class edges."""
import numpy as np
from drainage_core.remote_sensing import classified_features
# 16 ft x 60 ft Philadelphia rowhouse parcel, EPSG:2272 (US ft); imagery bbox = parcel + 100 ft
x0,y0=2691200.0,238600.0
parcel={'type':'Polygon','coordinates':[[[x0,y0],[x0+16,y0],[x0+16,y0+60],[x0,y0+60],[x0,y0]]]}
case={'crs':'EPSG:2272','parcel':parcel}
bounds=[x0-100,y0-100,x0+116,y0+160]
# 0.5 m semantic grid -> ~1.64 ft cells; everything (on and off parcel) is roof (class 5)
w=int(np.ceil(216*0.3048006/0.5)); h=int(np.ceil(260*0.3048006/0.5))
classes=np.full((h,w),5,dtype='uint8')
r=classified_features(classes,bounds,case,{'family':'t','url':None,'sha256':'0'*64,'vintage':'2025'})
row=[e for e in r['estimates'] if e['feature']=='roof'][0]
print('roof area %.1f  edge_lower %.1f (%.1f%% below)  edge_upper %.1f  unknown %.3f' % (row['area_sqft'],row['edge_lower_sqft'],100*(1-row['edge_lower_sqft']/row['area_sqft']),row['edge_upper_sqft'],r['unclassified_sqft']))
