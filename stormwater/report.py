"""Philadelphia-specific evidence report, built on reusable GIS visuals."""
from html import escape
import json
from drainage_core.report import map_svg,export_geojson as _export_geojson,COLORS,research_sections,modeled_sections


def export_geojson(case,result):
    from shapely.geometry import shape,mapping
    from drainage_core.geometry import reproject
    data=_export_geojson(case,result)
    for record in case.get('assessment',{}).get('records',[]):
        for role in ('geometry','footprint_geometry'):
            if not record.get(role):continue
            try:
                geom=shape(record[role])
                if geom.is_empty or not geom.is_valid:continue
                transformed=mapping(reproject(geom,case['crs'],'EPSG:4326'))
            except (ValueError,TypeError,KeyError):continue
            data['features'].append({'type':'Feature','id':'assessment-'+str(record['id'])+'-'+role,
                'geometry':transformed,'properties':{'layer':'assessment_evidence','category':record['category'],
                'role':'managed area' if role=='geometry' else 'physical footprint',
                'decision':record.get('decision'),'basis':record.get('basis'),
                'evidence_refs':record.get('evidence_refs',[]),'native_crs':case['crs'],
                'eligibility':'Not established by geometry'}})
    for info in result.get('assessment',{}).get('modeled_integration',{}).get('records',[]):
        for run in info.get('runs',[]):
            if not run.get('managed_geometry'):continue
            geom=shape(run['managed_geometry'])
            if geom.is_empty:continue
            data['features'].append({'type':'Feature','id':'modeled-assessment-'+info['record_id']+'-'+run['name'],
                'geometry':mapping(reproject(geom,case['crs'],'EPSG:4326')),
                'properties':{'layer':'modeled_assessment','record_id':info['record_id'],
                    'scenario':run['name'],'area_basis':run['area_basis'],'catchment_match':run['catchment_match'],
                    'receiver_id':run.get('receiver_id'),'composition':run.get('composition'),
                    'basis':'modeled estimate; eligibility unverified','native_crs':case['crs']}})
    return data

