"""Regression and adversarial checks for isolation, fixtures and trust boundaries."""

import copy
import hashlib
import json
import sys
import tempfile
import shutil
import subprocess
import unittest
import urllib.request
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))
import project_toolchain
from native_hook_probe import fixture_server
from run_native_container import validate_inspection
from verify_candidate import freeze
from ephemeral_containers import expired_owned, CONTROLLER


class OperationalTests(unittest.TestCase):
    def test_real_precommit_rejects_staged_secret_before_creating_a_commit(self):
        with tempfile.TemporaryDirectory(prefix="aie-git-hook-test-") as directory:
            root = Path(directory).resolve()
            for name in ("tools", "policy", ".githooks"):
                (root / name).mkdir()
            for name in ("tools/scan_secrets.py", "tools/check_repository.py", "policy/quality.json", ".gitleaks.toml", ".githooks/pre-commit"):
                shutil.copyfile(ROOT / name, root / name)
            (root / ".githooks/pre-commit").chmod(0o755)
            subprocess.run(["git", "init", "--initial-branch=main"], cwd=root, check=True, capture_output=True)
            subprocess.run(["git", "config", "--local", "core.hooksPath", ".githooks"], cwd=root, check=True)
            synthetic = 'token = "' + 'ghp_' + 'AbCdEf0123456789' * 2 + 'AbCdEf01' + '"'
            (root / "leak.txt").write_text(synthetic)
            subprocess.run(["git", "add", "--", "leak.txt"], cwd=root, check=True)
            result = subprocess.run(["git", "-c", "user.name=Synthetic", "-c", "user.email=synthetic@example.invalid",
                                     "-c", "commit.gpgsign=false", "commit", "-m", "must be rejected"],
                                    cwd=root, capture_output=True, text=True, timeout=15)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("detección bloqueante", result.stdout + result.stderr)
            self.assertNotIn(synthetic, result.stdout + result.stderr)
            head = subprocess.run(["git", "rev-parse", "--verify", "HEAD"], cwd=root, capture_output=True)
            self.assertNotEqual(head.returncode, 0)

    def test_anthropic_fixture_returns_a_real_sse_response_without_paid_requests(self):
        with fixture_server("Bash", {"command": "pwd"}) as (port, observed):
            request = urllib.request.Request("http://127.0.0.1:{}/v1/messages".format(port),
                data=json.dumps({"messages": [], "stream": True}).encode(), headers={"Content-Type": "application/json"})
            with urllib.request.urlopen(request, timeout=3) as response:
                payload = response.read().decode()
            self.assertIn('event: message_start', payload)
            self.assertIn('"tool_use"', payload)
            self.assertEqual(observed["requests"], 1)

    def test_responses_fixture_preserves_http_status_table_and_function_results(self):
        with fixture_server("exec_command", {"cmd": "pwd"}) as (port, observed):
            body = {"input": [{"type": "function_call_output", "call_id": "test", "output": "AI Engineering bloquea esta operación"}]}
            request = urllib.request.Request("http://127.0.0.1:{}/v1/responses".format(port), data=json.dumps(body).encode())
            with urllib.request.urlopen(request, timeout=3) as response:
                self.assertIn(b"response.completed", response.read())
            self.assertTrue(observed["tool_results"][0]["policy_denial"])

    def test_candidate_freeze_rejects_file_and_directory_symlinks(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve(); source = root / "source"; source.mkdir()
            (source / "escape").symlink_to(ROOT / "AGENTS.md")
            with self.assertRaises(OSError):
                freeze(source, root / "frozen")
            (source / "escape").unlink()
            (source / "escape").symlink_to(ROOT / "tools", target_is_directory=True)
            with self.assertRaises(ValueError):
                freeze(source, root / "frozen2")

    def test_candidate_freeze_rejects_local_state_and_oversized_inputs(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve(); source = root / "source"; source.mkdir()
            (source / ".git").mkdir()
            with self.assertRaises(ValueError):
                freeze(source, root / "frozen")
            (source / ".git").rmdir()
            (source / "file").write_bytes(b"x" * 40)
            with patch("verify_candidate.MAX_BYTES", 10):
                with self.assertRaises(ValueError):
                    freeze(source, root / "frozen2")
            (source / "file").unlink()
            for name in ("one", "two", "three"):
                (source / name).mkdir()
            with patch("verify_candidate.MAX_FILES", 2):
                with self.assertRaises(ValueError):
                    freeze(source, root / "frozen3")

    def test_candidate_freeze_rejects_hardlinks_to_host_data(self):
        import os
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve(); source = root / "source"; source.mkdir()
            (root / "host-data").write_text("synthetic-host-data")
            os.link(root / "host-data", source / "linked")
            with self.assertRaises(ValueError):
                freeze(source, root / "frozen")

    def test_forging_installation_receipt_cannot_replace_the_pinned_executable(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve(); destination = root / "cli"; destination.mkdir()
            executable = destination / "claude"; executable.write_bytes(b"tampered")
            (destination / "installation.json").write_text(json.dumps({"version": "2.1.295", "integrity": "pinned",
                "executable_sha256": hashlib.sha256(executable.read_bytes()).hexdigest()}))
            specification = ("2.1.295", {"integrity": "pinned", "executable_sha256": hashlib.sha256(b"authentic").hexdigest()})
            with patch.object(project_toolchain, "destination", return_value=destination), patch.object(project_toolchain, "specification", return_value=specification):
                with self.assertRaises(ValueError):
                    project_toolchain.binary("claude", root)

    def inspection(self):
        return {"HostConfig": {"NetworkMode": "none", "ReadonlyRootfs": True, "Privileged": False,
                "CapDrop": ["ALL"], "PidsLimit": 256, "Memory": 1073741824, "NanoCpus": 2000000000,
                "PidMode": "", "SecurityOpt": ["no-new-privileges"]}, "Config": {"User": "10001:10001"},
                "Mounts": [{"Type": "bind", "Destination": path, "RW": False} for path in ("/control", "/opt/aie-tools")]}

    def test_container_inspection_rejects_privilege_network_or_writable_controls(self):
        valid = self.inspection(); validate_inspection(valid)
        for key, value in (("Privileged", True), ("NetworkMode", "host"), ("ReadonlyRootfs", False), ("CapDrop", [])):
            bad = copy.deepcopy(valid); bad["HostConfig"][key] = value
            with self.assertRaises(ValueError):
                validate_inspection(bad)
        bad = copy.deepcopy(valid); bad["Mounts"][0]["RW"] = True
        with self.assertRaises(ValueError):
            validate_inspection(bad)

    def test_container_inspection_rejects_extra_host_mounts(self):
        bad = self.inspection(); bad["Mounts"].append({"Type": "bind", "Destination": "/var/run/docker.sock", "RW": True})
        with self.assertRaises(ValueError):
            validate_inspection(bad)

    def test_ttl_collection_ignores_live_or_unrelated_resources(self):
        item = {"Name": "/aie-native-" + "a" * 32, "Config": {"Labels": {
            "aie.owner": "native-verification", "aie.controller": CONTROLLER, "aie.expires": "100"}}}
        self.assertTrue(expired_owned(item, 101))
        self.assertFalse(expired_owned(item, 99))
        item["Config"]["Labels"]["aie.controller"] = "someone-else"
        self.assertFalse(expired_owned(item, 101))
        item["Config"]["Labels"]["aie.controller"] = CONTROLLER
        item["Name"] = "/unrelated"
        self.assertFalse(expired_owned(item, 101))
