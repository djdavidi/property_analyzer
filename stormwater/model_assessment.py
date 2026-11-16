"""Per-record policy interpretation of frozen AI/drainage estimates; no rerouting."""
from copy import deepcopy
from math import isfinite
from shapely.geometry import shape, mapping
from shapely.errors import ShapelyError
from drainage_core.geometry import case_area_sqft, union
from drainage_core.model_integration import composition, ia_bounds, EMPTY


def _region(value):
    if not value:return None
    try:
        g=shape(value)
        return g if g.is_valid and not g.is_empty and g.geom_type in ('Polygon','MultiPolygon') else None
    except (ValueError,TypeError,KeyError,ShapelyError):return None


def footprint(record,case):
    if record.get('footprint_geometry'):return _region(record['footprint_geometry'])
    if record.get('source',{}).get('crs')==case['crs'] and 'footprint' in str(record.get('public_geometry_role','')):
        return _region(record.get('public_geometry'))
    return None


def match(record,case,integration,run):
    """Identity first; a unique actual receiving-footprint overlap is a candidate."""
    facts=record.get('facts',{});raw=record.get('raw_record',{})
    category=record['category'];kind='outlet' if category=='direct_discharge' else 'gsi'
    wanted=[str(v) for v in ([facts.get('outfall_id'),record.get('outfall_id')] if kind=='outlet' else
            [record.get('gsi_id'),record.get('gsi_system_id'),facts.get('gsi_id'),facts.get('gsi_system_id'),raw.get('gsi_system_id')]) if v is not None and str(v).strip()]
    wanted=set(wanted)
    if len(wanted)>1:return {'status':'ambiguous','reason':'Conflicting receiver identifiers','candidate_ids':sorted(wanted)}
    if wanted:
        matches=[c for c in run['catchments'] if c['kind']==kind and c['receiver_id'] in wanted]
        if len(matches)==1:return {'status':'linked','basis':'explicit '+kind+' identity','catchment':matches[0]}
        return {'status':'missing','reason':'Explicit receiver has no modeled catchment','candidate_ids':sorted(wanted)}
    if kind=='outlet':return {'status':'missing','reason':'No explicit outfall identity; proximity does not establish discharge'}
    fp=footprint(record,case)
    if fp is None:return {'status':'missing','reason':'No receiver identity or usable system footprint'}
    ids={f['gsi_id'] for f in integration.get('receiving_features',[])
         if case_area_sqft(fp.intersection(shape(f['geometry'])),case)>.000001}
    matches=[c for c in run['catchments'] if c['kind']=='gsi' and c['receiver_id'] in ids]
    if len(ids)==1 and len(matches)==1:return {'status':'linked','basis':'unique receiving-footprint overlap; unverified','catchment':matches[0]}
    return {'status':'ambiguous' if len(ids)>1 else 'missing',
        'reason':'Multiple overlapping receiving systems' if len(ids)>1 else 'No uniquely linked receiving catchment',
        'candidate_ids':sorted(ids)}


def _conditions(record,case=None,gis=None,as_of=None):
    from .assessment_policy import COMMON,SMP,PAVEMENT,DIRECT
    category=record['category'];facts=record.get('facts',{})
    required=COMMON+(DIRECT if category=='direct_discharge' else SMP+ (PAVEMENT if category=='permeable_pavement' else ()))
    failed=[k for k in required if facts.get(k) is not None and facts.get(k) is not True]
    assumed=[k for k in required if facts.get(k) is not True]
    if facts.get('proposed_only') is True:failed.append('Proposed-only system; existing installation not established')
    if facts.get('installed') is False:failed.append('Installation recorded false')
    if category!='direct_discharge':
        value=facts.get('treatment_depth_inches');threshold=1 if facts.get('old_standard_renewal_verified') is True else 1.5
        if value is None:assumed.append('treatment_depth_inches >= '+str(threshold))
        else:
            try:
                if not isfinite(float(value)) or float(value)<threshold:failed.append('Insufficient recorded treatment depth')
            except (TypeError,ValueError):failed.append('Invalid recorded treatment depth')
        if facts.get('credit_path') not in (None,'management'):failed.append('Unsupported credit path')
    else:
        if facts.get('upstream_smp_present') is True:
            for key in ('upstream_smp_compliant','upstream_smp_functional'):
                if facts.get(key) is False:failed.append(key)
                elif facts.get(key) is not True:assumed.append(key)
        for key in ('waterway_name','outfall_id','upstream_smp_present'):
            if facts.get(key) is None:assumed.append(key)
    from drainage_core.installation import installation_issues
    failed+=installation_issues(facts,as_of)
    if case is not None:
        from .assessment_policy import screen_record
        # Modeled IA may differ from observed IA; all other known contradictory
        # geometry/evidence facts remain failures, not assumed successes.
        evaluated=screen_record(record,case,gis,as_of)
        failed += [k for k in evaluated['failed'] if k!='managed_geometry_matches_physical_ia']
        if 'source_update_review' in evaluated['missing']:failed.append('Unreconciled public source update')
    return list(dict.fromkeys(failed)),assumed


