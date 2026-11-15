"""PWD existing-site screens over frozen physical GIS; never acquires or reroutes.

A screen_pass describes reviewed prerequisites, not a grant, award or legal opinion.
The separate area ledger below implements Manual 4.3.5; it never adds independently
calculated savings or applies a further seven percent to already uplifted credits.
"""
from copy import deepcopy
from datetime import date
from decimal import Decimal
from hashlib import sha256
from urllib.parse import urlparse
import json
from shapely.geometry import shape
from shapely.errors import ShapelyError
from drainage_core.geometry import case_area_sqft, effective_features
from drainage_core.evidence import validate_references
from .billing import monthly_bill, default_tariff, cents, decimal
from .rules import screen, open_space_factor, MANUAL_URL, TARIFF_URL

VERSION = 'pwd-existing-site-2026-09-v1'
LABELS = {'green_roof':'Existing green roofs', 'permeable_pavement':'Existing permeable pavement',
          'direct_discharge':'Direct surface-water discharge', 'industrial_npdes':'Industrial NPDES'}
RULES = {'version':VERSION, 'verified_on':'2026-11-15', 'effective_from':'2026-09-01',
         'verified_through':'2027-08-31', 'manual':MANUAL_URL, 'tariff':TARIFF_URL,
         'gis_area_numerical_precision_sqft':'0.000000001',
         'manual_sections':['4.3.2.2','4.3.4','4.3.5','4.5.1','4.5.5'],
         'source_snapshots':[{'url': 'https://water.phila.gov/wp-content/uploads/files/stormwater-credits-appeals-manual.pdf', 'retrieved_at': '2026-11-15T06:51:38.544003+00:00', 'sha256': '5c7b6e87ae442731625b91e278ccdd160a21e960b3460886e8349aa42f8ffb49', 'bytes': 665543}, {'url': 'https://water.phila.gov/wp-content/uploads/files/rates-and-charges-2026-09-01.pdf', 'retrieved_at': '2026-11-15T06:51:38.781280+00:00', 'sha256': '880779871b2e47c11c619d33f499752afc9b3791dda5c326793165800f4ad9e6', 'bytes': 855667}],
         'claim':'Technical screening; PWD approval and actual billed reductions are not established.'}
COMMON = ('existing_installation','account_current','physical_area_confirmed','parcel_allocation_confirmed')
SMP = ('routing_confirmed','approved_record_drawings','current_condition_confirmed',
       'maintenance_documented','professional_reviewed')
PAVEMENT = ('material_confirmed','construction_documented','storage_documented','infiltration_or_underdrain_documented')
DIRECT = ('catchment_confirmed','route_confirmed','outfall_confirmed','destination_confirmed',
          'no_city_infrastructure','ownership_confirmed','no_erosion_or_detriment',
          'site_plan_documented','photographs_current','private_connections_resolved')
NPDES = ('site_match','operator_match','industrial_stormwater','active','compliance_previous_12_months',
         'permit_documented','discharge_monitoring_reports_previous_12_months')


def _area_decimal(value):
    # Remove sub-nanosquare-foot float conversion noise before 500 sqft ceilings.
    # This is numerical stabilization of GIS output, not billable-area rounding.
    return decimal(value).quantize(Decimal('.000000001'))


def _day(value):
    return date.fromisoformat(value) if isinstance(value,str) else value


def _prior_year(day):
    try:return day.replace(year=day.year-1)
    except ValueError:return day.replace(year=day.year-1,day=28)


def _source_url(value):
    if not isinstance(value,str):return False
    try:
        parsed=urlparse(value)
        return parsed.scheme in ('https','http') and bool(parsed.hostname)
    except ValueError:return False


