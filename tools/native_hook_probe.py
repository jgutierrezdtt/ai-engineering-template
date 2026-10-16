"""Exercise real CLIs against a loopback fixture, never a paid model service."""

import argparse
import contextlib
import json
import shutil
import sys
import tempfile
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from isolated_process import execute
from project_toolchain import binary
from hook_context import context


ROOT = Path(__file__).resolve().parents[1]


def toml_value(value):
    if isinstance(value, dict):
        return "{" + ",".join(json.dumps(key) + "=" + toml_value(item) for key, item in value.items()) + "}"
    if isinstance(value, list):
        return "[" + ",".join(toml_value(item) for item in value) + "]"
    return json.dumps(value, ensure_ascii=False)


@contextlib.contextmanager
def fixture_server(tool, arguments, expected_directory=None, expected_context=None):
    observed = {"requests": 0, "tool_results": [], "tool_names": [], "canonical_skill_names_received": False,
                "complete_canonical_context_received": False}

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def do_POST(self):
            length = int(self.headers.get("Content-Length", "0"))
            if not 0 < length < 2 * 1024 * 1024 or observed["requests"] >= 6:
                self.send_error(413)
                return
            body = json.loads(self.rfile.read(length))
            observed["requests"] += 1
            observed["tool_names"] = [item.get("name") for item in body.get("tools", [])]
            serialized = json.dumps(body, ensure_ascii=False)
            observed["canonical_skill_names_received"] = all(name in serialized for name in (
                "engineering-delivery", "engineering-architecture", "engineering-security", "engineering-quality",
                "engineering-agent-safety", "engineering-devops", "engineering-product-design", "engineering-compliance"))
            if expected_context:
                def strings(value):
                    if isinstance(value, str):
                        yield value
                    elif isinstance(value, dict):
                        for part in value.values():
                            yield from strings(part)
                    elif isinstance(value, list):
                        for part in value:
                            yield from strings(part)
                observed["complete_canonical_context_received"] = expected_context in "\n".join(strings(body))
            if "responses" in self.path:
                self.serve_responses(body)
                return
            for message in body.get("messages", []):
                content = message.get("content", [])
                if isinstance(content, list):
                    for block in content:
                        if block.get("type") == "tool_result":
                            text = block.get("content", "")
                            if not isinstance(text, str):
                                text = json.dumps(text)
                            observed["tool_results"].append({
                                "error": block.get("is_error") is True,
                                "policy_denial": "AI Engineering:" in text or "AI Engineering bloquea esta operación" in text,
                                "failure_block": "onFailure" in text and "block" in text,
                                "nonempty": bool(text.strip()),
                                "boundary_denial": "Read-only file system" in text or "Permission denied" in text,
                                "expected_output": expected_directory is not None and expected_directory in text})
            first = not observed["tool_results"] and observed["requests"] == 1
            message = {"id": "msg_aie_fixture", "type": "message", "role": "assistant",
                       "model": "aie-native-fixture", "content": [], "stop_reason": None,
                       "stop_sequence": None, "usage": {"input_tokens": 1, "output_tokens": 1}}
            block = {"type": "tool_use", "id": "toolu_aie_fixture", "name": tool, "input": {}} if first else {"type": "text", "text": "Fixture completed."}
            if body.get("stream"):
                self.send_response(200)
                self.send_header("Content-Type", "text/event-stream")
                self.send_header("Connection", "close")
                self.end_headers()
                events = [("message_start", {"type": "message_start", "message": message}),
                          ("content_block_start", {"type": "content_block_start", "index": 0, "content_block": block})]
                if first:
                    events.append(("content_block_delta", {"type": "content_block_delta", "index": 0,
                                   "delta": {"type": "input_json_delta", "partial_json": json.dumps(arguments)}}))
                events += [("content_block_stop", {"type": "content_block_stop", "index": 0}),
                           ("message_delta", {"type": "message_delta", "delta": {"stop_reason": "tool_use" if first else "end_turn", "stop_sequence": None}, "usage": {"output_tokens": 1}}),
                           ("message_stop", {"type": "message_stop"})]
                for name, data in events:
                    self.wfile.write(("event: " + name + "\ndata: " + json.dumps(data) + "\n\n").encode())
                self.wfile.flush()
            else:
                if first:
                    block["input"] = arguments
                message.update(content=[block], stop_reason="tool_use" if first else "end_turn")
                encoded = json.dumps(message).encode()
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(encoded)))
                self.end_headers()
                self.wfile.write(encoded)

        def serve_responses(self, body):
            for item in body.get("input", []):
                if isinstance(item, dict) and item.get("type") == "function_call_output":
                    value = item.get("output", "")
                    text = value if isinstance(value, str) else json.dumps(value)
                    observed["tool_results"].append({"policy_denial": "AI Engineering:" in text or "AI Engineering bloquea esta operación" in text,
                        "boundary_denial": "Read-only file system" in text or "Permission denied" in text,
                        "expected_output": expected_directory is not None and expected_directory in text,
                        "nonempty": bool(text.strip())})
            first = observed["requests"] == 1
            if first:
                block = {"id": "fc_aie", "type": "function_call", "call_id": "call_aie",
                         "name": "exec_command", "namespace": "functions",
                         "arguments": json.dumps(arguments), "status": "completed"}
            else:
                block = {"id": "msg_aie", "type": "message", "role": "assistant", "status": "completed",
                         "content": [{"type": "output_text", "text": "Fixture completed.", "annotations": []}]}
            response = {"id": "resp_aie_" + str(observed["requests"]), "object": "response", "created_at": 0,
                        "model": "aie-native-fixture", "status": "completed", "output": [block],
                        "usage": {"input_tokens": 1, "output_tokens": 1, "total_tokens": 2}}
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream")
            self.send_header("Connection", "close")
            self.end_headers()
            initial = dict(response, status="in_progress", output=[])
            events = [("response.created", {"response": initial}),
                      ("response.output_item.added", {"output_index": 0, "item": block}),
                      ("response.output_item.done", {"output_index": 0, "item": block}),
                      ("response.completed", {"response": response})]
            for name, value in events:
                self.wfile.write(("event: " + name + "\ndata: " + json.dumps(dict(value, type=name)) + "\n\n").encode())
            self.wfile.flush()

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    server.daemon_threads = True
    worker = threading.Thread(target=server.serve_forever, daemon=True)
    worker.start()
    try:
        yield server.server_port, observed
    finally:
        server.shutdown()
        server.server_close()
        worker.join(timeout=3)