def _counterfactual(case,gis,screened,recipes,as_of,tariff):
    """Reuse one existing ledger. No source facts or verified screens are edited."""
    from .assessment_policy import _economics,_blocked
    if not recipes:return _blocked(['No linked, positive modeled area for this scenario'])
    failures=[reason for recipe in recipes for reason in recipe['failed']]
    if failures:return _blocked(failures)
    working=deepcopy(case);source_records={r['id']:r for r in working.get('assessment',{}).get('records',[])}
    replacements={};assumptions=[];areas={}
    all_ia=shape(gis['modeled_integration']['measurement']['geometries']['physical_ia'])
    for recipe in recipes:
        record=source_records[recipe['id']];region=recipe['region'];area=case_area_sqft(region,case)
        if area<.000001:return _blocked(['Modeled area unavailable for '+recipe['id']+'; missing evidence is not zero savings'])
        record['geometry']=mapping(region);record['managed_area_sqft']=area
        # Geometric reservations are excluded below; aggregate/account proof still
        # has to pass the existing allocation-reconciliation code.
        record.setdefault('facts',{})['existing_overlap_reconciled']=True
        replacements[recipe['id']]={'id':recipe['id'],'category':record['category'],'basis':'modeled',
            'status':'screen_pass','managed_area_sqft':area}
        all_ia=all_ia.union(region);areas[recipe['id']]=area
        assumptions.extend(recipe['assumed'])
    entries=[replacements.get(r['id'],r) for r in screened]
    m=gis['modeled_integration']['measurement'];view={**gis,'measurement':{**m,
        'geometries':{**m['geometries'],'physical_ia':mapping(all_ia)}}}
    economics=_economics(working,view,entries,as_of,tariff);s=economics['modeled']
    return {**s,'basis':'conditional AI/catchment alternative','record_areas_sqft':areas,
        'financial_scope':'credits only against retained recorded areas; not net of area correction',
        'net_with_area_correction':economics.get('modeled_combined'),
        'assumed_prerequisites':sorted(set(assumptions)),
        'claim':'Alternative under stated source/model/ground and eligibility assumptions; not a verified screen, approval or award. Do not add to other scenarios.'}