def _validate_assessment_inputs(assessment):
    if not isinstance(assessment,dict):raise ValueError('Assessment must be an object')
    for field in ('records','existing_credit_allocations'):
        entries=assessment.get(field,[])
        if not isinstance(entries,list):raise ValueError(field+' must be a list')
        identifiers=set()
        for record in entries:
            if not isinstance(record,dict):raise ValueError(field+' entries must be objects')
            identifier=record.get('id')
            if not isinstance(identifier,str) or not identifier.strip():raise ValueError(field+' entries need a nonempty string ID')
            if identifier in identifiers:raise ValueError('Duplicate '+field+' ID: '+identifier)
            identifiers.add(identifier)
            if not isinstance(record.get('facts',{}),dict):raise ValueError('Facts must be an object')
            if field=='records':
                if record.get('category') not in LABELS:raise ValueError('Unsupported assessment category')
                if record.get('decision','candidate') not in ('candidate','confirmed','rejected'):raise ValueError('Invalid candidate decision')
                if record.get('basis','manual') not in ('public_candidate','manual','documented','modeled'):raise ValueError('Invalid evidence basis')
            refs=record.get('evidence_refs',[])
            if not isinstance(refs,list) or any(not isinstance(ref,dict) for ref in refs):raise ValueError('Evidence references must be a list of objects')


def _evidence(record, case):
    refs=record.get('evidence_refs') or []
    attachments={a['id'] for a in case.get('assessment',{}).get('attachments',[]) if 'id' in a}
    return any(isinstance(r,dict) and (_source_url(r.get('source_url'))
               or r.get('attachment_id') in attachments) for r in refs)


def screen_record(record, case, gis, as_of):
    category=record['category']; facts=record.get('facts') or {}; missing=[]; failed=[]
    output={key:deepcopy(record.get(key)) for key in ('id','category','decision','basis','evidence_refs','source')}
    output.update(label=LABELS[category],missing=missing,failed=failed,managed_area_sqft=None,
                  footprint_area_sqft=None,rule_version=VERSION)
    def require(name):
        if facts.get(name) is None:missing.append(name)
        elif facts[name] is not True:failed.append(name)
    def number(name,minimum=0):
        if facts.get(name) is None:missing.append(name);return
        try:
            if decimal(facts[name],name)<Decimal(str(minimum)):failed.append(name)
        except ValueError:failed.append(name)
    for key in ('account_current',) if category=='industrial_npdes' else COMMON:require(key)
    if not _evidence(record,case):missing.append('supporting_document_or_source_reference')
    if category=='industrial_npdes':
        for key in NPDES:require(key)
        if not facts.get('permit_id'):missing.append('permit_id')
        if facts.get('permit_type') in ('construction','municipal','no_exposure','terminated'):failed.append('permit_type')
        for key in ('effective_from','expires_on','compliance_from','compliance_through'):
            if not facts.get(key):missing.append(key);continue
            try:
                day=_day(facts[key])
                valid=(day<=as_of if key=='effective_from' else day>=as_of if key in ('expires_on','compliance_through') else day<=_prior_year(as_of))
                if not valid:failed.append(key)
            except (ValueError,TypeError):failed.append(key)
        if facts.get('terminated_on'):
            try:
                if _day(facts['terminated_on'])<=as_of:failed.append('terminated_on')
            except (ValueError,TypeError):failed.append('terminated_on')
    else:
        geom=None
        if not record.get('geometry'):missing.append('managed_area_geometry')
        else:
            try:
                geom=shape(record['geometry'])
                if not geom.is_valid or geom.is_empty or geom.geom_type not in ('Polygon','MultiPolygon'):raise ValueError()
                area=case_area_sqft(geom,case);output['managed_area_sqft']=area
                parcel=shape(case['parcel']);ia=shape(gis['measurement']['geometries']['physical_ia'])
                if geom.difference(parcel).area>1e-8:failed.append('managed_geometry_inside_parcel')
                if geom.difference(ia).area>1e-8:failed.append('managed_geometry_matches_physical_ia')
                if record.get('managed_area_sqft') is not None and abs(float(decimal(record['managed_area_sqft']))-area)>max(.1,area*.001):failed.append('managed_area_matches_geometry')
            except (ValueError,TypeError,KeyError,IndexError,AttributeError,ShapelyError):failed.append('managed_area_geometry')
        if record.get('footprint_geometry'):
            try:
                footprint=shape(record['footprint_geometry'])
                if footprint.is_empty or not footprint.is_valid or footprint.geom_type not in ('Polygon','MultiPolygon'):raise ValueError()
                output['footprint_area_sqft']=case_area_sqft(footprint,case)
                if footprint.difference(shape(case['parcel'])).area>1e-8:failed.append('footprint_inside_parcel')
            except (ValueError,TypeError,KeyError,IndexError,AttributeError,ShapelyError):failed.append('footprint_geometry')
        elif category in ('green_roof','permeable_pavement'):missing.append('physical_footprint_geometry')
        if category in ('green_roof','permeable_pavement'):
            for key in SMP:require(key)
            number('treatment_depth_inches',1 if facts.get('old_standard_renewal_verified') is True else 1.5)
            if category=='permeable_pavement':
                for key in PAVEMENT:require(key)
            if facts.get('credit_path') not in (None,'management'):failed.append('unsupported_credit_path')
        else:
            for key in DIRECT:require(key)
            if not facts.get('waterway_name'):missing.append('waterway_name')
            if not facts.get('outfall_id'):missing.append('outfall_id')
            if facts.get('upstream_smp_present') is None:missing.append('upstream_smp_present')
            elif not isinstance(facts['upstream_smp_present'],bool):failed.append('upstream_smp_present')
            elif facts['upstream_smp_present'] is True:
                require('upstream_smp_compliant');require('upstream_smp_functional')
    decision=record.get('decision','candidate')
    applicable=RULES['effective_from']<=as_of.isoformat()<=RULES['verified_through']
    output['rule_applicability']='applicable' if applicable else 'outside_verified_period'
    if not applicable:missing.append('applicable_rule_version')
    output['basis']=record.get('basis','manual')
    output['status']='rejected' if decision=='rejected' else 'candidate' if decision!='confirmed' else 'requirements_failed' if failed else 'missing_evidence' if missing else 'screen_pass'
    output['conclusion']='Prerequisites reviewed; eligibility/approval not established' if output['status']=='screen_pass' else 'No supported eligibility conclusion'
    return output


