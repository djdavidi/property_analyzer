"""One portable GIS project folder, with immutable input revisions."""
from pathlib import Path
import json
from .engine import analyze,canonical
from .report import render_report,export_geojson


class ProjectStore:
    def __init__(self,root):
        self.root=Path(root);self.root.mkdir(parents=True,exist_ok=True)

    def save(self,case):
        result=analyze(case);revisions=self.root/'revisions';revisions.mkdir(exist_ok=True)
        payload=canonical(case)+'\n';frozen=revisions/(result['input_sha256']+'.json')
        if not frozen.exists():frozen.write_text(payload)
        outputs={'case.json':payload,'analysis.json':canonical(result),
                 'measurements.geojson':canonical(export_geojson(case,result)),
                 'report.html':render_report(case,result)}
        for name,body in outputs.items():
            temp=self.root/(name+'.tmp');temp.write_text(body);temp.replace(self.root/name)
        return result

    def load(self):
        return json.loads((self.root/'case.json').read_text())

    def saved(self):
        from .saved import saved_view
        return saved_view(self.root,self.load())

    def list(self):
        if not (self.root/'case.json').exists():return []
        case=self.load();return [{'id':case['id'],'name':case['name']}]
