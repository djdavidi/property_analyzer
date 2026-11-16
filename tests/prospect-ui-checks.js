/* DOM behavior only; all requests are fixtures, never public data or assessments. */
'use strict';
const assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
const nodes=new Map(),calls=[];let job='idle',scheduled;
const node=id=>{if(!nodes.has(id))nodes.set(id,{value:'',innerHTML:'',textContent:'',hidden:false,disabled:false,querySelectorAll:()=>[]});return nodes.get(id);};
const member=id=>({parcel_id:id,address:id+' TEST ST',billing:{annual_charge:1200},freshness:{status:'fresh'}});
const p={rank:1,parcel_id:'1',parcel_count:2,owner:'OWNER <script> LLC',address:'1 TEST ST',group:'no_area_credit',system_types:['Rain Garden'],systems:[{system_id:'G1'}],projects:['P1'],reasons:['Known records'],history_flags:[],evidence_gaps:['Capacity'],billing_source:{url:'https://example.test',retrieved_at:'2026-11-15'},billing:{annual_charge:2400,monthly_charge:200,ia_credit_sqft:0,ga_credit_sqft:0},member_parcels:[member('1'),member('2')],grouping_basis:'Nearby parcels',needs_record_review:false};
const result={id:'a'.repeat(32),at:'2026-11-15',elapsed_seconds:.1,status:'partial',ranking:'Scale first',coverage:'Bounded',ownership_policy:'Name screened',counts:{inventory_features:100,ranked_prospects:1,returned:1,failed_requests_or_geometry:1,exclusions_by_status:{government:2}},groups:[{id:'no_area_credit',label:'No credits',count:1}],top:[p],retry_parcel_ids:['9']};
const context=vm.createContext({document:{getElementById:node},console,URLSearchParams,setTimeout:fn=>{scheduled=fn;return 1;},clearTimeout:()=>{},fetch:async(path,options)=>{const body=options?.body?JSON.parse(options.body):null;calls.push({path,body});let data;
 if(path==='/api/prospects/latest')data={result};
 else if(path==='/api/prospects/job')data={status:job,stage:'billing_and_credits',completed:0,total:1};
 else if(path==='/api/prospects/scan'){job=body.mode==='rerank'?'complete':'running';data={status:job};}
 else if(path==='/api/prospects/cancel'){job='cancelled';data={status:job,error:'Cancelled'};}
 else throw Error('Unexpected endpoint '+path);
 return {ok:true,json:async()=>data};}});
vm.runInContext(fs.readFileSync('stormwater/web/prospects.js','utf8'),context);
(async()=>{
 await new Promise(resolve=>setImmediate(resolve));
 assert.match(node('groups').innerHTML,/2 billing parcel/);assert.match(node('groups').innerHTML,/prospect=1/);assert.match(node('groups').innerHTML,/prospect=2/);
 assert(!node('groups').innerHTML.includes('<script>'));assert.match(node('groups').innerHTML,/&lt;script&gt;/);
 calls.length=0;await node('scan').onclick();assert.equal(calls.find(x=>x.path==='/api/prospects/scan').body.mode,'rerank');
 assert(!calls.some(x=>x.path.includes('assessment')||x.path.includes('analyze')));
 vm.runInContext("selection.add('1')",context);await node('update').onclick();assert.deepEqual(calls.filter(x=>x.path==='/api/prospects/scan').at(-1).body.parcel_ids,['1','2']);assert.equal(node('scan').disabled,true);assert.equal(node('cancel-scan').hidden,false);
 await node('cancel-scan').onclick();await scheduled();assert.equal(node('scan').disabled,false);
 assert.equal(node('retry-failed').hidden,false);await node('retry-failed').onclick();assert.deepEqual(calls.filter(x=>x.path==='/api/prospects/scan').at(-1).body,{mode:'update',parcel_ids:['9']});
 console.log('Prospect UI checks passed: member parcels, escaping, local rerank default, explicit update, cancellation, failed-billing retry, no assessment calls.');
})().catch(e=>{console.error(e);process.exitCode=1;});
