"""Garden installed 2024, source DEM acquired 2015: capacity still measured from the 2015 bowl."""
import sys, os; sys.path.insert(0, os.getcwd())
from tests.test_runoff_capacity_unit import fixture
from drainage_core.runoff_capacity import estimate_capacity
case, gis = fixture()
case['sources'] = [{'acquisition_date': '2015-04-01', 'vertical_unit': 'm', 'sha256': 'd'*64}]
case['terrain']['acquisition_date'] = '2015-04-01'
r = estimate_capacity(case, gis, '01073')
print(case['features']['features'][0]['properties']['year_installed'], r['status'], round(r['surface_storage_volume_cuft'], 1),
      'dem date in lineage:', 'acquisition' in str(r['source_lineage']))
