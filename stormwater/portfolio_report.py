"""Small existing-site portfolio views over saved GIS/policy outputs; no acquisition."""
from copy import deepcopy
from html import escape
from math import isfinite
from pathlib import Path
import json

CATEGORIES=(('ia_adjustment','Impervious-area adjustment'),('ga_adjustment','Gross-area adjustment'),
 ('canopy','Tree canopy'),('management','Existing stormwater systems'),
 ('permeable_pavement','Existing permeable pavement'),('green_roof','Existing green roofs'),
 ('roof_disconnection','Roof disconnection'),('pavement_disconnection','Pavement disconnection'),
 ('open_space','Open space / curve number'),('direct_discharge','Direct surface-water discharge'),
 ('industrial_npdes','Industrial permit'),('history','Prior credits / billing history / refunds'))


def complete_sum(values):
    """Unknown is not zero; only sum explicitly compatible complete member values."""
    values=list(values)
    if not values or any(v is None or isinstance(v,bool) or not isinstance(v,(int,float)) or not isfinite(v) for v in values):return None
    return sum(values)


def scenario(value,**context):
    keys=('status','basis','reasons','assumptions','assumed_prerequisites','financial_scope',
          'area_sqft','gross_monthly_reduction','gross_annual_reduction','monthly_savings','annual_savings',
          'net_with_area_correction','excluded_records','scope')
    out={k:deepcopy(value[k]) for k in keys if k in value};out.update(context)
    out['annual_change']=value.get('gross_annual_reduction',value.get('annual_savings')) if value.get('status')=='calculated' else None
    return out


def without_geometry(value):
    """Detailed polygons remain in frozen per-parcel artifacts, not every table."""
    if isinstance(value,list):return [without_geometry(v) for v in value]
    if isinstance(value,dict):return {k:without_geometry(v) for k,v in value.items() if k not in ('geometry','geometries')}
    return value


def joint_area_hypotheses(baseline,measurement):
    from .billing import calculate_scenarios
    from .assessment_policy import _area_decimal
    out=[]
    # The upper IA must use the same GA as its physical assumption. Mixing source
    # GA with a slightly smaller recorded GA can create an impossible IA > GA.
    ga=float(_area_decimal(measurement['ga_sqft']))
    for name,ia in [('unresolved_ground_pervious',measurement['ia_sqft']),
                    ('unresolved_ground_impervious',measurement['ga_sqft']-measurement['pervious_sqft'])]:
        trial={**measurement,'ga_sqft':ga,'ia_sqft':float(_area_decimal(ia)),'complete':True}
        try:value=calculate_scenarios(baseline,trial,[])['appeal_only']
        except ValueError as exc:value={'status':'blocked','reasons':[str(exc)]}
        out.append(scenario(value,name=name+' / source GA',ga_sqft=ga,ia_sqft=trial['ia_sqft'],
            basis='Joint GA/IA extreme assumption, not a supported appeal; do not add the GA-only row',
            assumptions=['Identified IA is correct','All unresolved ground takes the stated cover',
                'Source polygon GA accepted; source/billing boundary and class accuracy unverified']))
    return out


def canopy_compatibility(baseline,identified_ia,hidden_canopy,known_overlap=0):
    """Conditional total-IA compatibility cap, not a measurement or confidence bound."""
    from .billing import calculate_scenarios
    b=baseline or {};recorded=b.get('ia_sqft')
    assumptions=['Recorded IA is exact/current for the same boundary and date',
        'Identified roof/surface IA is correct; unresolved IA outside canopy may use the remaining budget',
        'The capped hidden-canopy area is qualifying ground IA; eligibility/account prerequisites are assumed',
        'Credit-only upper stress test, not expected savings, an award or a supported appeal; do not add to other categories']
    out={'name':'recorded_total_compatible_canopy_cap','basis':'joint-assumption stress test',
         'status':'unknown','annual_change':None,'assumptions':assumptions}
    if any(v is None or isinstance(v,bool) or not isinstance(v,(int,float)) or not isfinite(v) or v<0 for v in (recorded,identified_ia,hidden_canopy,known_overlap)):
        return {**out,'reasons':['Canopy/area inputs unknown']}
    if identified_ia>recorded+.1:
        return {**out,'status':'contradictory','reasons':['Identified IA exceeds recorded IA; a negative residual is not zero canopy overlap']}
    cap=min(hidden_canopy,max(0,recorded-identified_ia));area=known_overlap+cap
    out.update(area_sqft=area,hidden_area_cap_sqft=cap,raw_all_hidden_area_sqft=hidden_canopy,
               raw_all_hidden_consistent=hidden_canopy<=recorded-identified_ia+.1)
    if area<.000001:return {**out,'status':'blocked','reasons':['No positive compatible overlap established; not evidence of zero savings']}
    benefit={'id':'portfolio-canopy-cap','category':'canopy','area_sqft':area,'basis':'modeled',
        'ledger_ids':['portfolio-canopy-cap'],'existing_overlap_reconciled':True,
        'evidence':{k:True for k in ('physical_area_confirmed','ground_impervious_overlap_confirmed','parcel_allocation_confirmed','account_current')}}
    try:
        value=calculate_scenarios(b,{},[benefit])['credit_only']
        return {**out,**scenario(value),'basis':'joint-assumption canopy cap; credit only; not a spatial allocation',
            'assumptions':assumptions,'conditional_final_annual_bill':value.get('annualized_total')}
    except ValueError as exc:return {**out,'status':'blocked','reasons':[str(exc)]}


