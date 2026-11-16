import sys; sys.path.insert(0,'tests')
from test_modeled_assessment_unit import fixture, frozen_gis, assess, fake_research
from stormwater.portfolio_report import parcel_view, render_html, _plain_finding
from stormwater.billing import calculate_scenarios
c=fixture(); g=frozen_gis(c,fake_research(c)); a=assess(c,g)
r={**g,'assessment':a,'billing':{'baseline':calculate_scenarios(c['baseline'])['baseline']}}
m=parcel_view(c,r,{'parcel_id':'1','address':'Invented','systems':[{'system_id':'G1'}]})
cat=next(x for x in m['categories'] if x['category']=='management')
print('management status',cat['status'],'| scenarios',[(s['name'],s['status'],s['annual_change']) for s in cat['scenarios']])
print('plain amount:',_plain_finding(cat,m)[2])
