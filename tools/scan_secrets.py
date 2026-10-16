"""Fail closed on scanner errors, staged secrets and sensitive file paths."""

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import List

from check_repository import sensitive_path


ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / ".gitleaks.toml"


def invoke(args: List[str], cwd: Path, input_text=None, timeout=45):
    env = {k: v for k, v in os.environ.items() if not k.startswith("GITLEAKS_")}
    return subprocess.run(args, cwd=cwd, env=env, input=input_text, text=True,
                          stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=timeout)


def scan(root: Path = ROOT, staged: bool = False, history: bool = False) -> int:
    binary = shutil.which("gitleaks")
    if binary is None:
        print("Secretos: falta Gitleaks; no se omite el control")
        return 2
    expected = json.loads((ROOT / "policy/quality.json").read_text())["tool_versions"]["gitleaks"]
    version = invoke([binary, "version"], root, timeout=5)
    if version.returncode or version.stdout.strip() != expected:
        print("Secretos: versión no admitida; se requiere " + expected)
        return 2
    with tempfile.TemporaryDirectory(prefix="aie-secret-scan-") as temporary:
        ignore = Path(temporary) / "empty-ignore"
        ignore.touch(mode=0o600)
        flags = ["--config", str(CONFIG), "--gitleaks-ignore-path", str(ignore),
                 "--ignore-gitleaks-allow", "--redact=100", "--no-banner", "--no-color",
                 "--log-level", "error", "--timeout", "40"]
        # Deliberately synthetic, assembled to avoid putting a key-like literal in Git.
        probe = 'token = "' + 'ghp_' + 'AbCdEf0123456789' * 2 + 'AbCdEf01' + '"\n'
        canary = invoke([binary, "stdin"] + flags, root, probe, timeout=5)
        if canary.returncode != 1:
            print("Secretos: el scanner no superó su comprobación de detección")
            return 2
        if staged:
            names = invoke(["git", "diff", "--cached", "--name-only", "--diff-filter=ACM", "-z"], root)
            if names.returncode:
                print("Secretos: no se pudo leer el índice de Git")
                return 2
            if any(sensitive_path(name) for name in names.stdout.split("\0") if name):
                print("Secretos: hay archivos con nombres sensibles preparados para commit")
                return 1
            commands = [[binary, "git", "--pre-commit", "--staged", str(root)] + flags]
        else:
            commands = [[binary, "dir", str(root)] + flags]
            if history:
                commands.append([binary, "git", str(root), "--log-opts=--all"] + flags)
        for command in commands:
            result = invoke(command, root)
            if result.returncode:
                if result.returncode == 1:
                    print("Secretos: detección bloqueante; diagnosticar con Gitleaks y --redact=100")
                    return 1
                print("Secretos: error del scanner; no se interpreta como resultado limpio")
                return 2
    print("Secretos: OK (canary y alcance solicitado)")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=ROOT)
    modes = parser.add_mutually_exclusive_group()
    modes.add_argument("--staged", action="store_true")
    modes.add_argument("--history", action="store_true")
    args = parser.parse_args()
    try:
        return scan(root=args.root.resolve(strict=True), staged=args.staged, history=args.history)
    except (OSError, ValueError, KeyError, subprocess.TimeoutExpired):
        print("Secretos: control incompleto por error de herramienta o configuración")
        return 2


if __name__ == "__main__":
    sys.exit(main())
