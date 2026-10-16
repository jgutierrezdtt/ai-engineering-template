"""Generate Claude skill mirrors from one canonical source without overwriting extras."""

import argparse
import sys
from pathlib import Path

from check_repository import SKILLS


ROOT = Path(__file__).resolve().parents[1]


def sync(root=ROOT, check=False):
    destination = root / ".claude/skills"
    plans = []
    # Validate every input and output before the first write.
    for name in sorted(SKILLS):
        source = root / ".agents/skills" / name / "SKILL.md"
        target = destination / name / "SKILL.md"
        for path in (source, target):
            if any(part.is_symlink() for part in (path, *path.parents)):
                raise ValueError("Symlink in skill location")
        content = source.read_bytes()
        extras = list(target.parent.iterdir()) if target.parent.is_dir() else []
        if any(path.name != "SKILL.md" for path in extras):
            raise ValueError("Mirror contains manually maintained resources")
        plans.append((target, content))
    mismatches = [target for target, content in plans if not target.is_file() or target.read_bytes() != content]
    if check:
        return not mismatches
    for target, content in plans:
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(content)
    return True


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    try:
        valid = sync(check=args.check)
        print("Skills compartidas: " + ("OK" if valid else "copias pendientes de sincronizar"))
        sys.exit(0 if valid else 2)
    except Exception:
        print("Sincronización rechazada; revisar fuentes y copias antes de continuar")
        sys.exit(2)
