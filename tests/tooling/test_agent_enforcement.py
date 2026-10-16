"""Adversarial protocol tests; no provider requests or user configuration changes."""

import contextlib
import io
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))
import agent_hooks
import check_agent_setup
import hook_context
import install_agent_hooks
import processes
import tool_policy
import verify_change
from check_repository import SKILLS


class PolicyTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name).resolve()
        (self.root / "policy").mkdir()
        source = ROOT / "policy/agent-enforcement.json"
        (self.root / "policy/agent-enforcement.json").write_text(source.read_text())
        (self.root / "AGENTS.md").write_text("Canonical project policy")
        for name in SKILLS:
            file = self.root / ".agents/skills" / name / "SKILL.md"
            file.parent.mkdir(parents=True)
            file.write_text("Instructions " + name)
        self.policy = tool_policy.ToolPolicy(self.root)

    def payload(self, tool, arguments, event="PreToolUse"):
        return {"hook_event_name": event, "cwd": str(self.root), "tool_name": tool, "tool_input": arguments}

    def test_all_skills_are_materialized_and_fingerprint_changes(self):
        text, first = hook_context.context(self.root)
        for name in SKILLS:
            self.assertIn("Instructions " + name, text)
        (self.root / "AGENTS.md").write_text("Revised canonical policy")
        self.assertNotEqual(first, hook_context.context(self.root)[1])

    def test_missing_skill_denies_tools_instead_of_silently_omitting_it(self):
        name = next(iter(SKILLS))
        (self.root / ".agents/skills" / name / "SKILL.md").unlink()
        decision = agent_hooks.handle(self.payload("Bash", {"command": "pwd"}), self.root)
        self.assertEqual(decision["hookSpecificOutput"]["permissionDecision"], "deny")

    def test_oversized_context_is_not_truncated(self):
        (self.root / "AGENTS.md").write_text("x" * 65537)
        with self.assertRaises(ValueError):
            hook_context.context(self.root)

    def test_session_and_prompt_receive_canonical_content(self):
        for event in ("SessionStart", "UserPromptSubmit", "SubagentStart"):
            payload = {"cwd": str(self.root), "hook_event_name": event}
            decision = agent_hooks.handle(payload, self.root)["hookSpecificOutput"]
            self.assertEqual(decision["hookEventName"], event)
            self.assertIn("Canonical project policy", decision["additionalContext"])

    def test_native_read_and_product_edit_are_admitted_without_granting_permissions(self):
        payload = self.payload("Write", {"file_path": "packages/sdk/client.py", "content": "example"})
        self.assertEqual(agent_hooks.handle(payload, self.root), {})
        self.assertIsNone(self.policy.denial(self.payload("Read", {"file_path": "AGENTS.md"})))

    def test_control_and_test_runner_modifications_are_denied(self):
        for path in ("AGENTS.md", "policy/quality.json", ".codex/hooks.json", ".claude/settings.json",
                     "tools/quality.py", "tests/tooling/test_controls.py", ".github/workflows/foundation.yml"):
            self.assertIsNotNone(self.policy.denial(self.payload("Write", {"file_path": path})), path)

    def test_unknown_tools_and_external_connectors_are_denied(self):
        for tool in ("Unknown", "mcp__mail__send", "Agent", "NotebookEdit", "write_stdin"):
            self.assertIsNotNone(self.policy.denial(self.payload(tool, {})), tool)

    def test_shell_obfuscation_and_bypass_are_denied(self):
        commands = ("git push", "curl https://example.invalid", "python3 -c 'print(1)'",
                    "pwd; git push", "pwd\ntrue", "$(pwd)", "pwd | cat", "env X=1 pwd",
                    "bash -c pwd", "python3 -B tools/quality.py bootstrap && true")
        for command in commands:
            self.assertIsNotNone(self.policy.denial(self.payload("Bash", {"command": command})), command)

    def test_validation_must_use_the_root_and_exact_command(self):
        command = "python3 -B tools/quality.py quick"
        self.assertIsNone(self.policy.denial(self.payload("Bash", {"command": command})))
        folder = self.root / "packages/sdk"
        folder.mkdir(parents=True)
        payload = self.payload("Bash", {"command": command, "workdir": str(folder)})
        self.assertIsNotNone(self.policy.denial(payload))

    def test_sensitive_and_escaping_paths_are_denied(self):
        for path in (".env", "a/.env.production", "../outside", "packages/../../outside", ".git/config"):
            self.assertIsNotNone(self.policy.denial(self.payload("Read", {"file_path": path})), path)

    def test_symlink_escape_and_in_project_symlink_are_denied(self):
        (self.root / "packages").mkdir()
        (self.root / "packages/link").symlink_to(self.root / "policy", target_is_directory=True)
        self.assertIsNotNone(self.policy.denial(self.payload("Write", {"file_path": "packages/link/quality.json"})))

    def test_patch_rename_cannot_move_product_into_policy(self):
        command = "*** Begin Patch\n*** Update File: packages/client.py\n*** Move to: policy/quality.json\n@@\n-old\n+new\n*** End Patch"
        self.assertIsNotNone(self.policy.denial(self.payload("apply_patch", {"command": command})))

    def test_ordinary_product_patch_is_admitted(self):
        command = "*** Begin Patch\n*** Add File: packages/client.py\n+example\n*** End Patch"
        self.assertIsNone(self.policy.denial(self.payload("apply_patch", {"command": command})))

    def test_invalid_input_is_denied_without_echoing_sensitive_content(self):
        payload = self.payload("Bash", {"command": "private input must not appear"})
        result = agent_hooks.handle(payload, self.root)
        self.assertEqual(result["hookSpecificOutput"]["permissionDecision"], "deny")
        self.assertNotIn("private input", json.dumps(result))

    def test_stop_uses_product_gate_when_product_exists(self):
        self.assertEqual(verify_change.required_profile(self.root), "bootstrap")
        (self.root / "packages").mkdir()
        self.assertEqual(verify_change.required_profile(self.root), "quick")
        payload = {"cwd": str(self.root), "hook_event_name": "Stop"}
        with patch.object(agent_hooks, "run", return_value=processes.Result(2, 0.1)) as runner:
            self.assertEqual(agent_hooks.handle(payload, self.root)["decision"], "block")
        self.assertIn("verify_change.py", str(runner.call_args.args[0]))

    def test_stop_does_not_loop_forever_on_permanent_failure(self):
        payload = {"cwd": str(self.root), "hook_event_name": "Stop", "stop_hook_active": True}
        with patch.object(agent_hooks, "run", return_value=processes.Result(2, 0.1)):
            result = agent_hooks.handle(payload, self.root)
        self.assertIs(result["continue"], False)
        self.assertIn("no se acredita", result["stopReason"])

    def test_unexpected_control_error_produces_explicit_denial(self):
        with patch.object(agent_hooks, "context", side_effect=RuntimeError("internal")):
            result = agent_hooks.handle(self.payload("Bash", {"command": "pwd"}), self.root)
        self.assertEqual(result["hookSpecificOutput"]["permissionDecision"], "deny")

    def test_cli_malformed_json_produces_a_denial(self):
        result = subprocess.run([sys.executable, "-B", str(ROOT / "tools/agent_hooks.py")],
                                input="not JSON", capture_output=True, text=True, timeout=5)
        self.assertEqual(result.returncode, 0)
        self.assertEqual(json.loads(result.stdout)["hookSpecificOutput"]["permissionDecision"], "deny")


