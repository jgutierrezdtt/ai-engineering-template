"""Install a compatible project adapter; never edit global policy or trust hooks."""

import argparse
import sys
from pathlib import Path

import check_agent_setup


ROOT = Path(__file__).resolve().parents[1]


def install(provider: str, root: Path = ROOT) -> int:
    if check_agent_setup.check(provider):
        print("Instalación bloqueada por incompatibilidad; no se escribe configuración")
        return 2
    source = root / "policy/adapters" / (provider + ".json")
    target = root / (".codex/hooks.json" if provider == "codex" else ".claude/settings.json")
    content = source.read_text(encoding="utf-8")
    if target.parent.is_symlink() or target.is_symlink() or (target.exists() and target.read_text(encoding="utf-8") != content):
        print("Existe otra configuración; conservarla y revisar la integración antes de cambiarla")
        return 2
    target.parent.mkdir(exist_ok=True)
    target.write_text(content, encoding="utf-8")
    print("Adaptador de proyecto instalado. Confianza y carga efectiva deben verificarse en la herramienta.")
    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("provider", choices=["codex", "claude"])
    args = parser.parse_args()
    try:
        sys.exit(install(args.provider))
    except Exception:
        print("No se pudo instalar el adaptador; no se acredita activación")
        sys.exit(2)