def parcel_view(case,result,member):
    from shapely.geometry import shape
    from drainage_core.geometry import case_area_sqft,union
    from drainage_core.model_integration import _area_only
    from .model_assessment import footprint
    mi=result['modeled_integration'];a=result['assessment'];model=a.get('modeled_integration',{})
    m=mi['measurement'];baseline=case.get('baseline') or {};bill=result.get('billing',{}).get('baseline',{})
    categories={key:{'category':key,'label':label,'status':'unknown','supported_annual_change':None,
        'relevant_area_sqft':None,'scenarios':[],'missing':[],'records':[]} for key,label in CATEGORIES}
    sources={r['id']:r for r in case.get('assessment',{}).get('records',[])}
    selected={str(s['system_id']) for s in member.get('systems',[])}
    primary=(mi.get('runs') or [{'name':'no_terrain'}])[0]['name']
    for row in model.get('surface_scenario',{}).get('area_alternatives',[]):
        key='ga_adjustment' if row['name']=='gross_area_only' else 'ia_adjustment'
        categories[key]['scenarios'].append(scenario(row,name=row['name'],basis='Extreme area hypothesis, not a supported appeal'))
    categories['ia_adjustment']['raw_pipeline_hypotheses']=categories['ia_adjustment']['scenarios']
    categories['ia_adjustment']['scenarios']=joint_area_hypotheses(baseline,m)
    categories['ia_adjustment'].update(relevant_area_sqft=m['ia_sqft'],missing=['Complete current ground-surface IA and independently supported billing boundary'])
    categories['ga_adjustment'].update(relevant_area_sqft=m['ga_sqft'],missing=['Independent legal/billing boundary evidence; matching source totals are not validation'])
    canopy=m.get('canopy_sqft');hidden=None
    if canopy is not None:
        hidden=case_area_sqft(_area_only(shape(m['geometries']['canopy']).intersection(shape(m['geometries']['unknown']))),case)
    known=m.get('canopy_ground_ia_sqft')
    cap=canopy_compatibility(baseline,m['ia_sqft'],hidden,known)
    categories['canopy'].update(relevant_area_sqft=canopy,hidden_ground_sqft=hidden,
        qualifying_ground_ia_sqft=known if known and known>0 else None,scenarios=[cap],
        missing=['Ground material beneath crowns','Independent canopy/roof accuracy','Actual eligibility and existing award allocation'],
        raw_pipeline_hypotheses=[scenario(s,name=s['name']) for s in model.get('canopy_scenarios',[])])
    if cap.get('raw_all_hidden_consistent') is False:
        for v in categories['canopy']['raw_pipeline_hypotheses']:
            if v.get('name')=='hidden_ground_assumed_impervious':
                v['compatibility_review']='Not compatible with recorded total IA plus the identified IA hypothesis; withheld from available savings'
    for info in model.get('records',[]):
        record=sources[info['record_id']];key=record['category']
        if key not in categories or key=='industrial_npdes':continue
        sid=str(record.get('raw_record',{}).get('gsi_system_id',''))
        # Show selected mapped systems and explicitly identified on-parcel image
        # candidates. Adjacent discovered records remain in full raw artifacts.
        if sid and sid not in selected:continue
        fp=footprint(record,case)
        if fp is None or case_area_sqft(_area_only(fp.intersection(shape(case['parcel']))),case)<.000001:continue
        category=categories[key];category['records'].append({'id':record['id'],'system_id':sid or None,
            'decision':record.get('decision'),'facts':deepcopy(record.get('facts',{})),
            'source':deepcopy(record.get('source')),'evidence_refs':deepcopy(record.get('evidence_refs',[])),
            'footprint_area_sqft':info.get('footprint_composition',{}).get('region_area_sqft'),
            'class_composition':info.get('footprint_composition')})
        for run in info.get('runs',[]):
            for s in run['scenarios']:
                category['scenarios'].append(scenario(s,name=run['name']+' / '+s['bound'],run=run['name'],bound=s['bound'],
                    record_id=record['id'],area_basis=run.get('area_basis'),catchment_match=run.get('catchment_match')))
        category['status']='candidate';category['missing']=['Current installation/material','Approved served area and treatment','Condition, maintenance, invoice and award records']
    for key in ('permeable_pavement','green_roof','direct_discharge'):
        geoms=[_area_only(footprint(sources[r['id']],case).intersection(shape(case['parcel']))) for r in categories[key]['records']]
        if geoms:categories[key]['relevant_area_sqft']=case_area_sqft(union(geoms),case)
    categories['management']['records']=deepcopy(member.get('systems',[]))
    system_geoms=[_area_only(shape(f['geometry']).intersection(shape(case['parcel'])))
        for f in case.get('features',{}).get('features',[]) if f.get('properties',{}).get('kind')=='system_footprint'
        and str(f['properties'].get('gsi_system_id')) in selected]
    if system_geoms:categories['management']['relevant_area_sqft']=case_area_sqft(union(system_geoms),case)
    categories['management']['area_basis']='Mapped system footprint, not served or adequately treated drainage area'
    categories['management']['missing']=['Actual receiving entrances/pipe routes','Watershed extent','Approved treatment/allocation and current condition']
    categories['management']['scenarios']=[scenario(s,name=s['name']+' / '+s['receiver_id']+' / '+s['bound'],run=s['name'],bound=s['bound'],
        receiver_id=s['receiver_id']) for s in model.get('catchment_scenarios',[]) if s['receiver_id'] in selected]
    categories['management']['status']='blocked' if categories['management']['scenarios'] else 'unknown'
    for key in ('roof_disconnection','pavement_disconnection'):
        categories[key]['missing']=['Documented contributing area, receiving pervious ground, soils/slope and actual runoff route']
    categories['direct_discharge']['missing']=['Complete private conveyance/outfall route, receiving water, ownership and no City infrastructure']
    cn=a.get('open_space_curve_number',{})
    categories['open_space'].update(worksheet=without_geometry(cn),relevant_area_sqft=cn.get('mapped_open_space_sqft'),
        missing=cn.get('issues',[])+['Cover condition and supported site soil group; no assumed CN65'])
    # Existing primary-source review excludes two known construction permits.
    construction={'55527':('PAC510296','https://www.pacodeandbulletin.gov/secure/pabulletin/data/vol55/55-6/190b.html'),
                  '245240':('PAC510210','https://www.pacodeandbulletin.gov/secure/pabulletin/data/vol51/51-25/953b.html')}
    for r in case.get('assessment',{}).get('records',[]):
        if r['category']!='industrial_npdes':continue
        permit=r.get('facts',{}).get('permit_id');item={'id':r['id'],'permit_id':permit,'facts':deepcopy(r.get('facts',{})),'evidence_refs':deepcopy(r.get('evidence_refs',[]))}
        for s in model.get('permit_scenarios',[]):
            if s['record_id']!=r['id']:continue
            v=scenario(s,name=permit or r['id'])
            prior=construction.get(str(member['parcel_id']))
            if prior and permit==prior[0]:v.update(status='blocked',annual_change=None,reasons=['Primary-source notice identifies construction coverage; no industrial credit supported'],evidence_url=prior[1])
            categories['industrial_npdes']['scenarios'].append(v)
        categories['industrial_npdes']['records'].append(item)
    categories['industrial_npdes']['missing']=['Applicable current industrial coverage, exact site/operator match and required compliance history']
    categories['history'].update(records=deepcopy(a.get('public_credit_observations',[])),
        missing=['Actual dated bills, award/allocation letters, effective periods and adjustment records; no refund quantified'])
    views=list(categories.values())
    for category in views:
        positive=[s for s in category['scenarios'] if s.get('annual_change') is not None]
        if positive and category['status']=='unknown':category['status']='conditional'
        if category['category'] in ('ia_adjustment','ga_adjustment','canopy','open_space','industrial_npdes','history'):
            category['drainage_linkage']='Not a catchment-based calculation; see category evidence requirements'
        elif category['category'] in ('green_roof','permeable_pavement') and any('direct rainfall' in str(s.get('area_basis')) for s in category['scenarios']):
            category['drainage_linkage']='Direct-rainfall footprint hypothesis only; upstream contributing area unverified'
        else:category['drainage_linkage']='Partial extent; route unverified' if mi.get('runs') else 'Receiving route unverified; no usable saved terrain'
    ec=a.get('economics',{});net=ec.get('modeled_combined',{});supported=ec.get('documented',{})
    def classes():return {k:case_area_sqft(shape(g),case) for k,g in mi['ai']['geometries'].items()}
    return {'parcel_id':str(member['parcel_id']),'address':member['address'],'recorded_owner':member.get('owner'),
        'current_annual_public_charge':bill.get('annualized_total'),'current_monthly_public_charge':bill.get('monthly_total'),
        'source_published_monthly_charge':baseline.get('published_monthly_total'),
        'actual_invoice_verified':baseline.get('actual_bill_verified') is True,
        'recorded_ga_sqft':baseline.get('ga_sqft'),'recorded_ia_sqft':baseline.get('ia_sqft'),
        'identified_ia_sqft':m['ia_sqft'],'observed_surface_ia_sqft':result['measurement']['ia_sqft'],
        'unresolved_ground_sqft':m['unknown_sqft'],'visible_canopy_sqft':canopy,
        'appearance_areas_sqft':classes(),'existing_credits':{k:baseline.get(k) for k in ('existing_ga_credit_sqft','existing_ia_credit_sqft','existing_iar_sqft','npdes_fraction')},
        'supported_additional_annual_change':supported.get('gross_annual_reduction') if supported.get('status')=='calculated' and supported.get('basis')=='documented' else None,
        'net_annual_change':net.get('gross_annual_reduction') if net.get('status')=='calculated' else None,
        'net_status':net.get('status','unknown'),'net_blockers':net.get('reasons',[]),
        'bill_ladder':{'baseline':bill,'area_correction':ec.get('measurement_only'),
            'existing_credits':{k:baseline.get(k) for k in ('existing_ga_credit_sqft','existing_ia_credit_sqft','existing_iar_sqft','npdes_fraction')},
            'additional_credits':ec.get('modeled'),'final_with_area_correction':net},
        'categories':views,'primary_run':primary,'terrain_available':bool(case.get('terrain')),
        'watershed_extent_verified':bool(mi.get('runs')) and all(r.get('extent_sufficient') is True for r in mi['runs']),
        'sources':[ {k:s.get(k) for k in ('url','source_url','retrieved_at','acquisition_date','source_vintage','sha256')} for s in case.get('sources',[])],
        'imagery_vintage':case.get('automatic',{}).get('landcover',{}).get('source_vintage'),
        'model_sources':mi['ai'].get('sources',[]),'quality':result.get('quality_review'),
        'input_sha256':result.get('input_sha256'),'gis_analysis_sha256':result.get('gis_analysis_sha256')}