def _blocked(reasons):
    return {'status':'blocked','reasons':list(dict.fromkeys(reasons)),
            'gross_monthly_reduction':None,'gross_annual_reduction':None,'bill':None,'ledger':None}


def _legacy_benefits(case, gis):
    """Normalize the existing benefits into the same geometric ledger."""
    result=[]
    benefits=[b for b in case.get('benefits',[]) if not b.get('geometry')]
    benefits.extend({**f['properties']['benefit'],'geometry':f['geometry']} for f in effective_features(case)
                    if f['properties'].get('layer')=='benefit')
    for b in benefits:
        r=deepcopy(b); facts=r.setdefault('evidence',{})
        if r.get('geometry'):
            r['area_sqft']=case_area_sqft(shape(r['geometry']),case)
            target='pervious' if r['category'] in ('open_space','open-space') else 'canopy_ground_ia' if r['category'] in ('canopy','tree_canopy') else 'physical_ia'
            if shape(r['geometry']).difference(shape(gis['measurement']['geometries'][target])).area>1e-8:facts['physical_area_confirmed']=False
        else:facts['physical_area_confirmed']=None
        s=screen(r['category'],r['area_sqft'],facts)
        if s['status']=='screen_pass':result.append((r,s))
    return result


def _existing_allocations(case, gis, baseline):
    """An approved itemized ledger must reconcile every recorded existing credit."""
    items=case.get('assessment',{}).get('existing_credit_allocations',[])
    if not items:return [],['Detailed existing credit allocation ledger missing']
    errors=[];allocations=[];totals={key:Decimal(0) for key in ('ga_credit_sqft','ia_credit_sqft','iar_sqft')}
    for item in items:
        try:
            if item.get('facts',{}).get('approved_ledger_confirmed') is not True or not _evidence(item,case):
                raise ValueError('Approved existing allocation evidence missing')
            geometry=shape(item['geometry']);area=_area_decimal(case_area_sqft(geometry,case));cat=item['category']
            if geometry.is_empty or not geometry.is_valid or geometry.geom_type not in ('Polygon','MultiPolygon'):raise ValueError('Invalid existing allocation geometry')
            target='pervious' if cat=='open_space' else 'canopy_ground_ia' if cat=='canopy' else 'physical_ia'
            if geometry.difference(shape(gis['measurement']['geometries'][target])).area>1e-8:raise ValueError('Existing allocation is outside its physical area')
            if cat in ('management','direct_discharge'):
                factor=Decimal('.8' if cat=='management' else '.9');expected={'ga_credit_sqft':area*factor,'ia_credit_sqft':area*factor,'iar_sqft':Decimal(0)}
            elif cat=='open_space':expected={'ga_credit_sqft':area*Decimal(str(open_space_factor(item['facts']['curve_number']))),'ia_credit_sqft':Decimal(0),'iar_sqft':Decimal(0)}
            elif cat in ('canopy','roof_disconnection','pavement_disconnection'):
                expected={'ga_credit_sqft':Decimal(0),'ia_credit_sqft':Decimal(0),'iar_sqft':area*(Decimal('.5') if cat=='canopy' else Decimal(1))}
            else:raise ValueError('Unsupported existing allocation category')
            for key,value in expected.items():
                observed=decimal(item.get(key,0))
                if abs(value-observed)>Decimal('.000001'):raise ValueError('Existing allocation amount does not match supported rule')
                totals[key]+=observed
            allocations.append({**deepcopy(item),'area_sqft':float(area),'existing':True})
        except (ValueError,TypeError,KeyError,IndexError,AttributeError,ShapelyError) as exc:errors.append(str(exc))
    for key,total in totals.items():
        if abs(total-decimal(baseline.get('existing_'+key,0)))>Decimal('.000001'):errors.append('Existing allocation totals do not reconcile '+key)
    return allocations,errors


