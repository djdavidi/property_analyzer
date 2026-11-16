"""PWD existing-site screens over frozen physical GIS; never acquires or reroutes.

A screen_pass describes reviewed prerequisites, not a grant, award or legal opinion.
The separate area ledger below implements Manual 4.3.5; it never adds independently
calculated savings or applies a further seven percent to already uplifted credits.
"""
from copy import deepcopy
from datetime import date, timedelta
from decimal import Decimal
from hashlib import sha256
from urllib.parse import urlparse
import json
from shapely.geometry import shape
from shapely.errors import ShapelyError
from drainage_core.geometry import case_area_sqft, effective_features
from drainage_core.evidence import validate_references
from .billing import (monthly_bill, default_tariff, cents, decimal, bill_terms, undeveloped_unknown,
                      merge_status_alternatives, STATUS_ALTERNATIVES, billed_area_check)
from .rules import screen, open_space_factor, factor, MANUAL_URL, TARIFF_URL
from .prerequisites import case_vetoes

VERSION = 'pwd-existing-site-2026-09-v1'
LABELS = {'green_roof':'Existing green roofs', 'permeable_pavement':'Existing permeable pavement',
          'direct_discharge':'Direct surface-water discharge', 'industrial_npdes':'Industrial NPDES'}
RULES = {'version':VERSION, 'verified_on':'2026-11-15', 'effective_from':'2026-09-01',
         'verified_through':'2027-08-31', 'manual':MANUAL_URL, 'tariff':TARIFF_URL,
         'gis_area_numerical_precision_sqft':'0.000000001',
         'manual_sections':['4.3.2.2','4.3.3.1','4.3.3.2','4.3.4','4.3.5','4.4.1','4.5.1','4.5.5'],
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


def _lagging_dmr_period(facts, through, as_of, output, missing):
    """Manual 4.3.4 / 4.5.5: compliance during the preceding twelve months, shown by
    the required PADEP DMRs "from the previous 12 months". DMR periods end before
    the assessment date. A lagging period is complete evidence only while the next
    required DMR is not yet due (a sourced ``next_dmr_due`` fact); otherwise the
    record needs an update. Stale evidence is missing, never a failed permit.
    """
    output.setdefault('date_notes',[])
    due=facts.get('next_dmr_due')
    if through>=_prior_year(as_of) and due:
        try:
            if _day(due)>as_of:
                output['date_notes'].append('Latest DMR period ends '+through.isoformat()+'; next required DMR is due '+_day(due).isoformat()+', so the reporting cycle is current')
                return True
        except (ValueError,TypeError):return False
    output.setdefault('needs_update',[]).append('compliance_through')
    missing.append('compliance_through_current' if due else 'next_dmr_due')
    output['date_notes'].append('Compliance evidence ends '+through.isoformat()+' before the assessment date; supply the reporting schedule or later DMRs (needs update, not a failed requirement)')
    return None


def _administratively_continued(facts, expires, output, missing, failed):
    """25 Pa. Code 92a.7(b)-(c): an expiring NPDES permit is automatically continued
    when the permittee submitted a timely reissuance application (92a.75(a): at least
    180 days before expiry unless DEP permitted a later date) and DEP has not acted.
    ``administratively_continued`` is the reviewed fact; an expired permit without it
    lacks evidence rather than failing.
    """
    continued=facts.get('administratively_continued')
    output.setdefault('date_notes',[])
    if continued is None:
        missing.append('administratively_continued')
        output['date_notes'].append('Permit expiry '+expires.isoformat()+' precedes the assessment date; continuation under 25 Pa. Code 92a.7 is not established')
        return None
    if continued is not True:return False
    submitted=facts.get('renewal_application_submitted_on')
    if submitted:
        try:
            limit=expires-timedelta(days=180)
            if _day(submitted)>limit and facts.get('later_renewal_date_permitted') is not True:
                failed.append('renewal_application_submitted_on');return None
        except (ValueError,TypeError):failed.append('renewal_application_submitted_on');return None
    output['date_notes'].append('Expired permit treated as administratively continued under 25 Pa. Code 92a.7(b)-(c) (reviewed fact)')
    return True


def _managed_surfaces(record, category, geom, case, gis):
    """Manual 4.3.2.2 / 4.3.3.2: IA credit is for IA Managed, with equivalent GA
    underneath. A real SMP or surface-discharge drainage area may also contain open
    space. That open space is credited only as the manual allows (4.3.3.1 notes):
    direct discharge to surface water -> 90% GA (97% with NPDES, 4.3.5.4) regardless
    of cover or soil; an approved SMP sized for it with PWD design pre-approval ->
    80% GA (87% with NPDES). Unresolved surfaces are reported, never credited.
    """
    geometries=gis['measurement']['geometries']
    empty={'type':'GeometryCollection','geometries':[]}
    ia_part=geom.intersection(shape(geometries['physical_ia']))
    open_part=geom.intersection(shape(geometries.get('pervious') or empty))
    ia_area=case_area_sqft(ia_part,case) if not ia_part.is_empty else 0.
    open_area=case_area_sqft(open_part,case) if not open_part.is_empty else 0.
    total=case_area_sqft(geom,case)
    out={'managed_ia_sqft':ia_area,'managed_open_space_sqft':open_area,
         'managed_unresolved_sqft':max(0.,total-ia_area-open_area)}
    facts=record.get('facts') or {}
    if open_area<.000001:out['open_space_credit']={'status':'not_applicable'}
    elif category=='direct_discharge':
        out['open_space_credit']={'status':'screen_pass','basis':'manual 4.3.3.1 note: open space discharging directly to surface water, 90% regardless of cover or soil'}
    else:
        needed=('open_space_smp_sizing_confirmed','open_space_design_preapproval')
        absent=[k for k in needed if facts.get(k) is None];bad=[k for k in needed if facts.get(k) is not None and facts.get(k) is not True]
        out['open_space_credit']={'status':'requirements_failed' if bad else 'missing_evidence' if absent else 'screen_pass',
            'missing':absent,'failed':bad,
            'basis':'manual 4.3.3.1 note: open space managed by an approved SMP sized for it, with PWD design-phase pre-approval, may receive 80%'}
    return out


def _evidence(record, case):
    refs=record.get('evidence_refs') or []
    attachments={a['id'] for a in case.get('assessment',{}).get('attachments',[]) if 'id' in a}
    return any(isinstance(r,dict) and (_source_url(r.get('source_url'))
               or r.get('attachment_id') in attachments) for r in refs)


def _support_review(record):
    """A URL is a citation, not proof. Require an explicit human support review.

    This records an assertion by the reviewer; it never claims automatic source
    authentication or independent agency confirmation.
    """
    review=record.get('evidence_review') or {}
    keys={k for k,v in record.get('facts',{}).items() if v is not None}
    return (isinstance(review,dict) and all(review.get(k) is True for k in
        ('support_reviewed','property_match','period_match')) and
        isinstance(review.get('note'),str) and bool(review['note'].strip()) and
        isinstance(review.get('fact_keys'),list) and all(isinstance(k,str) for k in review['fact_keys']) and keys<=set(review['fact_keys']) and
        any(r.get('page') or r.get('locator') for r in record.get('evidence_refs',[])))


def screen_record(record, case, gis, as_of):
    category=record['category']; facts=record.get('facts') or {}; missing=[]; failed=[]
    output={key:deepcopy(record.get(key)) for key in ('id','category','decision','basis','evidence_refs','source')}
    output.update(label=LABELS[category],missing=missing,failed=failed,managed_area_sqft=None,
                  managed_ia_sqft=None,managed_open_space_sqft=None,managed_unresolved_sqft=None,
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
    if not _support_review(record):missing.append('property_period_fact_support_review')
    output['evidence_verification']='Human assertions linked to cited evidence; source content not automatically authenticated'
    if record.get('source_update',{}).get('status')=='pending_review':missing.append('source_update_review')
    if category=='industrial_npdes':
        for key in NPDES:require(key)
        if not facts.get('permit_id'):missing.append('permit_id')
        if facts.get('permit_type') in ('construction','municipal','no_exposure','terminated'):failed.append('permit_type')
        for key in ('effective_from','expires_on','compliance_from','compliance_through'):
            if not facts.get(key):missing.append(key);continue
            try:
                day=_day(facts[key])
                if key=='effective_from':valid=day<=as_of
                elif key=='compliance_from':valid=day<=_prior_year(as_of)
                elif key=='compliance_through':valid=day>=as_of or _lagging_dmr_period(facts,day,as_of,output,missing)
                else:valid=day>=as_of or _administratively_continued(facts,day,output,missing,failed)
                if valid is False:failed.append(key)
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
                parcel=shape(case['parcel'])
                if geom.difference(parcel).area>1e-8:failed.append('managed_geometry_inside_parcel')
                output.update(_managed_surfaces(record,category,geom,case,gis))
                if output['managed_ia_sqft']<.000001 and output['managed_open_space_sqft']<.000001:
                    # Only unresolved ground: neither managed IA nor open space is established.
                    missing.append('managed_area_surface_classification')
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
    from drainage_core.installation import installation_issues
    if category!='industrial_npdes':failed.extend(installation_issues(facts,as_of))
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


# Report table rows (historical names) -> the single assessment ledger scenario.
BILLING_VIEW=(('appeal_only','measurement_only'),('credit_only','modeled'),('combined','modeled_combined'),
              ('documented_credit_only','documented'),('documented_combined','documented_combined'))


def ledger_billing_view(economics):
    """The report's billing table read from ``_economics`` (decision D7).

    There is one savings path: these rows are relabelled ledger scenarios, never
    a second calculation. Blocked scenarios carry no totals or savings.
    """
    base=economics.get('baseline')
    if not isinstance(base,dict):
        reasons=list(dict.fromkeys((economics.get('documented') or {}).get('reasons') or ['Billing baseline unavailable']))
        return {'status':'blocked','reason':'; '.join(reasons),'reasons':reasons,'source':'assessment_economics'}
    view={'source':'assessment_economics','baseline':deepcopy(base),
          'claim':'Rows are the assessment ledger scenarios; alternatives, never additive.'}
    for key in ('billed_area_check','undeveloped_status'):
        if key in economics:view[key]=deepcopy(economics[key])
    for legacy,key in BILLING_VIEW:
        s=economics.get(key) or _blocked(['Scenario unavailable'])
        calculated=s.get('status')=='calculated'
        row={**(deepcopy(s.get('bill')) if calculated and s.get('bill') else {}),
             'status':s.get('status'),'basis':s.get('basis'),'reasons':list(s.get('reasons',[])),
             'monthly_savings':s.get('gross_monthly_reduction'),'annual_savings':s.get('gross_annual_reduction'),
             'ledger':deepcopy(s.get('ledger')),'assumptions':list(s.get('assumptions',[])),'ledger_scenario':key}
        if not calculated:row['monthly_total']=None
        if 'alternatives' in s:row['alternatives']=deepcopy(s['alternatives'])
        view[legacy]=row
    return view


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


IA_MANAGED_CATEGORIES = ('management','direct_discharge','green_roof','permeable_pavement')
OPEN_CATEGORIES = ('open_space','open_space_direct_discharge')
IAR_CATEGORIES = ('canopy','roof_disconnection','pavement_disconnection')
ECONOMIC_KEYS = ('documented','modeled','measurement_only','documented_combined','modeled_combined')


def _factors(direct, npdes):
    """Manual 4.3.5.1-4.3.5.4 maximum credit factors (config-loaded)."""
    if direct:
        return (factor('surface_discharge_npdes_factor' if npdes else 'surface_discharge_factor'),
                factor('surface_discharge_open_space_npdes_factor' if npdes else 'surface_discharge_open_space_factor'))
    return (factor('non_surface_management_npdes_factor' if npdes else 'non_surface_management_factor'),
            factor('managed_open_space_npdes_factor' if npdes else 'managed_open_space_factor'))


def _open_space_credit(area, curve_number, npdes):
    """Table A-2 open-space GA credit. With NPDES (manual 4.3.5.2) every uncredited
    area keeps the 7% residual; a Table A-2 factor below 7% (CN 74 -> 4.35%) would
    lower the parcel's credit, so that area stays in the residual instead."""
    rate=Decimal(str(open_space_factor(curve_number,npdes)))
    if npdes and rate<factor('npdes_unmanaged_area_factor'):
        return Decimal(0),False
    return area*rate,rate>0


def _allocation_surfaces(geometry, case, gis):
    geometries=gis['measurement']['geometries']
    empty={'type':'GeometryCollection','geometries':[]}
    ia_part=geometry.intersection(shape(geometries['physical_ia']))
    open_part=geometry.intersection(shape(geometries.get('pervious') or empty))
    ia=_area_decimal(case_area_sqft(ia_part,case)) if not ia_part.is_empty else Decimal(0)
    open_area=_area_decimal(case_area_sqft(open_part,case)) if not open_part.is_empty else Decimal(0)
    return ia,open_area,_area_decimal(case_area_sqft(geometry,case))-ia-open_area


def _existing_allocations(case, gis, baseline):
    """An approved itemized ledger must reconcile every recorded existing credit.

    Management/direct-discharge drainage areas may include open space (manual
    4.3.2.2, 4.3.3.1 notes): IA credit = factor x IA Managed; GA credit is the
    same amount, plus the open-space factor on the open part when that part was
    credited. ``open_space_direct_discharge`` is the GA-only 90% open-space
    surface-discharge credit of manual 4.3.3.1.
    """
    items=case.get('assessment',{}).get('existing_credit_allocations',[])
    if not items:return [],['Detailed existing credit allocation ledger missing']
    errors=[];allocations=[];totals={key:Decimal(0) for key in ('ga_credit_sqft','ia_credit_sqft','iar_sqft')}
    tolerance=Decimal('.000001')
    for item in items:
        try:
            if item.get('facts',{}).get('approved_ledger_confirmed') is not True or not _evidence(item,case):
                raise ValueError('Approved existing allocation evidence missing')
            geometry=shape(item['geometry']);area=_area_decimal(case_area_sqft(geometry,case));cat=item['category']
            if geometry.is_empty or not geometry.is_valid or geometry.geom_type not in ('Polygon','MultiPolygon'):raise ValueError('Invalid existing allocation geometry')
            extra={}
            observed={key:decimal(item.get(key,0)) for key in totals}
            if cat in ('management','direct_discharge'):
                ia_part,open_part,unresolved=_allocation_surfaces(geometry,case,gis)
                if unresolved>tolerance:raise ValueError('Existing allocation includes unresolved surfaces')
                rate,open_rate=_factors(cat=='direct_discharge',False)
                ia_credit=ia_part*rate
                credited_open=open_part if open_part>0 and abs(observed['ga_credit_sqft']-ia_credit-open_part*open_rate)<=tolerance else Decimal(0)
                expected={'ga_credit_sqft':ia_credit+credited_open*open_rate,'ia_credit_sqft':ia_credit,'iar_sqft':Decimal(0)}
                extra={'area_sqft':float(ia_part),'open_space_area_sqft':float(credited_open),'drainage_area_sqft':float(area)}
            else:
                target='pervious' if cat in OPEN_CATEGORIES else 'canopy_ground_ia' if cat=='canopy' else 'physical_ia'
                if geometry.difference(shape(gis['measurement']['geometries'][target])).area>1e-8:raise ValueError('Existing allocation is outside its physical area')
                if cat=='open_space':expected={'ga_credit_sqft':area*Decimal(str(open_space_factor(item['facts']['curve_number']))),'ia_credit_sqft':Decimal(0),'iar_sqft':Decimal(0)}
                elif cat=='open_space_direct_discharge':expected={'ga_credit_sqft':area*factor('surface_discharge_open_space_factor'),'ia_credit_sqft':Decimal(0),'iar_sqft':Decimal(0)}
                elif cat in IAR_CATEGORIES:
                    expected={'ga_credit_sqft':Decimal(0),'ia_credit_sqft':Decimal(0),'iar_sqft':area*(factor('canopy_ground_ia_overlap_iar_factor') if cat=='canopy' else Decimal(1))}
                else:raise ValueError('Unsupported existing allocation category')
            for key,value in expected.items():
                if abs(value-observed[key])>tolerance:raise ValueError('Existing allocation amount does not match supported rule')
                totals[key]+=observed[key]
            allocations.append({**deepcopy(item),'area_sqft':float(area),**extra,'existing':True})
        except (ValueError,TypeError,KeyError,IndexError,AttributeError,ShapelyError) as exc:errors.append(str(exc))
    for key,total in totals.items():
        if abs(total-decimal(baseline.get('existing_'+key,0)))>tolerance:errors.append('Existing allocation totals do not reconcile '+key)
    return allocations,errors


def _hypothetical_benefits(benefits):
    """Adapter alternatives (``system_pricing.price_benefit``) as ledger benefits.

    Each keeps its whole possible geometry for overlap checks while crediting its
    stated area (a weighted fraction may be smaller than the geometry). Saved case
    benefits are not credited alongside: each priced system is one alternative.
    """
    out=[];errors=[]
    for b in benefits:
        r=deepcopy(b);r.setdefault('basis','modeled');r.setdefault('existing_overlap_reconciled',True)
        try:s=screen(r['category'],r['area_sqft'],r.get('evidence'))
        except (ValueError,KeyError) as exc:errors.append(str(exc));continue
        if s['status']!='screen_pass':
            errors.append('Alternative '+str(r.get('id'))+' prerequisites: '+', '.join(s['failed']+s['missing']));continue
        out.append((r,s))
    return out,errors


def _economics(case, gis, records, as_of, tariff, hypothetical=None):
    """One ledger for every savings figure. Unknown undeveloped status on a parcel
    under 5,000 sq ft GA yields explicit developed/undeveloped alternatives (D6).

    ``hypothetical`` (list of benefits) replaces saved case benefits with adapter
    alternatives priced by this same ledger (D7); see ``_hypothetical_benefits``."""
    if case.get('assessment',{}).get('baseline_refresh',{}).get('status')=='pending_review':
        blocked=_blocked(['New public billing/credit facts differ from the retained baseline; review required'])
        return {'baseline':None,**{k:deepcopy(blocked) for k in ECONOMIC_KEYS}}
    baseline=case.get('baseline')
    if not baseline:return {'baseline':None,'documented':_blocked(['Billing baseline missing']),'modeled':_blocked(['Billing baseline missing'])}
    t=tariff or default_tariff()
    measured_ga=(gis.get('measurement') or {}).get('ga_sqft')
    if undeveloped_unknown(baseline,baseline.get('ga_sqft'),measured_ga,tariff=t):
        outputs={name:_economics_once(case,{**baseline,'undeveloped':flag},gis,records,as_of,t,hypothetical) for name,flag in STATUS_ALTERNATIVES}
        if any(output.get('baseline') is None for output in outputs.values()):return outputs[STATUS_ALTERNATIVES[0][0]]
        return merge_status_alternatives(outputs,ECONOMIC_KEYS,_blocked)
    return _economics_once(case,baseline,gis,records,as_of,t,hypothetical)


def _economics_once(case, baseline, gis, records, as_of, t, hypothetical=None):
    try:
        common,allocation=bill_terms(baseline,t)
        if not RULES['effective_from']<=as_of.isoformat()<=RULES['verified_through']:raise ValueError('Assessment date outside verified rule period')
        if not t['effective_from']<=as_of.isoformat()<=t['verified_through']:raise ValueError('Assessment date outside verified tariff period')
        ga=decimal(baseline.get('ga_sqft'));ia=decimal(baseline.get('ia_sqft'))
        cg=decimal(baseline.get('existing_ga_credit_sqft',0));ci=decimal(baseline.get('existing_ia_credit_sqft',0));ir=decimal(baseline.get('existing_iar_sqft',0));old_npdes=decimal(baseline.get('npdes_fraction',0))
        base=monthly_bill(ga,ia,ga_credit_sqft=cg,ia_credit_sqft=ci,iar_sqft=ir,npdes_fraction=old_npdes,**common)
    except (ValueError,KeyError) as exc:
        return {'baseline':None,'documented':_blocked([str(exc)]),'modeled':_blocked([str(exc)])}
    if allocation:base['allocation_status']=allocation
    for field,target in (('published_monthly_total','published_difference'),('actual_bill_total','actual_bill_difference')):
        if baseline.get(field) is not None:
            try:base[target]=float(cents(decimal(base['monthly_total'])-decimal(baseline[field])))
            except ValueError:pass
    vetoes=case_vetoes(case)
    residual_rate=factor('npdes_unmanaged_area_factor')
    minimum_credit_ga=factor('credit_minimum_gross_area_sqft')
    if hypothetical is None:legacy,hypothetical_errors=_legacy_benefits(case,gis),[]
    else:legacy,hypothetical_errors=_hypothetical_benefits(hypothetical)
    def scenario(documented, use_measure=False, use_benefits=True):
        total_ga,total_ia=ga,ia
        active=[r for r in records if use_benefits and r['status']=='screen_pass' and (not documented or r['basis']=='documented')]
        originals={r['id']:r for r in case.get('assessment',{}).get('records',[])}
        legacy_active=[(b,s) for b,s in legacy if use_benefits and (not documented or b.get('basis')=='documented')]
        if not use_measure and not active and not legacy_active:return _blocked((hypothetical_errors if use_benefits and not documented else [])+['No passing '+('documented' if documented else 'reviewed')+' existing-site or baseline benefits'])
        errors=[];regions=[];ledger=[];new_ga=Decimal(0);new_ia=Decimal(0);new_iar=Decimal(0)
        if use_benefits and not documented:errors.extend(hypothetical_errors)
        if active or legacy_active:errors.extend(vetoes)
        npdes=any(r['category']=='industrial_npdes' for r in active) or bool(old_npdes)
        if use_measure:
            measurement=gis.get('measurement',{})
            if measurement.get('complete') is not True:errors.append('Complete physical IA/GA measurements are missing')
            else:
                total_ga=_area_decimal(measurement.get('ga_sqft'));total_ia=_area_decimal(measurement.get('ia_sqft'))
        existing=bool(cg or ci or ir)
        if (active or legacy_active) and total_ga<minimum_credit_ga:errors.append('Minimum parcel gross area for credit is 500 square feet')
        if existing and baseline.get('existing_credits_spatially_reconciled') is not True:errors.append('Existing aggregate credits require spatial reconciliation')
        supplied_allocations=bool(case.get('assessment',{}).get('existing_credit_allocations'))
        existing_allocations,allocation_errors=_existing_allocations(case,gis,baseline) if existing or supplied_allocations else ([],[])
        if allocation_errors and (supplied_allocations or existing):errors.extend(allocation_errors)
        uplift=bool(npdes and not old_npdes)
        if existing_allocations and not allocation_errors:
            regions.extend((item['id'],shape(item['geometry'])) for item in existing_allocations)
            if uplift:
                # Manual 4.3.5.2/4.3.5.4: NPDES replaces 80/90% with 87/97%; the
                # recorded amounts are removed and recomputed, never added twice.
                new_ga=-cg;new_ia=-ci;new_iar=-ir
                for item in existing_allocations:
                    area=_area_decimal(item['area_sqft']);cat=item['category'];j=Decimal(0);open_area=Decimal(0);applied=True
                    if cat in ('management','direct_discharge'):
                        rate,open_rate=_factors(cat=='direct_discharge',True);open_area=_area_decimal(item.get('open_space_area_sqft',0))
                        i=area*rate;g=i+open_area*open_rate
                    elif cat=='open_space':g,applied=_open_space_credit(area,item['facts']['curve_number'],True);i=Decimal(0)
                    elif cat=='open_space_direct_discharge':g=area*factor('surface_discharge_open_space_npdes_factor');i=Decimal(0)
                    else:g=i=Decimal(0);j=decimal(item.get('iar_sqft',0))
                    new_ga+=g;new_ia+=i;new_iar+=j
                    ledger.append({'id':item['id'],'category':cat,'area_sqft':float(area),'open_space_area_sqft':float(open_area),
                                   'credit_applied':applied,'ga_credit_sqft':float(g),'ia_credit_sqft':float(i),'iar_sqft':float(j),'existing':True})
        if old_npdes and (any(r['category']!='industrial_npdes' for r in active) or legacy_active or use_measure):errors.append('Existing percentage-based NPDES baseline requires approved area-ledger reconciliation; unresolved')
        for r in active:
            if r['category']=='industrial_npdes':continue
            source=originals[r['id']];region=shape(source['geometry']);regions.append((r['id'],region))
            if existing and source.get('facts',{}).get('existing_overlap_reconciled') is not True:errors.append('New benefit overlap with existing credits is unreconciled')
            managed_ia=r.get('managed_ia_sqft');a=_area_decimal(managed_ia if managed_ia is not None else r['managed_area_sqft'])
            rate,open_rate=_factors(r['category']=='direct_discharge',npdes)
            open_area=_area_decimal(r.get('managed_open_space_sqft') or 0) if (r.get('open_space_credit') or {}).get('status')=='screen_pass' else Decimal(0)
            g=a*rate+open_area*open_rate;i=a*rate
            new_ga+=g;new_ia+=i
            ledger.append({'id':r['id'],'category':r['category'],'area_sqft':float(a),'open_space_area_sqft':float(open_area),
                           'factor':float(rate),'open_space_factor':float(open_rate) if open_area else None,
                           'ga_credit_sqft':float(g),'ia_credit_sqft':float(i),'iar_sqft':0})
        for b,s in legacy_active:
            # An unlocated adapter unit sensitivity has no geometry; it cannot be
            # reconciled against recorded existing credits.
            if not b.get('geometry') and (existing or supplied_allocations):errors.append('Unlocated area cannot be reconciled against existing credit allocations')
            region=shape(b.get('geometry') or {'type':'GeometryCollection','geometries':[]});regions.append((b['id'],region));a=_area_decimal(s['area_sqft']);cat=s['category'];applied=True
            if existing and b.get('existing_overlap_reconciled') is not True:errors.append('Baseline benefit overlap with existing credits is unreconciled')
            if cat=='management':g=i=a*_factors(False,npdes)[0];j=Decimal(0)
            elif cat=='open_space':g,applied=_open_space_credit(a,b['evidence']['curve_number'],npdes);i=j=Decimal(0)
            else:g=i=Decimal(0);j=decimal(s['iar_sqft'])
            new_ga+=g;new_ia+=i;new_iar+=j
            ledger.append({'id':b['id'],'category':cat,'area_sqft':float(a),'credit_applied':applied,
                           'ga_credit_sqft':float(g),'ia_credit_sqft':float(i),'iar_sqft':float(j)})
        for index,(identifier,region) in enumerate(regions):
            if any(region.intersection(other).area>1e-8 for _,other in regions[:index]):errors.append('Overlapping physical allocations: '+str(identifier))
        def total(rows,cats,key='area_sqft',only_applied=False):
            return sum((_area_decimal(x.get(key) or 0) for x in rows if x['category'] in cats and (not only_applied or x.get('credit_applied',True))),Decimal(0))
        # Existing areas remain occupied even when their recorded credit amount
        # is preserved rather than recomputed. Percentage credits are not physical
        # area: an 800 sqft credit can reserve a full 1000 sqft management region.
        preserved=existing_allocations if not allocation_errors and not uplift else []
        rows=ledger+preserved
        managed=total(rows,IA_MANAGED_CATEGORIES)
        iar_area=total(rows,IAR_CATEGORIES)
        open_area=total(rows,OPEN_CATEGORIES)+total(rows,IA_MANAGED_CATEGORIES,'open_space_area_sqft')
        open_credited=total(ledger,OPEN_CATEGORIES,only_applied=True)+total(ledger,IA_MANAGED_CATEGORIES,'open_space_area_sqft')
        reserved_aggregate_iar=ir if allocation_errors else Decimal(0)
        if managed+iar_area>total_ia-reserved_aggregate_iar:errors.append('Allocations exceed available physical impervious area')
        if open_area>total_ga-total_ia:errors.append('Open-space allocations exceed available physical open space')
        if npdes and (ir or new_iar):errors.append('NPDES with IAR requires an approved GA allocation interpretation; unresolved')
        if uplift:
            # Manual 4.3.5.2: uncredited IA receives 7% toward IA and the GA under it;
            # with no other credit the whole parcel receives 7% of IA and GA. One base
            # in both cases: residual GA = 7% x (GA - GA already credited by area), so
            # adding a qualifying credit can never reduce the total (review B1).
            unmanaged=total_ia-ir-new_iar-managed
            if unmanaged<0:errors.append('NPDES residual area is negative')
            residual_ga_base=max(Decimal(0),total_ga-managed-open_credited)
            residual_ia=max(Decimal(0),unmanaged)*residual_rate
            residual_ga=residual_ga_base*residual_rate
            new_ia+=residual_ia;new_ga+=residual_ga
            ledger.append({'id':'npdes-residual','category':'industrial_npdes','ga_credit_sqft':float(residual_ga),'ia_credit_sqft':float(residual_ia),'iar_sqft':0,
                           'area_sqft':float(max(Decimal(0),unmanaged)),'residual_ga_base_sqft':float(residual_ga_base)})
        if ci+new_ia+ir+new_iar>total_ia:errors.append('Credits exceed remaining IA')
        if cg+new_ga>total_ga:errors.append('Credits exceed GA')
        if errors:return _blocked(errors)
        try:
            bill=monthly_bill(total_ga,total_ia,ga_credit_sqft=cg+new_ga,ia_credit_sqft=ci+new_ia,iar_sqft=ir+new_iar,
                              npdes_fraction=old_npdes,**common)
        except ValueError as exc:return _blocked([str(exc)])
        saving=cents(decimal(base['monthly_total'])-decimal(bill['monthly_total']))
        basis='documented' if documented and baseline.get('actual_bill_verified') is True and not use_measure else 'conditional'
        assumptions=(['Complete GIS measurements used; independent empirical validation still required'] if use_measure else [])
        assumptions+=([] if baseline.get('actual_bill_verified') else ['Actual account bill, payer and special-rate enrollment are unverified'])
        assumptions+=([allocation['note']] if allocation else [])
        assumptions+=['Gross current-rate illustration; no approval, award or realized savings asserted']
        return {'status':'calculated','basis':basis,'gross_monthly_reduction':float(saving),'gross_annual_reduction':float(saving*12),
                'bill':bill,'ledger':{'existing_ga_credit_sqft':float(cg),'existing_ia_credit_sqft':float(ci),'existing_iar_sqft':float(ir),
                'allocations':ledger,'new_ga_credit_sqft':float(new_ga),'new_ia_credit_sqft':float(new_ia),'new_iar_sqft':float(new_iar)},
                'assumptions':assumptions}
    return {'baseline':base,'documented':scenario(True),'modeled':scenario(False),
            'measurement_only':scenario(True,True,False),'documented_combined':scenario(True,True),'modeled_combined':scenario(False,True),'tariff':t,
            'billed_area_check':billed_area_check(baseline,base),
            'claim':'One baseline minus one reconciled final bill; annual reduction is twelve times monthly. No refund included.'}


def research_economics(case, gis, records, as_of, tariff):
    """Counterfactual management value of frozen modeled catchments, never a fact.

    Reuse the existing reconciled ledger/minima/rule blocks. Assumed prerequisites
    live only in a local copy; no confirmed record or evidence is persisted.
    """
    research=gis.get('research_drainage',{})
    if not research.get('primary'):return {'status':'unavailable','scenarios':[]}
    from shapely.geometry import mapping
    from drainage_core.geometry import union
    reserved=[]
    for r in case.get('assessment',{}).get('existing_credit_allocations',[])+case.get('assessment',{}).get('records',[]):
        if r.get('geometry') and r.get('decision')!='rejected':
            try:reserved.append(shape(r['geometry']))
            except (ValueError,TypeError,ShapelyError):pass
    for f in effective_features(case):
        if f.get('properties',{}).get('layer')=='benefit':reserved.append(shape(f['geometry']))
    occupied=union(reserved); scenarios=[]
    # H16: surface GSI receivers' own beds are never contributing IA.
    from drainage_core.research import feature_inputs
    try:beds=union([shape(f['geometry']) for f in feature_inputs(case)[0] if f.get('role')=='gsi'
                    and shape(f['geometry']).geom_type in ('Polygon','MultiPolygon')])
    except (ValueError,TypeError,KeyError,ShapelyError):beds=union([])
    # Unknown prerequisites are assumed below; known-false ones are not (R1).
    vetoes=case_vetoes(case)
    assumed={key:True for key in ('physical_area_confirmed','parcel_allocation_confirmed','account_current',
             'routing_confirmed','approved_record_drawings','current_condition_confirmed',
             'maintenance_documented','professional_reviewed')}
    assumed['treatment_depth_inches']=1.5
    from .system_pricing import catchment_route,combine_routes
    for name,run in [('nominal',research['primary'])]+[(r['name'],r) for r in research.get('sensitivity',[])]:
        # D2: one per-catchment rule (app and pilot). Partial catchments are priced
        # in-window and labelled; untestable extent or a failed invariant blocks.
        route=combine_routes(catchment_route(c,run.get('invariants')) for c in run.get('catchments',[]))
        known=shape(run['known_ia_union_geometry'])
        unknown=shape(run.get('unknown_ground_union_geometry') or {'type':'GeometryCollection','geometries':[]})
        hypotheses=[('known_ground_only',known,False)]
        if not unknown.is_empty:hypotheses.append(('unknown_ground_assumed_impervious',known.union(unknown),True))
        for surface_basis,raw_region,assume_unknown in hypotheses:
            region=raw_region.difference(occupied)
            bed_area=case_area_sqft(region.intersection(beds),case) if not beds.is_empty else 0.
            region=region.difference(beds)
            scenario_assumptions=deepcopy(assumed)
            scenario_assumptions['existing_installation']=True
            view=gis
            if assume_unknown:
                scenario_assumptions['all_unclassified_catchment_ground_is_impervious']=True
                # Counterfactual policy view only: original physical measurement
                # and unknown geometry in the frozen GIS artifact stay unchanged.
                geoms={**gis['measurement']['geometries'],
                       'physical_ia':mapping(shape(gis['measurement']['geometries']['physical_ia']).union(unknown))}
                view={**gis,'measurement':{**gis['measurement'],'geometries':geoms}}
            if vetoes:
                s=_blocked(vetoes)
            elif route['blocked_reasons']:
                s=_blocked(route['blocked_reasons'])
            elif region.is_empty or case_area_sqft(region,case)<.000001:
                s=_blocked(['No unallocated known impervious area modeled to GSI; unknown surfaces and missing connections are not zero-area evidence'])
            else:
                working=deepcopy(case)
                working['features']['features'].append({'type':'Feature','id':'research-management-counterfactual',
                    'geometry':mapping(region),'properties':{'layer':'benefit','benefit':{
                        'id':'research-management-counterfactual','category':'management','area_sqft':case_area_sqft(region,case),
                        'basis':'modeled','existing_overlap_reconciled':True,'evidence':scenario_assumptions}}})
                s=_economics(working,view,records,as_of,tariff)['modeled']
            scenarios.append({**s,'name':name+' / '+surface_basis,'basis':'conditional research scenario',
                'route_state':route['route_state'],'route_state_reason':route['route_state_reason'],'partial_label':route['partial_label'],
                'surface_assumption':surface_basis,'modeled_unallocated_area_sqft':case_area_sqft(region,case),
                'system_bed_ia_excluded_sqft':bed_area,
                'assumed_prerequisites':scenario_assumptions,
                'claim':'Counterfactual: only if the modeled existing system meets all management prerequisites and the stated ground assumption holds. No screen pass, approval or treatment capacity is established.'})
    return {'status':'conditional','scenarios':scenarios,
            'claim':'Alternatives to the existing assessment, never additional savings to sum; physical/credit evidence is unchanged.'}


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
    checks=economics.get('billed_area_check') or {}
    alternatives=checks.get('alternatives') if checks.get('status')=='alternatives' else None
    consistent=[name for name,check in (alternatives or {}).items() if (check or {}).get('status')=='consistent']
    if checks.get('status')=='mismatch' or (alternatives and not consistent and any((c or {}).get('status')=='mismatch' for c in alternatives.values())):
        flags.append({'kind':'billed_area_discrepancy','status':'review_only','affected_from':baseline.get('bill_date'),
                      'affected_through':baseline.get('bill_period_end',baseline.get('bill_date')),
                      'rows':deepcopy(checks.get('rows') if not alternatives else alternatives),
                      'basis':'PWD FinalGross/FinalImperv differ from the computed final and billed areas',
                      'missing':['Recorded credit schedule and order','Undeveloped/statutory IA basis','Actual invoices'],
                      'refund_entitlement':None,'claim':'Validation flag only; no correction, refund or historical debt determined'})
    elif alternatives and consistent:
        flags.append({'kind':'billed_area_status_evidence','status':'review_only','consistent_alternatives':consistent,
                      'rows':deepcopy(alternatives),
                      'claim':'PWD billed areas are consistent with the listed undeveloped-status alternative(s); confirm the status with the property record before choosing one'})
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
    from .model_assessment import integrate as integrate_models
    modeled=integrate_models(case,gis_result,records,day,tariff)
    for info in modeled.get('records',[]):
        for record in records:
            if record['id']==info['record_id']:record['modeled_context']=info
    for category in categories:
        if category['category'] in modeled.get('category_context',{}):
            category['modeled_context']=modeled['category_context'][category['category']]
    result={'rule_version':VERSION,'as_of':day.isoformat(),'categories':categories,'economics':economics,
            'modeled_integration':modeled,
            'research_drainage_scenarios':research_economics(case,gis_result,records,day,tariff),
            'historical_flags':historical_flags(case,economics),
            'rules':{**deepcopy(RULES),'applicability':'applicable' if RULES['effective_from']<=day.isoformat()<=RULES['verified_through'] else 'outside_verified_period'}}
    from .curve_number import worksheet
    result['open_space_curve_number']=worksheet(case,gis_result)
    if result['rules']['applicability']!='applicable':
        result['open_space_curve_number']['credit_factor']=None
        result['open_space_curve_number']['issues'].append('Outside verified PWD policy period; credit factor unavailable')
        result['open_space_curve_number'].pop('worksheet_sha256',None)
        result['open_space_curve_number']['worksheet_sha256']=sha256(json.dumps(result['open_space_curve_number'],sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest()
    from drainage_core.quality import artifact_quality
    if artifact_quality(gis_result)['status']=='outdated':
        from .quality import safe_analysis
        result=safe_analysis({**gis_result,'assessment':result})['assessment']
    result['baseline_refresh']=deepcopy(assessment.get('baseline_refresh'))
    result['assessment_sha256']=sha256(json.dumps(result,sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest()
    return result
