"""Shared hook protocol for Codex/Claude; supported denials are explicit JSON."""

import json
import os
import sys
from pathlib import Path
from typing import Dict

from hook_context import context
from processes import run
from tool_policy import ToolPolicy
from verify_change import required_profile


ROOT = Path(__file__).resolve().parents[1]


def deny(reason: str) -> Dict:
    return {"hookSpecificOutput": {"hookEventName": "PreToolUse",
                                  "permissionDecision": "deny",
                                  "permissionDecisionReason": reason}}


def failure(event: str, active: bool = False) -> Dict:
    reason = "AI Engineering: control incompleto o fallido; no se acredita una entrega válida."
    if event == "PreToolUse":
        return deny(reason)
    if event == "Stop" and not active:
        return {"decision": "block", "reason": reason + " Corregir el fallo sin desactivar controles."}
    return {"continue": False, "stopReason": reason}


def handle(payload: Dict, root: Path = ROOT) -> Dict:
    event = payload.get("hook_event_name", "PreToolUse")
    try:
        cwd = Path(payload["cwd"]).resolve()
        cwd.relative_to(root.resolve())
        if event in {"SessionStart", "UserPromptSubmit", "SubagentStart"}:
            instructions, _ = context(root)
            return {"hookSpecificOutput": {"hookEventName": event, "additionalContext": instructions}}
        if event == "PreToolUse":
            context(root)  # Missing or oversized policies cannot silently disappear.
            reason = ToolPolicy(root).denial(payload)
            return deny(reason) if reason else {}
        if event == "Stop":
            # Product present => product checks. Never downgrade to bootstrap.
            profile = required_profile(root)
            env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1")
            result = run([sys.executable, "-B", str(root / "tools/verify_change.py")],
                         root, 125, env=env)
            if result.returncode:
                return failure(event, payload.get("stop_hook_active") is True)
            return {"systemMessage": "AI Engineering: validación " + profile + " comprobada; no autoriza publicación."}
        return failure(event)
    except Exception:
        return failure(event, payload.get("stop_hook_active") is True)


def main() -> int:
    try:
        raw = sys.stdin.buffer.read(262145)
        if len(raw) > 262144:
            raise ValueError("Entrada demasiado grande")
        payload = json.loads(raw)
        if not isinstance(payload, dict):
            raise ValueError("Se requiere un objeto")
        result = handle(payload)
    except Exception:
        result = deny("AI Engineering: entrada de hook inválida; se rechaza la operación.")
    print(json.dumps(result, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
