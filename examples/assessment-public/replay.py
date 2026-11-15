"""Offline replay of small frozen City/EPA examples; validates every original hash."""
from hashlib import sha256
import json
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT))
from stormwater.assessment_sources import normalize_gsi,normalize_permit

folder=Path(__file__).parent/'sources'
records=[];gaps=[]
for item in json.loads((folder/'manifest.json').read_text()):
    content=(folder/item['filename']).read_bytes()
    if sha256(content).hexdigest()!=item['sha256']:raise ValueError('Frozen public source hash mismatch')
    data=json.loads(content)
    if item['label'] in ('green_roof','permeable_pavement','direct_discharge'):
        for feature in data['features']:
            records.extend(normalize_gsi(feature,item['url'].split('/query?')[0],'EPSG:2272'))
        if not data['features']:gaps.append(item['label']+': no rows in this bounded public query; no real route/outfall example established')
    elif item['label']=='npdes_rows':
        records.extend(normalize_permit(row,item['url'],{'permit_id':'PA0054241'}) for row in data['Results']['Facilities'])
print(json.dumps({'records':records,'gaps':gaps+[
    'No site/operator match review or active industrial stormwater/compliance conclusion established.',
    'No credit award letters, renewal deadlines, actual account bills or historical discrepancy established.',
    'No independent IA or drainage measurements; this is candidate normalization, not empirical validation.']},indent=2))
