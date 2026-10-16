"""Record sanitized, reproducible local verification without claiming attestation."""

import argparse
import contextlib
import hashlib
import io
import json
import platform
import re
import subprocess
import sys
import time
import unittest
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SOURCE_DIRS = ("tools", "tests/tooling", "policy", ".agents", ".githooks", ".github", ".claude/skills")
SOURCE_FILES = ("AGENTS.md", "CLAUDE.md", ".codex/hooks.json", ".claude/settings.json", ".gitleaks.toml", ".gitignore", ".editorconfig")


def timestamp():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def snapshot(root: Path):
    paths = {root / name for name in SOURCE_FILES if (root / name).is_file()}
    for name in SOURCE_DIRS:
        paths.update(path for path in (root / name).rglob("*")
                     if path.is_file() and "__pycache__" not in path.parts and path.suffix != ".pyc")
    entries = []
    digest = hashlib.sha256()
    for path in sorted(paths):
        if path.is_symlink() or not path.resolve().is_relative_to(root.resolve()):
            raise ValueError("Origen no autorizado para la huella")
        data = path.read_bytes()
        name = path.relative_to(root).as_posix()
        fingerprint = hashlib.sha256(data).hexdigest()
        entries.append({"path": name, "bytes": len(data), "sha256": fingerprint})
        digest.update(name.encode("utf-8") + b"\0" + bytes.fromhex(fingerprint) + b"\0")
    return {"algorithm": "sha256", "aggregate_sha256": digest.hexdigest(), "files": entries}


class CaseResults(unittest.TestResult):
    """Persist IDs/outcomes only; never exception messages, tracebacks or stdout."""
    def __init__(self):
        super().__init__()
        self.cases = []
        self.started = {}

    def startTest(self, test):
        super().startTest(test)
        self.started[id(test)] = time.monotonic()

    def append(self, test, outcome):
        self.cases.append({"id": test.id(), "outcome": outcome,
                           "duration_seconds": round(time.monotonic() - self.started.get(id(test), time.monotonic()), 6)})

    def addSuccess(self, test):
        super().addSuccess(test)
        self.append(test, "pass")

    def addFailure(self, test, err):
        super().addFailure(test, err)
        self.append(test, "failure")

    def addError(self, test, err):
        super().addError(test, err)
        self.append(test, "error")

    def addSkip(self, test, reason):
        super().addSkip(test, reason)
        self.append(test, "skipped")

    def addExpectedFailure(self, test, err):
        super().addExpectedFailure(test, err)
        self.append(test, "expected-failure")

    def addUnexpectedSuccess(self, test):
        super().addUnexpectedSuccess(test)
        self.append(test, "unexpected-success")


def run_suite(suite):
    result = CaseResults()
    # This output is deliberately ephemeral, even when an exception contains data.
    with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
        suite.run(result)
    return {"count": result.testsRun, "all_passed": result.testsRun > 0 and
            len(result.cases) == result.testsRun and all(case["outcome"] == "pass" for case in result.cases),
            "cases": result.cases}


def check(root, identifier, args, expected, payload=None, timeout=150, json_predicate=None):
    start = time.monotonic()
    actual = None
    semantic = True
    try:
        result = subprocess.run(args, cwd=root, input=payload, text=True, capture_output=True, timeout=timeout)
        actual = result.returncode
        if json_predicate is not None:
            semantic = bool(json_predicate(json.loads(result.stdout)))
    except (OSError, subprocess.SubprocessError, ValueError, KeyError, TypeError):
        semantic = False
    return {"id": identifier, "command": ["python3" if item == sys.executable else item for item in args],
            "expected_exit_codes": expected, "actual_exit_code": actual,
            "semantic_check_passed": semantic,
            "outcome": "pass" if actual in expected and semantic else "failure",
            "duration_seconds": round(time.monotonic() - start, 6)}


def safe_version(command, root):
    try:
        result = subprocess.run(command, cwd=root, capture_output=True, text=True, timeout=10)
        found = re.search(r"\b\d+\.\d+\.\d+\b", result.stdout)
        return found.group(0) if result.returncode == 0 and found else None
    except (OSError, subprocess.SubprocessError):
        return None


def catalog_coverage(tests, catalog):
    observed = {case["id"] for case in tests["cases"]}
    declared = [case["method"] for case in catalog["cases"]]
    missing = sorted(observed - set(declared))
    stale = sorted(set(declared) - observed)
    return {"complete": bool(observed) and not missing and not stale and len(declared) == len(set(declared)),
            "unmapped_test_ids": missing, "unobserved_catalog_ids": stale}


