"""Run the foundation suite; empty discovery is a failure, not a green build."""

import sys
import unittest
import argparse
import json
from pathlib import Path

from record_verification import run_suite


ROOT = Path(__file__).resolve().parents[1]


def execute_suite(directory: Path, output=None) -> int:
    suite = unittest.TestLoader().discover(str(directory))
    if suite.countTestCases() == 0:
        print("No se han descubierto pruebas; control incompleto")
        return 2
    result = run_suite(suite)
    if output is not None:
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(result, indent=2) + "\n")
    print("Pruebas ejecutadas: " + str(result["count"]))
    for case in result["cases"]:
        if case["outcome"] != "pass":
            print(case["id"] + ": " + case["outcome"])
    return 0 if result["all_passed"] else 1


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    sys.exit(execute_suite(ROOT / "tests/tooling", args.output))
