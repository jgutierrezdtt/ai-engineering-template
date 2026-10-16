"""Build the exact native verification image and bind it to its reviewed recipe."""

import hashlib
import json
import subprocess
import sys
from pathlib import Path

from container_toolchain import install


ROOT = Path(__file__).resolve().parents[1]


def prepare():
    config = json.loads((ROOT / "policy/container-toolchain.json").read_text())
    recipe = ROOT / "tools/container/Dockerfile"
    if recipe.read_text().splitlines()[0] != "FROM " + config["base_image"]:
        raise ValueError("Recipe and pinned base disagree")
    install()
    subprocess.run(["docker", "build", "--platform", config["platform"], "--tag", "aie-native-checks:local",
                    "--file", str(recipe), str(recipe.parent)], check=True, timeout=180,
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    result = subprocess.run(["docker", "image", "inspect", "aie-native-checks:local"],
                            check=True, capture_output=True, text=True, timeout=10)
    image = json.loads(result.stdout)[0]
    receipt = {"image_id": image["Id"], "base_image": config["base_image"],
               "dockerfile_sha256": hashlib.sha256(recipe.read_bytes()).hexdigest(),
               "architecture": image["Architecture"], "scope": "local build receipt, unsigned"}
    (ROOT / ".artifacts/native-image.json").write_text(json.dumps(receipt, indent=2) + "\n")
    print("Imagen de comprobación fijada por digest y receta; sin publicación")


if __name__ == "__main__":
    try:
        prepare()
    except Exception as error:
        print("Entorno nativo incompleto: " + type(error).__name__)
        sys.exit(2)
