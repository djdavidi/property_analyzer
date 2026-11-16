import sys,unittest
sys.path.insert(0,'./tests'); sys.path.insert(0,__import__('os').getcwd())
import test_assessment_http as t
t.AssessmentHTTPTests.maxDiff=None
s=unittest.TestSuite([t.AssessmentHTTPTests('test_confirmed_candidate_corrections_survive_public_rerun_and_export')])
unittest.TextTestRunner(verbosity=1).run(s)
