"""Run a bounded validation process and clean up its process group (POSIX)."""

import os
import signal
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path
from threading import Event
from typing import Dict, List, Optional


@dataclass(frozen=True)
class Result:
    returncode: int
    elapsed: float


def live_group(group: int) -> bool:
    """Darwin can return EPERM when only zombies remain in a process group."""
    listing = subprocess.run(["/bin/ps", "-axo", "pgid=,stat="], check=True,
                             capture_output=True, text=True, timeout=3)
    for line in listing.stdout.splitlines():
        fields = line.split()
        if len(fields) == 2 and fields[0] == str(group) and not fields[1].startswith("Z"):
            return True
    return False


def run(command: List[str], cwd: Path, timeout: float,
        env: Optional[Dict[str, str]] = None,
        cancelled: Optional[Event] = None) -> Result:
    """Keep arbitrary tool output out of logs; callers report IDs and exit codes."""
    start = time.monotonic()
    if timeout <= 0 or (cancelled is not None and cancelled.is_set()):
        return Result(124, 0.0)
    if os.name != "posix":
        raise RuntimeError("Estas herramientas requieren macOS o Linux")
    process = subprocess.Popen(command, cwd=cwd, env=env, start_new_session=True,
                               stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    code = 124
    try:
        while True:
            remaining = timeout - (time.monotonic() - start)
            if remaining <= 0 or (cancelled is not None and cancelled.is_set()):
                break
            try:
                code = process.wait(timeout=min(0.1, remaining))
                break
            except subprocess.TimeoutExpired:
                continue
    finally:
        # Also stop children left in the group after their parent exits normally.
        try:
            try:
                os.killpg(process.pid, signal.SIGTERM)
                time.sleep(0.05)
                process.poll()  # Reap the parent before escalating to SIGKILL.
                os.killpg(process.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            except PermissionError:
                process.poll()
                if live_group(process.pid):
                    raise RuntimeError("No se pudo terminar un grupo de procesos del control")
        finally:
            process.wait(timeout=3)
    return Result(code, time.monotonic() - start)
