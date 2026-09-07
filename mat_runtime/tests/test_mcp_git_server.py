"""Tests for the MAT-1 MCP git server (MAT-101)."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from mat_runtime.mcp_git_server import (
    MatGitExecutor,
    build_git_argv,
    create_mcp_server,
    default_manifest_path,
    load_allowed_operations,
    op_to_tool_name,
    tool_name_to_op,
)


@pytest.fixture
def manifest_path() -> Path:
    return default_manifest_path()


@pytest.fixture
def executor(manifest_path: Path) -> MatGitExecutor:
    return MatGitExecutor.from_manifest(manifest_path)


def test_load_allowed_operations_from_manifest(manifest_path: Path) -> None:
    ops = load_allowed_operations(manifest_path)
    assert "git.status" in ops
    assert "git.commit" in ops
    assert "git.add" in ops
    assert "shell.exec" not in ops
    # All ops must have exactly one dot for the tool-name roundtrip to be correct.
    for op in ops:
        assert op.count(".") == 1, f"unexpected multi-dot op: {op!r}"


def test_load_allowed_operations_rejects_multi_dot_op(tmp_path: Path, manifest_path: Path) -> None:
    import pytest

    data = json.loads(manifest_path.read_text(encoding="utf-8"))
    bad = {**data, "allowed_operations": ["git.status", "git.op.sub"]}
    bad_path = tmp_path / "manifest.json"
    bad_path.write_text(json.dumps(bad), encoding="utf-8")
    with pytest.raises(ValueError, match="exactly one dot"):
        load_allowed_operations(bad_path)


def test_op_tool_name_roundtrip() -> None:
    assert op_to_tool_name("git.commit") == "git_commit"
    assert tool_name_to_op("git_commit") == "git.commit"
    assert tool_name_to_op("git_checkout_new_branch") == "git.checkout_new_branch"


def test_build_git_argv_rejects_dash_remote() -> None:
    import pytest

    with pytest.raises(ValueError, match="must not start with '-'"):
        build_git_argv("git.push", {"remote": "--upload-pack=/evil"})
    with pytest.raises(ValueError, match="must not start with '-'"):
        build_git_argv("git.pull", {"remote": "-evil"})
    with pytest.raises(ValueError, match="must not start with '-'"):
        build_git_argv("git.fetch", {"remote": "--evil"})
    with pytest.raises(ValueError, match="must not start with '-'"):
        build_git_argv("git.push", {"remote": "origin", "refspec": "--evil"})


def test_build_git_argv_rejects_dash_branch_and_path() -> None:
    import pytest

    with pytest.raises(ValueError, match="must not start with '-'"):
        build_git_argv("git.checkout_new_branch", {"branch": "--upload-pack=/evil"})
    with pytest.raises(ValueError, match="must not start with '-'"):
        build_git_argv(
            "git.checkout_new_branch",
            {"branch": "feature", "start_point": "--evil"},
        )
    with pytest.raises(ValueError, match="must not start with '-'"):
        build_git_argv("git.checkout_existing", {"branch": "-evil"})
    with pytest.raises(ValueError, match="must not start with '-'"):
        build_git_argv(
            "git.worktree_add", {"path": "-evil", "branch": "feature"}
        )
    with pytest.raises(ValueError, match="must not start with '-'"):
        build_git_argv(
            "git.worktree_add", {"path": "wt", "branch": "--evil"}
        )
    with pytest.raises(ValueError, match="must not start with '-'"):
        build_git_argv(
            "git.worktree_add",
            {"path": "wt", "branch": "feature", "base_ref": "--evil"},
        )
    with pytest.raises(ValueError, match="must not start with '-'"):
        build_git_argv("git.worktree_remove", {"path": "--evil"})


def test_build_git_argv_common_ops() -> None:
    assert build_git_argv("git.status", {}) == [
        "git",
        "status",
        "--porcelain=v1",
        "-b",
    ]
    assert build_git_argv("git.add", {"all": True}) == ["git", "add", "-A"]
    assert build_git_argv("git.add", {"pathspecs": ["a.py"]}) == [
        "git",
        "add",
        "--",
        "a.py",
    ]
    assert build_git_argv("git.commit", {"message": "msg"}) == [
        "git",
        "commit",
        "-m",
        "msg",
    ]
    assert build_git_argv("git.diff", {"cached": True}) == [
        "git",
        "diff",
        "--cached",
    ]


def test_allowlisted_op_executes_and_returns_stdout(
    executor: MatGitExecutor, tmp_path: Path
) -> None:
    fake = MagicMock(
        return_value=MagicMock(
            ok=True,
            stdout="## main\n",
            stderr="",
            return_code=0,
            argv=["git", "status", "--porcelain=v1", "-b"],
            timeout_exceeded=False,
        )
    )
    executor._runner = fake

    result = executor.call_tool(
        "git_status",
        {"repo_root": str(tmp_path), "params": {}},
    )

    assert result["ok"] is True
    assert result["stdout"] == "## main\n"
    assert "error" not in result
    fake.assert_called_once()
    args, kwargs = fake.call_args
    assert args[0] == tmp_path.resolve()
    assert args[1][0] == "git"
    assert "shell" not in kwargs


def test_non_allowlisted_op_returns_structured_error(
    executor: MatGitExecutor, tmp_path: Path
) -> None:
    fake = MagicMock()
    executor._runner = fake

    result = executor.call_tool(
        "git_rebase",
        {"repo_root": str(tmp_path), "params": {}},
    )

    assert result == {
        "ok": False,
        "error": "op_not_allowed",
        "op": "git.rebase",
        "tool": "git_rebase",
    }
    fake.assert_not_called()


def test_unknown_tool_name_never_shell_executes(
    executor: MatGitExecutor, tmp_path: Path
) -> None:
    fake = MagicMock()
    executor._runner = fake
    result = executor.call_tool("rm_rf", {"repo_root": str(tmp_path)})
    assert result["ok"] is False
    assert result["error"] == "op_not_allowed"
    fake.assert_not_called()


def test_manifest_reload(tmp_path: Path, manifest_path: Path) -> None:
    data = json.loads(manifest_path.read_text(encoding="utf-8"))
    slim = {
        **data,
        "allowed_operations": ["git.status", "git.diff"],
    }
    custom = tmp_path / "manifest.json"
    custom.write_text(json.dumps(slim), encoding="utf-8")

    exec_ = MatGitExecutor.from_manifest(custom)
    assert exec_.allowed_operations == frozenset({"git.status", "git.diff"})

    slim["allowed_operations"] = ["git.status"]
    custom.write_text(json.dumps(slim), encoding="utf-8")
    reloaded = exec_.reload_manifest()
    assert reloaded == frozenset({"git.status"})
    assert "git_diff" not in exec_.tool_names()


def test_create_mcp_server_registers_manifest_tools(
    manifest_path: Path,
) -> None:
    pytest.importorskip("mcp")
    import asyncio

    server = create_mcp_server(manifest_path)
    tools = asyncio.run(server.list_tools())
    names = {t.name for t in tools}
    allowed = load_allowed_operations(manifest_path)
    assert names == {op_to_tool_name(op) for op in allowed}
    assert "git_commit" in names
    assert "git_rebase" not in names


def test_mcp_call_tool_allowlisted(
    manifest_path: Path, tmp_path: Path
) -> None:
    pytest.importorskip("mcp")
    import asyncio

    server = create_mcp_server(manifest_path)
    exec_: MatGitExecutor = server.mat_git_executor
    exec_._runner = MagicMock(
        return_value=MagicMock(
            ok=True,
            stdout="diff --git a/x\n",
            stderr="",
            return_code=0,
            argv=["git", "diff"],
            timeout_exceeded=False,
        )
    )

    result = asyncio.run(
        server.call_tool(
            "git_diff",
            {"repo_root": str(tmp_path), "params": {}},
        )
    )
    # FastMCP may return (content_blocks, structured) or a plain dict.
    structured = result[1] if isinstance(result, tuple) else result
    assert isinstance(structured, dict)
    assert structured["ok"] is True
    assert "diff --git" in structured["stdout"]