def build_portfolio(selection,root):
    root=Path(root);sites=[]
    for rank,site in enumerate(selection['sites'],1):
        members=[]
        for member in site.get('member_parcels',[site]):
            folder=root/'cases'/('pwd-'+str(member['parcel_id']))
            c=json.loads((folder/'case.json').read_text());r=json.loads((folder/'analysis.json').read_text())
            if r.get('quality_review',{}).get('status')=='invalidated':raise ValueError('Refuse invalidated portfolio input')
            members.append(parcel_view(c,r,member))
        totals={k:complete_sum(m[k] for m in members) for k in ('current_annual_public_charge','recorded_ga_sqft','recorded_ia_sqft','identified_ia_sqft','unresolved_ground_sqft','visible_canopy_sqft','supported_additional_annual_change','net_annual_change')}
        sites.append({'rank':rank,'address':site['address'],'owner':site.get('owner'),'parcel_count':len(members),
            'parcel_ids':[m['parcel_id'] for m in members],**totals,'evidence_status':'Modeled / incomplete; no verified net savings',
            'next_action':'Approved managed-area/as-built records, current invoices/awards, ground cover and receiving-route evidence',
            'members':members})
    return {'as_of':'2026-11-15','selection_source_run':selection['source_run'],'sites':sites,
        'claim':'Current-rate conditional scenarios from saved data. Unknown is not zero. Categories/assumptions overlap and must not be added. No award, supported appeal or refund is established.'}


