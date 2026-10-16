"""Launch and inspect a bounded container; never mount credentials or the Docker socket."""

import argparse
import hashlib
import json
import subprocess
import sys
import tempfile
import uuid
import time
from datetime import datetime, timezone
from pathlib import Path

from native_hook_probe import prepare
from ephemeral_containers import collect, CONTROLLER
from record_verification import snapshot


ROOT = Path(__file__).resolve().parents[1]
IMAGE = "aie-native-checks:local"


def call(arguments, timeout=15):
    return subprocess.run(["docker", *arguments], capture_output=True, text=True, timeout=timeout, check=True).stdout


def validate_inspection(item):
    host, config = item["HostConfig"], item["Config"]
    if not (host["NetworkMode"] == "none" and host["ReadonlyRootfs"] is True
            and host["Privileged"] is False and host["CapDrop"] == ["ALL"]
            and host["PidsLimit"] == 256 and host["Memory"] == 1073741824
            and host["NanoCpus"] == 2000000000 and not host["PidMode"]
            and "no-new-privileges" in host["SecurityOpt"] and config["User"] == "10001:10001"):
        raise ValueError("Container isolation configuration rejected")
    mounts = item["Mounts"]
    if {mount["Destination"] for mount in mounts if mount["Type"] == "bind"} != {"/control", "/opt/aie-tools"}:
        raise ValueError("Unexpected container bind mount")
    if any(mount["RW"] for mount in mounts if mount["Type"] == "bind"):
        raise ValueError("Writable control mount")


def run(provider="all", scenario="all"):
    started = time.monotonic()
    started_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
    collect()
    source_before = snapshot(ROOT)
    config = json.loads((ROOT / "policy/container-toolchain.json").read_text())
    toolchain = ROOT / ".artifacts/container-toolchain"
    for name, item in config["packages"].items():
        binary = toolchain / name
        if binary.is_symlink() or hashlib.sha256(binary.read_bytes()).hexdigest() != item["executable_sha256"]:
            raise ValueError("Container CLI hash mismatch")
    identifier = "aie-native-" + uuid.uuid4().hex
    # The source tree is mounted read-only. No git metadata or toolchain secrets are needed.
    image = json.loads(call(["image", "inspect", IMAGE]))[0]
    image_id = image["Id"]
    receipt = json.loads((ROOT / ".artifacts/native-image.json").read_text())
    if (receipt["image_id"] != image_id or receipt["base_image"] != config["base_image"]
            or receipt["dockerfile_sha256"] != hashlib.sha256((ROOT / "tools/container/Dockerfile").read_bytes()).hexdigest()
            or image["Architecture"] != "arm64"):
        raise ValueError("Image does not match the locally reviewed build recipe")
    args = ["create", "--name", identifier, "--label", "aie.owner=native-verification",
            "--label", "aie.controller=" + CONTROLLER,
            "--label", "aie.expires=" + str(int(time.time()) + 240),
            "--network", "none", "--read-only", "--cap-drop", "ALL", "--security-opt", "no-new-privileges",
            "--pids-limit", "256", "--memory", "1g", "--cpus", "2", "--user", "10001:10001",
            "--tmpfs", "/tmp:rw,nosuid,nodev,noexec,size=256m,mode=1777",
            "--tmpfs", "/home/aie:rw,nosuid,nodev,noexec,size=64m,mode=700,uid=10001,gid=10001",
            "--mount", "type=bind,src=" + str(ROOT) + ",dst=/control,readonly",
            "--mount", "type=bind,src=" + str(toolchain) + ",dst=/opt/aie-tools,readonly", image_id,
            "--provider", provider, "--scenario", scenario]
    temporary = tempfile.TemporaryDirectory(prefix="aie-native-control-")
    staged = Path(temporary.name).resolve() / "control"
    staged.mkdir(mode=0o755)
    prepare(staged)
    # Docker's unprivileged UID needs directory traversal on the disposable snapshot.
    Path(temporary.name).chmod(0o755)
    mount_index = args.index("type=bind,src=" + str(ROOT) + ",dst=/control,readonly")
    args[mount_index] = "type=bind,src=" + str(staged) + ",dst=/control,readonly"
    created = False
    try:
        call(args)
        created = True
        inspected = json.loads(call(["inspect", identifier]))[0]
        validate_inspection(inspected)
        if inspected["Image"] != image_id:
            raise ValueError("Container image changed")
        result = subprocess.run(["docker", "start", "--attach", identifier], capture_output=True, text=True, timeout=210)
        try:
            report = json.loads(result.stdout)
        except ValueError:
            raise ValueError("Native suite did not produce valid evidence")
        report["container"] = {"image_id": image_id, "base_image": config["base_image"],
                               "platform": config["platform"], "settings_inspected_before_start": True,
                               "network": "none", "read_only_root": True, "user": "10001:10001",
                               "capabilities": [], "memory_bytes": 1073741824, "pids_limit": 256,
                               "docker_socket_mounted": False, "host_credentials_mounted": False}
    finally:
        try:
            if created:
                call(["rm", "--force", identifier])
        finally:
            temporary.cleanup()
    report["container"]["removed_after_run"] = True
    report["source_aggregate_sha256"] = source_before["aggregate_sha256"]
    report["started_at_utc"] = started_at
    report["elapsed_seconds"] = round(time.monotonic() - started, 6)
    report["source_unchanged_during_run"] = source_before == snapshot(ROOT)
    report["accepted"] = report["accepted"] and report["source_unchanged_during_run"]
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--provider", choices=["all", "claude", "codex"], default="all")
    parser.add_argument("--scenario", choices=["all", "allowed", "denied", "missing", "crash", "invalid-json", "timeout", "outer-boundary"], default="all")
    args = parser.parse_args()
    try:
        report = run(args.provider, args.scenario)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        with args.output.open("x") as target:
            json.dump(report, target, ensure_ascii=False, indent=2)
            target.write("\n")
        for case in report["cases"]:
            print(case["id"], "OK" if case["passed"] else "PENDIENTE", "exit=" + str(case["cli_exit_code"]))
        sys.exit(0 if report["accepted"] else 2)
    except Exception as error:
        print("Prueba nativa en contenedor incompleta: " + type(error).__name__)
        sys.exit(2)
