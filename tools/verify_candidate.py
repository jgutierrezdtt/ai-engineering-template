"""Freeze an untrusted working copy and verify it using controls from a Git reference."""

import argparse
import json
import os
import stat
import sys
import tempfile
import subprocess
import time
from pathlib import Path

from isolated_process import execute, safe_directory
from managed_workspace import checkout, protected_changes, tree_digest
from quality import selected_gates
from verify_change import required_profile


ROOT = Path(__file__).resolve().parents[1]
MAX_FILES, MAX_BYTES = 5000, 50 * 1024 * 1024


def freeze(source, target):
    """Copy through anchored directory descriptors; refuse links, devices and oversized trees."""
    source = safe_directory(source)
    target.mkdir(mode=0o700)
    count = size = 0
    for directory, folders, files, descriptor in os.fwalk(str(source), follow_symlinks=False):
        relative = Path(directory).relative_to(source)
        count += len(folders)
        if count > MAX_FILES:
            raise ValueError("Candidate entry budget exceeded")
        if any(name in {".git", ".artifacts", "node_modules", ".venv"} for name in folders):
            raise ValueError("Candidate must be a source export without local state")
        for name in folders:
            metadata = os.stat(name, dir_fd=descriptor, follow_symlinks=False)
            if not stat.S_ISDIR(metadata.st_mode):
                raise ValueError("Symlink directory in candidate")
            (target / relative / name).mkdir(parents=True, exist_ok=True)
        for name in files:
            count += 1
            if count > MAX_FILES:
                raise ValueError("Candidate file budget exceeded")
            handle = os.open(name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=descriptor)
            with os.fdopen(handle, "rb") as content:
                metadata = os.fstat(content.fileno())
                if not stat.S_ISREG(metadata.st_mode) or metadata.st_nlink != 1:
                    raise ValueError("Non-regular input")
                size += metadata.st_size
                if size > MAX_BYTES:
                    raise ValueError("Candidate byte budget exceeded")
                data = content.read(MAX_BYTES - size + metadata.st_size + 1)
                if len(data) != metadata.st_size:
                    raise ValueError("Candidate changed while copying")
            destination = target / relative / name
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_bytes(data)
            destination.chmod(metadata.st_mode & 0o777)


def verify(candidate, reference="HEAD"):
    with tempfile.TemporaryDirectory(prefix="aie-independent-check-") as directory:
        directory = Path(directory).resolve()
        frozen = directory / "candidate"
        freeze(candidate, frozen)
        trusted = directory / "controls"
        commit = checkout(ROOT, trusted, reference)
        policy = json.loads((trusted / "policy/agent-enforcement.json").read_text())
        differences = protected_changes(trusted, frozen, policy)
        if differences:
            return {"accepted": False, "reason": "protected-inputs-changed", "count": len(differences)}
        fingerprint = tree_digest(frozen)
        temporary = directory / "temporary"
        temporary.mkdir(mode=0o700)
        started = time.monotonic()
        config = json.loads((trusted / "policy/quality.json").read_text())
        profile = required_profile(frozen)
        product = selected_gates(config, profile)
        # Foundation checks execute only code/tests from the trusted reference.
        # Candidate inputs are parsed/scanned, never imported by the host controller.
        foundation = subprocess.run([sys.executable, "-B", str(trusted / "tools/quality.py"), "bootstrap",
                                     "--workspace", str(frozen)], capture_output=True, timeout=120,
                                    env=dict(os.environ, TMPDIR=str(temporary), PYTHONDONTWRITEBYTECODE="1"))
        code = foundation.returncode
        results = []
        if code == 0:
            for gate in product:
                state = temporary / gate["id"]
                state.mkdir(mode=0o700)
                budget = min(120, config["budgets_seconds"][profile] - (time.monotonic() - started))
                result = execute(gate["command"], frozen, [frozen, trusted], [state], timeout=budget,
                                 environment={"TMPDIR": str(state), "AIE_RUN_DIR": str(state)})
                results.append({"id": gate["id"], "code": result.code, "backend": result.backend})
                if result.code:
                    code = result.code
        unchanged = fingerprint == tree_digest(frozen)
        return {"schema_version": 1, "accepted": code == 0 and unchanged,
                "trusted_commit": commit, "candidate_sha256": fingerprint["sha256"],
                "candidate_unchanged": unchanged, "controls_from_candidate_executed": False,
                "exit_code": code, "profile": profile, "product_gates": results,
                "foundation_code_from_trusted_reference_only": True,
                "elapsed_seconds": round(time.monotonic() - started, 6),
                "network_allowed": False, "temporary_state_removed": True,
                "scope": "local verification against a committed reference; not an independent human review"}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("candidate", type=Path)
    parser.add_argument("--reference", default="HEAD")
    args = parser.parse_args()
    try:
        result = verify(args.candidate, args.reference)
        print(json.dumps(result, indent=2))
        sys.exit(0 if result["accepted"] else 2)
    except Exception:
        print("Verificación externa al candidato incompleta; ejecución rechazada")
        sys.exit(2)