def write_record(output: Path, record, source, supplemental=None):
    output.mkdir(parents=True, exist_ok=False)
    artifacts = {"results.json": record, "source-manifest.json": source}
    artifacts.update(supplemental or {})
    for name, content in artifacts.items():
        (output / name).write_text(json.dumps(content, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    lines = ["# Registro de verificación local", "", "Identificador: `" + record["record_id"] + "`.", "",
             "Inicio UTC: " + record["started_at_utc"] + ".", "",
             "Resultado del plan local: **" + ("superado" if record["accepted"] else "no superado") + "**.", "",
             "Casos ejecutados: " + str(record["tests"]["count"]) + ".", "",
             "| Comprobación | Salida esperada | Salida observada | Resultado |", "| --- | --- | --- | --- |"]
    for item in record["checks"]:
        lines.append("| {} | {} | {} | {} |".format(item["id"], item["expected_exit_codes"], item["actual_exit_code"], item["outcome"]))
    lines += ["", "Una salida esperada 2 acredita una denegación o requisito pendiente, no funcionamiento del producto.", "",
              "[Resultados por caso](results.json), [huellas de los archivos](source-manifest.json) y [comprobación de integridad](checksums.json).", "",
              "Registro local sin firma, sello de tiempo confiable ni revisión independiente. La activación nativa solo se acredita si scope.provider_native_hooks_observed es true y existe native-report.json. No acredita modelos reales ni nube.",
              "Un caso que observa el comportamiento fail-open documentado puede superar su oráculo: no acredita bloqueo por el hook. Outer-boundary comprueba por separado la protección del contenedor.", ""]
    (output / "README.md").write_text("\n".join(lines), encoding="utf-8")
    checksums = {name: hashlib.sha256((output / name).read_bytes()).hexdigest()
                 for name in (*artifacts, "README.md")}
    (output / "checksums.json").write_text(json.dumps(checksums, indent=2) + "\n", encoding="utf-8")


def verify_record(output):
    checksums = json.loads((output / "checksums.json").read_text())
    if (not {"results.json", "source-manifest.json", "README.md"} <= set(checksums)
            or len(checksums) > 10 or any(not re.fullmatch(r"[A-Za-z-]+\.(json|md)", name) for name in checksums)):
        return False
    return all(not (output / name).is_symlink() and
               hashlib.sha256((output / name).read_bytes()).hexdigest() == value
               for name, value in checksums.items())


def record(output: Path, record_id: str, client_date: str, native_report=None, workspace_report=None):
    root = ROOT.resolve()
    output = output.resolve()
    output.relative_to(root / ".artifacts/evidence")
    if output.exists() or not re.fullmatch(r"[A-Z0-9-]{5,80}", record_id):
        raise ValueError("Identificador inválido o destino existente")
    datetime.strptime(client_date, "%Y-%m-%d")
    started = timestamp()
    before = snapshot(root)
    suite = unittest.TestLoader().discover(str(root / "tests/tooling"))
    tests = run_suite(suite)
    coverage = catalog_coverage(tests, json.loads((root / "policy/test-catalog.json").read_text()))
    python = sys.executable
    commands = [
        ("CHECK-BASE", [python, "-B", "tools/verify_change.py"], [0]),
        ("CHECK-QUICK-BLOCK", [python, "-B", "tools/quality.py", "quick"], [2]),
        ("CHECK-RELEASE-BLOCK", [python, "-B", "tools/quality.py", "release"], [2]),
        ("CHECK-CODEX-COMPAT", [python, "-B", "tools/check_agent_setup.py", "codex"], [0]),
        ("CHECK-CLAUDE-COMPAT", [python, "-B", "tools/check_agent_setup.py", "claude"], [0]),
        ("CHECK-READINESS-BLOCK", [python, "-B", "tools/readiness.py"], [2]),
    ]
    checks = [check(root, identifier, args, expected) for identifier, args, expected in commands]
    checks.append(check(root, "CHECK-STOP", [python, "-B", "tools/agent_hooks.py"], [0],
                        payload=json.dumps({"cwd": str(root), "hook_event_name": "Stop", "stop_hook_active": False}),
                        json_predicate=lambda value: "comprobada" in value.get("systemMessage", "")))
    after = snapshot(root)
    unchanged = before == after
    source_adapter = root / "policy/adapters/codex.json"
    installed_adapter = root / ".codex/hooks.json"
    from project_toolchain import binary
    versions = {"codex": safe_version([binary("codex"), "--version"], root),
                "claude": safe_version([binary("claude"), "--version"], root),
                "claude_global": safe_version(["claude", "--version"], root),
                "gitleaks": safe_version(["gitleaks", "version"], root)}
    supplemental = {}
    native_valid = False
    workspace_valid = False
    if native_report:
        native = json.loads(native_report.read_text())
        modes = {"allowed", "denied", "missing", "crash", "invalid-json", "timeout", "outer-boundary"}
        expected = {(provider, mode) for provider in ("claude", "codex") for mode in modes}
        actual = {(case["provider"], case["scenario"]) for case in native["cases"]}
        native_valid = (native["accepted"] is True and actual == expected and len(native["cases"]) == 14
                        and all(case["passed"] and case["complete_canonical_context_received"] for case in native["cases"])
                        and native["container"]["settings_inspected_before_start"] is True
                        and native["container"]["removed_after_run"] is True
                        and native["container"]["network"] == "none"
                        and native["environment"]["tools"] == {"codex": "0.160.1", "claude": "2.1.295"}
                        and native["source_unchanged_during_run"] is True
                        and native["source_aggregate_sha256"] == before["aggregate_sha256"])
        supplemental["native-report.json"] = native
    if workspace_report:
        workspace = json.loads(workspace_report.read_text())
        workspace_valid = workspace["accepted"] is True and workspace["candidate_unchanged"] is True
        supplemental["workspace-report.json"] = workspace
    commit = subprocess.run(["git", "rev-parse", "HEAD"], cwd=root, capture_output=True, text=True, timeout=5)
    hook_path = subprocess.run(["git", "config", "--local", "--get", "core.hooksPath"], cwd=root,
                               capture_output=True, text=True, timeout=5)
    result = {"schema_version": 1, "record_id": record_id, "client_date": client_date,
              "client_timezone": "Europe/Madrid", "started_at_utc": started, "finished_at_utc": timestamp(),
              "environment": {"os": platform.system(), "os_release": platform.release(),
                              "architecture": platform.machine(), "python": platform.python_version(), "tools": versions},
              "source_aggregate_sha256": before["aggregate_sha256"], "source_unchanged_during_run": unchanged,
              "source_scope": "engineering code, tests, policies, skills, adapters and root instructions; prose docs excluded",
              "git_repository_present": (root / ".git").exists(), "git_commit": commit.stdout.strip() if commit.returncode == 0 else None,
              "git_configuration": {"hook_path_matches": hook_path.returncode == 0 and hook_path.stdout.strip() == ".githooks"},
              "scope": {"local_protocol_and_tools": True, "provider_native_hooks_observed": native_valid,
                        "real_model_evaluation": False, "cloud_execution_observed": False,
                        "host_isolation_verified": tests["all_passed"] and any(case["id"].startswith("test_isolation.") for case in tests["cases"]),
                        "external_candidate_verification": workspace_valid,
                        "signed_or_independently_reviewed": False},
              "installation": {"codex_adapter_matches_source": installed_adapter.is_file() and
                               installed_adapter.read_bytes() == source_adapter.read_bytes(),
                               "claude_project_hooks_present": (root / ".claude/settings.json").exists()},
              "tests": tests, "catalog_coverage": coverage, "checks": checks,
              "accepted": tests["all_passed"] and coverage["complete"] and unchanged and all(c["outcome"] == "pass" for c in checks)
                          and (native_valid if native_report else True) and (workspace_valid if workspace_report else True)}
    write_record(output, result, before, supplemental)
    print("Registro local: {} casos; plan {}".format(tests["count"], "superado" if result["accepted"] else "no superado"))
    return 0 if result["accepted"] else 1


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="mode", required=True)
    create = sub.add_parser("record")
    create.add_argument("--output", type=Path, required=True)
    create.add_argument("--id", required=True)
    create.add_argument("--client-date", required=True)
    create.add_argument("--native-report", type=Path)
    create.add_argument("--workspace-report", type=Path)
    verify = sub.add_parser("verify")
    verify.add_argument("directory", type=Path)
    args = parser.parse_args()
    try:
        if args.mode == "record":
            sys.exit(record(args.output, args.id, args.client_date, args.native_report, args.workspace_report))
        valid = verify_record(args.directory)
        print("Integridad de artefactos: " + ("OK" if valid else "FALLO"))
        sys.exit(0 if valid else 1)
    except Exception:
        print("Registro o verificación incompletos; no se acredita evidencia válida")
        sys.exit(2)
