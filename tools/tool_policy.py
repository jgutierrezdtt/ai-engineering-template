"""Conservative decisions for supported hook calls; never grant native permissions."""

import json
import re
import shlex
from pathlib import Path
from typing import Dict, Optional

from check_repository import sensitive_path


class ToolPolicy:
    def __init__(self, root: Path):
        self.root = root.resolve()
        self.config = json.loads((root / "policy/agent-enforcement.json").read_text())
        if self.config.get("schema_version") != 1:
            raise ValueError("Versión de política inválida")
        self.editable_roots = self.config["editable_roots"]
        self.editable_files = self.config["editable_files"]

    def path(self, raw: str, cwd: Path, writing: bool = False) -> Path:
        if not isinstance(raw, str) or not raw or len(raw) > 4096 or "\0" in raw:
            raise ValueError("Ruta inválida")
        candidate = Path(raw) if Path(raw).is_absolute() else cwd / raw
        # Reject symlinks even if their destination happens to be in this checkout.
        for part in [candidate] + list(candidate.parents):
            if part.is_symlink():
                raise ValueError("Enlaces simbólicos no autorizados")
            if part == self.root:
                break
        normalized = candidate.resolve()
        relative = normalized.relative_to(self.root)
        if ".git" in relative.parts or any(sensitive_path(p) for p in relative.parts):
            raise ValueError("Acceso a credenciales o metadatos Git denegado")
        if writing:
            name = relative.as_posix()
            inside = any(name.startswith(prefix + "/") for prefix in self.editable_roots)
            if name not in self.editable_files and not inside:
                raise ValueError("Ruta de control o ruta fuera de las áreas editables")
        return normalized

    def shell(self, command: str, cwd: Path) -> None:
        if not isinstance(command, str) or not command or len(command) > 16384:
            raise ValueError("Comando inválido")
        # This is an allowlist, not a blacklist of dangerous command names.
        if any(character in command for character in "\n\r;&|<>$`\\"):
            raise ValueError("Composición de shell no autorizada")
        if command in self.config["read_commands"]:
            return
        if command in self.config["validation_commands"]:
            if cwd != self.root:
                raise ValueError("La validación solo se ejecuta desde la raíz")
            return
        args = shlex.split(command)
        if len(args) >= 3 and args[:2] == ["/bin/cat", "--"]:
            if len(args) > 10:
                raise ValueError("Demasiados archivos en una lectura")
            for argument in args[2:]:
                path = self.path(argument, cwd)
                if not path.is_file():
                    raise ValueError("La lectura requiere un archivo existente")
            return
        raise ValueError("Comando fuera de la lista autorizada; proponer capacidad concreta al responsable")

    def patch(self, command: str, cwd: Path) -> None:
        if not isinstance(command, str) or not command.startswith("*** Begin Patch\n"):
            raise ValueError("Patch inválido")
        if not command.rstrip().endswith("*** End Patch"):
            raise ValueError("Patch incompleto")
        paths = re.findall(r"^\*\*\* (?:Add File|Update File|Delete File|Move to): (.+)$", command, re.MULTILINE)
        if not paths:
            raise ValueError("Patch sin rutas verificables")
        for path in paths:
            self.path(path, cwd, writing=True)

    def denial(self, payload: Dict) -> Optional[str]:
        try:
            cwd = Path(payload["cwd"]).resolve()
            cwd.relative_to(self.root)
            args = payload["tool_input"]
            if not isinstance(args, dict):
                raise ValueError("Entrada de herramienta inválida")
            effective = args.get("workdir", args.get("cwd", str(cwd)))
            cwd = self.path(effective, cwd)
            name = payload["tool_name"]
            if name == "Bash":
                self.shell(args.get("command"), cwd)
            elif name == "apply_patch" or (name in {"Edit", "Write"} and "command" in args):
                self.patch(args.get("command"), cwd)
            elif name in {"Read", "Write", "Edit"}:
                self.path(args.get("file_path"), cwd, writing=name != "Read")
            elif name == "MultiEdit":
                self.path(args.get("file_path"), cwd, writing=True)
            else:
                raise ValueError("Herramienta no autorizada en el perfil restrictivo")
        except (ValueError, TypeError, KeyError, OSError):
            # Do not echo user-controlled paths, commands, prompts or credentials.
            return "AI Engineering bloquea esta operación: herramienta, comando o ruta fuera de la política."
        return None
