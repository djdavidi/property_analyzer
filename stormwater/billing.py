"""Deterministic PWD nonresidential stormwater scenarios with an explicit ledger.

All area inputs are unrounded square feet. Decimal arithmetic avoids float-cent
artifacts. Unsupported account treatment or unreconciled overlap blocks scenarios.
"""
from copy import deepcopy
from decimal import Decimal, ROUND_CEILING, ROUND_HALF_UP
from .rules import screen, RULE_VERSION, MANUAL_URL, TARIFF_URL

D = Decimal


def decimal(value, name='value'):
    if value is None or isinstance(value, bool):
        raise ValueError(f'{name} is required and must be numeric')
    try: result = D(str(value))
    except Exception: raise ValueError(f'{name} must be numeric') from None
    if not result.is_finite() or result < 0:
        raise ValueError(f'{name} must be finite and nonnegative')
    return result


def cents(value):
    return value.quantize(D('.01'), rounding=ROUND_HALF_UP)


def default_tariff():
    return {'version':'pwd-2026-09-01','effective_from':'2026-09-01',
            'verified_on':'2026-11-15','verified_through':'2027-08-31',
            'ga_rate':'1.003','ia_rate':'7.048','unit_sqft':'500',
            'minimum_swms':'20.89','collection_charge':'2.81',
            'tariff_source':TARIFF_URL,'manual_source':MANUAL_URL,
            'money_rounding':'ROUND_HALF_UP each component and allocated account charge'}


def rounded_area(value, tariff=None):
    t = tariff or default_tariff(); u = decimal(t['unit_sqft'])
    return (decimal(value) / u).to_integral_value(rounding=ROUND_CEILING) * u


def monthly_bill(ga_sqft, ia_sqft, accounts=None, tariff=None,
                 ga_credit_sqft=0, ia_credit_sqft=0, iar_sqft=0,
                 npdes_fraction=0, property_type='NonRes', undeveloped=False,
                 bill_date=None, minimum_mode='parcel'):
    t = tariff or default_tariff()
    if property_type not in ['NonRes','Condo','Non-residential','Condominium']:
        raise ValueError('Only nonresidential and condominium billing is implemented')
    if bill_date and not (t['effective_from'] <= bill_date <= t['verified_through']):
        raise ValueError('Billing date is outside the verified tariff period; supply a verified tariff')
    ga, ia = decimal(ga_sqft,'ga_sqft'), decimal(ia_sqft,'ia_sqft')
    if ia > ga: raise ValueError('Physical IA cannot exceed GA')
    statutory_ia = ga * (D('.25') if undeveloped else D('.85')) if ga < 5000 else ia
    cg, ci, ir = [decimal(x) for x in [ga_credit_sqft,ia_credit_sqft,iar_sqft]]
    if cg > ga or ci+ir > statutory_ia:
        raise ValueError('Credits exceed the applicable billing area')
    npdes = decimal(npdes_fraction,'npdes_fraction')
    if npdes not in [D(0),D('.07')]: raise ValueError('Only 0% and 7% existing NPDES are supported')
    final_ga, final_ia = ga-cg, statutory_ia-ir-ci
    billed_ga, billed_ia = rounded_area(final_ga,t), rounded_area(final_ia,t)
    u = decimal(t['unit_sqft'])
    gross_charge = cents(billed_ga/u * decimal(t['ga_rate']))
    impervious_charge = cents(billed_ia/u * decimal(t['ia_rate']))
    area_charge = cents((gross_charge+impervious_charge) * (1-npdes))
    minimum = decimal(t['minimum_swms']); minimum_applied = area_charge < minimum
    parcel_charge = max(area_charge,minimum)
    accounts = accounts if accounts is not None else [{'allocation':1,'discount_factor':1}]
    if not accounts: raise ValueError('At least one account is required')
    allocations = [decimal(a.get('allocation'),'allocation') for a in accounts]
    if abs(sum(allocations)-1) > D('.000000001'):
        raise ValueError('Account allocations must sum to one')
    # Normalize only tiny representation error in thirds/twelfths.
    allocations = [x/sum(allocations) for x in allocations]
    lines = []
    for i,(a,allocation) in enumerate(zip(accounts,allocations)):
        discount = decimal(a.get('discount_factor',1),'discount_factor')
        if discount not in [D('1'),D('.75')]:
            raise ValueError('Only standard and verified 75% special rates are supported')
        if discount == D('.75') and a.get('discount_verified') is not True:
            raise ValueError('Special discount requires verified account evidence')
        if minimum_mode not in ['parcel','per_account_after_credit']:
            raise ValueError('Unknown minimum mode')
        allocated = cents(parcel_charge*allocation)
        if minimum_mode=='per_account_after_credit' and minimum_applied: allocated=minimum
        account_total = cents((allocated+decimal(t['collection_charge']))*discount)
        lines.append({'account_index':i,'allocation':float(allocation),'swms':float(allocated),
                      'collection_charge':float(decimal(t['collection_charge'])),
                      'discount_factor':float(discount),'total':float(account_total)})
    total = sum(decimal(x['total']) for x in lines)
    return {'status':'calculated','monthly_total':float(total),'annualized_total':float(total*12),
            'physical_ga_sqft':float(ga),'physical_ia_sqft':float(ia),
            'statutory_ia_sqft':float(statutory_ia),'final_ga_sqft':float(final_ga),
            'final_ia_sqft':float(final_ia),'billed_ga_sqft':float(billed_ga),
            'billed_ia_sqft':float(billed_ia),'ga_charge':float(gross_charge),
            'ia_charge':float(impervious_charge),'minimum_applied':minimum_applied,
            'minimum_mode':minimum_mode,'npdes_fraction':float(npdes),'accounts':lines,
            'tariff_version':t['version'], 'warning': 'Annualized current-rate illustration; not a historical invoice.'}


