"""Canopy context shares do not reconcile to the hidden crown area (soft share dropped)."""
import sys, os; sys.path.insert(0, os.getcwd())
from tests.test_surface_estimates_unit import fixture
from drainage_core.surface_estimates import estimate_surfaces
case, gis = fixture(); res = estimate_surfaces(case, gis, (2,))
c = res['canopy']['contexts'][0]; hidden = res['canopy']['hidden_ground_sqft']
s = c['road_context_under_canopy_sqft'] + c['developed_context_under_canopy_sqft'] + c['unclassified_context_under_canopy_sqft']
print('hidden', round(hidden, 3), 'road+dev+unclassified', round(s, 3), 'missing (soft share)', round(hidden - s, 3))
print('keys:', sorted(c))