class CompatibilityTests(unittest.TestCase):
    def setUp(self):
        # These protocol tests supply synthetic version responses. Native CLI
        # installation and behavior are exercised by the separate container job.
        resolver = patch.object(check_agent_setup, "binary", side_effect=lambda provider: provider)
        resolver.start()
        self.addCleanup(resolver.stop)

    def test_old_claude_cannot_claim_fail_closed_hook_support(self):
        response = subprocess.CompletedProcess([], 0, "2.1.289 (Claude Code)", "")
        with patch.object(check_agent_setup.subprocess, "run", return_value=response):
            with contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(check_agent_setup.check("claude"), 2)

    def test_no_version_or_feature_is_assumed(self):
        with self.assertRaises(ValueError):
            check_agent_setup.version_tuple("unknown")
        responses = [subprocess.CompletedProcess([], 0, "codex-cli 0.160.1", ""),
                     subprocess.CompletedProcess([], 0, "hooks stable false", "")]
        with patch.object(check_agent_setup.subprocess, "run", side_effect=responses):
            with contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(check_agent_setup.check("codex"), 2)

    def test_incompatible_provider_never_writes_native_settings(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            with patch.object(install_agent_hooks.check_agent_setup, "check", return_value=2):
                with contextlib.redirect_stdout(io.StringIO()):
                    self.assertEqual(install_agent_hooks.install("claude", root), 2)
            self.assertFalse((root / ".claude").exists())

    def test_installer_preserves_existing_settings(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "policy/adapters").mkdir(parents=True)
            (root / "policy/adapters/codex.json").write_text('{}\n')
            target = root / ".codex/hooks.json"
            target.parent.mkdir()
            target.write_text('{"existing": true}\n')
            with patch.object(install_agent_hooks.check_agent_setup, "check", return_value=0):
                with contextlib.redirect_stdout(io.StringIO()):
                    self.assertEqual(install_agent_hooks.install("codex", root), 2)
            self.assertEqual(json.loads(target.read_text()), {"existing": True})

    def test_installer_never_writes_through_a_symlink_directory(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "policy/adapters").mkdir(parents=True)
            (root / "policy/adapters/codex.json").write_text('{}\n')
            outside = root / "outside"
            outside.mkdir()
            (root / ".codex").symlink_to(outside, target_is_directory=True)
            with patch.object(install_agent_hooks.check_agent_setup, "check", return_value=0):
                with contextlib.redirect_stdout(io.StringIO()):
                    self.assertEqual(install_agent_hooks.install("codex", root), 2)
            self.assertFalse((outside / "hooks.json").exists())

    def test_claude_handlers_fail_closed_and_codex_context_is_not_spilled(self):
        for provider in ("claude", "codex"):
            adapter = json.loads((ROOT / "policy/adapters" / (provider + ".json")).read_text())
            self.assertEqual(adapter["hooks"]["PreToolUse"][0]["matcher"], ".*")
            for event, groups in adapter["hooks"].items():
                for group in groups:
                    for handler in group["hooks"]:
                        if provider == "claude":
                            self.assertEqual(handler["onFailure"], "block")
                        elif event in {"SessionStart", "UserPromptSubmit", "SubagentStart"}:
                            self.assertEqual(handler["additionalContextLimit"], 0)

    def test_adapter_command_works_from_a_nested_checkout_directory(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            shutil.copytree(ROOT / "tools", root / "tools")
            shutil.copytree(ROOT / ".agents", root / ".agents")
            shutil.copytree(ROOT / "policy", root / "policy")
            shutil.copyfile(ROOT / "AGENTS.md", root / "AGENTS.md")
            nested = root / "docs/product/nested"
            nested.mkdir(parents=True)
            adapter = json.loads((root / "policy/adapters/codex.json").read_text())
            command = adapter["hooks"]["SessionStart"][0]["hooks"][0]["command"]
            payload = {"cwd": str(nested), "hook_event_name": "SessionStart"}
            result = subprocess.run(["/bin/sh", "-c", command], cwd=nested, input=json.dumps(payload),
                                    capture_output=True, text=True, timeout=5)
            self.assertEqual(result.returncode, 0)
            loaded = json.loads(result.stdout)["hookSpecificOutput"]["additionalContext"]
            for name in SKILLS:
                self.assertIn(".agents/skills/" + name + "/SKILL.md", loaded)


if __name__ == "__main__":
    unittest.main()
