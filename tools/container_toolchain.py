"""Install verified Linux executables for the disposable native integration runner."""

import base64
import hashlib
import hmac
import json
import os
import shutil
import sys
import tarfile
import tempfile
import urllib.request
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def install(root=ROOT):
    config = json.loads((root / "policy/container-toolchain.json").read_text())
    output = root / ".artifacts/container-toolchain"
    if output.is_symlink() or output.parent.is_symlink():
        raise ValueError("Unsafe toolchain destination")
    output.mkdir(parents=True, exist_ok=True)
    for name, item in config["packages"].items():
        target = output / name
        expected = item.get("executable_sha256")
        if not expected or len(expected) != 64:
            raise ValueError("Executable hash must be reviewed in the lock before installation")
        if target.exists():
            if target.is_symlink() or not expected or hashlib.sha256(target.read_bytes()).hexdigest() != expected:
                raise ValueError("Changed container CLI")
            continue
        if not item["url"].startswith(("https://registry.npmjs.org/@openai/", "https://registry.npmjs.org/@anthropic-ai/")):
            raise ValueError("Unapproved package source")
        with tempfile.TemporaryDirectory(prefix="aie-cli-archive-") as directory:
            archive = Path(directory) / "package.tgz"
            digest = hashlib.sha512()
            size = 0
            with urllib.request.urlopen(item["url"], timeout=45) as response, archive.open("xb") as stream:
                if not response.url.startswith("https://registry.npmjs.org/"):
                    raise ValueError("Unapproved redirect")
                for block in iter(lambda: response.read(1024 * 1024), b""):
                    size += len(block)
                    if size > 512 * 1024 * 1024:
                        raise ValueError("Archive too large")
                    stream.write(block)
                    digest.update(block)
            if not hmac.compare_digest(digest.digest(), base64.b64decode(item["integrity"][7:], validate=True)):
                raise ValueError("Archive checksum mismatch")
            with tarfile.open(archive, "r:gz") as package:
                member = package.getmember(item["member"])
                if not member.isfile() or not 0 < member.size < 512 * 1024 * 1024:
                    raise ValueError("Invalid executable")
                with package.extractfile(member) as stream, target.open("xb") as destination:
                    shutil.copyfileobj(stream, destination)
            target.chmod(0o755)
            fingerprint = hashlib.sha256(target.read_bytes()).hexdigest()
            if expected and not hmac.compare_digest(fingerprint, expected):
                target.unlink()
                raise ValueError("Executable checksum mismatch")
        print(name + " container executable verified")


if __name__ == "__main__":
    try:
        install()
    except Exception as error:
        print("Container toolchain incomplete: " + type(error).__name__)
        sys.exit(2)
