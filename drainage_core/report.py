"""Neutral GIS map snapshots, reports and portable RFC 7946 geometry."""
from html import escape
import base64
import json
from shapely.geometry import shape, mapping
from .geometry import effective_features, reproject

COLORS={'roof':'#52677b','pavement':'#b29872','pervious':'#88b195','unknown':'#d99d42',
        'canopy':'#38745b','footprint':'#ac7099','barrier':'#da615c','inlet':'#438bd0',
        'physical_ia':'#687a87','canopy_ground_ia':'#25806a','connection':'#627ad0'}


def map_svg(case,result=None):
    parcel=shape(case['parcel']); xmin,ymin,xmax,ymax=parcel.bounds
    pad=max(xmax-xmin,ymax-ymin)*.06 or 1
    xmin-=pad;ymin-=pad;xmax+=pad;ymax+=pad
    width,height=xmax-xmin,ymax-ymin
    def path(geom):
        g=shape(geom)
        if g.geom_type=='Point':
            return f'<circle cx="{g.x-xmin}" cy="{ymax-g.y}" r="{width/170}"/>'
        if hasattr(g,'geoms'): return ''.join(path(mapping(x)) for x in g.geoms)
        rings=[g.exterior,*g.interiors] if g.geom_type=='Polygon' else [g]
        d=' '.join('M '+' L '.join(f'{x-xmin:.5f},{ymax-y:.5f}' for x,y,*_ in r.coords)+(' Z' if g.geom_type=='Polygon' else '') for r in rings)
        return f'<path d="{d}" fill-rule="evenodd"/>'
    out=[f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" role="img" aria-label="Case map snapshot">',
         f'<rect width="{width}" height="{height}" fill="#f0f4f1"/>']
    if case.get('imagery'):
        from pathlib import Path
        from hashlib import sha256
        info=case['imagery'];digest=info.get('sha256','')
        if len(digest)==64 and all(c in '0123456789abcdef' for c in digest):
            from .media import read_blob
            try:
                payload=read_blob(info)
            except FileNotFoundError:
                payload=None
            if payload is not None:
                if sha256(payload).hexdigest()!=digest:raise ValueError('Imagery snapshot hash mismatch')
                b=info['bounds'];uri=base64.b64encode(payload).decode()
                out.append(f'<image href="data:image/png;base64,{uri}" x="{b[0]-xmin}" y="{ymax-b[3]}" width="{b[2]-b[0]}" height="{b[3]-b[1]}" preserveAspectRatio="none"/>')
    if result:
        catchments=[c for c in result['drainage'].get('catchments',[]) if not c['outlet'].startswith('unresolved:roof')]
        for c in sorted(catchments,key=lambda c:c['contributing_area_sqft'],reverse=True)[:250]:
            out.append(f'<g fill="#438b9d" fill-opacity=".08" stroke="#2d7585" stroke-opacity=".4" stroke-width="{width/1200}">{path(c["geometry"])}</g>')
        for route in result['drainage'].get('flow_paths',[]):
            points=' '.join(f'{x-xmin},{ymax-y}' for x,y in route['coordinates'])
            out.append(f'<polyline points="{points}" fill="none" stroke="#277eaa" stroke-width="{width/700}"/>')
        for key in ('unknown','physical_ia','canopy_ground_ia'):
            out.append(f'<g fill="{COLORS[key]}" fill-opacity=".28">{path(result["measurement"]["geometries"][key])}</g>')
    for f in effective_features(case):
        p=f['properties']; color=COLORS.get(p.get('class'),COLORS.get(p.get('layer'),'#707e7c'))
        fill='none' if p.get('layer') in ('barrier','connection') else color
        out.append(f'<g fill="{fill}" fill-opacity=".45" stroke="{color}" stroke-width="{width/500}"><title>{escape(str(f["id"]))}</title>{path(f["geometry"])}</g>')
    out.append(f'<g fill="none" stroke="#1c4c42" stroke-width="{width/300}">{path(case["parcel"])}</g></svg>')
    return ''.join(out)


def export_geojson(case,result):
    features=[]
    def add(geom,props,id):
        if shape(geom).is_empty:return
        features.append({'type':'Feature','id':id,'properties':{'native_crs':case['crs'],**props},
                         'geometry':mapping(reproject(shape(geom),case['crs'],'EPSG:4326'))})
    add(case['parcel'],{'layer':'parcel','boundary_claim':result['measurement']['boundary_claim']},'parcel')
    for f in effective_features(case): add(f['geometry'],f['properties'],f['id'])
    for key,g in result['measurement']['geometries'].items():add(g,{'layer':'measurement','class':key},key)
    for i,c in enumerate(result['drainage'].get('catchments',[])):
        add(c['geometry'],{k:v for k,v in c.items() if k!='geometry'},'catchment-'+str(i))
    return {'type':'FeatureCollection','features':features,'input_sha256':result['input_sha256'],
            'area_accounting_crs':case.get('area_crs',case['crs'])}


