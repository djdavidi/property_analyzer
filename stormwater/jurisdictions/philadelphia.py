"""Philadelphia PWD eligibility/billing adapter over frozen GIS evidence.

No data acquisition, physical measurement or drainage routing occurs here. The
adapter may spatially allocate policy-specific benefit regions against already
measured physical geometry. Missing evidence and unsupported combinations remain
blocked by the existing versioned PWD rules.
"""
from copy import deepcopy
from hashlib import sha256
import json

from shapely.geometry import shape

from ..billing import calculate_scenarios, default_tariff
from ..rules import RULE_VERSION, screen

PROFILE_ID = 'philadelphia-pwd'
PROFILE_VERSION = 'philadelphia-pwd-v1'


def _canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False)


def _policy_case(case, policy_inputs):
    overlay=deepcopy(policy_inputs or {})
    extra=set(overlay)-{'baseline','benefits','assessment','tariff','jurisdiction','profile'}
    if extra:
        raise ValueError('Unsupported Philadelphia policy inputs: '+', '.join(sorted(extra)))
    for key in ('jurisdiction','profile'):
        if overlay.get(key) not in (None,PROFILE_ID):
            raise ValueError('Policy input jurisdiction does not match '+PROFILE_ID)
    working=deepcopy(case)
    for key in ('baseline','benefits','assessment'):
        if key in overlay:
            working[key]=overlay[key]
    return working,overlay


