"""Single local/CI entry point; unconfigured product gates cannot pass."""

import argparse
import concurrent.futures
import json
import math
import os
import re
import sys
import tempfile
import time
from pathlib import Path
from threading import Event
from typing import Dict, List

from processes import run


ROOT = Path(__file__).resolve().parents[1]


def selected_gates(config: Dict, profile: str) -> List[Dict]:
    if config.get("schema_version") != 1:
        raise ValueError("Versión de política no soportada")
    budgets = config["budgets_seconds"]
    if any(not isinstance(budgets.get(p), (int, float)) or isinstance(budgets[p], bool)
           or not math.isfinite(budgets[p]) or budgets[p] <= 0
           for p in ("bootstrap", "quick", "release")):
        raise ValueError("Presupuestos inválidos")
    parallel = config.get("max_parallel")
    if not isinstance(parallel, int) or isinstance(parallel, bool) or not 1 <= parallel <= 4:
        raise ValueError("Concurrencia fuera del límite 1–4")
    all_gates = config["gates"]
    if not all_gates or len({g["id"] for g in all_gates}) != len(all_gates):
        raise ValueError("Inventario de controles vacío o duplicado")
    for gate in all_gates:
        if not isinstance(gate["id"], str) or not re.fullmatch(r"[a-z0-9-]+", gate["id"]):
            raise ValueError("ID de control inválido")
        profiles = gate["profiles"]
        if not isinstance(profiles, list) or not profiles or not set(profiles) <= {"quick", "release"}:
            raise ValueError("Perfiles de control inválidos")
        if "quick" in profiles and "release" not in profiles:
            raise ValueError("Release debe incluir todos los controles de quick")
    gates = [gate for gate in all_gates if profile in gate["profiles"]]
    if profile != "bootstrap" and not gates:
        raise ValueError("No hay controles de producto para el perfil")
    missing = [g["id"] for g in gates if g["command"] is None]
    if missing:
        raise ValueError("Controles de producto pendientes: " + ", ".join(missing))
    for gate in gates:
        cmd = gate["command"]
        if not isinstance(cmd, list) or not cmd or any(not isinstance(x, str) or not x for x in cmd):
            raise ValueError("Comando inválido: " + gate["id"])
    return gates


def execute(gates: List[Dict], root: Path, deadline: float, parallel: int) -> int:
    cancelled = Event()
    failed = False
    with tempfile.TemporaryDirectory(prefix="engineering-quality-") as temporary:
        pool = concurrent.futures.ThreadPoolExecutor(max_workers=parallel)

        def execute_one(gate):
            try:
                directory = Path(temporary) / gate["id"]
                directory.mkdir(mode=0o700)
                env = dict(os.environ, AIE_RUN_DIR=str(directory), PYTHONDONTWRITEBYTECODE="1")
                result = run(gate["command"], root, deadline - time.monotonic(), env, cancelled)
                return gate["id"], result.returncode, result.elapsed
            except (OSError, RuntimeError):
                return gate["id"], 127, 0.0

        try:
            futures = [pool.submit(execute_one, gate) for gate in gates]
            for future in concurrent.futures.as_completed(futures):
                name, code, elapsed = future.result()
                print("{} {} ({:.2f}s, exit={})".format("OK" if code == 0 else "FALLO", name, elapsed, code))
                failed = failed or code != 0
        except BaseException:
            cancelled.set()
            raise
        finally:
            pool.shutdown(wait=True)
    return 1 if failed else 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("profile", choices=["bootstrap", "quick", "release"])
    parser.add_argument("--history", action="store_true", help="Incluir historial Git disponible")
    parser.add_argument("--workspace", type=Path, default=ROOT, help="Árbol de trabajo; los controles se leen de la raíz confiable")
    args = parser.parse_args()
    start = time.monotonic()
    try:
        config = json.loads((ROOT / "policy/quality.json").read_text())
        workspace = args.workspace.resolve(strict=True)
        product = selected_gates(config, args.profile)
        deadline = start + config["budgets_seconds"][args.profile]
        scanner = [sys.executable, "-B", str(ROOT / "tools/scan_secrets.py"), "--root", str(workspace)]
        if args.history:
            scanner.append("--history")
        foundation = [
            {"id": "repository", "command": [sys.executable, "-B", str(ROOT / "tools/check_repository.py"), "--root", str(workspace)]},
            {"id": "secrets", "command": scanner},
            {"id": "tooling-tests", "command": [sys.executable, "-B", str(ROOT / "tools/run_tooling_tests.py")]},
        ]
        if execute(foundation, workspace, deadline, config["max_parallel"]):
            print("Bootstrap incompleto. Ejecutar el control fallido directamente para diagnosticarlo.")
            return 1
        if product and execute(product, workspace, deadline, config["max_parallel"]):
            print("Producto: controles fallidos; salida de herramientas omitida para evitar datos sensibles.")
            return 1
        print("{}: OK ({:.2f}s); alcance limitado al perfil ejecutado".format(args.profile, time.monotonic() - start))
        return 0
    except (ValueError, KeyError, TypeError, OSError) as error:
        print("BLOQUEADO: " + str(error))
        return 2
    except KeyboardInterrupt:
        print("Cancelado; procesos terminados y directorio temporal cerrado")
        return 130


if __name__ == "__main__":
    sys.exit(main())
