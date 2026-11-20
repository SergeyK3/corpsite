"""No database required: check the release identity guard with disposable files."""
import json
import tempfile
import unittest
from pathlib import Path

from scripts.verify_frontend_runtime_id import verify


class FrontendRuntimeIdTest(unittest.TestCase):
    def test_matching_build_and_runtime_id(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            build = root / ".next"
            build.mkdir()
            expected = "a" * 40
            (build / "required-server-files.json").write_text(
                json.dumps({"config": {"deploymentId": expected}}), encoding="utf-8")
            env = root / "frontend.env"
            env.write_text(f"NEXT_DEPLOYMENT_ID={expected}\n", encoding="utf-8")
            self.assertEqual(verify(build, env), expected)

    def test_old_runtime_id_blocks_switch(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            build = root / ".next"
            build.mkdir()
            (build / "required-server-files.json").write_text(
                json.dumps({"config": {"deploymentId": "b" * 40}}), encoding="utf-8")
            env = root / "frontend.env"
            env.write_text("NEXT_DEPLOYMENT_ID=" + "a" * 40 + "\n", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "differs"):
                verify(build, env)


if __name__ == "__main__":
    unittest.main()
