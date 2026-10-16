"""OS-enforced local execution; no silent fallback to an unrestricted process."""

import hashlib
import json
import os
import platform
import shutil
import signal
import subprocess
import sys
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path


@dataclass
class Execution:
    code: int
    stdout: bytes
    stderr: bytes
    elapsed: float
    backend: str
    profile_sha256: str
    output_limit_exceeded: bool = False


def safe_directory(path):
    path = Path(path).absolute()
    if not path.is_dir() or any(p.is_symlink() for p in (path, *path.parents)):
        raise ValueError("Isolation requires real, existing directories")
    return path.resolve()


def configuration(readable, writable, port=None):
    reads = [safe_directory(path) for path in readable]
    writes = [safe_directory(path) for path in writable]
    if not reads or not writes or any(str(p) == "/" or str(p) == str(Path.home()) for p in reads + writes):
        raise ValueError("Overbroad isolation roots")
    if port is not None and (type(port) is not int or not 1024 <= port <= 65535):
        raise ValueError("Invalid loopback port")
    if platform.system() == "Darwin":
        system = ["/usr", "/bin", "/sbin", "/System", "/Library/Developer", "/Applications/Xcode.app", "/opt/homebrew"]
        filters = " ".join("(subpath " + json.dumps(str(p)) + ")" for p in system + reads + writes)
        write_filters = " ".join("(subpath " + json.dumps(str(p)) + ")" for p in writes)
        profile = ("(version 1)(deny default)(allow process-exec)(allow process-fork)"
                   "(allow signal (target children))(allow signal (target self))"
                   '(allow sysctl-read)(allow file-read-metadata)(allow file-read* (literal "/"))'
                   "(allow file-read-data " + filters + ' (literal "/dev/null") (literal "/dev/urandom"))'
                   '(allow file-write* ' + write_filters + ' (literal "/dev/null"))')
        if port is not None:
            profile += '(allow network-outbound (remote tcp "localhost:' + str(port) + '"))'
        return ["/usr/bin/sandbox-exec", "-p", profile], "macOS-seatbelt", profile
    if platform.system() == "Linux":
        bwrap = shutil.which("bwrap")
        if not bwrap:
            raise RuntimeError("Linux isolation requires bubblewrap; execution refused")
        if port is not None:
            raise RuntimeError("Loopback networking requires a separately configured gateway on Linux")
        command = [bwrap, "--unshare-all", "--new-session", "--die-with-parent", "--cap-drop", "ALL",
                   "--proc", "/proc", "--dev", "/dev", "--tmpfs", "/tmp"]
        for path in ("/usr", "/bin", "/sbin", "/lib", "/lib64", "/etc/ssl", "/etc/ld.so.cache"):
            if Path(path).exists():
                command += ["--ro-bind", path, path]
        for path in reads:
            command += ["--ro-bind", str(path), str(path)]
        for path in writes:
            command += ["--bind", str(path), str(path)]
        return command + ["--"], "linux-bubblewrap", json.dumps(command)
    raise RuntimeError("Unsupported isolation backend; execution refused")


def execute(command, cwd, readable, writable, timeout=30, port=None, environment=None, input_bytes=None):
    if not command or not 0 < timeout <= 120:
        raise ValueError("Invalid execution budget")
    cwd = safe_directory(cwd)
    helper = Path(__file__).resolve().parent / "resource_exec.py"
    prefix, backend, profile = configuration(list(readable) + [helper.parent], writable, port)
    # Never inherit credentials, agent configuration, proxy settings or provider keys.
    env = {"PATH": str(Path(sys.executable).parent) + ":/usr/bin:/bin:/usr/sbin:/sbin:/opt/homebrew/bin", "LANG": "en_US.UTF-8",
           "PYTHONDONTWRITEBYTECODE": "1", "PYTHONNOUSERSITE": "1"}
    # Preserve the user's actual home location without granting read/write access.
    if "HOME" in os.environ:
        env["HOME"] = os.environ["HOME"]
    if environment:
        forbidden = {"HOME", "CODEX_HOME", "PATH", "PYTHONPATH", "DYLD_INSERT_LIBRARIES", "LD_PRELOAD"}
        if any(key in forbidden for key in environment):
            raise ValueError("Unsafe environment override")
        env.update(environment)
    started = time.monotonic()
    with tempfile.TemporaryFile(dir=writable[0]) as out, tempfile.TemporaryFile(dir=writable[0]) as err:
        child = subprocess.Popen(prefix + [sys.executable, "-B", str(helper)] + list(command),
                                 cwd=cwd, env=env, stdin=subprocess.PIPE, stdout=out, stderr=err,
                                 start_new_session=True)
        try:
            try:
                child.communicate(input_bytes, timeout=timeout)
                code = child.returncode
            except subprocess.TimeoutExpired:
                os.killpg(child.pid, signal.SIGKILL)
                child.communicate(timeout=5)
                code = 124
        finally:
            try:
                os.killpg(child.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            child.wait(timeout=5)
        out.seek(0); err.seek(0)
        stdout, stderr = out.read(1024 * 1024 + 1), err.read(1024 * 1024 + 1)
        exceeded = len(stdout) > 1024 * 1024 or len(stderr) > 1024 * 1024
        if exceeded:
            code = 125
            stdout, stderr = stdout[:1024 * 1024], stderr[:1024 * 1024]
    return Execution(code, stdout, stderr, round(time.monotonic() - started, 6),
                     backend, hashlib.sha256(profile.encode()).hexdigest(), exceeded)
