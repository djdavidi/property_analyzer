'use strict';
const assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
const src=fs.readFileSync('drainage_core/web/app.js','utf8');
const start=src.indexOf('function curveNumberHtml('),end=src.indexOf('function renderAssessment(){',start);
const context=vm.createContext({esc:x=>String(x).replaceAll('&','&amp;').replaceAll('<','&lt;').replaceAll('>','&gt;').replaceAll('"','&quot;'),fmt:x=>x==null?'Unknown':Number(x).toFixed(2)});
vm.runInContext(src.slice(start,end),context);
const w={claim:'Conditional, not approved',average_cn:null,mapped_open_space_average_cn:61,known_portion_average_cn:61,mapped_open_space_sqft:1000,unknown_cn_area_sqft:0,image_candidate_area_sqft:500,unresolved_ground_sqft:500,formula:'sum(area × CN) / area',credit_factor:null,rounding:'No automatic savings allocation',issues:['Missing soil'],rows:[{feature_id:'<img src=x>',basis:'image_candidate',area_sqft:500,cover:null,condition:null,soil_group:null,mapunit_name:'<script>bad</script>',curve_number:null,area_times_cn:null,candidate_cn_min:61,candidate_cn_max:89,missing:['Cover condition unknown'],input_basis:'mapped attributes'}]};
context.w=w;const html=vm.runInContext('curveNumberHtml(w)',context);
assert.match(html,/Property open-space CN: Unknown/);assert.match(html,/Mapped open-space average: 61.00/);
assert.match(html,/Cover condition unknown/);assert.match(html,/Candidate range: 61.00–89.00/);
assert.match(html,/cn-save-inputs/);assert(!html.includes('<script>bad</script>'));assert(!html.includes('<img src=x>'));
assert.match(html,/&lt;script&gt;/);assert.match(html,/Soil components, source requests, dates/);
w.rows=[];assert.match(vm.runInContext('curveNumberHtml(w)',context),/No zero area or credit/);
// B8/A5: UB stays a reviewer choice; the finance scenario is labelled conditional.
assert(!html.includes('cn-soil-ub'),'No UB control without an eligible urban-soil map unit');
const ub={...w,rows:[{feature_id:'lawn',basis:'mapped_open_space',area_sqft:800,cover:'lawn',condition:'fair',soil_group:null,soil_basis:null,mapunit_key:'1479568',mapunit_name:'Urban land <b>x</b>',curve_number:null,area_times_cn:null,candidate_cn_min:null,candidate_cn_max:null,ub_choice_available:true,ub_candidate_cn:69,ub_candidate_cn_min:69,ub_candidate_cn_max:69,missing:['Soil hydrologic group missing or unsupported'],input_basis:'manual review'}],
 ub_candidate:{status:'candidate_requires_reviewer_ub_choice',average_cn:69,credit_factor:.24,claim:'Reviewer choice only'},
 finance_scenario:{status:'requires_review',label:'Conditional open-space credit scenario',curve_number:null,credit_factor:null,open_space_area_sqft:null,ga_credit_sqft:null,gross_monthly_reduction:null,gross_annual_reduction:null,assumed_prerequisites:{cover_confirmed:true,soil_confirmed:true},reasons:['Cover <i>review</i> needed'],claim:'Only if accepted'}};
context.w=ub;const ubHtml=vm.runInContext('curveNumberHtml(w)',context);
assert.match(ubHtml,/UB candidate \(reviewer choice required\): 69\.00/);assert.match(ubHtml,/Property CN if a reviewer records UB: 69\.00; standard factor 24\.00%/);
assert.match(ubHtml,/id="cn-soil-ub"/);assert.match(ubHtml,/id="cn-soil-withdraw"/);assert.match(ubHtml,/never chosen automatically/);
assert.match(ubHtml,/site soil test/);assert(!ubHtml.includes('<b>x</b>'));assert(!ubHtml.includes('<i>review</i>'));
assert.match(ubHtml,/Conditional open-space finance scenario/);assert.match(ubHtml,/requires review/);assert.match(ubHtml,/Unknown\/month/);
assert.match(ubHtml,/Assumed, not established: cover confirmed, soil confirmed/);
ub.finance_scenario={...ub.finance_scenario,status:'conditional',curve_number:69,credit_factor:.24,open_space_area_sqft:800,ga_credit_sqft:192,gross_monthly_reduction:5,gross_annual_reduction:60,increment:{status:'calculated',gross_monthly_reduction:0.39,gross_annual_reduction:4.68},reasons:[]};
const priced=vm.runInContext('curveNumberHtml(w)',context);
assert.match(priced,/\$0\.39\/month, \$4\.68\/year/);assert.match(priced,/GA credit 192\.00 sq ft/);
console.log('CN worksheet UI: unknowns, subset averages, candidate ranges, review controls, UB reviewer choice, conditional finance scenario and escaping passed.');
