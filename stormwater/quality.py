"""Presentation/policy quarantine over immutable physical artifacts. No routing."""
from copy import deepcopy
from hashlib import sha256
import json
from pathlib import Path
from drainage_core.quality import artifact_quality


def policy_fingerprint():
    folder=Path(__file__).parent
    names=('rules.py','billing.py','assessment_policy.py','model_assessment.py',
           'jurisdictions/philadelphia.py','quality.py','curve_number.py','renewals.py')
    return sha256('\n'.join(name+':'+sha256((folder/name).read_bytes()).hexdigest() for name in names).encode()).hexdigest()


def safe_analysis(result):
    """Return an explicitly derived safe view, never edit a frozen artifact.

    Historical bytes remain exportable in evidence bundles with a quarantine
    manifest. Ordinary views/reports/exports must not serve their old dollars.
    """
    q=artifact_quality(result)
    policy_changed=result.get('policy_processing_fingerprint') is not None and result['policy_processing_fingerprint']!=policy_fingerprint()
    physical_invalid=q['status']=='invalidated'
    if policy_changed and not physical_invalid:
        q={**q,'status':'invalidated','reason':'Saved policy processing changed; recalculate policy over frozen GIS before using these savings.',
           'affected':['derived_scenarios']}
    if q['status']!='invalidated':return {**result,'quality_review':q}
    out=deepcopy(result);out['quality_review']=q
    reason=q['reason']
    def redact(value):
        if isinstance(value,list):return [redact(v) for v in value]
        if not isinstance(value,dict):return value
        value={k:redact(v) for k,v in value.items()}
        monetary=[k for k in value if any(s in k.lower() for s in
            ('savings','reduction','monthly_','annual_','annualized_')) or k in
            ('ga_charge','ia_charge','collection_charge','total_weighted_charge')]
        for key in monetary:
            if isinstance(value[key],(int,float)) and not isinstance(value[key],bool):value[key]=None
        if monetary and value.get('status') in ('calculated','conditional','screen_pass'):
            value.update(status='invalidated',reasons=[reason])
        return value
    out=redact(out)
    for row in out.get('automatic',{}).get('estimates',[]):
        if row.get('feature')=='other_pavement':
            row.update(feature='developed_space',original_feature='other_pavement',
                basis='Historical image appearance only; not a physical IA measurement')
    blocked={'status':'invalidated','reason':reason,'reasons':[reason]}
    if 'billing' in out:out['billing']=deepcopy(blocked)
    if 'surface_assumption_scenarios' in out:out['surface_assumption_scenarios']={}
    if out.get('assessment'):
        a=out['assessment'];a['economics']={k:deepcopy(blocked) for k in a.get('economics',{})}
        a['modeled_integration']={'status':'invalidated','reason':reason,'claim':reason,'records':[],'combined':[]}
        a['research_drainage_scenarios']=deepcopy(blocked)
        for category in a.get('categories',[]):
            category.pop('modeled_context',None)
            for record in category.get('records',[]):record.pop('modeled_context',None)
        a.pop('assessment_sha256',None)
    if physical_invalid and out.get('modeled_integration'):
        out['modeled_integration']={'status':'invalidated','reason':reason,
            'version':out['modeled_integration'].get('version'),'runs':[]}
    out['warnings']=list(dict.fromkeys([reason,*out.get('warnings',[])]))
    out['presentation_only']=True
    out.setdefault('presentation_input_sha256',sha256(json.dumps(result,sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest())
    out.pop('analysis_sha256',None)
    return out
