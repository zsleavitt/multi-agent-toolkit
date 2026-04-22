"""Opt-in smoke checks for local MAT-16 + CLI toolchains (Codex, Gemini, Claude, …)."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import uuid
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from mat_runtime.adapters import ADAPTER_REGISTRY
from mat_runtime.config import AgentDefinition
from mat_runtime.router import AgentRouter, MAT2Request

# Instruction kept tiny to limit tokens; agents must not modify code for this to succeed.
SMOKE_INSTRUCTION = (
    "MAT runtime connectivity check only. "
    "Print exactly one line of stdout containing the text: SMOKE_OK"
)

# If set to "1", `smoke --real` also requires this env (optional belt-and-suspenders for CI scripts).
SMOKE_REAL_ENV = "MAT_SMOKE_REAL_CLI"

# Used when the agent has no `allowed_mat_ops` (orchestrator, researcher, …).
DEFAULT_SMOKE_OP = "smoke.ping"

# One canonical agent per CLI for `smoke --real --per-cli` (lightest / clearest for each tool).
_PREFERRED_AGENT_BY_CLI: dict[str, str] = {
    "codex": "coder",
    "codex-review": "reviewer",
    "gemini": "researcher",
    "claude": "orchestrator",
}

# Preference order for MAT ops (cheapest / least side-effect for smoke).
_OP_PREFERENCE: tuple[str, ...] = (
    "codex.review",
    "codex.diagnose",
    "codex.test",
    "codex.refactor",
    "codex.implement",
)


def _mise_broken_version_output(text: str) -> bool:
    t = (text or "").lower()
    if "mise" in t and "not currently active" in t:
        return True
    if "mise error" in t:
        return True
    if "no version is set for shim" in t:
        return True
    return False


def _preflight_executable_for_mat_cli(cli: str) -> str:
    """Resolve the process to preflight (e.g. Codex adapters run via `npx @openai/codex`)."""
    if cli in ("codex", "codex-review"):
        return "npx"
    return cli


def check_cli_on_path(cli: str) -> tuple[bool, str]:
    """
    Return (ok, detail) for whether the CLI is callable and self-identifies (e.g. --version).
    """
    path = shutil.which(cli)
    if not path:
        return False, f"not on PATH (which {cli!r} empty)"

    try:
        out = subprocess.run(
            [cli, "--version"],
            capture_output=True,
            text=True,
            timeout=20,
            stdin=subprocess.DEVNULL,
        )
    except (OSError, subprocess.TimeoutExpired) as e:
        return False, str(e)

    combined = (out.stdout or "") + (out.stderr or "")
    if _mise_broken_version_output(combined) or (out.returncode != 0 and "mise" in combined):
        return False, "shim on PATH but tool not active (mise) — " + combined.strip()[:200]

    if out.returncode != 0 and not combined.strip():
        return False, f"--version exit {out.returncode}"

    line1 = (out.stdout or out.stderr or "").splitlines()[:1]
    return True, (line1[0] if line1 else f"ok (exit {out.returncode})")[:200]


def pick_smoke_op(agent: AgentDefinition) -> str:
    """Select a MAT-2 op the agent is allowed to run; prefer read-only or review-style ops."""
    if agent.allowed_mat_ops:
        for op in _OP_PREFERENCE:
            if op in agent.allowed_mat_ops:
                return op
        return agent.allowed_mat_ops[0]
    return DEFAULT_SMOKE_OP


def _representative_agent_for_cli(agents: dict[str, AgentDefinition], cli: str) -> str | None:
    per_cli = {n: a for n, a in agents.items() if a.cli == cli}
    if not per_cli:
        return None
    pref = _PREFERRED_AGENT_BY_CLI.get(cli)
    if pref and pref in per_cli:
        return pref
    return sorted(per_cli.keys())[0]


def _unique_clis(agents: dict[str, AgentDefinition]) -> set[str]:
    clis: set[str] = set()
    for a in agents.values():
        if a.cli:
            clis.add(a.cli)
    return {c for c in clis if c in ADAPTER_REGISTRY}


@dataclass
class CLICheck:
    """One CLI binary preflight row."""

    cli: str
    ok: bool
    detail: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class InvokeCheck:
    """One MAT-2 invoke result."""

    agent: str
    op: str
    ok: bool
    error: str | None
    result_preview: str | None
    detail: str

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        if self.result_preview and len(self.result_preview) > 200:
            d["result_preview"] = self.result_preview[:200] + "…"
        return d


def run_dry_prelude(
    agents: dict[str, AgentDefinition],
) -> list[CLICheck]:
    """For each unique adapter-backed CLI, check PATH + --version."""
    rows: list[CLICheck] = []
    mat_clis = sorted(_unique_clis(agents))
    by_exe: dict[str, list[str]] = {}
    for cli in mat_clis:
        exe = _preflight_executable_for_mat_cli(cli)
        by_exe.setdefault(exe, []).append(cli)
    for exe in sorted(by_exe.keys()):
        ok, detail = check_cli_on_path(exe)
        mat_names = ", ".join(sorted(by_exe[exe]))
        label = exe if mat_names == exe else f"{exe} (mat: {mat_names})"
        rows.append(CLICheck(cli=label, ok=ok, detail=detail))
    return rows


def _emit_table_dry(rows: list[CLICheck], as_json: bool) -> None:
    if as_json:
        print(json.dumps([r.to_dict() for r in rows], indent=2))
        return
    for r in rows:
        state = "ok  " if r.ok else "FAIL"
        print(f"  [{state}] {r.cli:8s}  {r.detail}")


def _require_real_env() -> str | None:
    """If SMOKE_REAL_ENV is set to '0' or 'false', block real invocations."""
    v = (os.environ.get(SMOKE_REAL_ENV) or "").strip().lower()
    if v in ("0", "false", "no", "off"):
        return f"{SMOKE_REAL_ENV} is disabled — real smoke invocations are not allowed"
    return None


def _invoke_one(
    router: AgentRouter,
    repo_root: Path,
    agent: str,
    op: str,
    instruction: str,
    timeout_ms: int,
) -> InvokeCheck:
    req = MAT2Request(
        schema_version="1.2.0",
        correlation_id=str(uuid.uuid4()),
        idempotency_key=str(uuid.uuid4()),
        op=op,
        repo_root=str(repo_root),
        instruction=instruction,
        timeout_ms=timeout_ms,
    )
    res = router.invoke(agent, req)
    preview = None
    if res.ok and res.result:
        preview = json.dumps(res.result)[:500]
    err_msg = None
    if not res.ok and res.error:
        err_msg = res.error.get("message", str(res.error))
    det = f"op={op} ok={res.ok}"
    if err_msg:
        det += f" err={err_msg!r}"
    return InvokeCheck(
        agent=agent,
        op=op,
        ok=res.ok,
        error=err_msg,
        result_preview=preview,
        detail=det,
    )


def run_real_invocations(
    router: AgentRouter,
    repo_root: Path,
    *,
    agents: list[str],
    instruction: str,
    timeout_ms: int,
) -> list[InvokeCheck]:
    out: list[InvokeCheck] = []
    for name in agents:
        adef = router.agents.get(name)
        if not adef:
            out.append(
                InvokeCheck(
                    agent=name,
                    op="",
                    ok=False,
                    error="agent_not_found",
                    result_preview=None,
                    detail=f"unknown agent {name!r}",
                )
            )
            continue
        op = pick_smoke_op(adef)
        out.append(
            _invoke_one(router, repo_root, name, op, instruction, timeout_ms)
        )
    return out


def run_real_per_cli(
    router: AgentRouter,
    repo_root: Path,
    *,
    instruction: str,
    timeout_ms: int,
) -> list[InvokeCheck]:
    """One MAT-2 invoke per unique CLI (representative agent per tool)."""
    out: list[InvokeCheck] = []
    for cli in sorted(_unique_clis(router.agents)):
        rep = _representative_agent_for_cli(router.agents, cli)
        if not rep:
            continue
        adef = router.agents[rep]
        op = pick_smoke_op(adef)
        out.append(_invoke_one(router, repo_root, rep, op, instruction, timeout_ms))
    return out


def _emit_table_real(rows: list[InvokeCheck], as_json: bool) -> None:
    if as_json:
        print(json.dumps([r.to_dict() for r in rows], indent=2))
        return
    for r in rows:
        st = "ok  " if r.ok else "FAIL"
        print(f"  [{st}] {r.agent:16s}  {r.detail}")


def run_smoke(
    repo_root: Path,
    *,
    real: bool,
    per_cli: bool,
    agent: str | None,
    instruction: str,
    timeout_ms: int,
    strict: bool,
    as_json: bool,
) -> int:
    """
    Top-level entry for the `smoke` CLI.

    Returns process exit code (0 = success).
    """
    root = repo_root.resolve()
    router = AgentRouter(repo_root=root)

    if not router.agents:
        print("No agent definitions under agents/ — check repo_root and agents/*.md", file=sys.stderr)
        return 1

    block = _require_real_env()
    if real and block:
        print(block, file=sys.stderr)
        return 1

    if real and (os.environ.get(SMOKE_REAL_ENV) or "").strip() != "1":
        print(
            f"Refusing --real without {SMOKE_REAL_ENV}=1 (confirms billable/CLI usage you intend).",
            file=sys.stderr,
        )
        return 1

    if not real:
        rows = run_dry_prelude(router.agents)
        if not as_json and rows:
            print("CLI preflight (PATH + --version) for adapter-backed tools in agents/:\n")
        elif not as_json and not rows:
            print("No adapter-backed clis in agents/ — nothing to preflight.\n")
        if rows:
            _emit_table_dry(rows, as_json)
        if strict:
            bad = [r for r in rows if not r.ok]
            if bad:
                if not as_json:
                    print(
                        f"\n{len(bad)} tool(s) failed preflight. Fix PATH/mise, or run without --strict.",
                        file=sys.stderr,
                    )
                return 1
        if not as_json and rows:
            print(
                f"\nDry run only. For live agent calls: `MAT_SMOKE_REAL_CLI=1 "
                f"python -m mat_runtime smoke --real` (see docs/adr/0005-smoke-cli-verification.md).",
            )
        return 0

    # Real
    if per_cli:
        who = "one representative agent per CLI"
        res = run_real_per_cli(
            router, root, instruction=instruction, timeout_ms=timeout_ms
        )
    else:
        if agent is None:
            print("Error: --real requires --agent NAME or use --per-cli", file=sys.stderr)
            return 1
        who = f"agent {agent!r}"
        res = run_real_invocations(
            router,
            root,
            agents=[agent],
            instruction=instruction,
            timeout_ms=timeout_ms,
        )

    if not as_json:
        print(
            f"Real MAT-2 invocations ({who}), timeout_ms={timeout_ms}:\n"
        )
    _emit_table_real(res, as_json)
    if any(not r.ok for r in res):
        if not as_json:
            print("\nOne or more invocations failed.", file=sys.stderr)
        return 1
    if not as_json:
        print(
            f"\nAll invocations returned ok. If stdout did not follow instructions, check adapter flags "
            f"and that {SMOKE_REAL_ENV}=1 is only used when you expect billable/usage from CLIs."
        )
    return 0
