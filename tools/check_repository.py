"""Check structural policies without installing a parser or fetching the network."""

import json
import argparse
import os
import re
import sys
from pathlib import Path
from typing import List
from urllib.parse import unquote, urlsplit


ROOT = Path(__file__).resolve().parents[1]
SKILLS = {
    "engineering-delivery", "engineering-architecture", "engineering-agent-safety", "engineering-security",
    "engineering-quality", "engineering-devops", "engineering-product-design", "engineering-compliance",
}
SKIP = {".git", ".artifacts", "node_modules", ".venv", "__pycache__", ".cache", "dist", "build"}


def sensitive_path(path: str) -> bool:
    name = Path(path).name.lower()
    return (
        (name == ".env" or name.startswith(".env.")) and name != ".env.example"
        or name.endswith((".pem", ".key", ".p12", ".pfx", ".jks", ".keystore", ".tfplan"))
        or ".tfstate" in name or name == "credentials.json"
        or (name.startswith("service-account") and name.endswith(".json"))
    )


def workflow_errors(text: str) -> List[str]:
    errors = []
    for target in re.findall(r"^\s*(?:-\s*)?uses:\s*([^\s#]+)", text, re.MULTILINE):
        if not target.startswith("./") and not re.fullmatch(r"[^@]+@[0-9a-f]{40}", target):
            errors.append("Acción externa sin SHA completo")
    if re.search(r"^\s*pull_request_target\s*:", text, re.MULTILINE):
        errors.append("Evento privilegiado requiere diseño de seguridad específico")
    return errors


def broken_links(path: Path, root: Path) -> List[str]:
    errors = []
    for raw in re.findall(r"\[[^\]]*\]\(([^\s)]+)\)", path.read_text(encoding="utf-8")):
        raw = raw.strip("<>")
        parsed = urlsplit(raw)
        if parsed.scheme or raw.startswith("#"):
            continue
        target = (path.parent / unquote(parsed.path)).resolve()
        try:
            target.relative_to(root.resolve())
        except ValueError:
            errors.append("Referencia local fuera del proyecto")
            continue
        if not target.exists():
            errors.append("Referencia local inexistente: " + raw)
    return errors


def skill_errors(path: Path) -> List[str]:
    content = path.read_text(encoding="utf-8")
    match = re.match(r"\A---\nname: ([a-z0-9-]+)\ndescription: ([^\n]+)\n---\n", content)
    if not match or match.group(1) != path.parent.name:
        return ["Manifest de skill inválido o nombre discordante"]
    if len(match.group(2)) > 1024 or len(match.group(2)) < 20:
        return ["Descripción de skill fuera de rango"]
    return []


def check(root: Path = ROOT) -> List[str]:
    errors = []
    actual = {p.parent.name for p in (root / ".agents/skills").glob("*/SKILL.md")}
    if actual != SKILLS:
        errors.append("Inventario de skills distinto al acordado; revisar rutas e instrucciones")
    required = ["AGENTS.md", "README.md", ".gitleaks.toml", "policy/quality.json",
                ".githooks/pre-commit", ".github/workflows/foundation.yml",
                "tools/run_tooling_tests.py", "policy/agent-enforcement.json",
                "policy/adapters/codex.json", "policy/adapters/claude.json", "LICENSE"]
    for name in required:
        if not (root / name).is_file():
            errors.append("Falta archivo requerido: " + name)
    paths = []
    for directory, folders, files in os.walk(root, followlinks=False):
        folders[:] = [name for name in folders if name not in SKIP]
        paths.extend(Path(directory) / name for name in files)
        paths.extend(Path(directory) / name for name in folders if (Path(directory) / name).is_symlink())
    for path in paths:
        relative = path.relative_to(root)
        if path.is_symlink():
            errors.append(str(relative) + ": enlace simbólico requiere revisión explícita")
            continue
        if not path.is_file():
            continue
        if sensitive_path(str(relative)):
            errors.append(str(relative) + ": nombre sensible en el árbol")
        if path.suffix == ".md":
            errors.extend(str(relative) + ": " + e for e in broken_links(path, root))
        if path.name == "SKILL.md":
            errors.extend(str(relative) + ": " + e for e in skill_errors(path))
        if relative.parts[:2] == (".github", "workflows") and path.suffix in {".yml", ".yaml"}:
            errors.extend(str(relative) + ": " + e for e in workflow_errors(path.read_text()))
    policy = root / "policy/quality.json"
    if policy.exists():
        try:
            config = json.loads(policy.read_text())
            if config["schema_version"] != 1:
                errors.append("Versión de política no soportada")
            ids = [gate["id"] for gate in config["gates"]]
            if len(ids) != len(set(ids)):
                errors.append("IDs de controles duplicados")
        except (ValueError, KeyError, TypeError):
            errors.append("Política JSON inválida")
    for provider, target in (("codex", ".codex/hooks.json"), ("claude", ".claude/settings.json")):
        active = root / target
        source = root / "policy/adapters" / (provider + ".json")
        if active.exists() and source.exists() and active.read_text() != source.read_text():
            errors.append("Adaptador instalado distinto de la fuente revisable: " + target)
    for name in SKILLS:
        canonical = root / ".agents/skills" / name / "SKILL.md"
        mirror = root / ".claude/skills" / name / "SKILL.md"
        if not mirror.is_file() or mirror.is_symlink() or mirror.read_bytes() != canonical.read_bytes():
            errors.append("Skill de Claude ausente o distinta de su fuente: " + name)
    return errors


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=ROOT)
    args = parser.parse_args()
    errors = check(args.root.resolve(strict=True))
    for error in errors:
        print(error)
    print("Integridad: " + ("FALLO" if errors else "OK"))
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
