"""Known-answer model-output accounting; these checks do not prove model accuracy."""
from hashlib import sha256
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch
import numpy as np
from shapely.geometry import box,mapping
from drainage_core.semantic_cover import semantic_cover
from drainage_core.geometry import measure,SQFT_PER_M2
from test_automatic_site import fixture,png


class SemanticCoverTests(unittest.TestCase):
    def test_semantic_class_mapping_alpha_and_candidate_physical_separation(self):
        c=fixture();c['parcel']=mapping(box(0,0,2,1))
        raw=png([[[100,100,100,255]]*4,[[100,100,100,255]]*3+[[100,100,100,0]]])
        labels=np.array([[5,2,8,3],[5,0,8,3]],dtype='uint8')
        with tempfile.TemporaryDirectory() as temporary:
            folder=Path(temporary);weights=folder/'weights';weights.write_bytes(b'known fixture weights')
            runtime=folder/'python';runtime.touch()
            def infer(command,**kwargs):
                np.save(command[-1],labels,allow_pickle=False)
                return SimpleNamespace(returncode=0,stderr='')
            with patch('drainage_core.semantic_cover.MODEL_SHA256',sha256(weights.read_bytes()).hexdigest()), \
                 patch('drainage_core.semantic_cover.subprocess.run',side_effect=infer) as process:
                result=semantic_cover(raw,[0,0,2,1],c,{'sha256':sha256(raw).hexdigest(),'source_vintage':'2025'},
                                      runtime=runtime,weights=weights,cache=folder/'cache')
                again=semantic_cover(raw,[0,0,2,1],c,{'sha256':sha256(raw).hexdigest(),'source_vintage':'2025'},
                                     runtime=runtime,weights=weights,cache=folder/'cache')
                self.assertEqual(process.call_count,1)
                self.assertEqual(result['prediction_sha256'],again['prediction_sha256'])
                rows={r['feature']:r for r in result['estimates']}
                self.assertAlmostEqual(rows['canopy']['area_sqft'],.5*SQFT_PER_M2)
                self.assertAlmostEqual(rows['roof']['area_sqft'],.5*SQFT_PER_M2)
                self.assertAlmostEqual(rows['developed_space']['area_sqft'],.25*SQFT_PER_M2)
                self.assertNotIn('other_pavement',rows)
                self.assertAlmostEqual(result['unclassified_sqft'],.5*SQFT_PER_M2)
                c['features']['features']=result['features'];m=measure(c)
                self.assertIsNone(m['canopy_sqft']);self.assertEqual(m['ia_sqft'],0)
                self.assertAlmostEqual(m['unknown_sqft'],2*SQFT_PER_M2)
                # A bad cache entry is a miss: recomputed and repaired, never a permanent fallback.
                cache_file=next((folder/'cache').glob('*.npy'));cache_file.write_bytes(b'tampered')
                repaired=semantic_cover(raw,[0,0,2,1],c,{'sha256':sha256(raw).hexdigest(),'source_vintage':'2025'},
                                        runtime=runtime,weights=weights,cache=folder/'cache')
                self.assertEqual(process.call_count,2)
                self.assertEqual(repaired['prediction_sha256'],result['prediction_sha256'])
                self.assertEqual(cache_file.with_suffix('.sha256').read_text().strip(),sha256(cache_file.read_bytes()).hexdigest())

    def test_weights_must_match_pinned_model_before_any_inference(self):
        with tempfile.TemporaryDirectory() as temporary:
            folder=Path(temporary);weights=folder/'weights';weights.write_bytes(b'tampered')
            runtime=folder/'python';runtime.touch()
            with patch('drainage_core.semantic_cover.subprocess.run') as process:
                with self.assertRaisesRegex(ValueError,'weight hash mismatch'):
                    semantic_cover(b'not even an image',[0,0,4,2],fixture(),{},runtime=runtime,weights=weights)
                process.assert_not_called()
