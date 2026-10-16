"""Run the foundation suite; empty discovery is a failure, not a green build."""

import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def execute_suite(directory: Path) -> int:
    suite = unittest.TestLoader().discover(str(directory))
    if suite.countTestCases() == 0:
        print("No se han descubierto pruebas; control incompleto")
        return 2
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    return 0 if result.wasSuccessful() else 1


if __name__ == "__main__":
    sys.exit(execute_suite(ROOT / "tests/tooling"))
