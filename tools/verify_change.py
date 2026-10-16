"""Select the minimum required gate from the checkout, rather than an AI claim."""

import sys
import argparse
from pathlib import Path

import quality


ROOT = Path(__file__).resolve().parents[1]
PRODUCT_ROOTS = ("src", "app", "apps", "lib", "cmd", "internal", "services", "packages", "agents", "evals", "infra", "tests/product")
PRODUCT_MANIFESTS = ("package.json", "pyproject.toml", "requirements.txt", "go.mod", "Cargo.toml", "pom.xml", "build.gradle", "composer.json", "Gemfile")


def required_profile(root: Path) -> str:
    product = any((root / p).exists() for p in PRODUCT_ROOTS + PRODUCT_MANIFESTS)
    product = product or any(p.is_file() and p.suffix in {".py", ".js", ".ts", ".tsx", ".jsx", ".go", ".rs", ".java", ".cs", ".php", ".rb"} for p in root.iterdir())
    return "quick" if product else "bootstrap"


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--history", action="store_true")
    parser.add_argument("--workspace", type=Path, default=ROOT)
    args = parser.parse_args()
    sys.argv = [sys.argv[0], required_profile(args.workspace), "--workspace", str(args.workspace)]
    if args.history:
        sys.argv.append("--history")
    sys.exit(quality.main())
