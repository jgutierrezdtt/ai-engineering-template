"""Install one pinned scanner in an explicitly selected local/CI directory."""

import argparse
import hashlib
import io
import json
import platform
import sys
import tarfile
import urllib.request
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def install(directory):
    config = json.loads((ROOT / "policy/verification-tools.json").read_text())
    source = config["archives"][platform.system() + "-" + platform.machine()]
    if directory.exists() or any(path.is_symlink() for path in directory.absolute().parents):
        raise ValueError("Scanner destination must be new and without symlinks")
    url = "https://github.com/gitleaks/gitleaks/releases/download/v" + config["gitleaks_version"] + "/" + source["name"]
    with urllib.request.urlopen(url, timeout=45) as response:
        data = response.read(64 * 1024 * 1024 + 1)
    if len(data) > 64 * 1024 * 1024 or hashlib.sha256(data).hexdigest() != source["sha256"]:
        raise ValueError("Scanner archive integrity failure")
    with tarfile.open(fileobj=io.BytesIO(data), mode="r:gz") as archive:
        member = archive.getmember("gitleaks")
        if not member.isfile() or not 0 < member.size < 64 * 1024 * 1024:
            raise ValueError("Unexpected scanner executable")
        directory.mkdir(parents=True, mode=0o700)
        with archive.extractfile(member) as content:
            (directory / "gitleaks").write_bytes(content.read())
        (directory / "gitleaks").chmod(0o700)
    print("Scanner fijado por versión e integridad; instalado en ámbito temporal")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--directory", type=Path, required=True)
    args = parser.parse_args()
    try:
        install(args.directory.absolute())
    except Exception:
        print("No se pudo aprovisionar el scanner; no se omite el control")
        sys.exit(2)
