import sys, warnings, inspect
warnings.filterwarnings('ignore')
from drainage_core import engine, quality
from stormwater.fixtures import synthetic_case
engine.analyze(synthetic_case())
loaded={m.split('.')[1]+'.py' for m in sys.modules if m.startswith('drainage_core.') }
src=inspect.getsource(quality.processing_fingerprint)
covered={n for n in loaded if f"'{n}'" in src}
print('GIS modules loaded by analyze():',sorted(loaded))
print('NOT in processing_fingerprint:',sorted(loaded-covered))
