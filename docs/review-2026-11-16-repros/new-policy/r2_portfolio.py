"""Repros for stormwater/portfolio_report.py (synthetic fixtures only; temp dir in scratchpad)."""
import json, sys, tempfile, re
from copy import deepcopy
from pathlib import Path
sys.path.insert(0, 'tests')
from test_modeled_assessment_unit import fixture, frozen_gis, assess, candidate
from shapely.geometry import box
from stormwater.portfolio_report import canopy_compatibility, parcel_view, render_html, build_portfolio
from stormwater.quality import safe_analysis
from stormwater.billing import calculate_scenarios

SCRATCH = Path(__import__('tempfile').mkdtemp())

print('=== R4: canopy cap ignores physical area occupied by existing credit allocations ===')
b = fixture()['baseline']
b.update(ia_sqft=6000, existing_ga_credit_sqft=4000, existing_ia_credit_sqft=4000,
         existing_credits_spatially_reconciled=True)
# Existing management award: 4000 sqft credit = 80% of 5000 sqft of IA physically occupied.
v = canopy_compatibility(b, 4000, 9000)
print(' recorded IA 6000; existing mgmt allocation occupies 5000; canopy cap area', v['area_sqft'],
      '-> status', v['status'], 'annual', v['annual_change'])
print(' occupied total =', 5000 + v['area_sqft'], '> recorded IA 6000')

print('\n=== R5: build_portfolio accepts an analysis that safe_analysis quarantines ===')
c = fixture(); c['features']['features'] = [candidate('canopy', box(0, 0, 30.48, 30.48))]
g = frozen_gis(c); a = assess(c, g)
bill = calculate_scenarios(c['baseline'])['baseline']
r = {**g, 'assessment': a, 'billing': {'baseline': bill},
     'quality_review': {'status': 'not_independently_validated'},
     'policy_processing_fingerprint': 'stale-fingerprint-from-older-billing-code'}
print(' safe_analysis status:', safe_analysis(r)['quality_review']['status'])
with tempfile.TemporaryDirectory(dir=SCRATCH) as tmp:
    folder = Path(tmp) / 'cases' / 'pwd-1'; folder.mkdir(parents=True)
    (folder / 'case.json').write_text(json.dumps(c)); (folder / 'analysis.json').write_text(json.dumps(r))
    p = build_portfolio({'source_run': 'x', 'sites': [{'parcel_id': '1', 'address': 'Invented', 'systems': []}]}, tmp)
    print(' build_portfolio accepted; as_of =', p['as_of'], '; charge =', p['sites'][0]['current_annual_public_charge'])

print('\n=== R6: computed charge rendered as "public records"; computed supported credit never shown ===')
c = fixture(); c['features']['features'] = [candidate('canopy', box(0, 0, 30.48, 30.48))]
c['baseline'].update(published_monthly_total=10.00)
g = frozen_gis(c); a = assess(c, g)
bill = calculate_scenarios(c['baseline'])['baseline']
r = {**g, 'assessment': a, 'billing': {'baseline': bill}}
m = parcel_view(c, r, {'parcel_id': '1', 'address': 'Invented', 'systems': []})
print(' published monthly', m['source_published_monthly_charge'], '-> computed monthly', m['current_monthly_public_charge'],
      'published_difference', bill.get('published_difference'))
m['supported_additional_annual_change'] = 500.0  # documented, verified-bill credit (as parcel_view would emit)
m['actual_invoice_verified'] = True
site = {'rank': 1, 'address': 'Site', 'owner': None, 'parcel_count': 1, 'parcel_ids': ['1'], 'members': [m],
        'current_annual_public_charge': m['current_annual_public_charge']}
html = render_html({'as_of': '2026-11-15', 'sites': [site]})
print(' overview cell:', re.search(r'<td>(\$[\d,]+)</td>', html).group(1), 'under header "Annual charge in public records"')
print(' "New credits confirmed: none established" present:', 'New credits confirmed: none established' in html)
print(' owner None rendered as:', re.search(r'</h2><p>([^<]*)</p>', html).group(1))
