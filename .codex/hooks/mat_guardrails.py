#!/usr/bin/env python3
"""
Optional Codex PreToolUse / PostToolUse guardrails (MAT #75).

These hooks are not a security sandbox — see OpenAI Codex hooks documentation.
They flag obviously risky Bash or non-zero Bash exits when enabled.

Configuration (highest precedence first):
  1. Environment variable MAT_CODEX_GUARDRAILS_MODE = off | warn | enforce
  2. File .codex/guardrails.toml — [guardrails] mode = "off" | "warn" | "enforce"

Default when unset / missing file: off (exit 0, no stdout — no Codex overhead).

stdin/stdout: Codex command hook JSON. MAT-1 vs MAT-2: we do not block normal git
read-only commands; we target egregious host-wide destructive patterns only.
"""
from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path
from typing import Any

try:
    import tomllib
except ModuleNotFoundError:  # pragma: no cover - py3.10 only
    tomllib = None  # type: ignore[misc, assignment]


MODES = frozenset({"off", "warn", "enforce"})


def get_repo_root() -> Path:
    return Path(__file__).resolve().parent.parent.parent


def load_mode(repo_root: Path) -> str:
    env = os.environ.get("MAT_CODEX_GUARDRAILS_MODE", "").strip().lower()
    if env in MODES:
        return env
    cfg = repo_root / ".codex" / "guardrails.toml"
    if tomllib is not None and cfg.is_file():
        try:
            data = tomllib.loads(cfg.read_text(encoding="utf-8"))
            section = data.get("guardrails")
            if isinstance(section, dict):
                m = str(section.get("mode", "off")).strip().lower()
                if m in MODES:
                    return m
        except (OSError, ValueError, TypeError):
            pass
    return "off"


def _bash_command(data: dict[str, Any]) -> str:
    ti = data.get("tool_input")
    if isinstance(ti, dict):
        cmd = ti.get("command")
        if isinstance(cmd, str):
            return cmd
    return ""


def destructive_bash_reason(command: str) -> str | None:
    """Return a short reason if the command matches an obviously destructive pattern.

    Known limitations (by design — this is not a security sandbox):
    - Command substitution bypasses: rm -rf $(echo /)
    - Variable expansion: rm -rf $HOME/../../
    - Encoded/obfuscated commands
    """
    if not command.strip():
        return None
    c = command.strip()

    # rm targeting filesystem root: /, //, /./, /../ variants
    if re.search(
        r"(?is)\brm(?:\s+-[a-zA-Z0-9]+)*\s+(?:--\s+)?/+(?:\.\.?/)*\s*(?:$|[;&|'\"#\n])",
        c,
    ):
        return "rm targeting filesystem root (/)"
    if re.search(
        r"(?is)\brm(?:\s+-[a-zA-Z0-9]+)*\s+(?:--\s+)?/+(?:\.\.?/)*\*\s*(?:$|[;&|'\"#\n])",
        c,
    ):
        return "rm with root-level glob (/*)"

    if re.search(r"(?i)\bmkfs\b", c):
        return "disk formatting (mkfs)"
    if re.search(r"(?i)\bdd\b[^\n;|&]*\bof=/dev/", c):
        return "dd writing to a device under /dev/"
    # Fork bomb: classic :(){ :|:& };: and variants like f(){ f|f& };f
    # Use [:\w]+ to match both : and word chars as function names
    if re.search(r"([:\w]+)\(\)\s*\{\s*\1\s*\|\s*\1\s*&\s*\}\s*;\s*\1", c):
        return "fork bomb shell idiom"
    # chmod 777 on paths starting with / (system paths)
    if re.search(r"(?i)\bchmod\b[^\n;|&]*\b777\b[^\n;|&]*/(?:\w|(?:\s|$))", c):
        return "chmod 777 on system paths"
    if re.search(r"(?i)[\s;|&]>\s*/dev/sd[a-z]", c):
        return "redirect to raw block device"
    # Piping remote content into shell (curl/wget)
    if re.search(r"(?i)\b(?:curl|wget)\b[^\n|]*\|\s*(?:sudo\s+)?(?:ba)?sh\b", c):
        return "piping remote content into a shell"
    return None


def _bash_exit_code(data: dict[str, Any]) -> int | None:
    tr = data.get("tool_response")
    if isinstance(tr, dict):
        for key in ("exit_code", "exitCode"):
            if key in tr and tr[key] is not None:
                try:
                    return int(tr[key])
                except (TypeError, ValueError):
                    return None
        # Some payloads nest shell metadata
        meta = tr.get("metadata")
        if isinstance(meta, dict) and "exit_code" in meta:
            try:
                return int(meta["exit_code"])
            except (TypeError, ValueError):
                return None
    return None


def handle_pre_tool_use(data: dict[str, Any], mode: str) -> dict[str, Any] | None:
    if mode == "off":
        return None
    tool = data.get("tool_name")
    if tool != "Bash":
        return None
    cmd = _bash_command(data)
    reason = destructive_bash_reason(cmd)
    if not reason:
        return None
    if mode == "enforce":
        return {
            "hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "permissionDecision": "deny",
                "permissionDecisionReason": f"MAT guardrails (enforce): {reason}",
            }
        }
    # warn
    return {
        "systemMessage": f"MAT guardrails (warn): {reason}. Review before running.",
        "hookSpecificOutput": {"hookEventName": "PreToolUse"},
    }


def handle_post_tool_use(data: dict[str, Any], mode: str) -> dict[str, Any] | None:
    if mode not in ("warn", "enforce"):
        return None
    if data.get("tool_name") != "Bash":
        return None
    code = _bash_exit_code(data)
    if code is None or code == 0:
        return None
    msg = f"MAT guardrails: last Bash command exited with code {code}. Check output and side effects."
    return {
        "systemMessage": msg,
        "hookSpecificOutput": {
            "hookEventName": "PostToolUse",
            "additionalContext": msg,
        },
    }


def main() -> int:
    try:
        raw = sys.stdin.read()
        data = json.loads(raw) if raw.strip() else {}
    except json.JSONDecodeError:
        return 0

    if not isinstance(data, dict):
        return 0

    repo_root = get_repo_root()
    mode = load_mode(repo_root)
    if mode == "off":
        return 0

    event = data.get("hook_event_name")
    out: dict[str, Any] | None = None
    if event == "PreToolUse":
        out = handle_pre_tool_use(data, mode)
    elif event == "PostToolUse":
        out = handle_post_tool_use(data, mode)

    if out is not None:
        json.dump(out, sys.stdout)
        sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
