"""Native fixture suite entrypoint, only inside an externally inspected container."""

import json
import argparse
import os
import subprocess
import sys
import tempfile
import time
import signal
import re
import platform
from project_toolchain import binary
from pathlib import Path

import native_hook_probe
from isolated_process import Execution


def contained_execute(command, cwd, readable, writable, timeout=30, port=None, environment=None, input_bytes=None):
    if not Path("/.dockerenv").is_file() or os.getuid() != 10001:
        raise RuntimeError("This entrypoint requires the disposable container")
    env = {"HOME": os.environ["HOME"], "PATH": "/opt/aie-tools:/usr/local/bin:/usr/bin:/bin",
           "PYTHONDONTWRITEBYTECODE": "1", "PYTHONNOUSERSITE": "1", "LANG": "C.UTF-8"}
    env.update(environment or {})
    started = time.monotonic()
    helper = Path(__file__).with_name("resource_exec.py")
    with tempfile.TemporaryFile() as out, tempfile.TemporaryFile() as err:
        child = subprocess.Popen([sys.executable, "-B", str(helper), *command], cwd=cwd, env=env,
                                 stdin=subprocess.PIPE, stdout=out, stderr=err, start_new_session=True)
        try:
            child.communicate(input_bytes, timeout=timeout)
            code = child.returncode
        except subprocess.TimeoutExpired:
            os.killpg(child.pid, 9)
            child.communicate(timeout=5)
            code = 124
        finally:
            try:
                os.killpg(child.pid, 9)
            except ProcessLookupError:
                pass
        out.seek(0); err.seek(0)
        stdout, stderr = out.read(1024 * 1024 + 1), err.read(1024 * 1024 + 1)
        exceeded = len(stdout) > 1024 * 1024 or len(stderr) > 1024 * 1024
    return Execution(125 if exceeded else code, stdout[:1024 * 1024], stderr[:1024 * 1024],
                     round(time.monotonic() - started, 6), "docker-network-none", "externally-inspected", exceeded)


if __name__ == "__main__":
    signal.alarm(180)  # PID 1 exits even if the host-side controller disappears.
    parser = argparse.ArgumentParser()
    parser.add_argument("--provider", choices=["all", "claude", "codex"], default="all")
    parser.add_argument("--scenario", choices=["all", "allowed", "denied", "missing", "crash", "invalid-json", "timeout", "outer-boundary"], default="all")
    args = parser.parse_args()
    native_hook_probe.execute = contained_execute
    # A restricted diagnosis is available without exporting raw provider messages.
    result = native_hook_probe.run(args.provider, args.scenario)
    versions = {}
    for provider in ("claude", "codex"):
        version = subprocess.run([binary(provider), "--version"], capture_output=True, text=True, timeout=10, check=True)
        versions[provider] = re.search(r"\d+\.\d+\.\d+", version.stdout).group(0)
    result["environment"] = {"python": platform.python_version(), "os": platform.system(),
                             "architecture": platform.machine(), "uid": os.getuid(), "tools": versions}
    print(json.dumps(result, ensure_ascii=False))
    sys.exit(0 if result["accepted"] else 2)