def render_report(case,result):
    """Physical evidence only; no jurisdiction, credit eligibility or money."""
    e=lambda x:escape(str(x))
    n=lambda x:'Unknown' if x is None else f'{x:,.2f}'
    m=result['measurement'];terrain=case.get('terrain') or {}
    keys=[('Boundary area','ga'),('Known impervious area','ia'),('Unclassified area','unknown'),
          ('Known pervious area','pervious'),('Canopy over ground impervious','canopy_ground_ia')]
    rows=''.join(f'<tr><td>{label}</td><td>{n(m.get(key+"_m2",m[key+"_sqft"]*.09290304))}</td><td>{n(m[key+"_sqft"])}</td></tr>' for label,key in keys)
    warnings=''.join(f'<li>{e(w)}</li>' for w in result['warnings'])
    corrections=''.join(f'<li>{e(c["at"])} — {e(c["action"])}: {e(c["reason"])}</li>' for c in case.get('corrections',[])) or '<li>None recorded</li>'
    details={k:result[k] for k in ('validation','source_quality_issues','processing_settings')}
    return f'''<!doctype html><html lang="en"><meta charset="utf-8"><title>{e(case['name'])} — GIS evidence</title>
<style>body{{font:15px/1.5 system-ui;color:#183b34;max-width:1100px;margin:40px auto;padding:0 28px}}h1{{font-size:30px}}h2{{margin-top:32px}}table{{border-collapse:collapse;width:100%;font-size:13px}}td,th{{text-align:left;border-bottom:1px solid #cdd9d3;padding:9px}}svg{{max-height:560px;width:100%;border:1px solid #cdd9d3}}pre{{white-space:pre-wrap;overflow-wrap:anywhere;background:#f1f4f2;padding:16px}}.warning{{background:#fff1d8;padding:16px}}</style>
<h1>{e(case['name'])}</h1><p>Local GIS evidence • Case {e(case['id'])}<br>Input SHA-256: {e(result['input_sha256'])}<br>Analysis SHA-256: {e(result['analysis_sha256'])}</p>
<p class="warning">{e(result['claim'])}.</p>{map_svg(case,result)}
<p>Map/terrain CRS: {e(case['crs'])}; area accounting CRS: {e(m.get('area_crs',case['crs']))}. The boundary is source geometry; its legal accuracy is unverified. Roofs, pavement, pervious ground, canopy, barriers and collection/conveyance remain distinct.</p>
<h2>Physical areas</h2><table><tr><th>Quantity</th><th>m²</th><th>ft²</th></tr>{rows}</table><p>Surface coverage: {'complete' if m['complete'] else 'partial'}. Unknown surfaces remain explicit.</p>
<h2>Drainage</h2><p>Status: {e(result['drainage'].get('status'))}. Displayed terminal regions: {len(result['drainage'].get('catchments',[]))}. Elevation units: {e(terrain.get('vertical_unit','Unknown'))}; horizontal units: {e(terrain.get('horizontal_unit','Unknown'))}; cell size: {e(terrain.get('cell_size','Unknown'))}. A collection footprint is not a confirmed inlet. No automatic pit filling or unknown private connection is implied.</p>
<pre>{e(json.dumps({k:v for k,v in terrain.items() if k not in ('elevations','parcel_mask')},indent=2))}</pre>
<h2>Missing evidence and assumptions</h2><ul>{warnings}</ul><pre>{e(json.dumps(case.get('assumptions',[]),indent=2))}</pre>
<h2>Source and construction/condition evidence</h2><p>Reported construction completion: {e(case.get('construction_completed','Unknown'))}. Source dates do not establish unchanged grading or present condition.</p><pre>{e(json.dumps({'sources':case.get('sources',[]),'quality_reviews':case.get('source_quality_reviews',[])},indent=2))}</pre>
<h2>Manual corrections</h2><ul>{corrections}</ul><h2>Separate measurement and routing validation</h2><pre>{e(json.dumps(details,indent=2))}</pre>
<p>Calculation: {result['processing_seconds']:.6f} seconds. Logged manual review: {n(case.get('manual_review_minutes'))} minutes. Full geometry and terminal-region accounting are in measurements.geojson and analysis.json.</p></html>'''