def render_report(case,result):
    e=lambda x:escape(str(x))
    num=lambda x:'Unknown' if x is None else f'{x:,.2f}'
    m=result['measurement']; baseline=case.get('baseline') or {}; b=result['billing']
    rows=[('Gross area',m['ga_sqft'],baseline.get('ga_sqft')),
          ('Known physical impervious area',m['ia_sqft'],baseline.get('ia_sqft')),
          ('Unknown surface area',m['unknown_sqft'],None),
          ('Canopy over ground impervious',m['canopy_ground_ia_sqft'],None)]
    area=''.join(f'<tr><td>{label}</td><td>{num(a)}</td><td>{num(c)}</td></tr>' for label,a,c in rows)
    billing=''
    for key in ('baseline','appeal_only','credit_only','combined','documented_credit_only','documented_combined'):
        s=b.get(key,{})
        if not s:continue
        billing+=f'<tr><td>{e(key.replace("_"," "))}</td><td>{e(s.get("status"))}</td><td>{num(s.get("monthly_total"))}</td><td>{num(s.get("annual_savings"))}</td><td>{e("; ".join(s.get("reasons",[])))}</td></tr>'
    sources=''.join(f'<tr><td>{e(s.get("url",s.get("source_url",s.get("source","Local input"))))}</td><td>{e(s.get("retrieved_at",s.get("retrieved_at_utc","Unknown")))}</td><td>{e(s.get("acquisition_date","Unknown"))}</td><td>{e(s.get("sha256","Not supplied"))}</td></tr>' for s in case.get('sources',[]))
    warnings=''.join(f'<li>{e(w)}</li>' for w in result['warnings'])
    corrections=''.join(f'<li>{e(c["at"])} — {e(c["action"])}: {e(c["reason"])}</li>' for c in case.get('corrections',[])) or '<li>None recorded</li>'
    data=e(json.dumps({k:result[k] for k in ('screens','surface_assumption_scenarios','validation')},indent=2))
    terrain=case.get('terrain') or {}
    from .assessment_report import sections
    assessment_sections=sections(case,result)
    # Map evidence overlays only; never feed these polygons into GIS measurement.
    from copy import deepcopy
    from shapely.geometry import shape
    map_case=deepcopy(case)
    for record in case.get('assessment',{}).get('records',[]):
        if record.get('decision')=='rejected':continue
        for role in ('geometry','footprint_geometry'):
            try:
                geom=shape(record[role])
                if geom.is_empty or not geom.is_valid or geom.geom_type not in ('Polygon','MultiPolygon'):continue
            except (KeyError,ValueError,TypeError):continue
            map_case['features']['features'].append({'type':'Feature','id':str(record['id'])+' '+role,
                'geometry':record[role],'properties':{'layer':'footprint'}})
    return f'''<!doctype html><html lang="en"><meta charset="utf-8"><title>{e(case['name'])} — evidence report</title>
<style>body{{font:15px/1.5 system-ui;color:#183b34;max-width:1100px;margin:40px auto;padding:0 28px}}h1{{font-size:30px}}h2{{margin-top:32px}}table{{border-collapse:collapse;width:100%;font-size:13px}}td,th{{text-align:left;border-bottom:1px solid #cdd9d3;padding:9px;overflow-wrap:anywhere}}svg{{max-height:560px;width:100%;border:1px solid #cdd9d3}}pre{{white-space:pre-wrap;overflow-wrap:anywhere;background:#f1f4f2;padding:16px}}.warning{{background:#fff1d8;padding:16px}}@media print{{body{{margin:10px}}pre{{font-size:10px}}}}</style>
<h1>{e(case['name'])}</h1><p>Local stormwater evidence report • Case {e(case['id'])}<br>Input SHA-256: {e(result['input_sha256'])}</p>
<p class="warning">{e(result['claim'])}. No application or approval is represented. Annual values use the selected current tariff for twelve months; they are not historical invoices or expected recoveries.</p>
{map_svg(map_case,result)}<p>Map coordinates: {e(case['crs'])}. Roof: blue-gray; pavement: tan; pervious: green; unknown: amber; canopy: dark green; systems and assessment evidence: purple; inlets: blue; barriers: red. Assessment polygons are evidence overlays with status and areas below; they do not change physical IA or establish inlets.</p>
<h2>Physical and recorded areas (square feet)</h2><p>Area accounting CRS: {e(m.get('area_crs',case['crs']))}. Map/terrain CRS may differ; physical area accounting is preserved across terrain coordinate changes.</p><table><tr><th>Quantity</th><th>Measured</th><th>Recorded baseline</th></tr>{area}</table>
<p>{e(m['boundary_claim'])}. IA remains between {num(m['ia_min_sqft'])} and {num(m['ia_max_sqft'])} square feet until unknown surfaces are resolved. Source dependence: {e(m['source_dependence'] or 'None identified; independence still requires reference review')}.</p>
<h2>Billing and benefit ledger</h2><p>Observed public monthly total: ${num(baseline.get('published_monthly_total'))}. This remains source evidence when a calculation is blocked.</p><table><tr><th>Scenario</th><th>Status</th><th>Monthly total ($)</th><th>Annualized reduction ($)</th><th>Blockers</th></tr>{billing}</table><p>{e(b.get('reason',''))}</p>
<p>Existing benefits, rounded areas, per-account values and baseline differences are retained in analysis.json. Standard public charges do not establish the actual payer, discounts or paid invoice.</p>
{assessment_sections}
{research_sections(result)}
{modeled_sections(result)}
<h3>Conditional research bill-reduction alternatives</h3><p>These alternatives use the existing ledger and assume management prerequisites. Do not add them to existing assessment savings. Actual treatment capacity and approval remain unverified.</p><pre>{e(json.dumps(result.get('assessment',{}).get('research_drainage_scenarios',{}),indent=2))}</pre>
<h2>Missing evidence and limitations</h2><ul>{warnings}</ul>
<h2>Drainage</h2><p>Status: {e(result['drainage'].get('status','processed'))}. Catchments: {len(result['drainage'].get('catchments',[]))}. Horizontal unit: {e(terrain.get('horizontal_unit','Unknown'))}; vertical unit: {e(terrain.get('vertical_unit','Unknown'))}; cell size: {e(terrain.get('cell_size','Unknown'))}. Off-parcel IA is unmeasured; no whole-parcel allocation is assumed. Map snapshot shows up to 250 largest non-roof catchments and sampled flow paths; full geometries are in GeoJSON. Unconnected roof cells are grouped for display, not treated as confirmed outlets.</p>
<pre>{e(json.dumps({k:v for k,v in terrain.items() if k not in ('elevations','parcel_mask')},indent=2))}</pre>
<h2>Credit screens, surface scenarios and separate validation</h2><pre>{data}</pre>
<h2>Source snapshot</h2><table><tr><th>Source URL / input</th><th>Retrieved</th><th>Acquired</th><th>SHA-256</th></tr>{sources}</table><pre>{e(json.dumps(case.get('sources',[]),indent=2))}</pre><h2>Source quality reviews</h2><pre>{e(json.dumps({'reviews':case.get('source_quality_reviews',[]),'issues':result.get('source_quality_issues',[])},indent=2))}</pre>
<h2>Manual corrections</h2><ul>{corrections}</ul><h2>Assumptions</h2><pre>{e(json.dumps(case.get('assumptions',[]),indent=2))}</pre>
<p>Analysis processing: {result['processing_seconds']:.6f} seconds. Logged manual review: {num(case.get('manual_review_minutes'))} minutes. This is case-specific elapsed processing, not a throughput estimate; professional field review has not been measured.</p></html>'''
