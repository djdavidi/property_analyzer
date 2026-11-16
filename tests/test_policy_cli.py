import contextlib
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from stormwater.policy_cli import main
from test_jurisdiction_adapter import fixture


class PolicyCLITests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        for name, data in zip(("case", "gis", "policy"), fixture()):
            (self.root / (name + ".json")).write_text(json.dumps(data))
        self.args = [
            "--jurisdiction",
            "philadelphia-pwd",
            "--case",
            str(self.root / "case.json"),
            "--gis",
            str(self.root / "gis.json"),
            "--policy",
            str(self.root / "policy.json"),
            "--output",
            str(self.root / "credits.json"),
        ]

    def invoke(self, args):
        with contextlib.redirect_stdout(io.StringIO()) as out:
            result = main(args)
        return result, json.loads(out.getvalue())

    def test_separate_frozen_inputs_create_policy_artifact_without_gis_run(self):
        before = {p.name: p.read_bytes() for p in self.root.glob("*.json")}
        with patch(
            "drainage_core.engine.analyze", side_effect=AssertionError("No GIS run permitted")
        ):
            code, summary = self.invoke(self.args)
        self.assertEqual(code, 0)
        self.assertEqual(summary["jurisdiction"], "philadelphia-pwd")
        result = json.loads((self.root / "credits.json").read_text())
        self.assertEqual(result["artifact_type"], "jurisdiction-policy-analysis")
        self.assertEqual(result["billing"]["credit_only"]["monthly_savings"], 7.05)
        for name, content in before.items():
            self.assertEqual((self.root / name).read_bytes(), content)

    def test_output_cannot_overwrite_any_frozen_input(self):
        for name in ("case", "gis", "policy"):
            args = self.args[:-1] + [str(self.root / (name + ".json"))]
            code, error = self.invoke(args)
            self.assertEqual(code, 1)
            self.assertIn("must not overwrite", error["error"])

    def test_stale_artifact_and_invalid_policy_fail_without_output(self):
        case = json.loads((self.root / "case.json").read_text())
        case["name"] = "changed snapshot"
        (self.root / "case.json").write_text(json.dumps(case))
        code, error = self.invoke(self.args)
        self.assertEqual(code, 1)
        self.assertIn("does not match", error["error"])
        self.assertFalse((self.root / "credits.json").exists())

    def test_modified_physical_measurement_digest_is_rejected(self):
        artifact = json.loads((self.root / "gis.json").read_text())
        artifact["measurement"]["ia_sqft"] = 0
        (self.root / "gis.json").write_text(json.dumps(artifact))
        code, error = self.invoke(self.args)
        self.assertEqual(code, 1)
        self.assertIn("content digest", error["error"])
        self.assertFalse((self.root / "credits.json").exists())


if __name__ == "__main__":
    unittest.main()