def _economics(case, gis, records, as_of, tariff):
    baseline=case.get('baseline')
    if not baseline:return {'baseline':None,'documented':_blocked(['Billing baseline missing']),'modeled':_blocked(['Billing baseline missing'])}
    t=tariff or default_tariff(); common={k:baseline[k] for k in ('accounts','property_type','undeveloped','bill_date') if k in baseline};common['tariff']=t
    try:
        if not RULES['effective_from']<=as_of.isoformat()<=RULES['verified_through']:raise ValueError('Assessment date outside verified rule period')
        if not t['effective_from']<=as_of.isoformat()<=t['verified_through']:raise ValueError('Assessment date outside verified tariff period')
        ga=decimal(baseline.get('ga_sqft'));ia=decimal(baseline.get('ia_sqft'))
        cg=decimal(baseline.get('existing_ga_credit_sqft',0));ci=decimal(baseline.get('existing_ia_credit_sqft',0));ir=decimal(baseline.get('existing_iar_sqft',0));old_npdes=decimal(baseline.get('npdes_fraction',0))
        base=monthly_bill(ga,ia,ga_credit_sqft=cg,ia_credit_sqft=ci,iar_sqft=ir,npdes_fraction=old_npdes,
                          minimum_mode='per_account_after_credit' if cg or ci or ir or old_npdes else 'parcel',**common)
    except (ValueError,KeyError) as exc:
        return {'baseline':None,'documented':_blocked([str(exc)]),'modeled':_blocked([str(exc)])}
    legacy=_legacy_benefits(case,gis)
    def scenario(documented, use_measure=False, use_benefits=True):
        total_ga,total_ia=ga,ia
        active=[r for r in records if use_benefits and r['status']=='screen_pass' and (not documented or r['basis']=='documented')]
        originals={r['id']:r for r in case.get('assessment',{}).get('records',[])}
        legacy_active=[(b,s) for b,s in legacy if use_benefits and (not documented or b.get('basis')=='documented')]
        if not use_measure and not active and not legacy_active:return _blocked(['No passing '+('documented' if documented else 'reviewed')+' existing-site or baseline benefits'])
        errors=[];regions=[];ledger=[];new_ga=Decimal(0);new_ia=Decimal(0);new_iar=Decimal(0)
        npdes=any(r['category']=='industrial_npdes' for r in active) or bool(old_npdes)
        if use_measure:
            measurement=gis.get('measurement',{})
            if measurement.get('complete') is not True:errors.append('Complete physical IA/GA measurements are missing')
            else:
                total_ga=_area_decimal(measurement.get('ga_sqft'));total_ia=_area_decimal(measurement.get('ia_sqft'))
        existing=bool(cg or ci or ir)
        if (active or legacy_active) and total_ga<500:errors.append('Minimum parcel gross area for credit is 500 square feet')
        if existing and baseline.get('existing_credits_spatially_reconciled') is not True:errors.append('Existing aggregate credits require spatial reconciliation')
        supplied_allocations=bool(case.get('assessment',{}).get('existing_credit_allocations'))
        existing_allocations,allocation_errors=_existing_allocations(case,gis,baseline) if existing or supplied_allocations else ([],[])
        if allocation_errors and (supplied_allocations or existing):errors.extend(allocation_errors)
        if existing_allocations and not allocation_errors:
            regions.extend((item['id'],shape(item['geometry'])) for item in existing_allocations)
            if npdes and not old_npdes:
                new_ga=-cg;new_ia=-ci;new_iar=-ir
                for item in existing_allocations:
                    area=_area_decimal(item['area_sqft']);cat=item['category'];j=Decimal(0)
                    if cat in ('management','direct_discharge'):g=i=area*Decimal('.87' if cat=='management' else '.97')
                    elif cat=='open_space':g=area*Decimal(str(open_space_factor(item['facts']['curve_number'],True)));i=Decimal(0)
                    else:g=i=Decimal(0);j=decimal(item.get('iar_sqft',0))
                    new_ga+=g;new_ia+=i;new_iar+=j
                    ledger.append({'id':item['id'],'category':cat,'area_sqft':float(area),'ga_credit_sqft':float(g),'ia_credit_sqft':float(i),'iar_sqft':float(j),'existing':True})
        if old_npdes and (any(r['category']!='industrial_npdes' for r in active) or legacy_active or use_measure):errors.append('Existing percentage-based NPDES baseline requires approved area-ledger reconciliation; unresolved')
        for r in active:
            if r['category']=='industrial_npdes':continue
            source=originals[r['id']];region=shape(source['geometry']);regions.append((r['id'],region))
            if existing and source.get('facts',{}).get('existing_overlap_reconciled') is not True:errors.append('New benefit overlap with existing credits is unreconciled')
            a=_area_decimal(r['managed_area_sqft']);factor=Decimal('.97' if npdes else '.90') if r['category']=='direct_discharge' else Decimal('.87' if npdes else '.80')
            new_ga+=a*factor;new_ia+=a*factor
            ledger.append({'id':r['id'],'category':r['category'],'area_sqft':float(a),'factor':float(factor),'ga_credit_sqft':float(a*factor),'ia_credit_sqft':float(a*factor),'iar_sqft':0})
        for b,s in legacy_active:
            region=shape(b['geometry']);regions.append((b['id'],region));a=_area_decimal(s['area_sqft']);cat=s['category']
            if existing and b.get('existing_overlap_reconciled') is not True:errors.append('Baseline benefit overlap with existing credits is unreconciled')
            if cat=='management':g=i=a*Decimal('.87' if npdes else '.8');j=Decimal(0)
            elif cat=='open_space':g=a*Decimal(str(open_space_factor(b['evidence']['curve_number'],npdes)));i=j=Decimal(0)
            else:g=i=Decimal(0);j=decimal(s['iar_sqft'])
            new_ga+=g;new_ia+=i;new_iar+=j
            ledger.append({'id':b['id'],'category':cat,'area_sqft':float(a),'ga_credit_sqft':float(g),'ia_credit_sqft':float(i),'iar_sqft':float(j)})
        for index,(identifier,region) in enumerate(regions):
            if any(region.intersection(other).area>1e-8 for _,other in regions[:index]):errors.append('Overlapping physical allocations: '+str(identifier))
        managed=sum((decimal(x['area_sqft']) for x in ledger if x['category'] not in ('open_space','canopy','roof_disconnection','pavement_disconnection')),Decimal(0))
        iar_area=sum((decimal(x['area_sqft']) for x in ledger if x['category'] in ('canopy','roof_disconnection','pavement_disconnection')),Decimal(0))
        # Existing areas remain occupied even when their recorded credit amount
        # is preserved rather than recomputed. Percentage credits are not physical
        # area: an 800 sqft credit can reserve a full 1000 sqft management region.
        preserved=existing_allocations if not allocation_errors and not (npdes and not old_npdes) else []
        managed+=sum((_area_decimal(x['area_sqft']) for x in preserved if x['category'] in ('management','direct_discharge')),Decimal(0))
        iar_area+=sum((_area_decimal(x['area_sqft']) for x in preserved if x['category'] in ('canopy','roof_disconnection','pavement_disconnection')),Decimal(0))
        open_area=sum((_area_decimal(x['area_sqft']) for x in ledger+preserved if x['category']=='open_space'),Decimal(0))
        reserved_aggregate_iar=ir if allocation_errors else Decimal(0)
        if managed+iar_area>total_ia-reserved_aggregate_iar:errors.append('Allocations exceed available physical impervious area')
        if open_area>total_ga-total_ia:errors.append('Open-space allocations exceed available physical open space')
        if npdes and (ir or new_iar):errors.append('NPDES with IAR requires an approved GA allocation interpretation; unresolved')
        if npdes and not old_npdes:
            # Manual 4.3.5.2: 87/97% already includes uplift on managed areas.
            # Only unmanaged IA receives the residual 7%; no second multiplier.
            unmanaged=total_ia-ir-new_iar-managed
            if unmanaged<0:errors.append('NPDES residual area is negative')
            residual_ia=max(Decimal(0),unmanaged)*Decimal('.07')
            residual_ga=(total_ga if not ledger else max(Decimal(0),unmanaged))*Decimal('.07')
            new_ia+=residual_ia;new_ga+=residual_ga
            ledger.append({'id':'npdes-residual','category':'industrial_npdes','ga_credit_sqft':float(residual_ga),'ia_credit_sqft':float(residual_ia),'iar_sqft':0,'area_sqft':float(max(Decimal(0),unmanaged))})
        if ci+new_ia+ir+new_iar>total_ia:errors.append('Credits exceed remaining IA')
        if cg+new_ga>total_ga:errors.append('Credits exceed GA')
        if errors:return _blocked(errors)
        try:
            bill=monthly_bill(total_ga,total_ia,ga_credit_sqft=cg+new_ga,ia_credit_sqft=ci+new_ia,iar_sqft=ir+new_iar,
                              npdes_fraction=old_npdes,minimum_mode='per_account_after_credit' if active or legacy_active or existing or old_npdes else 'parcel',**common)
        except ValueError as exc:return _blocked([str(exc)])
        saving=cents(decimal(base['monthly_total'])-decimal(bill['monthly_total']))
        basis='documented' if documented and baseline.get('actual_bill_verified') is True and not use_measure else 'conditional'
        return {'status':'calculated','basis':basis,'gross_monthly_reduction':float(saving),'gross_annual_reduction':float(saving*12),
                'bill':bill,'ledger':{'existing_ga_credit_sqft':float(cg),'existing_ia_credit_sqft':float(ci),'existing_iar_sqft':float(ir),
                'allocations':ledger,'new_ga_credit_sqft':float(new_ga),'new_ia_credit_sqft':float(new_ia),'new_iar_sqft':float(new_iar)},
                'assumptions':(['Complete GIS measurements used; independent empirical validation still required'] if use_measure else [])+([] if baseline.get('actual_bill_verified') else ['Actual account bill, payer and special-rate enrollment are unverified'])+['Gross current-rate illustration; no approval, award or realized savings asserted']}
    return {'baseline':base,'documented':scenario(True),'modeled':scenario(False),
            'measurement_only':scenario(True,True,False),'documented_combined':scenario(True,True),'modeled_combined':scenario(False,True),'tariff':t,
            'claim':'One baseline minus one reconciled final bill; annual reduction is twelve times monthly. No refund included.'}


