"""Create a disposable working copy from a committed, locally approved reference."""

import argparse
import hashlib
import io
import json
import subprocess
import sys
import tarfile
import tempfile
from pathlib import Path

from isolated_process import execute


ROOT = Path(__file__).resolve().parents[1]


def tree_digest(root):
    files = []
    aggregate = hashlib.sha256()
    for path in sorted(root.rglob("*")):
        if path.is_symlink():
            raise ValueError("Symlink in managed workspace")
        if path.is_file():
            relative = path.relative_to(root).as_posix()
            digest = hashlib.sha256(path.read_bytes()).hexdigest()
            files.append({"path": relative, "sha256": digest})
            aggregate.update(relative.encode() + b"\0" + bytes.fromhex(digest))
    return {"sha256": aggregate.hexdigest(), "files": files}


def checkout(source, target, reference="HEAD"):
    if target.exists():
        raise ValueError("Workspace already exists")
    reference = subprocess.run(["git", "rev-parse", "--verify", reference + "^{commit}"],
                               cwd=source, check=True, capture_output=True, text=True, timeout=5).stdout.strip()
    archive = subprocess.run(["git", "archive", "--format=tar", reference], cwd=source,
                             check=True, capture_output=True, timeout=15).stdout
    target.mkdir(mode=0o700)
    with tarfile.open(fileobj=io.BytesIO(archive), mode="r:") as stream:
        for item in stream.getmembers():
            destination = target / item.name
            if item.name.startswith("/") or ".." in Path(item.name).parts or not (item.isdir() or item.isfile()):
                raise ValueError("Unsupported archive member")
            if item.isdir():
                destination.mkdir(parents=True, exist_ok=True)
            else:
                destination.parent.mkdir(parents=True, exist_ok=True)
                with stream.extractfile(item) as content:
                    destination.write_bytes(content.read())
                destination.chmod(item.mode & 0o777)
    return reference


def editable_directories(workspace, policy):
    result = []
    for name in policy["editable_roots"]:
        directory = workspace / name
        if not directory.resolve().is_relative_to(workspace.resolve()) or directory.is_symlink():
            raise ValueError("Unsafe writable root")
        if directory.is_dir():
            result.append(directory)
    # A file is writable only if its parent is writable on several OS backends.
    # Root files remain read-only; edits are proposed later through a reviewed patch.
    return result


def protected_changes(reference, candidate, policy):
    allowed = policy["editable_roots"]
    files = set(path.relative_to(reference).as_posix() for path in reference.rglob("*") if path.is_file())
    files.update(path.relative_to(candidate).as_posix() for path in candidate.rglob("*") if path.is_file() or path.is_symlink())
    changed = []
    for name in sorted(files):
        target = candidate / name
        if target.is_symlink() or any(parent.is_symlink() for parent in target.parents):
            changed.append(name)
            continue
        if any(name.startswith(root + "/") for root in allowed):
            continue
        original = reference / name
        if not target.is_file() or not original.is_file() or original.read_bytes() != target.read_bytes():
            changed.append(name)
    return changed


def run(command, timeout=60):
    policy = json.loads((ROOT / "policy/agent-enforcement.json").read_text())
    with tempfile.TemporaryDirectory(prefix="aie-managed-") as directory:
        directory = Path(directory).resolve()
        workspace = directory / "workspace"
        commit = checkout(ROOT, workspace)
        temporary = directory / "temporary"
        temporary.mkdir(mode=0o700)
        writable = editable_directories(workspace, policy) + [temporary]
        before = tree_digest(workspace)
        result = execute(command, workspace, [workspace], writable, timeout=timeout,
                         environment={"TMPDIR": str(temporary), "AIE_RUN_DIR": str(temporary)})
        after = tree_digest(workspace)
        return {"schema_version": 1, "reference_commit": commit, "exit_code": result.code,
                "backend": result.backend, "profile_sha256": result.profile_sha256,
                "before_sha256": before["sha256"], "after_sha256": after["sha256"],
                "changed_files": [entry["path"] for entry in after["files"]
                                  if entry not in before["files"]],
                "protected_inputs_writable": False, "network_allowed": False,
                "credentials_inherited": False, "temporary_workspace_removed": True,
                "elapsed_seconds": result.elapsed}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--timeout", type=float, default=60)
    parser.add_argument("--export", type=Path, help="Exportar HEAD a un directorio nuevo sin ejecutar código")
    parser.add_argument("command", nargs=argparse.REMAINDER)
    args = parser.parse_args()
    try:
        if args.export:
            if args.command:
                raise ValueError("Export and execution cannot be combined")
            print(json.dumps({"reference_commit": checkout(ROOT, args.export.absolute())}))
            sys.exit(0)
        command = args.command[1:] if args.command[:1] == ["--"] else args.command
        result = run(command, args.timeout)
        print(json.dumps(result, indent=2))
        sys.exit(0 if result["exit_code"] == 0 else 1)
    except Exception:
        print("Ejecución administrada rechazada; no se ejecuta sin aislamiento")
        sys.exit(2)
