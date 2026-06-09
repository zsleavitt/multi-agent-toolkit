# mat_runtime/tests/test_adapters.py
"""Command-line shape checks for MAT CLI adapters (no subprocess to real CLIs)."""

from __future__ import annotations

from mat_runtime.adapters import (
    ClaudeAdapter,
    CodexAdapter,
    CodexReviewAdapter,
    GeminiAdapter,
    get_adapter,
)


def test_codex_adapter_invokes_codex_exec() -> None:
    a = CodexAdapter()
    cmd = a.build_command("do the thing", system_prompt="sys")
    assert cmd[0] == "codex"
    assert cmd[:3] == ["codex", "exec", "--full-auto"]
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


def test_claude_adapter_forwards_model_hint() -> None:
    cmd = ClaudeAdapter().build_command("task", model="sonnet")
    assert "--model" in cmd
    assert cmd[cmd.index("--model") + 1] == "sonnet"


def test_codex_adapter_forwards_model_hint() -> None:
    cmd = CodexAdapter().build_command("task", model="gpt-4.1")
    assert cmd[:3] == ["codex", "exec", "--full-auto"]
    assert "--model" in cmd
    assert cmd[cmd.index("--model") + 1] == "gpt-4.1"


def test_codex_review_adapter_forwards_model_hint_via_config() -> None:
    cmd = CodexReviewAdapter().build_command("review this", model="gpt-4.1")
    assert cmd[:6] == [
        "npx",
        "--yes",
        "--package=@openai/codex",
        "--",
        "codex",
        "review",
    ]
    assert cmd[-3:-1] == ["-c", 'model="gpt-4.1"']
    assert cmd[-1] == "-"


def test_gemini_adapter_forwards_model_hint() -> None:
    cmd = GeminiAdapter().build_command("task", model="gemini-2.0-flash")
    assert "--model" in cmd
    assert cmd[cmd.index("--model") + 1] == "gemini-2.0-flash"


def test_get_adapter_drops_empty_flags_to_keep_defaults() -> None:
    """
    AgentRouter passes `flags=[]` from provider config for worker agents.
    That must not replace adapter class defaults, or argv degenerates and `npx` fails (ETARGET).
    """
    a = get_adapter("codex-review", flags=[], working_dir=".")
    assert a.flags
    assert a.build_command("x")[-1] == "-"
