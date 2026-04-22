# mat_runtime/tests/test_adapters.py
"""Command-line shape checks for MAT CLI adapters (no subprocess to real CLIs)."""

from __future__ import annotations

from mat_runtime.adapters import CodexAdapter, CodexReviewAdapter, get_adapter


def test_codex_adapter_invokes_npx_exec() -> None:
    a = CodexAdapter()
    cmd = a.build_command("do the thing", system_prompt="sys")
    assert cmd[0] == "npx"
    assert cmd[:5] == ["npx", "--yes", "@openai/codex", "exec", "--full-auto"]
    assert "do the thing" in cmd[-1]
    assert "sys" in cmd[-1]


def test_codex_review_adapter_invokes_npx_review_stdin() -> None:
    a = CodexReviewAdapter()
    cmd = a.build_command("review this", system_prompt="sys")
    assert cmd == [
        "npx",
        "--yes",
        "--package=@openai/codex",
        "--",
        "codex",
        "review",
        "-",
    ]


def test_get_adapter_drops_empty_flags_to_keep_defaults() -> None:
    """
    AgentRouter passes `flags=[]` from provider config for worker agents.
    That must not replace adapter class defaults, or argv degenerates and `npx` fails (ETARGET).
    """
    a = get_adapter("codex-review", flags=[], working_dir=".")
    assert a.flags
    assert a.build_command("x")[-1] == "-"