def prepare(root):
    for directory in ("tools", "policy", ".agents"):
        shutil.copytree(ROOT / directory, root / directory, ignore=shutil.ignore_patterns("__pycache__"))
    shutil.copytree(ROOT / ".agents/skills", root / ".claude/skills")
    for name in ("AGENTS.md", "CLAUDE.md"):
        shutil.copyfile(ROOT / name, root / name)


def claude_probe(mode):
    cli = Path(binary("claude"))
    with tempfile.TemporaryDirectory(prefix="aie-native-") as directory:
        directory = Path(directory).resolve()
        workspace = directory / "workspace"
        workspace.mkdir()
        prepare(workspace)
        state = directory / "state"
        state.mkdir(mode=0o700)
        (state / ".claude.json").write_text('{"hasCompletedOnboarding":true}')
        adapter = json.loads((ROOT / "policy/adapters/claude.json").read_text())
        # Stop is independently checked by the quality runner; keep this probe finite.
        adapter["hooks"].pop("Stop", None)
        handler = adapter["hooks"]["PreToolUse"][0]["hooks"][0]
        replacements = {"missing": "/aie-nonexistent-hook", "crash": "exit 7",
                        "invalid-json": "printf '%s' '{invalid}'", "timeout": "sleep 5"}
        if mode in replacements:
            handler.update(command=replacements[mode], timeout=1)
        if mode == "outer-boundary":
            adapter["hooks"].pop("PreToolUse")
        audit = state / "hook-events.txt"
        for event, groups in adapter["hooks"].items():
            for group in groups:
                for callback in group["hooks"]:
                    callback["command"] = "printf '%s\\n' " + event + " >> " + str(audit) + "\n" + callback["command"]
        settings = workspace / ".claude/settings.json"
        settings.parent.mkdir(exist_ok=True)
        settings.write_text(json.dumps(adapter))
        command = "pwd" if mode == "allowed" else "printf bypass > blocked-marker"
        if mode == "outer-boundary":
            command = "printf bypass > /control/policy/agent-enforcement.json"
        instructions, _ = context(workspace)
        canonical = state / "canonical-instructions.txt"
        canonical.write_text(instructions)
        with fixture_server("Bash", {"command": command, "description": "Synthetic hook verification"}, str(workspace), instructions) as (port, observed):
            args = [str(cli), "-p", "--output-format", "stream-json", "--verbose", "--include-hook-events",
                    "--no-session-persistence", "--permission-mode", "dontAsk", "--allowedTools", "Bash",
                    "--tools", "Bash", "--settings", str(settings), "--setting-sources", "project",
                    "--strict-mcp-config", "--mcp-config", '{"mcpServers":{}}', "--model", "aie-native-fixture",
                    "--append-system-prompt-file", str(canonical),
                    "--max-turns", "3", "--max-budget-usd", "0.01", "Execute the synthetic fixture tool once, then finish."]
            result = execute(args, workspace, [workspace, cli.parent], [state, workspace], timeout=25, port=port,
                             environment={"ANTHROPIC_API_KEY": "synthetic-loopback-token",
                                          "ANTHROPIC_BASE_URL": "http://127.0.0.1:" + str(port),
                                          "CLAUDE_CONFIG_DIR": str(state), "TMPDIR": str(state),
                                          "CLAUDE_CODE_TMPDIR": str(state),
                                          "CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC": "1",
                                          "CLAUDE_CODE_DISABLE_AUTO_MEMORY": "1", "DISABLE_AUTOUPDATER": "1"})
        events = []
        for line in result.stdout.splitlines():
            try:
                value = json.loads(line)
                if value.get("type") == "system" and value.get("hook_event"):
                    events.append(value["hook_event"])
            except ValueError:
                pass
        tool_results = observed["tool_results"]
        allowed = mode == "allowed"
        correct = bool(tool_results) and any(not item["error"] if allowed else item["error"] for item in tool_results)
        if mode == "denied":
            correct = correct and any(item["policy_denial"] for item in tool_results)
        if mode in replacements:
            correct = correct and any(item["failure_block"] for item in tool_results)
        if allowed:
            correct = correct and any(item["expected_output"] for item in tool_results)
        if mode == "outer-boundary":
            correct = bool(tool_results) and any(item.get("boundary_denial") for item in tool_results)
        effect = (workspace / "blocked-marker").exists()
        actual_events = audit.read_text().splitlines() if audit.exists() else []
        correct = correct and ("PreToolUse" in actual_events or mode == "outer-boundary")
        return {"id": "NATIVE-CLAUDE-" + mode.upper(), "provider": "claude", "scenario": mode,
                "cli_exit_code": result.code, "fixture_requests": observed["requests"],
                "tool_result_observed": bool(tool_results), "expected_decision_observed": bool(correct),
                "forbidden_effect_observed": effect, "hook_events": sorted(set(events)),
                "canonical_skill_names_received": observed["canonical_skill_names_received"],
                "complete_canonical_context_received": observed["complete_canonical_context_received"],
                "callbacks_observed": actual_events,
                "backend": result.backend, "elapsed_seconds": result.elapsed,
                "passed": result.code == 0 and correct and not effect and observed["complete_canonical_context_received"],
                "diagnostic_class": "none" if result.code == 0 else "native-startup-or-session-failed"}