def apply(case, gis_result, policy_inputs=None, tariff=None, as_of=None):
    """Apply PWD rules to an unchanged core case/result pair.

    ``policy_inputs`` may supply a separate ``baseline``, ``benefits`` and
    ``tariff``. This permits reusing a saved GIS artifact for multiple billing
    configurations without rerouting. Its benefit coordinates must use the case
    CRS and the existing evidence schema. Original case/result objects are never
    mutated. The returned dictionary contains only policy enrichment, not copied
    measurements, routing or independent-validation claims. ``as_of`` (ISO date)
    pins the assessment date; by default it is today in Philadelphia.
    """
    from drainage_core.engine import input_hash,result_hash
    from drainage_core.geometry import effective_features, case_area_sqft

    if gis_result.get('schema_version') != 1 or gis_result.get('result_type') != 'gis-analysis' or not isinstance(gis_result.get('measurement'),dict):
        raise ValueError('A supported saved GIS analysis artifact is required')
    analysis_digest=result_hash(gis_result)
    if gis_result.get('analysis_sha256') is not None and gis_result['analysis_sha256'] != analysis_digest:
        raise ValueError('GIS artifact content digest does not match; regenerate the modified analysis')
    expected=input_hash(case)
    if gis_result.get('input_sha256') != expected:
        raise ValueError('GIS artifact does not match case inputs; rerun GIS for changed physical inputs')
    working,overlay=_policy_case(case,policy_inputs)
    from drainage_core.evidence import validate_references
    validate_references(working.get('assessment',{}))
    if tariff is not None and overlay.get('tariff') is not None:
        raise ValueError('Supply tariff once, in policy inputs or as an argument')
    selected_tariff=deepcopy(tariff if tariff is not None else overlay.get('tariff') or default_tariff())
    measurement=deepcopy(gis_result['measurement'])
    screens=[];spatial_benefits=[];allocated=[]
    all_benefits=[b for b in working.get('benefits',[]) if not b.get('geometry')]
    all_benefits.extend({**f['properties']['benefit'],'geometry':f['geometry']}
                        for f in effective_features(working) if f['properties'].get('layer')=='benefit')
    for original in all_benefits:
        benefit=deepcopy(original)
        evidence=benefit.setdefault('evidence',{})
        geom=benefit.get('geometry')
        if geom:
            region=shape(geom).intersection(shape(working['parcel']))
            category=benefit['category']
            target='pervious' if category in ('open_space','open-space') else 'canopy_ground_ia' if category in ('canopy','tree_canopy') else 'physical_ia'
            eligible=shape(measurement['geometries'][target])
            claimed=case_area_sqft(region,working)
            if region.difference(eligible).area > 1e-8:
                evidence['physical_area_confirmed']=False
            if any(region.intersection(other).area>1e-8 for other in allocated):
                evidence['parcel_allocation_confirmed']=False
            allocated.append(region)
            benefit['area_sqft']=claimed
            benefit['ledger_ids']=[benefit['id']]
        else:
            # Scalar hypotheses are not spatially reconciled credits.
            evidence['physical_area_confirmed']=None
        screens.append({'id':benefit['id'],**screen(benefit['category'],benefit['area_sqft'],evidence)})
        spatial_benefits.append(benefit)

    warnings=[]
    if working.get('baseline'):
        try:
            billing=calculate_scenarios(working['baseline'],measurement,spatial_benefits,tariff=selected_tariff)
        except ValueError as exc:
            billing={'status':'blocked','reason':str(exc)}
    else:
        billing={'status':'blocked','reason':'No public billing baseline or actual bill supplied'}
    if billing.get('status')=='blocked':
        warnings.append(billing['reason'])
    surface_scenarios={}
    if working.get('baseline') and not measurement['complete']:
        for name,key in [('unknown_assumed_pervious','ia_min_sqft'),('unknown_assumed_impervious','ia_max_sqft')]:
            try:
                scenarios=calculate_scenarios(working['baseline'],{**measurement,'complete':True,'ia_sqft':measurement[key]},[],tariff=selected_tariff)
                surface_scenarios[name]={
                    'assumption':'All unknown surfaces assigned as stated; extreme assumption, not a confidence interval',
                    'ia_sqft':measurement[key],'appeal':scenarios['appeal_only']}
            except ValueError as exc:
                surface_scenarios[name]={'status':'blocked','reason':str(exc)}
    if working.get('assessment',{}).get('baseline_refresh',{}).get('status')=='pending_review':
        billing={'status':'blocked','reason':'Public billing baseline changed; review the pending comparison before savings calculations'}
        surface_scenarios={};warnings.append(billing['reason'])
    if not working.get('baseline',{}):
        warnings.append('Actual billing baseline unavailable')
    if not (working.get('baseline') or {}).get('actual_bill_verified'):
        warnings.append('Actual account bill, special-rate enrollment and payer responsibility are unverified')

    from ..assessment_policy import evaluate_assessment
    from ..renewals import history_assessment, today
    assessment=evaluate_assessment(working,gis_result,as_of=as_of or today().isoformat(),tariff=selected_tariff)
    history=history_assessment(working,assessment.get('as_of'))
    assessment['categories'].append(history)
    assessment['renewals']=history['renewals']
    assessment['credit_history']=history['records']
    assessment['public_credit_observations']=history['public_observations']
    assessment['source_status']=deepcopy(working.get('assessment',{}).get('source_status',[]))
    assessment['attachments']=deepcopy(working.get('assessment',{}).get('attachments',[]))
    assessment.pop('assessment_sha256',None)
    assessment['assessment_sha256']=sha256(_canonical(assessment).encode()).hexdigest()
    policy_record={'jurisdiction':PROFILE_ID,'profile_version':PROFILE_VERSION,'rule_version':RULE_VERSION,
                   'baseline':working.get('baseline'),'benefits':all_benefits,'tariff':selected_tariff,
                   'assessment':working.get('assessment'),'assessment_rules':assessment.get('rules'),
                   'assessment_as_of':assessment.get('as_of')}
    from ..quality import POLICY_INTERPRETATION_VERSION
    output={
        'policy_interpretation_version':POLICY_INTERPRETATION_VERSION,
        'jurisdiction':PROFILE_ID,'profile_version':PROFILE_VERSION,'rule_version':RULE_VERSION,
        'gis_input_sha256':expected,
        'gis_analysis_sha256':analysis_digest,
        'gis_artifact_sha256':sha256(_canonical(gis_result).encode()).hexdigest(),
        'policy_input_sha256':sha256(_canonical(policy_record).encode()).hexdigest(),
        'screens':screens,'billing':billing,'surface_assumption_scenarios':surface_scenarios,
        'assessment':assessment,
        'warnings':list(dict.fromkeys(warnings)),
        'policy_claim':'Philadelphia PWD screening only; eligibility, approval and actual billed savings require separate evidence.'}
    from drainage_core.quality import artifact_quality
    if artifact_quality(gis_result)['status']=='outdated':
        from ..quality import safe_analysis
        safe=safe_analysis({**gis_result,**output})
        output={k:safe[k] for k in output};output['quality_review']=safe['quality_review']
    return output


evaluate = apply