def historical_flags(case, economics):
    """Review flags retain periods and evidence; do not calculate recoveries."""
    baseline=case.get('baseline') or {};flags=[];base=economics.get('baseline') or {}
    for observed_field,label in (('actual_bill_total','Actual bill'),('published_monthly_total','Public snapshot')):
        observed=baseline.get(observed_field)
        if observed is None or base.get('monthly_total') is None:continue
        try:delta=cents(decimal(base['monthly_total'])-decimal(observed))
        except ValueError:continue
        if delta:
            flags.append({'kind':'billing_discrepancy','status':'review_only','affected_from':baseline.get('bill_date'),
                          'affected_through':baseline.get('bill_period_end',baseline.get('bill_date')),
                          'observed_discrepancy':float(delta),'basis':label+' differs from current tariff illustration',
                          'source_basis':deepcopy(baseline.get('source',case.get('sources',[]))),
                          'missing':['Applicable historical tariff','Actual invoices and account allocations','Award/effective-period records'],
                          'refund_entitlement':None,'claim':'Review issue only; no refund or historical debt determined'})
    for record in case.get('assessment',{}).get('historical_issues',[]):
        flags.append({**deepcopy(record),'status':'review_only','refund_entitlement':None,
                      'claim':'Manually recorded issue for review; excluded from ongoing savings'})
    return flags


