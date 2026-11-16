"""Policy changes over a frozen GIS artifact; never relabel its input hash."""
from copy import deepcopy
from hashlib import sha256
import json
from drainage_core.engine import canonical,input_hash,result_hash,ENGINE_VERSION


def normalize_numbers(value):
    """Treat JSON 1 and 1.0 identically without losing large integer precision."""
    if isinstance(value,float) and value.is_integer():return int(value)
    if isinstance(value,dict):return {k:normalize_numbers(v) for k,v in value.items()}
    if isinstance(value,(list,tuple)):return [normalize_numbers(v) for v in value]
    return value


def physical_signature(case):
    # Unknown/new fields remain physical by default. Map features, corrections,
    # provenance, parameters, imagery/model and validation references all count.
    policy={'baseline','assessment','tariff'}
    if not case.get('corrections'):policy.add('benefits')
    return sha256(canonical(normalize_numbers({k:v for k,v in case.items() if k not in policy})).encode()).hexdigest()


def load_frozen(folder,case,*,allow_historical=False):
    path=folder/'gis-analysis.json'
    if not path.exists():return None
    gis=json.loads(path.read_text())
    digest=gis.get('input_sha256','')
    if len(digest)!=64 or any(c not in '0123456789abcdef' for c in digest):raise ValueError('Invalid frozen GIS input hash')
    revision=folder/'revisions'/(digest+'.json')
    if not revision.exists():return None
    original=json.loads(revision.read_text())
    if input_hash(original)!=digest:raise ValueError('Frozen input revision hash mismatch')
    if gis.get('analysis_sha256')!=result_hash(gis):raise ValueError('Frozen GIS content hash mismatch')
    if physical_signature(original)!=physical_signature(case):return None
    # Judged by explicit interpretation versions only (never code bytes or libraries).
    # allow_historical=True reuses an outdated artifact, labelled, for policy-only
    # changes; recompute passes False so an outdated artifact is rerun.
    from drainage_core.quality import artifact_quality
    if not allow_historical and (gis.get('engine_version')!=ENGINE_VERSION or
        artifact_quality(gis)['status']=='outdated'):return None
    return original,gis


def policy_overlay(case):
    return {k:deepcopy(case.get(k,default)) for k,default in
            (('baseline',None),('assessment',{}),('benefits',[]),('tariff',None))}
