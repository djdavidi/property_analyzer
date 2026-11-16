"""Human-readable policy evidence sections; all entered strings are escaped."""
from html import escape
import json


def modeled_record_section(info):
    if not info:return ''
    e=lambda value:escape(str(value if value is not None else 'Unknown'))
    n=lambda value:'Unknown' if value is None else f'{value:,.2f}'
    parts=['<h5>AI and drainage estimates for this record</h5><p>'+e(info.get('reason') or info.get('basis'))+'</p>']
    composition=info.get('footprint_composition') or next((r['composition'] for r in info.get('runs',[]) if r.get('composition')),None)
    if composition:
        parts.append('<p>AI-estimated visible cover; ground beneath canopy remains unresolved.</p><table><tr><th>Class</th><th>Estimated area (ft²)</th><th>Pixel-edge range</th></tr>')
        for row in composition['classes']:
            parts.append('<tr><td>'+e(row['class'].replace('_',' '))+'</td><td>'+n(row['area_sqft'])+'</td><td>'+n(row['edge_lower_sqft'])+'–'+n(row['edge_upper_sqft'])+'</td></tr>')
        parts.append('</table>')
    for run in info.get('runs',[]):
        link=run['catchment_match']
        parts.append('<p>'+e(run['name'])+' · catchment '+e(link['status'])+' · '+e(run.get('receiver_id') or link.get('reason'))+'<br>'+e(run.get('area_basis'))+'</p>')
        parts.append('<table><tr><th>Assumption</th><th>Modeled IA (ft²)</th><th>Status</th><th>Monthly reduction</th><th>Annual reduction</th></tr>')
        for s in run['scenarios']:
            parts.append('<tr><td>'+e(s['bound'])+'</td><td>'+n(s.get('area_sqft'))+'</td><td>'+e(s['status'])+'</td><td>'+n(s.get('gross_monthly_reduction'))+'</td><td>'+n(s.get('gross_annual_reduction'))+'</td></tr>')
        parts.append('</table>')
    parts.append('<details><summary>Class areas, sources, uncertainty, blockers and assumed prerequisites</summary><pre>'+e(json.dumps(info,indent=2))+'</pre></details>')
    return ''.join(parts)


def modeled_combined_section(data):
    if not data:return ''
    e=lambda x:escape(str(x))
    n=lambda v:'Unknown' if v is None else f'{v:,.2f}'
    out=['<h3>AI/catchment-informed alternatives</h3><p>'+e(data['claim'])+'</p><p>These are alternatives to the existing findings and to each other. Tested bounds are assumptions, not statistical confidence. No approval or actual savings is established.</p><table><tr><th>Drainage run / area assumption</th><th>Status</th><th>Monthly reduction</th><th>Annual reduction</th><th>Blockers</th></tr>']
    for s in data.get('combined',[]):
        out.append('<tr><td>'+e(s['name']+' / '+s['bound'])+'</td><td>'+e(s['status'])+'</td><td>'+n(s.get('gross_monthly_reduction'))+'</td><td>'+n(s.get('gross_annual_reduction'))+'</td><td>'+e('; '.join(s.get('reasons',[])))+'</td></tr>')
    out.append('</table><h4>Area appeal assumptions</h4><p>Negative reductions mean bill increases. These cover assumptions do not establish a complete survey or a supported appeal.</p><table><tr><th>Assumption</th><th>Gross area (ft²)</th><th>Impervious area (ft²)</th><th>Monthly reduction</th><th>Annual reduction</th></tr>')
    for v in data.get('surface_scenario',{}).get('area_alternatives',[]):
        out.append('<tr><td>'+e(v['name'])+'</td><td>'+n(v['ga_sqft'])+'</td><td>'+n(v['ia_sqft'])+'</td><td>'+n(v.get('monthly_savings'))+'</td><td>'+n(v.get('annual_savings'))+'</td></tr>')
    out.append('</table>')
    for label,key in [('Mapped GSI management alternatives','catchment_scenarios'),('Industrial permit what-if','permit_scenarios'),('Canopy alternatives','canopy_scenarios')]:
        out.append('<h4>'+label+'</h4><p>Conditional alternatives only; eligibility and actual savings are unverified.</p><table><tr><th>Scenario / receiver</th><th>Area (ft²)</th><th>Status</th><th>Monthly reduction</th><th>Annual reduction</th></tr>')
        for v in data.get(key,[]):
            name=' / '.join(str(v.get(k)) for k in ('name','receiver_id','permit_id','bound') if v.get(k))
            out.append('<tr><td>'+e(name)+'</td><td>'+n(v.get('area_sqft'))+'</td><td>'+e(v['status'])+'</td><td>'+n(v.get('gross_monthly_reduction'))+'</td><td>'+n(v.get('gross_annual_reduction'))+'</td></tr>')
        out.append('</table>')
    out.append('<details><summary>Canopy, surface corrections, model ledgers and image context</summary><pre>'+e(json.dumps({k:v for k,v in data.items() if k!='records'},indent=2))+'</pre></details>')
    return ''.join(out)


