"""Reproducible engineering-source bundles; no product release or signing claim."""

import argparse
import gzip
import hashlib
import io
import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def build(output, reference="HEAD", source=ROOT):
    if output.exists() or output.parent.is_symlink():
        raise ValueError("Bundle destination must be new")
    commit = subprocess.run(["git", "rev-parse", "--verify", reference + "^{commit}"], cwd=source,
                            check=True, capture_output=True, text=True, timeout=5).stdout.strip()
    subprocess.run([sys.executable, "-B", str(ROOT / "tools/scan_secrets.py"), "--root", str(source), "--history"],
                   check=True, capture_output=True, timeout=100)
    data = subprocess.run(["git", "archive", "--format=tar", "--prefix=aie-source/", commit], cwd=source,
                          check=True, capture_output=True, timeout=15).stdout
    buffer = io.BytesIO()
    with gzip.GzipFile(filename="", mode="wb", fileobj=buffer, mtime=0) as compressed:
        compressed.write(data)
    archive = buffer.getvalue()
    output.mkdir(parents=True, mode=0o700)
    (output / "source.tar.gz").write_bytes(archive)
    manifest = {"schema_version": 1, "kind": "engineering-source", "source_commit": commit,
                "artifact": "source.tar.gz", "sha256": hashlib.sha256(archive).hexdigest(),
                "bytes": len(archive), "signed": False, "product_release": False,
                "scope": "committed source; pinned secret scan passed; no runtime credentials added; unsigned"}
    (output / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    return manifest


def verify(output):
    manifest = json.loads((output / "manifest.json").read_text())
    artifact = output / "source.tar.gz"
    return (not output.is_symlink() and not artifact.is_symlink() and manifest["artifact"] == "source.tar.gz"
            and manifest["kind"] == "engineering-source" and manifest["product_release"] is False
            and artifact.stat().st_size == manifest["bytes"]
            and hashlib.sha256(artifact.read_bytes()).hexdigest() == manifest["sha256"])


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=["build", "verify"])
    parser.add_argument("directory", type=Path)
    parser.add_argument("--reference", default="HEAD")
    args = parser.parse_args()
    try:
        if args.action == "build":
            build(args.directory, args.reference)
        elif not verify(args.directory):
            raise ValueError("Invalid bundle")
        print("Artefacto de ingeniería comprobado; sin firma ni autorización de publicación")
    except Exception:
        print("Artefacto de ingeniería incompleto o alterado")
        sys.exit(2)