def catchment_alternatives(case,gis,screened,as_of,tariff,occupied,record_infos):
    """Show existing mapped GSI value even where it is not one of the five record types."""
    from .assessment_policy import _economics,_blocked
    integrated=gis['modeled_integration'];out=[]
    represented={r['receiver_id'] for i in record_infos for r in i.get('runs',[]) if r.get('receiver_id')}
    facts={k:True for k in ('physical_area_confirmed','parcel_allocation_confirmed','account_current','routing_confirmed',
        'approved_record_drawings','current_condition_confirmed','maintenance_documented','professional_reviewed')}
    facts['treatment_depth_inches']=1.5
    def value(region):
        if case_area_sqft(region,case)<.000001:return _blocked(['No unallocated modeled IA in this catchment'])
        working=deepcopy(case)
        working['features']['features'].append({'id':'ai-gsi-management-alternative','geometry':mapping(region),
            'properties':{'layer':'benefit','benefit':{'id':'ai-gsi-management-alternative','category':'management',
                'area_sqft':case_area_sqft(region,case),'basis':'modeled','evidence':facts,'existing_overlap_reconciled':True}}})
        m=integrated['measurement'];view={**gis,'measurement':{**m,'geometries':{**m['geometries'],
            'physical_ia':mapping(shape(m['geometries']['physical_ia']).union(region))}}}
        e=_economics(working,view,screened,as_of,tariff)
        return {**e['modeled'],'financial_scope':'credits only against retained recorded areas; not net of area correction',
            'net_with_area_correction':e.get('modeled_combined')}
    for run in integrated['runs']:
        unions={k:[] for k in ('lower','nominal','upper')}
        for c in run['catchments']:
            if c['kind']!='gsi' or c['receiver_id'] in represented or c['composition']['region_area_sqft']<.000001:continue
            from drainage_core.installation import installation_issues
            receiver=next((f for f in integrated.get('receiving_features',[]) if str(f['gsi_id'])==c['receiver_id']),None)
            source=(receiver or {}).get('source',{})
            failed,_=_conditions({'category':'green_roof','facts':{**source,**source.get('facts',{})}},as_of=as_of)
            if run.get('extent_sufficient') is not True:failed.append('Surrounding watershed extent is unverified')
            if receiver is None:failed.append('Receiving feature source is unavailable')
            for bound,region in ia_bounds(case,integrated,shape(c['geometry'])).items():
                region=region.difference(occupied)
                if not failed:unions[bound].append(region)
                out.append({'name':run['name'],'receiver_id':c['receiver_id'],'bound':bound,
                    'area_sqft':case_area_sqft(region,case),'on_parcel_contributing_sqft':c['composition']['region_area_sqft'],
                    **(_blocked(failed) if failed else value(region)),'basis':'conditional mapped-GSI management alternative',
                    'assumptions':['Mapped receiver is an existing eligible system and serves this parcel',
                        'All management prerequisites, 1.5-inch treatment and approved allocation are assumed',
                        'AI classes and modeled flow are unvalidated; upper adds unresolved ground as impervious',
                        'No verified inlet, ownership, treatment performance or award is established']})
        for bound,regions in unions.items():
            if regions:out.append({'name':run['name'],'receiver_id':'all_unassigned_gsi','bound':bound,
                'area_sqft':case_area_sqft(union(regions),case),**value(union(regions)),
                'basis':'conditional combined mapped-GSI alternative; deduplicated union, not sum of savings'})
    return out


def permit_alternatives(case,gis,screened,as_of,tariff):
    """Explicit what-if only; discovery status and source facts stay unchanged."""
    from .assessment_policy import _economics,_blocked,NPDES
    out=[]
    for r in case.get('assessment',{}).get('records',[]):
        if r['category']!='industrial_npdes' or r.get('decision')=='rejected':continue
        from .assessment_policy import screen_record
        facts=r.get('facts',{})
        failed=screen_record(r,case,gis,as_of)['failed']
        if r.get('source_update',{}).get('status')=='pending_review':failed.append('Unreconciled public source update')
        if failed:s=_blocked(failed)
        else:
            hypothetical=[{**x,'basis':'modeled','status':'screen_pass'} if x['id']==r['id'] else x for x in screened]
            s=_economics(case,gis,hypothetical,as_of,tariff)['modeled']
        out.append({'record_id':r['id'],'permit_id':facts.get('permit_id'),**s,'basis':'conditional industrial-coverage what-if',
            'assumptions':['Only if this permit is applicable active industrial coverage for this site/operator',
                'Account and previous-12-month compliance/reporting prerequisites are assumed, not established',
                'Do not add to canopy/management alternatives; combined benefits require their shared ledger']})
    return out