PLAIN_LABELS={
 'ia_adjustment':'Roof and pavement area on the bill',
 'ga_adjustment':'Property size on the bill',
 'canopy':'Trees over pavement',
 'management':'Rain gardens, basins and other stormwater systems',
 'permeable_pavement':'Permeable pavement',
 'green_roof':'Green roofs',
 'roof_disconnection':'Roof drains that empty onto planted ground',
 'pavement_disconnection':'Pavement that drains onto planted ground',
 'open_space':'Grass, soil and other open areas',
 'direct_discharge':'Runoff sent directly to a waterway',
 'industrial_npdes':'Industrial stormwater permit credit',
 'history':'Past credits, billing errors and refunds'}


def _plain_money(value):
    return 'Cannot estimate yet' if value is None else ('−' if value<0 else '')+'$'+f'{abs(value):,.0f}'


def _saving_example(value,ceiling=False):
    if value==0:return 'No bill change in this example'
    if value<0:return 'Example: bill about '+_plain_money(abs(value))+'/year higher'
    return 'Example: '+('up to ' if ceiling else '')+'about '+_plain_money(value)+'/year lower'


def _example_values(category,member):
    return [s['annual_change'] for s in category.get('scenarios',[])
        if s.get('status')=='calculated' and s.get('annual_change') is not None
        and s.get('run',member['primary_run'])==member['primary_run']
        and s.get('bound','upper')=='upper']