def calculate_scenarios(baseline, measured=None, benefits=None, tariff=None):
    """Calculate appeal, credits, combined from one baseline; never add savings.

    Benefits must identify disjoint physical ledger_ids if more than one passes.
    Aggregate existing credits require an explicit spatial reconciliation before
    either measurement corrections or new benefits can be combined with them.
    """
    t=tariff or default_tariff(); measured=measured or {}; benefits=benefits or []
    ga=decimal(baseline.get('ga_sqft'),'ga_sqft'); ia=decimal(baseline.get('ia_sqft'),'ia_sqft')
    cg=decimal(baseline.get('existing_ga_credit_sqft',0)); ci=decimal(baseline.get('existing_ia_credit_sqft',0))
    ir=decimal(baseline.get('existing_iar_sqft',0)); npdes=decimal(baseline.get('npdes_fraction',0))
    common={k:baseline[k] for k in ['accounts','property_type','undeveloped','bill_date'] if k in baseline}
    common['tariff']=t
    base=monthly_bill(ga,ia,ga_credit_sqft=cg,ia_credit_sqft=ci,iar_sqft=ir,npdes_fraction=npdes,minimum_mode='per_account_after_credit' if cg or ci or ir or npdes else 'parcel',**common)
    warnings=[]
    if baseline.get('published_monthly_total') is not None:
        delta=cents(decimal(base['monthly_total'])-decimal(baseline['published_monthly_total']))
        base['published_difference']=float(delta)
        if delta: warnings.append('Calculated baseline differs from public snapshot; reconcile account rounding and billing treatment.')
    if baseline.get('actual_bill_total') is not None:
        base['actual_bill_difference']=float(cents(decimal(base['monthly_total'])-decimal(baseline['actual_bill_total'])))
    if not baseline.get('actual_bill_verified'): warnings.append('Actual account bill, payer, and special-rate enrollment are unverified.')
    screened=[]
    for b in benefits:
        s=screen(b['category'],b['area_sqft'],b.get('evidence')); s.update({'id':b.get('id'),'basis':b.get('basis','modeled')}); screened.append(s)
    output={'rule_version':RULE_VERSION,'tariff':t,'baseline':base,'screens':screened,'warnings':warnings}
    def scenario(use_measure,use_benefits,documented_only=False):
        errors=[]; a,g=ia,ga
        if use_measure:
            if measured.get('complete') is not True or measured.get('ia_sqft') is None or measured.get('ga_sqft') is None:
                errors.append('Complete physical IA/GA measurements are missing.')
            else: a,g=decimal(measured['ia_sqft']),decimal(measured['ga_sqft'])
            if a>g: errors.append('Measured IA exceeds measured GA.')
        existing=bool(cg or ci or ir)
        if existing and (use_measure or use_benefits) and baseline.get('existing_credits_spatially_reconciled') is not True:
            errors.append('Existing aggregate credits need spatial reconciliation before changes.')
        active=[(b,s) for b,s in zip(benefits,screened) if s['status']=='screen_pass' and (not documented_only or s['basis']=='documented')] if use_benefits else []
        if active and g < 500:
            errors.append('Credit eligibility requires at least 500 square feet of parcel gross area.')
        if any(b.get('evidence',{}).get('npdes') is True for b,_ in active) and not npdes:
            errors.append('Benefit assumes NPDES but the baseline has no verified existing NPDES benefit.')
        if npdes and active:
            errors.append('New credits with existing NPDES require a detailed approved area ledger; combination is unresolved.')
        if use_benefits and benefits and not active:
            errors.append('No benefit has complete passing prerequisites for this evidence basis.')
        used=set(); iar_add=D(0); ga_add=D(0); ia_add=D(0); physical_ia_used=D(0); physical_open_used=D(0)
        for b,s in active:
            ids=set(map(str,b.get('ledger_ids',[])))
            if len(active)>1 and not ids: errors.append('Multiple benefits require disjoint physical ledger_ids.')
            if used.intersection(ids): errors.append('Benefits overlap the same physical area; resolve sequencing and overlap.')
            used.update(ids)
            if existing and b.get('existing_overlap_reconciled') is not True:
                errors.append('New benefit overlap with existing credits is unreconciled.')
            area=decimal(s['area_sqft'])
            if s['category']=='open_space': physical_open_used+=area
            else: physical_ia_used+=area
            iar_add+=decimal(s['iar_sqft']);ga_add+=decimal(s['ga_credit_sqft']);ia_add+=decimal(s['ia_credit_sqft'])
        if physical_ia_used>a: errors.append('Benefit allocations exceed remaining physical IA after correction.')
        if physical_open_used>g-a: errors.append('Open-space allocations exceed remaining physical open space.')
        if ci+ir+ia_add+iar_add>a: errors.append('IA credits exceed remaining IA; corrected-away area cannot earn credit.')
        if cg+ga_add>g: errors.append('GA credits exceed remaining GA.')
        if errors:return {'status':'blocked','reasons':list(dict.fromkeys(errors)),'monthly_savings':None,'annual_savings':None}
        try:
            bill=monthly_bill(g,a,ga_credit_sqft=cg+ga_add,ia_credit_sqft=ci+ia_add,iar_sqft=ir+iar_add,
                              npdes_fraction=npdes,minimum_mode='per_account_after_credit' if active or existing or npdes else 'parcel',**common)
        except ValueError as e:return {'status':'blocked','reasons':[str(e)],'monthly_savings':None,'annual_savings':None}
        saving=cents(decimal(base['monthly_total'])-decimal(bill['monthly_total']))
        bill.update({'monthly_savings':float(saving),'annual_savings':float(saving*12),
                     'basis':'documented' if documented_only else 'modeled' if any(s['basis']!='documented' for _,s in active) or use_measure else 'documented',
                     'ledger':{'existing_ga_credit_sqft':float(cg),'existing_ia_credit_sqft':float(ci),'existing_iar_sqft':float(ir),
                               'new_ga_credit_sqft':float(ga_add),'new_ia_credit_sqft':float(ia_add),'new_iar_sqft':float(iar_add),
                               'allocated_physical_ia_sqft':float(physical_ia_used),'allocated_open_space_sqft':float(physical_open_used)}})
        return bill
    output['appeal_only']=scenario(True,False)
    output['credit_only']=scenario(False,True)
    output['combined']=scenario(True,True)
    output['documented_credit_only']=scenario(False,True,True)
    output['documented_combined']=scenario(True,True,True)
    return output
