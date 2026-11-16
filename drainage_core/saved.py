"""Small, hash-checked saved views. No analysis, acquisition or jurisdiction imports."""
from hashlib import sha256
from pathlib import Path
import json
import os
import tempfile
from .engine import canonical, input_hash, ENGINE_VERSION

VIEW_VERSION=3


def atomic_write(path, content):
    """Write bytes/text through a unique temporary file in the same folder, then replace."""
    path=Path(path);data=content.encode() if isinstance(content,str) else content
    descriptor,temp=tempfile.mkstemp(dir=path.parent,prefix='.'+path.name+'.',suffix='.tmp')
    try:
        with os.fdopen(descriptor,'wb') as stream:stream.write(data)
        os.replace(temp,path)
    except BaseException:
        try:os.unlink(temp)
        except FileNotFoundError:pass
        raise


def atomic_json(path, value):
    atomic_write(path,canonical(value))


def display_analysis(result):
    from .quality import safe_physical_view
    result=safe_physical_view(result)
    # Keep exact map geometries, areas, findings and provenance. Raster diagnostics
    # remain in the full export rather than being sent to every browser view.
    def research(value):
        if isinstance(value,list):return [research(v) for v in value]
        if isinstance(value,dict):return {k:research(v) for k,v in value.items() if k!='rasters'}
        return value
    out=dict(result)
    if isinstance(out.get('drainage'),dict):
        out['drainage']={k:v for k,v in out['drainage'].items() if k not in ('labels','next_cells','counts','outlets')}
    if out.get('research_drainage'):out['research_drainage']=research(out['research_drainage'])
    if out.get('modeled_integration'):
        out['modeled_integration']=dict(out['modeled_integration'])
        out['modeled_integration'].pop('ai_roof_drainage',None) # runs already contain its display catchments
    out['display_only']=True
    return out


def saved_view(folder,case):
    """Small cached display view. The cache key includes the current interpretation
    versions, so a version bump re-evaluates quality instead of serving a stale label."""
    from .quality import current_versions
    folder=Path(folder);source=folder/'analysis.json';expected=input_hash(case)
    if not source.exists():return {'case':case,'analysis':None,'saved_status':{'state':'missing','message':'No saved result. Run explicitly when ready.','revision':expected}}
    content=source.read_bytes();digest=sha256(content).hexdigest();versions=current_versions()
    viewfile=folder/'analysis-view.json';manifestfile=folder/'analysis-view-manifest.json'
    if viewfile.exists() and manifestfile.exists():
        manifest=json.loads(manifestfile.read_text())
        if (manifest.get('source_sha256')==digest and manifest.get('input_sha256')==expected and
                manifest.get('view_version')==VIEW_VERSION and manifest.get('interpretation_versions')==versions):
            payload=viewfile.read_bytes()
            if sha256(payload).hexdigest()!=manifest['view_sha256']:raise ValueError('Saved display hash mismatch')
            result=json.loads(payload)
            return {'case':case,'analysis':result,'saved_status':_status(result,expected)}
    result=json.loads(content)
    if result.get('input_sha256')!=expected:
        return {'case':case,'analysis':None,'saved_status':{'state':'input_changed','message':'Saved result does not match current inputs. Recalculate explicitly.','revision':expected}}
    view=display_analysis(result);atomic_json(viewfile,view)
    atomic_json(manifestfile,{'view_version':VIEW_VERSION,'source_sha256':digest,'input_sha256':expected,
        'interpretation_versions':versions,'view_sha256':sha256(viewfile.read_bytes()).hexdigest()})
    return {'case':case,'analysis':view,'saved_status':_status(view,expected)}


def _status(result,revision=None):
    old=result.get('engine_version')!=ENGINE_VERSION
    q=result.get('quality_review',{})
    if q.get('status') in ('outdated','invalidated'):return {
        'state':'outdated','message':q['reason'],'label':q.get('label'),'engine_changed':old,
        'recompute_available':True,'revision':revision,
        'assessment_as_of':result.get('assessment',{}).get('as_of')}
    return {'state':'historical' if old else 'saved','message':'Showing saved results; no recalculation or source refresh.'+(' Saved engine version differs from current code.' if old else ''),
        'engine_changed':old,'recompute_available':False,'revision':revision,'assessment_as_of':result.get('assessment',{}).get('as_of')}
