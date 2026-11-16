"""DOM behavior checks; pointer/visual validation is a separate check."""

from pathlib import Path
import shutil
import subprocess
import unittest


class AssessmentUITests(unittest.TestCase):
    @unittest.skipUnless(shutil.which("node"), "Node is unavailable; UI behavior checks omitted")
    def test_policy_and_gis_workflows(self):
        result = subprocess.run(
            ["node", "tests/assessment-ui-checks.js"],
            cwd=Path(__file__).resolve().parents[1],
            capture_output=True,
            text=True,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    @unittest.skipUnless(shutil.which("node"), "Node is unavailable; UI behavior checks omitted")
    def test_curve_number_worksheet_rendering(self):
        result = subprocess.run(
            ["node", "tests/curve-number-ui-checks.js"],
            cwd=Path(__file__).resolve().parents[1],
            capture_output=True,
            text=True,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
