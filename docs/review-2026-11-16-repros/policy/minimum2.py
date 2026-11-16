from stormwater.billing import calculate_scenarios
accts=[{'allocation':'0.3333333333333333333'},{'allocation':'0.3333333333333333333'},{'allocation':'0.3333333333333333334'}]
ev={k:True for k in ('physical_area_confirmed','parcel_allocation_confirmed','account_current','ground_impervious_overlap_confirmed')}
for canopy in (800,1000):
    out=calculate_scenarios({'ga_sqft':6000,'ia_sqft':1000,'accounts':accts},benefits=[{'id':'c','category':'canopy','area_sqft':canopy,'evidence':ev,'basis':'documented'}])
    s=out["credit_only"]; print(s.get("reasons")) if s["status"]=="blocked" else print(f"canopy {canopy} sqft: baseline {out['baseline']['monthly_total']} -> credited {s['monthly_total']} savings {s['monthly_savings']}/mo {s['annual_savings']}/yr")
