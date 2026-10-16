"""Collect only expired native-check containers owned by this local controller."""

import hashlib
import json
import re
import subprocess
import time
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CONTROLLER = hashlib.sha256(str(ROOT).encode()).hexdigest()[:24]


def expired_owned(item, now):
    labels = item.get("Config", {}).get("Labels", {})
    return (labels.get("aie.owner") == "native-verification"
            and labels.get("aie.controller") == CONTROLLER
            and re.fullmatch(r"/aie-native-[0-9a-f]{32}", item.get("Name", "")) is not None
            and str(labels.get("aie.expires", "")).isdigit()
            and int(labels["aie.expires"]) < now)


def collect():
    found = subprocess.run(["docker", "ps", "--all", "--quiet", "--filter", "label=aie.owner=native-verification",
                            "--filter", "label=aie.controller=" + CONTROLLER], check=True,
                           capture_output=True, text=True, timeout=10).stdout.split()
    removed = 0
    for identifier in found:
        inspection = subprocess.run(["docker", "inspect", identifier], capture_output=True, text=True, check=True, timeout=10)
        if expired_owned(json.loads(inspection.stdout)[0], time.time()):
            subprocess.run(["docker", "rm", "--force", identifier], capture_output=True, check=True, timeout=15)
            removed += 1
    return removed


if __name__ == "__main__":
    print("Contenedores propios caducados retirados: " + str(collect()))
