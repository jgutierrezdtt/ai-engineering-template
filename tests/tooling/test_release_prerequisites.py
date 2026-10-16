"""A source archive, configuration string or successful fixture is not a release."""

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))
import readiness
import source_bundle


class ReleasePrerequisitesTests(unittest.TestCase):
    def test_missing_business_targets_and_product_gates_remain_blocking(self):
        targets = {}
        quality = {"gates": [{"id": "synthetic-unit", "command": None}, {"id": "synthetic-release", "command": None}]}
        missing = readiness.blockers(targets, quality)
        self.assertIn("REMOTE-REPOSITORY", missing)
        self.assertIn("INFERENCE-PROVIDER", missing)
        self.assertEqual(len([item for item in missing if item.startswith("GATE-")]), 2)

    def test_local_metadata_does_not_claim_external_activation_or_approval(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); (root / "policy").mkdir()
            targets = {"repository": "synthetic/repository", "reviewers": ["synthetic"],
                       "cloud": {"provider": "synthetic", "project": "synthetic", "region": "synthetic"},
                       "inference": {"provider": "synthetic", "model": "synthetic"},
                       "product": {"first_agent": "synthetic", "allowed_actions": [], "data_classes": []},
                       "independent_review": {"technical_reference": "unverified", "legal_reference": "unverified"}}
            (root / "policy/targets.json").write_text(json.dumps(targets))
            (root / "policy/quality.json").write_text('{"gates":[]}')
            report = readiness.report(root)
        self.assertFalse(report["production_ready"])
        self.assertIn("RELEASE-SIGNATURE-VERIFIED", report["external_milestones_not_yet_verified"])

    def test_bundle_is_reproducible_and_tampering_is_detected(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve(); source = root / "repository"; source.mkdir()
            subprocess.run(["git", "init", "--initial-branch=main"], cwd=source, check=True, capture_output=True)
            (source / "file.txt").write_text("synthetic source")
            subprocess.run(["git", "add", "--", "file.txt"], cwd=source, check=True)
            subprocess.run(["git", "-c", "user.name=Synthetic", "-c", "user.email=synthetic@example.invalid",
                            "commit", "-m", "synthetic source"], cwd=source, check=True, capture_output=True)
            first = source_bundle.build(root / "bundle1", source=source)
            second = source_bundle.build(root / "bundle2", source=source)
            self.assertEqual(first["sha256"], second["sha256"])
            self.assertTrue(source_bundle.verify(root / "bundle1"))
            self.assertFalse(first["signed"])
            (root / "bundle1/source.tar.gz").write_bytes(b"tampered")
            self.assertFalse(source_bundle.verify(root / "bundle1"))