def _plain_finding(category,member):
    key=category['category'];area=category.get('relevant_area_sqft')
    amount='Cannot estimate yet';values=_example_values(category,member)
    if key=='ia_adjustment':
        found='Too much of the ground surface is still unknown to check the billed roof and pavement area.'
        action='Check dated imagery or plans; confirm hidden ground where needed.'
    elif key=='ga_adjustment':
        found='The map and billed property sizes are close. This comparison has not shown a saving.'
        if values:
            amount=_saving_example(values[0])
        action='Check the billing boundary if an independent survey or title plan shows a difference.'
    elif key=='canopy':
        found=('The image shows about '+f'{area:,.0f}'+' sq ft of tree crowns. We have not verified the pavement beneath them.'
               if area is not None else 'Tree coverage or the ground beneath it is not known well enough.')
        if values:
            amount=_saving_example(values[0],ceiling=True)
        action='Confirm pavement under the trees. The example also assumes the recorded total paved area and mapped roofs are correct.'
    elif key=='management':
        found=(str(len(category.get('records',[])))+' mapped system record(s). Their outlines do not show how much runoff they receive or can treat.'
               if category.get('records') else 'We do not have a confirmed system and the area it serves.')
        action='Find the approved drainage plan, area served and treatment design; check current condition.'
    elif key=='permeable_pavement':
        found=('Public records mark possible permeable pavement. Its material, installation and treatment still need checking.'
               if category.get('records') else 'No permeable pavement area was established in this pass.')
        if values:
            amount='Separate mapped-area examples: '+'; '.join(_saving_example(v) for v in values)+'. These are not a site total.'
        action='Check the approved pavement design and current credit record. Resolve overlapping or duplicate areas before adding any examples.'
    elif key=='green_roof':
        found='Mapped candidates or vegetation on a roof do not yet confirm an existing green roof.'
        action='Check plans and current photos. Overhanging trees can look like roof vegetation.'
    elif key in ('roof_disconnection','pavement_disconnection'):
        found='We have not confirmed where this runoff goes or whether the receiving ground qualifies.'
        action='Trace the actual drainage route and check the receiving ground, soil and slope.'
    elif key=='open_space':
        found='The saved data do not establish the soil, ground cover and condition needed to calculate this credit.'
        action='Check available soil records and cover condition. No new soil records were downloaded in this pass.'
    elif key=='direct_discharge':
        found='A qualifying private route to a waterway has not been confirmed.'
        action='Confirm the full route, outlet and ownership, including whether City infrastructure is used.'
    elif key=='industrial_npdes':
        construction=any('construction' in ' '.join(s.get('reasons',[])).lower() for s in category.get('scenarios',[]))
        found=('The matched construction permit does not establish eligibility for this industrial credit.' if construction else
               'The saved permit records do not yet establish eligibility for this industrial credit.')
        action='Check permit type, current coverage, property/operator match and required compliance records.'
    else:
        found='No refund or missed past credit has been established. Public flags are not a complete award or billing history.'
        action='Compare dated bills with credit approval letters and the periods they cover.'
    return PLAIN_LABELS[key],found,amount,action