def sections(case, result):
    assessment=result.get('assessment')
    if not assessment:return ''
    e=lambda value:escape(str(value if value is not None else 'Unknown'))
    number=lambda value:'Unknown' if value is None else f'{value:,.2f}'
    data=lambda value:'<pre>'+e(json.dumps(value,indent=2,ensure_ascii=False))+'</pre>'
    output=['<h2>Existing-site assessment</h2>',
            '<p>Assessment as of '+e(assessment.get('as_of'))+'. Candidate, reviewed manual, documented and modeled evidence remain distinct. Passing prerequisites does not establish approval or an award.</p>']
    if result.get('automatic'):
        auto=result['automatic'];output.append('<h3>Automatically acquired canopy and surface estimates</h3><p>'+e(auto.get('claim'))+'</p>')
        output.append('<table><tr><th>Feature</th><th>Source area (sq ft)</th><th>Pixel-edge sensitivity range</th><th>Source year</th></tr>')
        for row in auto.get('estimates',[]):
            output.append('<tr><td>'+e(row['feature'])+'</td><td>'+number(row['area_sqft'])+'</td><td>'+number(row['edge_lower_sqft'])+'–'+number(row['edge_upper_sqft'])+'</td><td>'+e(row['source_vintage'])+'<br>'+e(row.get('basis'))+'</td></tr>')
        output.append('</table><p>Image-derived canopy and surface areas are modeled, with independent local accuracy unverified. Without the local semantic model, only RGB cover candidates are available. Ranges represent pixel-edge sensitivity, not statistical confidence or current-site accuracy. Trees obscure ground surfaces. Satellite/aerial imagery must be within three years of the saved assessment date; other datasets retain their own validity rules; older snapshots remain historical.</p>')
        output.append(data({'imagery_age_policy':auto.get('imagery_age_policy'),'source_status':auto.get('source_status'),'system_footprints':auto.get('system_footprints'),
            'rgb_green_cover_candidate_sqft':auto.get('image_vegetation_candidate_sqft'),
            'rgb_green_overlap_historical_canopy_sqft':auto.get('image_green_overlap_historical_canopy_sqft'),
            'rgb_roof_vegetation_candidate_sqft':auto.get('roof_vegetation_candidate_sqft'),
            'landcover_method':auto.get('landcover',{}).get('settings'),'prediction_sha256':auto.get('landcover',{}).get('prediction_sha256'),'model_unavailable':auto.get('landcover',{}).get('model_unavailable'),'image_method':auto.get('image_method'),'warnings':auto.get('warnings')}))
    for category in assessment['categories']:
        output.append('<h3>'+e(category['label'])+' — '+e(category['status'])+'</h3>')
        if category.get('modeled_context'):
            output.append('<p>'+e(category['modeled_context']['claim'])+'</p>'+data(category['modeled_context']))
        if category.get('missing'):output.append('<p>Missing: '+e('; '.join(category['missing']))+'</p>')
        for record in category.get('records',[]):
            if category['category']=='prior_credits':continue
            output.append('<h4>Record '+e(record.get('id'))+' · '+e(record.get('status'))+'</h4>')
            output.append('<p>Basis: '+e(record.get('basis'))+'; physical footprint: '+number(record.get('footprint_area_sqft'))+
                          ' sq ft; contributing/managed area: '+number(record.get('managed_area_sqft'))+' sq ft.</p>')
            output.append('<p>Missing: '+e('; '.join(record.get('missing',[])) or 'None listed')+
                          '. Failed: '+e('; '.join(record.get('failed',[])) or 'None listed')+'.</p>')
            output.append('<p>Document/page and source references:</p>'+data(record.get('evidence_refs',[])))
            output.append(modeled_record_section(record.get('modeled_context')))
    economics=assessment.get('economics',{})
    output.append('<h3>Incremental gross ongoing reductions</h3><p>Each scenario compares one final bill with the same baseline. Scenarios are alternatives and must not be added together. Annual amounts illustrate twelve months at the selected rates.</p>')
    output.append('<table><tr><th>Scenario</th><th>Basis / status</th><th>Gross monthly reduction ($)</th><th>Gross annual reduction ($)</th><th>Missing evidence / assumptions</th></tr>')
    for key in ('documented','modeled','measurement_only','documented_combined','modeled_combined'):
        value=economics.get(key)
        if not value:continue
        output.append('<tr><td>'+e(key.replace('_',' '))+'</td><td>'+e(value.get('basis'))+' / '+e(value.get('status'))+
                      '</td><td>'+number(value.get('gross_monthly_reduction'))+'</td><td>'+number(value.get('gross_annual_reduction'))+
                      '</td><td>'+e('; '.join(value.get('reasons',[])+value.get('assumptions',[])))+'</td></tr>')
    output.append('</table><details><summary>Reconciled benefit ledgers, rounded areas and account bills</summary>'+data(economics)+'</details>')
    output.append(modeled_combined_section(assessment.get('modeled_integration')))
    output.append('<h3>Credit history and renewal reminders</h3><p>Reminder lead time is '+e(case.get('assessment',{}).get('renewal_lead_days',90))+ ' days, a configurable product preference rather than a legal deadline. Unknown dates are never inferred from a maximum term.</p>')
    output.append('<table><tr><th>Credit</th><th>Reminder state</th><th>Recorded deadline</th><th>Days remaining</th><th>Evidence gaps</th></tr>')
    for row in assessment.get('renewals',[]):
        output.append('<tr><td>'+e(row['credit_id'])+'</td><td>'+e(row['status'])+'</td><td>'+e(row['deadline'])+
                      '</td><td>'+e(row['days_remaining'])+'</td><td>'+e('; '.join(row['missing']+row['warnings']))+'</td></tr>')
    output.append('</table>'+data(assessment.get('credit_history',[])))
    output.append('<h4>Public credit-status observations</h4><p>Counts and flags are source observations. They do not establish an award, lapse, renewal deadline, denial or refund.</p>'+data(assessment.get('public_credit_observations',[])))
    output.append('<h3>Possible historical billing issues for review</h3><p>No refund entitlement or historical recovery is established. These flags are excluded from ongoing reductions.</p>')
    flags=assessment.get('historical_flags',[])
    output.append(data(flags) if flags else '<p>No discrepancy is established by the available records. Missing invoices, historical tariffs and award records prevent a complete historical review.</p>')
    output.append('<h3>Public-record coverage and failures</h3>'+data(assessment.get('source_status',[])))
    evidence=case.get('assessment',{})
    output.append('<h3>Manual facts and document inventory</h3>'+data({'records':evidence.get('records',[]),'attachments':evidence.get('attachments',[])}))
    output.append('<h3>Review lineage and assessment snapshots</h3>'+data({'reviews':evidence.get('reviews',[]),'snapshots':evidence.get('snapshots',[])}))
    output.append('<h3>Verified rule sources and versions</h3>'+data(assessment.get('rules',{})))
    return ''.join(output)
