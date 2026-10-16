"""Negative effects observed in real OS-sandboxed child processes."""

import json
import socket
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))
from isolated_process import execute, configuration
from managed_workspace import protected_changes


class IsolationTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="aie-isolation-test-")
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name).resolve()
        self.workspace = self.root / "workspace"
        self.workspace.mkdir()
        self.scratch = self.root / "scratch"
        self.scratch.mkdir()
        self.secret = self.root / "host-secret"
        self.secret.write_text("synthetic-sensitive-marker")
        self.control = self.workspace / "policy.json"
        self.control.write_text("protected-policy")

    def child(self, source, timeout=10, port=None):
        return execute([sys.executable, "-B", "-c", source], self.workspace,
                       [self.workspace], [self.scratch], timeout=timeout, port=port)

    def test_product_output_is_writable_and_control_is_readable(self):
        source = "from pathlib import Path; assert Path('policy.json').read_text() == 'protected-policy'; Path({!r}).write_text('allowed')".format(str(self.scratch / "output"))
        self.assertEqual(self.child(source).code, 0)
        self.assertEqual((self.scratch / "output").read_text(), "allowed")

    def test_control_write_is_denied_even_without_any_hook(self):
        self.assertNotEqual(self.child("from pathlib import Path; Path('policy.json').write_text('bypass')").code, 0)
        self.assertEqual(self.control.read_text(), "protected-policy")

    def test_host_secret_read_is_denied_without_exporting_its_content(self):
        result = self.child("from pathlib import Path; print(Path({!r}).read_text())".format(str(self.secret)))
        self.assertNotEqual(result.code, 0)
        self.assertNotIn(b"synthetic-sensitive-marker", result.stdout + result.stderr)

    def test_child_process_inherits_filesystem_restrictions(self):
        source = "import subprocess,sys; sys.exit(subprocess.run([sys.executable,'-B','-c',\"from pathlib import Path; Path('policy.json').unlink()\"]).returncode)"
        self.assertNotEqual(self.child(source).code, 0)
        self.assertTrue(self.control.exists())

    def test_symlink_in_writable_area_cannot_escape_to_control(self):
        (self.scratch / "link").symlink_to(self.control)
        result = self.child("from pathlib import Path; Path({!r}).write_text('bypass')".format(str(self.scratch / "link")))
        self.assertNotEqual(result.code, 0)
        self.assertEqual(self.control.read_text(), "protected-policy")

    def test_network_is_blocked_even_to_a_live_loopback_listener(self):
        with socket.socket() as listener:
            listener.bind(("127.0.0.1", 0)); listener.listen()
            port = listener.getsockname()[1]
            result = self.child("import socket; socket.create_connection(('127.0.0.1', {}),timeout=1)".format(port))
            self.assertNotEqual(result.code, 0)

    def test_timeout_is_a_failure_and_writable_temporary_state_is_owned(self):
        self.assertEqual(self.child("import time; time.sleep(10)", timeout=0.15).code, 124)
        self.assertTrue(self.secret.exists())

    def test_overbroad_roots_and_environment_overrides_are_rejected(self):
        with self.assertRaises(ValueError):
            configuration([Path("/")], [self.scratch])
        with self.assertRaises(ValueError):
            execute(["/usr/bin/true"], self.workspace, [self.workspace], [self.scratch],
                    environment={"PYTHONPATH": str(self.scratch)})

    def test_excessive_output_is_bounded_and_cannot_accredit_success(self):
        result = self.child("import sys; sys.stdout.write('x' * (1024 * 1024 + 100))")
        self.assertEqual(result.code, 125)
        self.assertTrue(result.output_limit_exceeded)
        self.assertLessEqual(len(result.stdout), 1024 * 1024)

    def test_external_verifier_rejects_modified_control_and_escaped_links(self):
        candidate = self.root / "candidate"
        candidate.mkdir()
        (candidate / "policy.json").write_text("forged")
        (candidate / "packages").mkdir()
        (candidate / "packages/client.py").write_text("product")
        policy = {"editable_roots": ["packages"]}
        self.assertEqual(protected_changes(self.workspace, candidate, policy), ["policy.json"])
        (candidate / "packages/link").symlink_to(self.secret)
        self.assertIn("packages/link", protected_changes(self.workspace, candidate, policy))
