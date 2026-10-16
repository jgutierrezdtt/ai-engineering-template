"""Adoption checks: canonical rules, native permissions and server enforcement identity."""

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))
import configure_github
import launch_agent
import sync_skills
import verify_change
from check_repository import SKILLS


class AdoptionTests(unittest.TestCase):
    def sources(self, root):
        for name in SKILLS:
            path = root / ".agents/skills" / name / "SKILL.md"
            path.parent.mkdir(parents=True)
            path.write_text("Canonical instructions for " + name)

    def test_skill_mirrors_detect_divergence_and_recover_from_canonical_source(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            self.sources(root)
            self.assertFalse(sync_skills.sync(root, check=True))
            self.assertTrue(sync_skills.sync(root))
            target = root / ".claude/skills" / sorted(SKILLS)[0] / "SKILL.md"
            target.write_text("Divergent instructions")
            self.assertFalse(sync_skills.sync(root, check=True))
            sync_skills.sync(root)
            self.assertTrue(sync_skills.sync(root, check=True))

    def test_mirror_symlink_never_writes_to_its_destination(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            self.sources(root)
            outside = root / "outside"
            outside.mkdir()
            (root / ".claude").symlink_to(outside, target_is_directory=True)
            with self.assertRaises(ValueError):
                sync_skills.sync(root)
            self.assertEqual(list(outside.iterdir()), [])

    def test_missing_canonical_skill_does_not_partially_write_other_mirrors(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            self.sources(root)
            (root / ".agents/skills" / sorted(SKILLS)[-1] / "SKILL.md").unlink()
            with self.assertRaises(FileNotFoundError):
                sync_skills.sync(root)
            self.assertFalse((root / ".claude").exists())

    def test_root_level_application_cannot_select_bootstrap(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.assertEqual(verify_change.required_profile(root), "bootstrap")
            (root / "main.py").write_text("print('synthetic application')")
            self.assertEqual(verify_change.required_profile(root), "quick")

    def test_launcher_passes_hooks_without_bypassing_native_security(self):
        version = subprocess.CompletedProcess([], 0, "codex-cli 0.160.1", "")
        with patch.object(launch_agent, "binary", return_value="codex"), patch.object(launch_agent.subprocess, "run", return_value=version):
            command = launch_agent.command("codex", ["--help"])
        self.assertIn("hooks", command)
        self.assertTrue(any(item.startswith("hooks=") for item in command))
        self.assertFalse(any("bypass" in item for item in command))
        self.assertNotIn("danger-full-access", command)

    def test_launcher_refuses_unvalidated_codex_version(self):
        version = subprocess.CompletedProcess([], 0, "codex-cli 0.160.2", "")
        with patch.object(launch_agent, "binary", return_value="codex"), patch.object(launch_agent.subprocess, "run", return_value=version):
            with self.assertRaises(ValueError):
                launch_agent.command("codex", [])

    def checks(self):
        return [{"name": name, "status": "completed", "conclusion": "success",
                 "app": {"id": 123, "slug": "github-actions"}} for name in configure_github.CONTEXTS]

    def test_server_rules_bind_checks_to_github_actions_and_require_another_reviewer(self):
        ruleset = configure_github.ruleset("main", self.checks())
        self.assertEqual(ruleset["bypass_actors"], [])
        rules = {item["type"]: item.get("parameters") for item in ruleset["rules"]}
        self.assertEqual(rules["pull_request"]["required_approving_review_count"], 1)
        self.assertTrue(rules["pull_request"]["require_last_push_approval"])
        self.assertTrue(all(item["integration_id"] == 123 for item in rules["required_status_checks"]["required_status_checks"]))

    def test_missing_failed_or_spoofed_ci_checks_prevent_rule_activation(self):
        for alteration in ("missing", "failed", "spoofed"):
            checks = self.checks()
            if alteration == "missing":
                checks.pop()
            elif alteration == "failed":
                checks[0]["conclusion"] = "failure"
            else:
                checks[0]["app"]["slug"] = "untrusted-app"
            with self.assertRaises(ValueError):
                configure_github.ruleset("main", checks)

    def test_github_preview_does_not_mutate_server_settings(self):
        def response(path, method="GET", body=None):
            self.assertEqual(method, "GET")
            self.assertIsNone(body)
            if path.endswith("/check-runs?filter=latest&per_page=100"):
                return {"check_runs": self.checks()}
            if "/commits/" in path:
                return {"sha": "a" * 40}
            return {"permissions": {"admin": True}, "default_branch": "main"}
        with patch.object(configure_github, "api", side_effect=response):
            result = configure_github.configure("synthetic/repository")
        self.assertEqual(result["mode"], "preview")
