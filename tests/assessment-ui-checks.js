/* Behavior checks with a minimal DOM. These do not replace pointer/visual browser QA. */
'use strict';
const assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
const source=fs.readFileSync('drainage_core/web/app.js','utf8');
class Element{
 constructor(id=''){this.id=id;this.value='';this.innerHTML='';this.textContent='';this.dataset={};this.children=[];this.options=[];this.files=[];this.checked=false;this.tagName='INPUT';this.type='text';}
 addEventListener(){}setAttribute(){}append(child){this.children.push(child);}replaceChildren(){this.children=[];}querySelector(){return null;}querySelectorAll(){return this.fields||[];}scrollIntoView(){}remove(){}showModal(){}close(){}insertAdjacentHTML(_where,html){this.innerHTML=html+this.innerHTML;}
}
const clone=x=>JSON.parse(JSON.stringify(x));
const site={schema_version:1,id:'ui-fixture',name:'Site <script>bad</script>',crs:'EPSG:2272',parcel:{type:'Polygon',coordinates:[[[0,0],[20,0],[20,20],[0,20],[0,0]]]},features:{type:'FeatureCollection',features:[]},sources:[],corrections:[],assessment:{records:[],attachments:[],credit_history:[],snapshots:[]}};
const analysis={measurement:{ga_sqft:400,ia_sqft:null,unknown_sqft:400,canopy_ground_ia_sqft:0},billing:{status:'blocked'},drainage:{status:'unavailable'},validation:{ia:{status:'incomplete'},drainage:{status:'incomplete'}},warnings:[],assessment:{categories:[{category:'green_roof',status:'missing_evidence',records:[{id:'<img onerror=bad>',status:'missing_evidence',missing:['<script>bad</script>'],managed_area_sqft:null,footprint_area_sqft:null}]}],economics:{documented:{status:'blocked',gross_monthly_reduction:null,gross_annual_reduction:null,reasons:['Missing billing evidence']}},renewals:[],historical_flags:[]}};
analysis.assessment.public_credit_observations=[{credits_flag:null,expired_flag:1,appeals_flag:0,retrieved_at:'2026-11-15T12:00:00Z',source_url:'https://example.test/<script>flag</script>',effective_date:null,expiry_date:null,interpretation:'Public flags do not establish an award, lapse, renewal deadline or refund entitlement.',missing_evidence:['Award and date records']}];
async function harness(mode){
 const nodes=new Map(),calls=[];const node=id=>{if(!nodes.has(id))nodes.set(id,new Element(id));return nodes.get(id);};node('assessment-category').value='green_roof';
 const context=vm.createContext({document:{body:{dataset:{}},getElementById:node,querySelectorAll:()=>[],createElementNS:()=>new Element()},window:{addEventListener(){}},location:{search:''},URLSearchParams,structuredClone:clone,console,crypto:{randomUUID:()=> 'manual-event'},confirm:()=>true,fetch:async(path,options)=>{const payload=options?.body?JSON.parse(options.body):undefined;calls.push({path,payload});let data;if(path==='/api/config')data={mode,title:'Test',saved_views:true};else if(path==='/api/cases')data=[];else if(path==='/api/renewals')data={as_of:'2026-11-15',lead_days:90,properties:[]};else if(path.startsWith('/api/saved/'))data={case:clone(site),analysis:clone(analysis),saved_status:{message:'Showing saved results'}};else if(path.startsWith('/api/cases/'))data=clone(site);else if(path==='/api/analyze')data=clone(analysis);else if(path==='/api/save')data={...clone(analysis),quality_review:{status:'not_independently_validated',recompute_available:false}};else if(path==='/api/assessment/run'||path==='/api/property/assess')data={case:clone(site),analysis:{...clone(analysis),...(path==='/api/property/assess'?{automatic:{claim:'Source estimates',estimates:[{feature:'canopy',area_sqft:null,edge_lower_sqft:null,edge_upper_sqft:null,source_vintage:'2018'}],source_status:[{provider:'Land cover',status:'unavailable'}]}}:{})}};else if(path==='/api/assessment/review')data={case:{...clone(site),assessment:{...clone(site.assessment),records:[payload.record]}},analysis:clone(analysis)};else if(path==='/api/assessment/history')data={case:{...clone(site),assessment:{...clone(site.assessment),credit_history:[payload.event]}},analysis:clone(analysis)};else throw Error('Unexpected endpoint '+path);return {ok:true,json:async()=>data};}});
 vm.runInContext(source,context);await new Promise(resolve=>setImmediate(resolve));return {context,calls,node,run:code=>vm.runInContext(code,context)};
}
(async()=>{
 const p=await harness('philadelphia');p.calls.length=0;
 await p.run("load('ui-fixture')");
 assert(p.calls.some(c=>c.path==='/api/saved/ui-fixture'),'Open reads saved evidence');assert(!p.calls.some(c=>c.path==='/api/analyze'),'Open must not recalculate');
 assert(!p.calls.some(c=>c.path==='/api/assessment/run'),'Open must not gather public records or replace snapshot');
 assert.match(p.node('assessment-results').innerHTML,/Unknown/,'Unknown values remain explicit');
 assert(!p.node('assessment-results').innerHTML.includes('<script>bad</script>'),'Facts and record identifiers must be escaped');
 assert.match(p.node('assessment-results').innerHTML,/&lt;script&gt;/);
 assert.match(p.node('assessment-results').innerHTML,/Public credit flags/);assert.match(p.node('assessment-results').innerHTML,/Expired flag: <strong>1<\/strong>/);assert.match(p.node('assessment-results').innerHTML,/Effective date: Unknown/);assert.match(p.node('assessment-results').innerHTML,/do not establish an award/);
 p.calls.length=0;await p.node('run').onclick();
 assert.equal(p.calls.filter(c=>c.path==='/api/assessment/run').length,1,'Run assessment uses one public acquisition action');
 assert.match(p.node('status').textContent,/snapshot saved/);
 p.node('assessment-decision').value='rejected';p.node('assessment-basis').value='manual';p.node('assessment-reason').value='Reviewed source plan; proposed only';p.node('assessment-extra').value=JSON.stringify({source:{url:'https://example.test/plan'},evidence_refs:[{source_url:'https://example.test/plan',page:2}]});p.node('assessment-url').value='https://example.test/decision';p.node('assessment-page').value='3';
 await p.node('assessment-save-record').onclick();
 const reviewed=p.calls.find(c=>c.path==='/api/assessment/review').payload;
 assert.equal(reviewed.record.decision,'rejected');assert.equal(reviewed.record.evidence_refs.length,2,'Review retains previous document references');assert.equal(reviewed.record.evidence_refs[1].page,3);assert.equal(reviewed.reason,'Reviewed source plan; proposed only');
 // The editor must reload the just-recorded lineage before another correction.
 p.node('assessment-reason').value='Added another supporting record';p.node('assessment-url').value='https://example.test/next-record';p.node('assessment-page').value='4';await p.node('assessment-save-record').onclick();
 const secondReview=p.calls.filter(c=>c.path==='/api/assessment/review').at(-1).payload.record;assert.equal(secondReview.evidence_refs.length,3,'Repeated reviews must retain references introduced by the preceding review');
 p.node('assessment-category').value='industrial_npdes';p.node('assessment-category').onchange();assert.match(p.node('assessment-facts').innerHTML,/data-fact="account_current"/,'Industrial manual records must expose the account-current prerequisite');
 p.node('history-credit-id').value='unexplained-expired';p.node('history-event').value='expired';p.node('history-notes').value='Public record flag only';
 await p.node('history-add').onclick();
 const history=p.calls.find(c=>c.path==='/api/assessment/history').payload.event;
 assert.equal(history.status,'expired');assert(!('expires_on' in history));assert(!('effective_from' in history));assert(!('credited_area_sqft' in history),'Unknown history must not become zero area');
 p.calls.length=0;p.node('parcel-id').value='1901 Vine St';await p.node('acquire').onclick();
 assert.equal(p.calls[0].path,'/api/property/assess');assert.equal(p.calls[0].payload.query,'1901 Vine St');assert.match(p.node('automatic-results').innerHTML,/Automatic site estimates/);assert.match(p.node('automatic-results').innerHTML,/Unknown/);assert.match(p.node('automatic-results').innerHTML,/2018/);assert.match(p.node('automatic-results').innerHTML,/not statistical confidence/);
 const g=await harness('gis');g.calls.length=0;await g.run("current="+JSON.stringify(site));await g.node('run').onclick();
 assert(g.calls.some(c=>c.path==='/api/analyze'));assert(!g.calls.some(c=>c.path.includes('assessment')||c.path==='/api/renewals'),'GIS operation remains independent of policy endpoints');
 const research={method:'villanova-temple-local-v1',status:'partial',source:{url:'https://example.test/paper'},primary:{grid:{cell_size:1,horizontal_unit:'m'},filled_cells:5,catchments:[],known_ia_union_sqft:0,parameters:{},feature_audit:[{id:'<script>bad</script>'}],raster_sha256:{}},sensitivity:[],warnings:['<img onerror=bad>'],validation:{missing:['Independent drainage boundary']},omitted_features:[]};
 await g.run('result.research_drainage='+JSON.stringify(research)+';renderResults()');
 assert.match(g.node('research-results').innerHTML,/Villanova\/Temple additional drainage evidence/);
 assert.match(g.node('research-results').innerHTML,/Independent drainage boundary/);
 assert.match(g.node('research-results').innerHTML,/&lt;img/);
 assert(!g.node('research-results').innerHTML.includes('<script>bad</script>'));
 assert.equal(typeof g.node('show-research').onchange,'function');
 // D2 (final review p7): partial research money rows carry their label; vetoed receivers are listed.
 await g.run("result.assessment={research_drainage_scenarios:{scenarios:[{name:'nominal / known_ground_only',status:'calculated',gross_monthly_reduction:7.05,gross_annual_reduction:84.6,route_state:'partial_upstream_unknown',partial_label:'partial: true value may be higher',reasons:[]},{name:'conservative / known_ground_only',status:'blocked',route_state:'partial_upstream_unknown',partial_label:null,reasons:['Receiver G1 is not re-priced'],excluded_receivers:[{receiver_id:'G1',reasons:['Record rej was manually rejected']}]}]}};renderResults()");
 assert.match(g.node('research-results').innerHTML,/partial: true value may be higher/,'Partial research row shows its label');
 assert.match(g.node('research-results').innerHTML,/Route state: partial_upstream_unknown/,'A partial row without a label shows its route state');
 assert.match(g.node('research-results').innerHTML,/Receiver G1 not re-priced: Record rej was manually rejected/);
 const partialRows=await p.run("modeledScenarioRows([{bound:'nominal',status:'calculated',gross_annual_reduction:12,route_state:'partial_upstream_unknown',partial_label:null}])");
 assert.match(partialRows,/Route state: partial_upstream_unknown/);
 const invalid=await p.run("modeledCombinedHtml({status:'invalidated',reason:'Historical <script>bad</script> figures invalidated'})");
 assert.match(invalid,/Model-derived savings unavailable/);assert(!invalid.includes('<script>'));
 const subset=await p.run("modeledScenarioRows([{bound:'upper',status:'calculated',gross_annual_reduction:20,financial_scope:'credits only',scope:'calculable subset',excluded_records:[{record_id:'off',reasons:['outside parcel']}],net_with_area_correction:{status:'calculated',gross_annual_reduction:-200}}])");
 assert.match(subset,/credits only/);assert.match(subset,/calculable subset/);assert.match(subset,/Excluded off/);assert.match(subset,/Net with area correction/);assert.match(subset,/-200/);
 assert.equal(p.node('assessment-support-reviewed').checked,false,'Source support review must not carry over automatically');
 const beforePending=p.calls.length;
 await p.run("result.assessment.baseline_refresh={status:'pending_review',fields_changed:['ia_sqft'],candidate:{ia_sqft:123}};renderAssessment()");
 assert.match(p.node('assessment-results').innerHTML,/Public billing changes need review/);
 assert.match(p.node('assessment-results').innerHTML,/Savings are blocked/);
 assert.equal(typeof p.node('baseline-use-public').onclick,'function');assert.equal(typeof p.node('baseline-retain').onclick,'function');
 assert.equal(p.calls.length,beforePending,'Rendering a pending baseline must not recalculate or acquire');
 // Outdated saved results stay visible with an explicit, local recompute offer.
 await p.run("result={...result,quality_review:{status:'outdated',label:'Calculated by an older physical interpretation version 1; current version is 2.',recompute_available:true}};offerRecompute()");
 assert.equal(p.node('recompute-offer').hidden,false,'Outdated results offer Recompute from saved inputs');
 assert.match(p.node('recompute-label').textContent,/older physical interpretation version 1/);
 p.calls.length=0;await p.node('recompute').onclick();
 const recompute=p.calls.find(c=>c.path==='/api/save');
 assert(recompute&&recompute.payload.recompute_gis===true&&recompute.payload.case,'Recompute saves the case with recompute_gis');
 assert(!p.calls.some(c=>c.path==='/api/assessment/run'||c.path==='/api/property/assess'||c.path==='/api/acquire'),'Recompute never refreshes public sources');
 assert.equal(p.node('recompute-offer').hidden,true,'A current result hides the recompute offer');
 assert.match(p.node('status').textContent,/Recomputed from saved inputs/);
 const withheld=await p.run("modeledCombinedHtml({status:'outdated',reason:'Calculated by an older policy interpretation version 1'})");
 assert.match(withheld,/Model-derived savings unavailable/);
 console.log('UI behavior checks passed: local open, explicit assessment, unknowns, escaping, review lineage, history dates, GIS isolation, recompute offer.');
})().catch(error=>{console.error(error);process.exitCode=1;});
