from stormwater.billing import monthly_bill, calculate_scenarios
accts=[{'allocation':'0.3333333333333333333'},{'allocation':'0.3333333333333333333'},{'allocation':'0.3333333333333333334'}]
ev={k:True for k in ('physical_area_confirmed','parcel_allocation_confirmed','account_current','ground_impervious_overlap_confirmed')}
# parcel: GA 6000, IA 1500 -> GA 12*1.003=12.04, IA 3*7.048=21.14 => 33.18 > 20.89
base={'ga_sqft':6000,'ia_sqft':1500,'accounts':accts}
for area in (0,1000):
    out=calculate_scenarios(base,benefits=[{'id':'c','category':'canopy','area_sqft':area,'evidence':ev,'basis':'documented'}] if area else [])
    b=out['baseline']; print('baseline total',b['monthly_total'],'per-acct swms',[a['swms'] for a in b['accounts']],'min applied',b['minimum_applied'])
    if area:
        s=out['credit_only']; print('canopy 1000 sqft (IAR 500): area_charge -> total',s['monthly_total'],'per-acct swms',[a['swms'] for a in s['accounts']],'monthly_savings',s['monthly_savings'],'annual',s['annual_savings'])
# Non-monotonic cliff inside per_account_after_credit mode:
for ga,ia in ((6000,1000),(6000,500)):
    b=monthly_bill(ga,ia,accounts=accts,minimum_mode='per_account_after_credit')
    print(f'per_account mode GA{ga} IA{ia}: ga_charge+ia_charge={b["ga_charge"]+b["ia_charge"]:.2f} min_applied={b["minimum_applied"]} per-acct swms={[a["swms"] for a in b["accounts"]]} total={b["monthly_total"]}')