def evaluate_assessment(case, gis_result, as_of=None, tariff=None):
    assessment=case.get('assessment',{})
    _validate_assessment_inputs(assessment)
    validate_references({**assessment,'records':assessment.get('records',[])+assessment.get('existing_credit_allocations',[])})
    day=_day(as_of) if as_of else date.today();records=[]
    for record in case.get('assessment',{}).get('records',[]):
        if record.get('category') in LABELS:records.append(screen_record(record,case,gis_result,day))
    categories=[]
    for category,label in LABELS.items():
        selected=[r for r in records if r['category']==category]
        statuses={r['status'] for r in selected}
        status='screen_pass' if 'screen_pass' in statuses else 'missing_evidence' if not selected else 'candidate' if 'candidate' in statuses else 'requirements_failed' if 'requirements_failed' in statuses else 'missing_evidence' if 'missing_evidence' in statuses else 'rejected'
        categories.append({'category':category,'label':label,'status':status,'records':selected,
                           'missing':['No reviewed evidence records supplied'] if not selected else [],'managed_area_sqft':None if not selected else sum(r['managed_area_sqft'] for r in selected if r['managed_area_sqft'] is not None) if any(r['managed_area_sqft'] is not None for r in selected) else None})
    economics=_economics(case,gis_result,records,day,tariff)
    result={'rule_version':VERSION,'as_of':day.isoformat(),'categories':categories,'economics':economics,
            'historical_flags':historical_flags(case,economics),
            'rules':{**deepcopy(RULES),'applicability':'applicable' if RULES['effective_from']<=day.isoformat()<=RULES['verified_through'] else 'outside_verified_period'}}
    result['assessment_sha256']=sha256(json.dumps(result,sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest()
    return result
