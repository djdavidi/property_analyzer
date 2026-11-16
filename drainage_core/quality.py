"""Physical artifact interpretation/version checks. No jurisdiction or money."""
from hashlib import sha256
from importlib.metadata import version
from pathlib import Path

QUALITY_VERSION='physical-quality-v2'
INVALID_REASON=('Invalid historical image-to-IA interpretation: developed space/road '
    'were treated as impermeable and vegetation/soil as pervious. Derived results '
    'require explicit recalculation under corrected semantics; no property was rerun.')


def artifact_quality(result):
    from .model_integration import INTERPRETATION_VERSION
    m=result.get('modeled_integration') or {}
    legacy=bool(m) and m.get('version')!=INTERPRETATION_VERSION
    changed=result.get('processing_fingerprint') is not None and result['processing_fingerprint']!=processing_fingerprint()
    invalid=bool(legacy or changed or m.get('status')=='invalidated')
    return {'version':QUALITY_VERSION,'status':'invalidated' if invalid else 'not_independently_validated',
            'reason':(INVALID_REASON if legacy else m.get('reason') or
                'Processing code/dependencies changed; derived results require explicit recalculation, not automatic reuse') if invalid
                else 'Physical interpretation checks do not establish real-site accuracy',
            'affected':['modeled_integration','derived_scenarios'] if invalid else []}


def safe_physical_view(result):
    from copy import deepcopy
    q=artifact_quality(result)
    if q['status']!='invalidated':return {**result,'quality_review':q}
    out=deepcopy(result);out['quality_review']=q
    if q['status']=='invalidated':
        old=out.get('modeled_integration',{})
        out['modeled_integration']={'status':'invalidated','reason':q['reason'],
            'version':old.get('version'),'runs':[]}
        out['warnings']=list(dict.fromkeys([q['reason'],*out.get('warnings',[])]))
        if out.get('research_drainage'):
            out['research_drainage']['status']='historical'
            out['research_drainage']['warnings']=list(dict.fromkeys([q['reason'],*out['research_drainage'].get('warnings',[])]))
        out['presentation_only']=True
    return out


def processing_fingerprint():
    """Invalidate frozen processing on relevant code or numerical-library changes."""
    names=('engine.py','geometry.py','drainage.py','research.py','model_integration.py',
           'remote_sensing.py','semantic_cover.py','model_worker.py','freshness.py','installation.py','quality.py')
    folder=Path(__file__).parent
    parts=[name+':'+sha256((folder/name).read_bytes()).hexdigest() for name in names]
    parts.extend(name+':'+version(name) for name in ('numpy','shapely','rasterio','pyproj'))
    return sha256('\n'.join(parts).encode()).hexdigest()
