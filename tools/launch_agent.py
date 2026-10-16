"""Load reviewed project adapters explicitly; preserve native permissions and trust."""

import argparse
import json
import subprocess
import sys
from pathlib import Path

from native_hook_probe import toml_value
from project_toolchain import binary
from check_agent_setup import version_tuple


ROOT = Path(__file__).resolve().parents[1]


def command(provider, extra):
    adapter = ROOT / "policy/adapters" / (provider + ".json")
    executable = binary(provider)
    version = subprocess.run([executable, "--version"], capture_output=True, text=True, timeout=10, check=True)
    policy = json.loads((ROOT / "policy/agent-enforcement.json").read_text())
    current = version_tuple(version.stdout)
    if provider == "codex":
        if current != version_tuple(policy["validated_codex_version"]):
            raise ValueError("Codex version differs from the validated compatibility baseline")
        hooks = json.loads(adapter.read_text())["hooks"]
        return [executable, "--enable", "hooks", "-c", "hooks=" + toml_value(hooks), *extra]
    if current < version_tuple(policy["minimum_claude_version"]):
        raise ValueError("Claude version lacks the required failure handling")
    return [executable, "--settings", str(adapter), *extra]


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("provider", choices=["codex", "claude"])
    parser.add_argument("arguments", nargs=argparse.REMAINDER)
    args = parser.parse_args()
    try:
        extra = args.arguments[1:] if args.arguments[:1] == ["--"] else args.arguments
        sys.exit(subprocess.call(command(args.provider, extra), cwd=ROOT))
    except Exception:
        print("Inicio rechazado: revisar CLI, versión y adaptador; no se omiten hooks ni permisos")
        sys.exit(2)
