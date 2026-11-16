import tempfile, json
from pathlib import Path
from unittest.mock import patch
from drainage_core import saved, quality
from drainage_core.engine import input_hash, ENGINE_VERSION, canonical
case={'id':'x','name':'t'}
with tempfile.TemporaryDirectory() as d:
    a={'input_sha256':input_hash(case),'processing_fingerprint':quality.processing_fingerprint(),'engine_version':ENGINE_VERSION,'measurement':{}}
    (Path(d)/'analysis.json').write_text(canonical(a))
    v1=saved.saved_view(d,case);print('first view :',v1['saved_status']['state'],v1['analysis']['quality_review']['status'])
    with patch.object(quality,'processing_fingerprint',return_value='0'*64):
        v2=saved.saved_view(d,case);print('code changed, cached view :',v2['saved_status']['state'],v2['analysis']['quality_review']['status'])
        (Path(d)/'analysis-view.json').unlink()
        v3=saved.saved_view(d,case);print('code changed, view rebuilt:',v3['saved_status']['state'],v3['analysis']['quality_review']['status'])
