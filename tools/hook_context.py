"""Materialize bounded, canonical engineering instructions for both adapters."""

import hashlib
import json
from pathlib import Path
from typing import Tuple

from check_repository import SKILLS


def context(root: Path) -> Tuple[str, str]:
    policy = json.loads((root / "policy/agent-enforcement.json").read_text())
    if policy.get("schema_version") != 1:
        raise ValueError("Política de hooks no soportada")
    limit = policy["context_max_bytes"]
    if not isinstance(limit, int) or isinstance(limit, bool) or not 1024 <= limit <= 65536:
        raise ValueError("Límite de contexto inválido")
    files = [root / "AGENTS.md"]
    files.extend(root / ".agents/skills" / name / "SKILL.md" for name in sorted(SKILLS))
    digest = hashlib.sha256()
    sections = []
    size = 0
    for file in files:
        if file.is_symlink() or not file.resolve().is_relative_to(root.resolve()):
            raise ValueError("Origen de instrucciones fuera del proyecto")
        content = file.read_bytes()
        size += len(content)
        if size > limit:
            raise ValueError("Contexto excede el límite: no se entrega truncado")
        name = file.relative_to(root).as_posix()
        digest.update(name.encode() + b"\0" + content + b"\0")
        sections.append("\n## Fuente: " + name + "\n\n" + content.decode("utf-8"))
    fingerprint = digest.hexdigest()
    header = (
        "AI Engineering: instrucciones de ingeniería cargadas por el hook. Ocho skills completas.\n"
        "SHA-256 del conjunto: " + fingerprint + "\n"
        "La carga prueba disponibilidad en contexto, no atención ni obediencia del modelo.\n"
        "Aplicar las reglas pertinentes. Las restricciones de permisos se deciden fuera del modelo.\n"
    )
    result = header + "".join(sections)
    if len(result.encode("utf-8")) > limit:
        raise ValueError("Salida de contexto excede el límite")
    return result, fingerprint
