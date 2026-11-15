"""Human-readable policy evidence sections; all entered strings are escaped."""
from html import escape
import json


def sections(case, result):
    assessment=result.get('assessment')
    if not assessment:return ''
    e=lambda value:escape(str(value if value is not None else 'Unknown'))
    number=lambda value:'Unknown' if value is None else f'{value:,.2f}'
    data=lambda value:'<pre>'+e(json.dumps(value,indent=2,ensure_ascii=False))+'</pre>'
    output=['<h2>Existing-site assessment</h2>',
            '<p>Assessment as of '+e(assessment.get('as_of'))+'. Candidate, reviewed manual, documented and modeled evidence remain distinct. Passing prerequisites does not establish approval or an award.</p>']
    for category in assessment['categories']:
        output.append('<h3>'+e(category['label'])+' — '+e(category['status'])+'</h3>')
        if category.get('missing'):output.append('<p>Missing: '+e('; '.join(category['missing']))+'</p>')
        for record in category.get('records',[]):
            if category['category']=='prior_credits':continue
            output.append('<h4>Record '+e(record.get('id'))+' · '+e(record.get('status'))+'</h4>')
            output.append('<p>Basis: '+e(record.get('basis'))+'; physical footprint: '+number(record.get('footprint_area_sqft'))+
                          ' sq ft; contributing/managed area: '+number(record.get('managed_area_sqft'))+' sq ft.</p>')
            output.append('<p>Missing: '+e('; '.join(record.get('missing',[])) or 'None listed')+
                          '. Failed: '+e('; '.join(record.get('failed',[])) or 'None listed')+'.</p>')
            output.append('<p>Document/page and source references:</p>'+data(record.get('evidence_refs',[])))
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
