"""Physical artifact interpretation/version checks. No jurisdiction or money.

Saved results are judged by explicit interpretation versions, never by the bytes
of source files or by installed library versions. A comment, formatting or
refactoring edit therefore cannot invalidate anything. Library versions are
recorded for provenance only.

Bump ``PHYSICAL_INTERPRETATION_VERSION`` (an integer) whenever a change alters
what a saved physical result means: measurement, geometry clipping, conservative
drainage routing, research drainage, model integration, semantic cover,
installation status, source handling or validation semantics (the modules in
``PHYSICAL_SCOPE``). ``ENGINE_VERSION`` and the model-integration
``INTERPRETATION_VERSION`` remain explicit, narrower versions and are checked too.

An outdated result stays visible with a label and a **Recompute from saved
inputs** action. Observations and measurements are never hidden; derived model
results are withheld until recomputed.
"""
from copy import deepcopy
from hashlib import sha256
from importlib.metadata import PackageNotFoundError, version
import json

QUALITY_VERSION='physical-quality-v3'
# 2 (2026-11-16, Phase 3): polygon-only clipping, overlap precedence, raised-wall
# corner blocking, inlet-in-GSI, touched point/line rasterization, canopy coverage,
# flat-tolerance exits, roof-sliver IA, measured/per-catchment extent, class-edge
# erosion and the installation-status allowlist.
PHYSICAL_INTERPRETATION_VERSION=2
PHYSICAL_SCOPE=('engine','geometry','drainage','research','model_integration','semantic_cover',
                'remote_sensing','model_worker','freshness','installation','sources','validation','extent')
PROVENANCE_LIBRARIES=('numpy','shapely','rasterio','pyproj')
# A real engine artifact carries one of these. One without an interpretation version
# predates explicit versions (byte fingerprints or none at all): "unknown/legacy".
TRACKED_MARKERS=('physical_interpretation_version','engine_version','processing_fingerprint','research_drainage')
OUTDATED='outdated'
RECOMPUTE_HINT=('Saved observations and measurements remain visible. Use Recompute from saved '
    'inputs (no source refresh) to calculate derived results with the current version.')
INVALID_REASON=('Invalid historical image-to-IA interpretation: developed space/road '
    'were treated as impermeable and vegetation/soil as pervious. Derived results '
    'require recalculation under corrected semantics; no property was rerun automatically. '
    +RECOMPUTE_HINT)


def library_versions():
    """Provenance only. A library upgrade alone never marks a result outdated."""
    found={}
    for name in PROVENANCE_LIBRARIES:
        try:found[name]=version(name)
        except PackageNotFoundError:found[name]=None
    return found


def current_versions():
    from .engine import ENGINE_VERSION
    from .model_integration import INTERPRETATION_VERSION
    return {'physical':PHYSICAL_INTERPRETATION_VERSION,'engine':ENGINE_VERSION,
            'model_integration':INTERPRETATION_VERSION,'quality':QUALITY_VERSION}


def processing_fingerprint():
    """Semantic fingerprint of the explicit physical versions; never file bytes."""
    v=current_versions()
    return sha256(json.dumps({k:v[k] for k in ('physical','engine','model_integration')},
                             sort_keys=True).encode()).hexdigest()


def version_label(stage,saved,current):
    if saved is None:
        return f'Calculated by an unknown (legacy) {stage} interpretation version; current version is {current}.'
    return f'Calculated by an older {stage} interpretation version {saved}; current version is {current}.'


def artifact_quality(result):
    current=current_versions()
    m=result.get('modeled_integration') or {}
    saved={'physical':result.get('physical_interpretation_version'),'engine':result.get('engine_version'),
           'model_integration':m.get('version') if m else None}
    tracked=any(key in result for key in TRACKED_MARKERS)
    physical_old=tracked and saved['physical']!=PHYSICAL_INTERPRETATION_VERSION
    engine_old=saved['engine'] is not None and saved['engine']!=current['engine']
    model_old=bool(m) and saved['model_integration']!=current['model_integration']
    withheld=m.get('status') in ('invalidated',OUTDATED)
    interpretation={'saved':saved,'current':{k:current[k] for k in saved}}
    if not (physical_old or engine_old or model_old or withheld):
        return {'version':QUALITY_VERSION,'status':'not_independently_validated',
                'reason':'Physical interpretation checks do not establish real-site accuracy',
                'affected':[],'interpretation':interpretation,'recompute_available':False}
    if physical_old:label=version_label('physical',saved['physical'],PHYSICAL_INTERPRETATION_VERSION)
    elif engine_old:label=version_label('GIS engine',saved['engine'],current['engine'])
    elif model_old:label=version_label('AI model-integration',saved['model_integration'],current['model_integration'])
    else:label='Derived model results were withheld from this saved view.'
    if model_old:reason=label+' '+INVALID_REASON
    elif withheld and m.get('reason') and not (physical_old or engine_old):reason=m['reason']
    else:reason=label+' '+RECOMPUTE_HINT
    return {'version':QUALITY_VERSION,'status':OUTDATED,'label':label,'reason':reason,
            'affected':['modeled_integration','derived_scenarios'],'interpretation':interpretation,
            'recompute_available':True,'observations_retained':True}


def withhold_physical(out,q):
    """Withhold derived model runs in place; measurements and observations stay."""
    old=out.get('modeled_integration')
    if old:
        out['modeled_integration']={'status':OUTDATED,'reason':q['reason'],'version':old.get('version'),
                                    'runs':[],'recompute_available':True}
    out['warnings']=list(dict.fromkeys([q['reason'],*out.get('warnings',[])]))
    if out.get('research_drainage'):
        out['research_drainage']['status']='historical'
        out['research_drainage']['warnings']=list(dict.fromkeys([q['reason'],*out['research_drainage'].get('warnings',[])]))
    out['presentation_only']=True
    return out


def safe_physical_view(result):
    q=artifact_quality(result)
    if q['status']!=OUTDATED:return {**result,'quality_review':q}
    out=deepcopy(result);out['quality_review']=q
    return withhold_physical(out,q)