def codex_probe(mode="allowed"):
    cli = Path(binary("codex"))
    with tempfile.TemporaryDirectory(prefix="aie-codex-native-") as directory:
        directory = Path(directory).resolve()
        workspace = directory / "workspace"
        workspace.mkdir()
        prepare(workspace)
        state = directory / "state"
        state.mkdir()
        adapter = json.loads((ROOT / "policy/adapters/codex.json").read_text())
        adapter["hooks"].pop("Stop", None)
        handler = adapter["hooks"]["PreToolUse"][0]["hooks"][0]
        replacements = {"missing": "/aie-nonexistent-hook", "crash": "exit 7",
                        "invalid-json": "printf '%s' '{invalid}'", "timeout": "sleep 5"}
        if mode in replacements:
            handler.update(command=replacements[mode], timeout=1)
        if mode == "outer-boundary":
            adapter["hooks"].pop("PreToolUse")
        audit = state / "hook-events.txt"
        for event, groups in adapter["hooks"].items():
            for group in groups:
                for callback in group["hooks"]:
                    callback["command"] = "printf '%s\\n' " + event + " >> " + str(audit) + "\n" + callback["command"]
        (workspace / ".codex").mkdir()
        (workspace / ".codex/hooks.json").write_text(json.dumps(adapter))
        (workspace / ".codex/config.toml").write_text('[features]\nhooks = true\n')
        args = [str(cli), "exec", "--ignore-user-config", "--ignore-rules", "--ephemeral",
                "--skip-git-repo-check", "--json", "--dangerously-bypass-hook-trust", "--sandbox",
                "danger-full-access" if Path("/.dockerenv").is_file() else "read-only"]
        values = {"sqlite_home": str(state), "log_dir": str(state), "model_provider": "aie-fixture",
                  "model_providers.aie-fixture.name": "aie-fixture",
                  "model_providers.aie-fixture.base_url": "http://127.0.0.1:12345/v1",
                  "model_providers.aie-fixture.env_key": "AIE_NATIVE_TOKEN",
                  "model_providers.aie-fixture.wire_api": "responses",
                  "model_providers.aie-fixture.request_max_retries": 0,
                  "model_providers.aie-fixture.stream_max_retries": 0}
        values["projects." + json.dumps(str(workspace)) + ".trust_level"] = "trusted"
        values["approval_policy"] = "never"
        values["model"] = "aie-native-fixture"
        # Automation explicitly vets this adapter and passes it as an active layer.
        # Project autodiscovery/trust in an interactive desktop session is a separate check.
        values["hooks"] = adapter["hooks"]
        for key, value in values.items():
            args += ["-c", key + "=" + toml_value(value)]
        command = "pwd" if mode == "allowed" else "printf bypass > blocked-marker"
        if mode == "outer-boundary":
            command = "printf bypass > /control/policy/agent-enforcement.json"
        with fixture_server("exec_command", {"cmd": command, "yield_time_ms": 1000}, str(workspace), context(workspace)[0]) as (port, observed):
            args += ["-c", 'model_providers.aie-fixture.base_url=' + json.dumps("http://127.0.0.1:" + str(port) + "/v1")]
            args += ["Execute the synthetic fixture tool once, then finish."]
            result = execute(args, workspace, [workspace, cli.parent], [state, workspace], timeout=20, port=port,
                             environment={"TMPDIR": str(state), "AIE_NATIVE_TOKEN": "synthetic-loopback-token"})
        failure = b"failed to initialize in-process app-server client" in result.stderr
        effect = (workspace / "blocked-marker").exists()
        tool_results = observed["tool_results"]
        correct = any(item["expected_output"] for item in tool_results) if mode == "allowed" else any(item["policy_denial"] for item in tool_results)
        if mode in replacements:
            # Codex documents hook runtime errors as fail-open. Observe the gap explicitly.
            correct = effect
        if mode == "outer-boundary":
            correct = bool(tool_results) and any(item.get("boundary_denial") for item in tool_results)
        actual_events = audit.read_text().splitlines() if audit.exists() else []
        correct = correct and ("PreToolUse" in actual_events or mode == "outer-boundary")
        return {"id": "NATIVE-CODEX-" + mode.upper(), "provider": "codex", "scenario": mode,
                "cli_exit_code": result.code, "native_initialization_permission_failure": failure,
                "hook_execution_demonstrated": bool(tool_results), "backend": result.backend,
                "fixture_requests": observed["requests"], "canonical_skill_names_received": observed["canonical_skill_names_received"],
                "complete_canonical_context_received": observed["complete_canonical_context_received"],
                "tool_result_observed": bool(tool_results), "expected_decision_observed": bool(correct),
                "callbacks_observed": actual_events,
                "forbidden_effect_observed": effect, "expected_fail_open": mode in replacements,
                "passed": result.code == 0 and correct and observed["complete_canonical_context_received"], "status": "blocked" if failure else "observed",
                "elapsed_seconds": result.elapsed,
                "reason": "Hook failures require the external OS/container boundary; hook results alone are not authority"}


def run(provider="all", scenario="all"):
    modes = ("allowed", "denied", "missing", "crash", "invalid-json", "timeout", "outer-boundary") if scenario == "all" else (scenario,)
    results = [claude_probe(mode) for mode in modes] if provider in {"all", "claude"} else []
    if provider in {"all", "codex"}:
        results += [codex_probe(mode) for mode in modes]
    return {"schema_version": 1, "scope": "real native CLI and synthetic loopback responses; no real model evaluation",
            "external_network_allowed": False, "global_settings_modified": False,
            "hook_failures_block_all_actions": False,
            "temporary_state_removed": True, "cases": results,
            "accepted": all(item["passed"] for item in results)}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    try:
        report = run()
        if args.output:
            args.output.parent.mkdir(parents=True, exist_ok=True)
            with args.output.open("x") as target:
                json.dump(report, target, ensure_ascii=False, indent=2)
                target.write("\n")
        for case in report["cases"]:
            print(case["id"], "OK" if case["passed"] else "PENDIENTE", "exit=" + str(case["cli_exit_code"]))
        sys.exit(0 if report["accepted"] else 2)
    except Exception:
        print("Prueba nativa incompleta; no se acredita ejecución de hooks")
        sys.exit(2)