def integrate(case,gis,screened,as_of,tariff):
    from .assessment_policy import _blocked,_area_decimal,RULES
    from .billing import calculate_scenarios,default_tariff
    integrated=gis.get('modeled_integration')
    if not integrated:return {'status':'unavailable','records':[],'combined':[]}
    from drainage_core.quality import artifact_quality
    quality=artifact_quality(gis)
    if quality['status']=='outdated':return {'status':'outdated','records':[],'combined':[],
        'claim':quality['reason'],'reason':quality['reason'],'recompute_available':True}
    if case.get('assessment',{}).get('baseline_refresh',{}).get('status')=='pending_review':
        return {'status':'blocked','records':[],'combined':[],'claim':'Public billing baseline changed; reconcile before calculating savings'}
    parcel=shape(case['parcel']);sources=case.get('assessment',{}).get('records',[])
    items=[];recipes_by_key={}
    reserved=[]
    for r in case.get('assessment',{}).get('existing_credit_allocations',[]):
        if (g:=_region(r.get('geometry'))) is not None:reserved.append(g)
    # Retain existing legacy benefit allocations too. The ledger checks unsupported
    # overlap/reconciliation even when an item lacks usable geometry.
    from drainage_core.geometry import effective_features
    reserved.extend(shape(f['geometry']) for f in effective_features(case) if f.get('properties',{}).get('layer')=='benefit')
    occupied=union(reserved)
    runs=integrated.get('runs') or [{'name':'no_terrain','catchments':[]}]
    for record in sources:
        rid=record['id'];category=record['category'];fp=footprint(record,case)
        info={'record_id':rid,'basis':'modeled AI/drainage context','runs':[],
            'source_lineage':deepcopy(integrated['ai']['sources']),
            'prediction_sha256':integrated['ai']['prediction_sha256'],
            'input_lineage_sha256':integrated['input_lineage_sha256'],
            'uncertainty':deepcopy(integrated['ai']['uncertainty']),
            'footprint_composition':composition(case,integrated['ai'],integrated['measurement'],mapping(fp)) if fp is not None else None}
        if category=='industrial_npdes':
            info.update(status='not_applicable',reason='AI/drainage does not establish permit coverage, operator identity or compliance')
            items.append(info);continue
        if record.get('decision')=='rejected':
            info.update(status='rejected',reason='Manual rejection retained; no new modeled allocation')
            items.append(info);continue
        failed,assumed=_conditions(record,case,gis,as_of)
        if record.get('facts',{}).get('existing_overlap_reconciled') is False:failed.append('Existing overlap explicitly unreconciled')
        info['status']='modeled';info['known_failed_prerequisites']=failed
        info['unverified_prerequisites']=assumed
        for run in runs:
            linked=match(record,case,integrated,run);region=None;area_basis=None
            declared=_region(record.get('geometry'))
            if linked['status']=='linked':
                region=shape(linked['catchment']['geometry']).intersection(parcel);area_basis='linked research catchment'
            elif linked['status']!='ambiguous' and declared is not None:
                region=declared.intersection(parcel);area_basis='source-declared managed geometry; research connection unverified'
            elif linked['status']!='ambiguous' and fp is not None and category in ('green_roof','permeable_pavement'):
                region=fp.intersection(parcel);area_basis='direct rainfall on mapped footprint only; upstream contributing area unknown'
            output={'name':run['name'],'catchment_match':{k:v for k,v in linked.items() if k!='catchment'},
                'area_basis':area_basis,'managed_geometry':mapping(region) if region is not None else None,'scenarios':[]}
            if linked.get('catchment'):
                output['receiver_id']=linked['catchment']['receiver_id']
                output['off_parcel_area_sqft']=linked['catchment']['off_parcel_area_sqft']
            if region is not None:
                output['composition']=composition(case,integrated['ai'],integrated['measurement'],mapping(region))
                bounds=ia_bounds(case,integrated,region)
                # A mapped vegetated roof/permeable surface can be misclassified
                # by the generic model. The upper scenario explicitly assumes
                # unconfirmed ground in this region is qualifying IA.
                observed_pervious=shape(integrated['observed_pervious_geometry'])
                bounds['upper']=bounds['upper'].union(region.difference(observed_pervious))
                for bound,geom in bounds.items():
                    geom=geom.difference(occupied)
                    assumptions=assumed+['AI class accuracy and modeled drainage are unverified',area_basis,
                        'Required approval, condition and treatment evidence must cover the modeled area, not only an earlier recorded area']
                    if bound=='upper':assumptions+=['All unconfirmed ground in this region assumed impervious; not a confidence bound']
                    if bound=='lower':assumptions+=['Observed IA plus eroded AI boundaries; classification error remains unbounded']
                    route_failed=['Surrounding watershed extent is unverified'] if linked['status']=='linked' and run.get('extent_sufficient') is not True else []
                    recipe={'id':rid,'region':geom,'failed':failed+route_failed,'assumed':assumptions}
                    s=_counterfactual(case,gis,screened,[recipe],as_of,tariff)
                    output['scenarios'].append({'bound':bound,'area_sqft':case_area_sqft(geom,case),**s})
                    recipes_by_key.setdefault((run['name'],bound),[]).append(recipe)
            else:output['scenarios'].append({'bound':'unavailable',**_blocked([linked.get('reason','Catchment unavailable')])})
            info['runs'].append(output)
        items.append(info)
    combined=[]
    for (run,bound),recipes in recipes_by_key.items():
        usable=[r for r in recipes if not r['failed'] and case_area_sqft(r['region'],case)>.000001]
        excluded=[{'record_id':r['id'],'reasons':r['failed'] or ['No positive on-parcel modeled area; not zero savings']} for r in recipes if r not in usable]
        combined.append({'name':run,'bound':bound,**_counterfactual(case,gis,screened,usable,as_of,tariff),
            'scope':'calculable subset' if excluded else 'listed record alternatives',
            'excluded_records':excluded,'complete_opportunity':False})
    surface={};t=tariff or default_tariff()
    finance_allowed=RULES['effective_from']<=as_of.isoformat()<=RULES['verified_through'] and t['effective_from']<=as_of.isoformat()<=t['verified_through']
    if not finance_allowed:surface={'status':'blocked','reason':'Assessment date outside verified rule/tariff period'}
    elif case.get('baseline') and integrated['ai']['status']=='modeled':
        try:
            measured={**integrated['measurement'],**{k:float(_area_decimal(integrated['measurement'][k])) for k in ('ga_sqft','ia_sqft')}}
            b=calculate_scenarios(case['baseline'],measured,[],tariff=tariff)
            surface={'status':'conditional','measurement_only':b['appeal_only'],
                'claim':'AI-based surface correction alternative only; imagery classes and legal/billed areas are unverified. Do not add to credit alternatives.'}
            surface['area_alternatives']=[]
            baseline=case['baseline'];m=integrated['measurement']
            options=[('gross_area_only',m['ga_sqft'],baseline['ia_sqft'],[]),
                ('ia_unknown_assumed_pervious',baseline['ga_sqft'],m['ia_sqft'],['Unclassified/canopy-hidden ground assumed pervious']),
                ('ia_unknown_assumed_impervious',baseline['ga_sqft'],m['ia_sqft']+m['unknown_sqft'],['All unclassified/canopy-hidden ground assumed impervious'])]
            for name,ga,ia,assumptions in options:
                trial={**m,'ga_sqft':float(_area_decimal(ga)),'ia_sqft':float(_area_decimal(ia)),'complete':True}
                scenario=calculate_scenarios(baseline,trial,[],tariff=tariff)['appeal_only']
                surface['area_alternatives'].append({'name':name,'ga_sqft':trial['ga_sqft'],'ia_sqft':trial['ia_sqft'],
                    'assumptions':assumptions+['Counterfactual completed cover assumption, not a complete measured survey or a supported appeal'],
                    **scenario})
        except ValueError as exc:surface={'status':'blocked','reason':str(exc)}
    # Image context is not a permeability or green-roof detector.
    roof_shapes=[shape(f['geometry']) for f in effective_features(case) if f.get('properties',{}).get('class')=='roof' and f.get('properties',{}).get('layer')=='surface']
    roof_shapes.append(shape(integrated['ai']['roof_supplement_geometry']))
    vegetation=shape(integrated['ai']['geometries']['canopy']).union(shape(integrated['ai']['geometries']['grass_shrub']))
    roof_vegetation=vegetation.intersection(union(roof_shapes))
    canopy_scenarios=[]
    if case.get('baseline') and integrated['ai']['status']=='modeled':
        m=integrated['measurement'];canopy=shape(m['geometries']['canopy'])
        known_overlap=shape(m['geometries']['canopy_ground_ia'])
        hidden_overlap=canopy.intersection(shape(m['geometries']['unknown']))
        for name,region in [('modeled_overlap',known_overlap),('hidden_ground_assumed_impervious',known_overlap.union(hidden_overlap))]:
            region=region.difference(occupied);area=float(_area_decimal(case_area_sqft(region,case)))
            assumptions=['Canopy classification and overlap are modeled; eligibility/actual account bill remain unverified']
            if name.startswith('hidden'):assumptions.append('All unresolved ground below predicted canopy assumed impervious')
            if not finance_allowed:s=_blocked(['Assessment date outside verified rule/tariff period'])
            elif area<.000001:s=_blocked(['No supported modeled ground-IA overlap; canopy-hidden ground remains unknown'])
            else:
                benefit={'id':'ai-canopy-alternative','category':'canopy','area_sqft':area,'basis':'modeled',
                    'ledger_ids':['ai-canopy-alternative'],'existing_overlap_reconciled':True,
                    'evidence':{k:True for k in ('physical_area_confirmed','parcel_allocation_confirmed','account_current','ground_impervious_overlap_confirmed')}}
                try:
                    b=calculate_scenarios(case['baseline'],m,[benefit],tariff=tariff);v=b['credit_only']
                    s={'status':v['status'],'gross_monthly_reduction':v.get('monthly_savings'),
                        'gross_annual_reduction':v.get('annual_savings'),'reasons':v.get('reasons',[]),'bill':v}
                except ValueError as exc:s=_blocked([str(exc)])
            canopy_scenarios.append({'name':name,'area_sqft':area,'basis':'conditional AI canopy alternative',
                'assumptions':assumptions,**s})
    available=integrated['ai']['status']=='modeled'
    pavement=shape(integrated['ai']['geometries']['road']).union(shape(integrated['ai']['geometries']['developed_space']))
    categories={
        'green_roof':{'possible_roof_vegetation_sqft':case_area_sqft(roof_vegetation,case) if available else None,
            'claim':'Image vegetation on roof outlines nominates a possible feature; tree overhang and other causes remain possible. No green roof is established.'},
        'permeable_pavement':{'developed_or_road_appearance_sqft':case_area_sqft(pavement,case) if available else None,
            'permeability':'Unknown','claim':'Developed-space/road appearance is not a pavement measurement or permeability class.'},
        'direct_discharge':{'explicit_outlet_candidates':[{'receiver_id':c['receiver_id'],'composition':c['composition']}
            for c in (integrated.get('runs') or [{}])[0].get('catchments',[]) if c['kind']=='outlet'],
            'claim':'Only supplied outlet connections are traced. Water destination, private ownership and qualifying discharge remain unverified.'}}
    return {'status':integrated['status'],'records':items,'combined':combined,'surface_scenario':surface,
        'catchment_scenarios':catchment_alternatives(case,gis,screened,as_of,tariff,occupied,items),
        'permit_scenarios':permit_alternatives(case,gis,screened,as_of,tariff),
        'category_context':categories,
        'canopy_scenarios':canopy_scenarios,
        'image_context':{'possible_roof_vegetation_geometry':mapping(roof_vegetation),
            'possible_roof_vegetation_sqft':case_area_sqft(roof_vegetation,case) if integrated['ai']['status']=='modeled' else None,
            'claim':'Roof vegetation may be overhanging trees. Pavement classes do not establish permeability; no new treatment is confirmed.'},
        'claim':'Record-specific modeled alternatives alongside unchanged evidence-based findings. Combined scenarios use one ledger; unresolved overlaps block calculation.'}
