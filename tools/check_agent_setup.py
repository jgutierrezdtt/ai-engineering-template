"""Check CLI compatibility, without starting a model or changing user settings."""

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

from project_toolchain import binary


ROOT = Path(__file__).resolve().parents[1]


def version_tuple(text):
    match = re.search(r"\b(\d+)\.(\d+)\.(\d+)\b", text)
    if match is None:
        raise ValueError("Versión no reconocida")
    return tuple(int(part) for part in match.groups())


def check(provider):
    policy = json.loads((ROOT / "policy/agent-enforcement.json").read_text())
    executable = binary(provider)
    result = subprocess.run([executable, "--version"], capture_output=True, text=True, timeout=10)
    if result.returncode:
        raise ValueError("No se pudo comprobar la versión")
    version = version_tuple(result.stdout)
    if provider == "claude":
        minimum = version_tuple(policy["minimum_claude_version"])
        if version < minimum:
            print("Claude: incompatible con bloqueo ante fallo del hook; requiere >= " + policy["minimum_claude_version"])
            return 2
    else:
        result = subprocess.run([executable, "features", "list"], capture_output=True, text=True, timeout=10)
        if result.returncode or not re.search(r"^hooks\s+\S+\s+true\s*$", result.stdout, re.MULTILINE):
            print("Codex: hooks no habilitados o no comprobables")
            return 2
    print(provider + ": compatibilidad básica comprobada; confianza, cobertura real y aislamiento pendientes")
    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("provider", choices=["codex", "claude"])
    args = parser.parse_args()
    try:
        sys.exit(check(args.provider))
    except (OSError, ValueError, subprocess.TimeoutExpired):
        print("No se pudo verificar compatibilidad; no se presupone soporte")
        sys.exit(2)
