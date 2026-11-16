# Repro: GIS-mode saved_view caches the display view keyed only on analysis bytes,
# input hash and VIEW_VERSION. After code changes (processing fingerprint differs),
# the cached view is returned with its old 'not_independently_validated' review.
import tempfile
from pathlib import Path
from unittest.mock import patch
from drainage_core.cli import demo_case
from drainage_core.workspace import ProjectStore
from drainage_core.quality import safe_physical_view
with tempfile.TemporaryDirectory() as d:
    s=ProjectStore(d); s.save(demo_case())
    first=s.saved()                       # builds + caches analysis-view.json
    with patch('drainage_core.quality.processing_fingerprint',return_value='changed-code'):
        second=s.saved()
        import json; raw=json.loads((Path(d)/'analysis.json').read_text())
        fresh=safe_physical_view(raw)['quality_review']['status']
    print('first view state:',first['saved_status']['state'])
    print('after code change, cached view state:',second['saved_status']['state'],
          '| quality_review:',second['analysis']['quality_review']['status'],'| fresh gate would say:',fresh)
