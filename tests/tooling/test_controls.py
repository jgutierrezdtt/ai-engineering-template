"""Behavioral tests of the enforcement tools, with synthetic, isolated state."""

import contextlib
import io
import json
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))
import check_repository
import processes
import quality
import scan_secrets as secret_controls
import run_tooling_tests


class RepositoryTests(unittest.TestCase):
    def test_sensitive_paths_and_example_boundary(self):
        for name in (".env", "a/.env.prod", "signing.key", "terraform.tfstate.backup", "a/client.p12"):
            self.assertTrue(check_repository.sensitive_path(name), name)
        for name in (".env.example", "packages/key.ts", "public/certificate.crt"):
            self.assertFalse(check_repository.sensitive_path(name), name)

    def test_external_action_requires_full_sha(self):
        self.assertTrue(check_repository.workflow_errors("    uses: vendor/action@v1\n"))
        self.assertFalse(check_repository.workflow_errors("    uses: vendor/action@" + "a" * 40 + "\n"))
        self.assertFalse(check_repository.workflow_errors("    uses: ./local/action\n"))

    def test_broken_and_external_local_links(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            document = root / "doc.md"
            document.write_text("[bad](missing.md) [escape](../outside.md) [web](https://example.com)")
            self.assertEqual(len(check_repository.broken_links(document, root)), 2)


class QualityTests(unittest.TestCase):
    def config(self):
        return json.loads((ROOT / "policy/quality.json").read_text())

    def test_unconfigured_product_cannot_pass(self):
        for profile in ("quick", "release"):
            with self.assertRaises(ValueError):
                quality.selected_gates(self.config(), profile)
        self.assertEqual(quality.selected_gates(self.config(), "bootstrap"), [])

    def test_empty_test_inventory_cannot_pass(self):
        config = self.config()
        config["gates"] = []
        with self.assertRaises(ValueError):
            quality.selected_gates(config, "quick")

    def test_empty_test_discovery_is_failure(self):
        with tempfile.TemporaryDirectory() as directory:
            with contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(run_tooling_tests.execute_suite(Path(directory)), 2)

    def test_commands_do_not_accept_shell_strings(self):
        config = self.config()
        for gate in config["gates"]:
            gate["command"] = "echo successful"
        with self.assertRaises(ValueError):
            quality.selected_gates(config, "quick")

    def test_release_cannot_omit_quick_controls(self):
        config = self.config()
        config["gates"][0]["profiles"] = ["quick"]
        with self.assertRaises(ValueError):
            quality.selected_gates(config, "release")

    def test_infinite_budget_is_rejected(self):
        config = self.config()
        config["budgets_seconds"]["quick"] = float("inf")
        with self.assertRaises(ValueError):
            quality.selected_gates(config, "quick")

    def test_parallel_gates_have_separate_temporary_state(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            program = "import os,pathlib,sys; pathlib.Path(sys.argv[1]).write_text(os.environ['AIE_RUN_DIR'])"
            gates = [{"id": name, "command": [sys.executable, "-c", program, str(root / name)]}
                     for name in ("first", "second")]
            with contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(quality.execute(gates, root, time.monotonic() + 5, 2), 0)
            paths = [(root / name).read_text() for name in ("first", "second")]
            self.assertNotEqual(paths[0], paths[1])
            self.assertTrue(all(not Path(path).exists() for path in paths))

    def test_nonzero_exit_fails_and_temporary_state_is_removed(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            locator = root / "locator"
            program = (
                "import os,pathlib,sys; "
                "p=pathlib.Path(os.environ['AIE_RUN_DIR']); "
                "(p/'synthetic-state').write_text('test'); "
                "pathlib.Path(sys.argv[1]).write_text(str(p)); sys.exit(7)"
            )
            gate = {"id": "failure", "command": [sys.executable, "-B", "-c", program, str(locator)]}
            with contextlib.redirect_stdout(io.StringIO()):
                code = quality.execute([gate], root, time.monotonic() + 5, 1)
            self.assertNotEqual(code, 0)
            self.assertFalse(Path(locator.read_text()).exists())

    def test_expired_budget_never_starts_command(self):
        with tempfile.TemporaryDirectory() as directory:
            marker = Path(directory) / "should-not-exist"
            result = processes.run([sys.executable, "-c", "import pathlib,sys; pathlib.Path(sys.argv[1]).touch()", str(marker)],
                                   Path(directory), 0)
            self.assertEqual(result.returncode, 124)
            self.assertFalse(marker.exists())

    def test_timeout_stops_descendants(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            marker = root / "orphan-finished"
            child = "import time,pathlib,sys; time.sleep(0.7); pathlib.Path(sys.argv[1]).touch()"
            parent = "import subprocess,sys,time; subprocess.Popen([sys.executable,'-c',sys.argv[1],sys.argv[2]]); time.sleep(30)"
            result = processes.run([sys.executable, "-c", parent, child, str(marker)], root, 0.3)
            self.assertEqual(result.returncode, 124)
            time.sleep(0.6)
            self.assertFalse(marker.exists())


class SecretTests(unittest.TestCase):
    def scan(self, root, **kwargs):
        with contextlib.redirect_stdout(io.StringIO()):
            return secret_controls.scan(root, **kwargs)

    def test_missing_scanner_is_failure(self):
        with patch.object(secret_controls.shutil, "which", return_value=None):
            self.assertEqual(self.scan(ROOT), 2)

    def test_canary_failure_is_not_a_clean_result(self):
        version = subprocess.CompletedProcess([], 0, "8.30.1\n", "")
        missed = subprocess.CompletedProcess([], 0, "", "")
        with patch.object(secret_controls, "invoke", side_effect=[version, missed]):
            self.assertEqual(self.scan(ROOT), 2)

    def init_index(self, root):
        subprocess.run(["git", "init", "-q", str(root)], check=True, capture_output=True)

    def stage(self, root, name, content):
        (root / name).write_text(content)
        subprocess.run(["git", "-C", str(root), "add", "--force", "--", name], check=True, capture_output=True)

    def fake_secret(self):
        return 'token = "' + 'ghp_' + 'AbCdEf0123456789' * 2 + 'AbCdEf01' + '"\n'

    def test_staged_secret_detected_even_if_working_file_clean(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.init_index(root)
            self.stage(root, "config.txt", self.fake_secret())
            (root / "config.txt").write_text("safe working copy\n")
            self.assertEqual(self.scan(root, staged=True), 1)

    def test_staged_scope_does_not_scan_unstaged_content(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.init_index(root)
            self.stage(root, "config.txt", "safe index\n")
            (root / "config.txt").write_text(self.fake_secret())
            self.assertEqual(self.scan(root, staged=True), 0)

    def test_sensitive_file_blocked_even_without_recognized_secret(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.init_index(root)
            self.stage(root, ".env", "SOME_SETTING=local\n")
            self.assertEqual(self.scan(root, staged=True), 1)

    def test_history_detects_secret_removed_from_current_tree(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.init_index(root)
            self.stage(root, "config.txt", self.fake_secret())
            commit = ["git", "-C", str(root), "-c", "user.name=AI Engineering test",
                      "-c", "user.email=tooling@example.invalid", "-c", "commit.gpgsign=false",
                      "-c", "core.hooksPath=/dev/null", "commit", "-qm"]
            subprocess.run(commit + ["synthetic fixture"], check=True, capture_output=True)
            self.stage(root, "config.txt", "safe current tree\n")
            subprocess.run(commit + ["remove synthetic fixture"], check=True, capture_output=True)
            self.assertEqual(self.scan(root), 0)
            self.assertEqual(self.scan(root, history=True), 1)


if __name__ == "__main__":
    unittest.main()