def _site_next_step(site):
    cats=[c for m in site['members'] for c in m['categories']]
    pavement=sum(len(c.get('records',[])) for c in cats if c['category']=='permeable_pavement')
    systems=sum(len(c.get('records',[])) for c in cats if c['category']=='management')
    if pavement:return 'Possible permeable pavement ('+str(pavement)+' mapped records)','Look for the approved pavement plan and current bill/credit record.'
    if systems:return str(systems)+' mapped stormwater system records','Look for the approved plan showing which areas drain into each system.'
    return 'Tree cover and billed area','Check ground cover beneath trees and compare it with the billed area.'


def render_html(data):
    """Plain-language presentation only. All calculations remain in saved JSON."""
    e=lambda v:escape(str(v));n=lambda v:'Not known' if v is None else f'{v:,.0f}'
    def table(headers,rows):
        return '<div class="scroll"><table><thead><tr>'+''.join('<th>'+e(h)+'</th>' for h in headers)+'</tr></thead><tbody>'+''.join(
            '<tr'+(' data-category="'+row[0]+'"' if len(row)==5 else '')+'>'+''.join('<td>'+v+'</td>' for v in (row[1:] if len(row)==5 else row))+'</tr>' for row in rows)+'</tbody></table></div>'
    overview=[]
    for site in data['sites']:
        lead,next_step=_site_next_step(site)
        overview.append([f'<a href="#site-{site["rank"]}">{e(site["address"])}</a>',
            _plain_money(site['current_annual_public_charge']),e(lead),e(next_step)])
    out=['<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">',
        '<title>Top ten properties: savings review</title><style>body{font:16px/1.55 system-ui;color:#183a33;max-width:1150px;margin:30px auto;padding:0 20px}h1{line-height:1.2}h2{margin-top:38px}h3{margin-top:24px}.note{background:#fff3da;padding:16px;border-left:4px solid #bd842a}.scroll{overflow:auto}table{border-collapse:collapse;width:100%;font-size:14px}th,td{padding:12px;text-align:left;vertical-align:top;border-bottom:1px solid #d3dfd7}th{background:#edf4ef}td:first-child{font-weight:600;min-width:135px}details{margin:16px 0}summary{cursor:pointer;font-weight:600}a{color:#19654d}.small{font-size:14px;color:#435f55}</style>',
        '<h1>Top ten properties: where savings may be worth checking</h1>',
        '<p>Results date: '+e(data['as_of'])+'. This review uses saved public records and image estimates.</p>',
        '<div class="note"><strong>We cannot give a reliable total saving for any property yet.</strong> We found leads to check. Missing information does not mean there is no saving.</div>',
        '<p><strong>How to read the money:</strong> the current charge comes from public records, not a checked invoice. An <strong>example</strong> shows what a credit could be worth if the stated checks pass. It is not a prediction or an approved credit. Different examples may cover the same ground, so do not add them.</p>',
        '<h2>Quick overview</h2><p>The properties stay in the earlier list order. This is not a ranking of confirmed savings.</p>',
        table(['Property','Annual charge in public records','Lead to check','First next step'],overview)]
    for site in data['sites']:
        lead,next_step=_site_next_step(site)
        out.append('<details class="property" id="site-'+str(site['rank'])+'"><summary>'+e(site['address'])+' — '+_plain_money(site['current_annual_public_charge'])+'/year in public records</summary><h2>'+e(site['address'])+'</h2><p>'+e(site['owner'])+'</p><p><strong>First next step:</strong> '+e(next_step)+'</p>')
        if len(site['members'])>1:out.append('<p>This site has '+str(len(site['members']))+' billing parcels. Each is shown separately below.</p>')
        for member in site['members']:
            if len(site['members'])>1:out.append('<h3>'+e(member['address'])+' — billing parcel '+e(member['parcel_id'])+'</h3><p>Annual public-record charge for this parcel: '+_plain_money(member['current_annual_public_charge'])+'.</p>')
            rows=[];other=[]
            for category in member['categories']:
                label,found,amount,action=_plain_finding(category,member)
                row=[category['category'],e(label),e(found),e(amount),e(action)]
                main=category['category'] in ('ia_adjustment','canopy','management') or (category['category']=='permeable_pavement' and category.get('records'))
                (rows if main else other).append(row)
            headers=['Possible saving','What we found','Money: example, not confirmed','Next check']
            out.append(table(headers,rows))
            out.append('<details><summary>Other checks: property size, roofs, drainage, soil, permits and refunds</summary>'+table(headers,other)+'</details>')
            measures=[['Whole billing property',n(member.get('recorded_ga_sqft'))+' sq ft',''],
                ['Roof and pavement area on the bill',n(member.get('recorded_ia_sqft'))+' sq ft','This is the area recorded by PWD.'],
                ['Mapped roofs / recorded hard surfaces',n(member.get('identified_ia_sqft'))+' sq ft','Partial map estimate; this is not the total actual roof/pavement area.'],
                ['Ground surface still unknown',n(member.get('unresolved_ground_sqft'))+' sq ft','We cannot yet classify this ground as paved or unpaved.'],
                ['Tree crowns visible from above',n(member.get('visible_canopy_sqft'))+' sq ft','Tree cover does not tell us what is underneath.']]
            out.append('<details><summary>See the area numbers behind this review</summary>'+table(['Measure','Area','What it means'],measures)+'<p>The difference between the billed area and the partial map estimate is <strong>not an appeal amount</strong>. We need a more complete ground-cover check first.</p></details>')
            credits=member.get('existing_credits',{})
            out.append('<details><summary>See the bill check and existing credits</summary><p>Public-record annual charge: '+_plain_money(member['current_annual_public_charge'])+'. The actual invoice has '+('been checked.' if member.get('actual_invoice_verified') else 'not been checked.')+'</p><p>Recorded area credits: '+n(credits.get('existing_ga_credit_sqft'))+' sq ft against property area and '+n(credits.get('existing_ia_credit_sqft'))+' sq ft against roof/pavement area. These figures do not establish a complete award history.</p><p><strong>Bill after area corrections: cannot estimate yet.<br>New credits confirmed: none established.<br>Final bill and total saving: cannot estimate yet.</strong></p><p>We need to check the area, existing credits and new credits together before giving one total.</p></details>')
            out.append('<p class="small">Billing parcel '+e(member['parcel_id'])+' · <a href="cases/pwd-'+e(member['parcel_id'])+'/analysis.json">Saved calculation data for a reviewer</a></p>')
        out.append('</details>')
    out.append('<h2>What can fill the gaps?</h2><p>Approved plans and public permit records may answer some questions. Actual bills, credit approval letters, maintenance records or a site check may be needed for the rest. We have not checked enough of these to confirm a final saving.</p><details><summary>Data, methods and checks</summary><p>Whole-property area is sometimes called GA. Roof and pavement area is called impervious area, or IA. A credit reduces the bill if requirements are met; an appeal corrects wrong billing information.</p><p>Image classes do not prove permeability. Soil and runoff routes remain unconfirmed. The calculated tree examples assume the recorded paved-area total and mapped roofs are correct, enough pavement lies under trees, and the credit qualifies. Broad all-paved/all-unpaved calculations are saved for review; they are not reliable appeal estimates.</p><p>No new property data or image classification was obtained for this review. The saved results were reused for this wording update. No browser or field validation was performed.</p><p><a href="comparison.json">Full saved results and assumptions</a> · <a href="https://water.phila.gov/wp-content/uploads/files/stormwater-credits-appeals-manual.pdf">PWD credit and appeal rules</a> · <a href="https://water.phila.gov/wp-content/uploads/files/rates-and-charges-2026-09-01.pdf">PWD rate schedule</a></p></details></html>')
    return ''.join(out)
