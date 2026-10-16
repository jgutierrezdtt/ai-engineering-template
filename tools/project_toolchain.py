"""Resolve a pinned project CLI without changing global installations."""

import argparse
import base64
import hashlib
import hmac
import json
import os
import platform
import shutil
import subprocess
import sys
import tarfile
import tempfile
import urllib.request
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
LIMIT = 512 * 1024 * 1024


def specification(root=ROOT):
    config = json.loads((root / "policy/toolchain.json").read_text())
    if config["schema_version"] != 1:
        raise ValueError("Unsupported toolchain")
    item = config["claude"]
    return item["version"], item["platforms"][platform.system() + "-" + platform.machine()]


def destination(root=ROOT):
    version, _ = specification(root)
    directory = root / ".artifacts/toolchain" / ("claude-" + version)
    if any(path.is_symlink() for path in (root / ".artifacts", directory.parent, directory)):
        raise ValueError("Symlink in toolchain destination")
    return directory


def file_hash(path):
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for data in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(data)
    return digest.hexdigest()


def binary(provider, root=ROOT):
    if provider == "claude":
        directory = destination(root)
        executable = directory / "claude"
        receipt = directory / "installation.json"
        if executable.is_file() or receipt.is_file():
            if executable.is_symlink() or receipt.is_symlink():
                raise ValueError("Symlink in toolchain")
            recorded = json.loads(receipt.read_text())
            version, source = specification(root)
            if (recorded["version"] != version or recorded["integrity"] != source["integrity"]
                    or not hmac.compare_digest(file_hash(executable), source["executable_sha256"])):
                raise ValueError("Project toolchain changed")
            return str(executable)
    found = shutil.which(provider)
    if not found:
        raise ValueError("Missing CLI: " + provider)
    return found


def install(root=ROOT):
    version, source = specification(root)
    output = destination(root)
    if output.exists():
        binary("claude", root)
        print("Claude de proyecto: instalación fijada ya verificada")
        return
    output.parent.mkdir(parents=True, exist_ok=True)
    if not source["url"].startswith("https://registry.npmjs.org/@anthropic-ai/"):
        raise ValueError("Unapproved download origin")
    with tempfile.TemporaryDirectory(prefix=".install-", dir=output.parent) as temporary:
        temporary = Path(temporary)
        archive = temporary / "package.tgz"
        digest = hashlib.sha512()
        size = 0
        with urllib.request.urlopen(source["url"], timeout=45) as response, archive.open("xb") as target:
            if not response.url.startswith("https://registry.npmjs.org/"):
                raise ValueError("Unapproved redirect")
            while True:
                block = response.read(1024 * 1024)
                if not block:
                    break
                size += len(block)
                if size > LIMIT:
                    raise ValueError("Download too large")
                digest.update(block)
                target.write(block)
        expected = base64.b64decode(source["integrity"].removeprefix("sha512-"), validate=True)
        if not hmac.compare_digest(digest.digest(), expected):
            raise ValueError("Archive integrity failure")
        prepared = temporary / "ready"
        prepared.mkdir(mode=0o700)
        with tarfile.open(archive, "r:gz") as package:
            members = [item for item in package.getmembers()
                       if item.name in {"package/claude", "package/bin/claude"}]
            if len(members) != 1 or not members[0].isfile() or not 0 < members[0].size < LIMIT:
                raise ValueError("Unexpected executable in verified package")
            executable = prepared / "claude"
            with package.extractfile(members[0]) as content, executable.open("xb") as target:
                shutil.copyfileobj(content, target)
        executable.chmod(0o700)
        if not hmac.compare_digest(file_hash(executable), source["executable_sha256"]):
            raise ValueError("Executable integrity failure")
        result = subprocess.run([str(executable), "--version"], capture_output=True, text=True, timeout=10)
        if result.returncode or result.stdout.split()[0] != version:
            raise ValueError("Executable version mismatch")
        receipt = {"version": version, "integrity": source["integrity"],
                   "executable_sha256": file_hash(executable), "archive_bytes": size,
                   "scope": "project-local; archive integrity checked; no independent publisher attestation"}
        (prepared / "installation.json").write_text(json.dumps(receipt, indent=2) + "\n")
        os.rename(prepared, output)
    print("Claude de proyecto: versión " + version + " instalada y verificada; sin scripts de instalación")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=["install-claude", "check"])
    args = parser.parse_args()
    try:
        if args.action == "install-claude":
            install()
        else:
            binary("claude")
            print("Toolchain: integridad local comprobada")
    except Exception as error:
        print("Toolchain bloqueada: " + type(error).__name__)
        sys.exit(2)
