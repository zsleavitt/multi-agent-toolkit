"""MAT-1 git executor exposed as an MCP server (MAT-101).

Reads ``schemas/gemini-git-ops/v1/manifest.json`` at startup and exposes each
allowlisted MAT-1 ``op`` as an MCP tool. The manifest is the permission
boundary: unknown tools never reach ``subprocess``.

MAT-1 remains the source of truth for the allowlist. MCP tool names are the
dotted ops with ``.`` replaced by ``_`` (e.g. ``git.commit`` → ``git_commit``).
See ``docs/integrations/mcp-git-server.md``.
"""

from __future__ import annotations

import json
import os
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

DEFAULT_TIMEOUT_MS = 60_000
DEFAULT_MANIFEST_RELATIVE = Path("schemas/gemini-git-ops/v1/manifest.json")


def default_manifest_path(repo_root: Path | None = None) -> Path:
    """Resolve the MAT-1 manifest path (env override or repo-relative default)."""
    env = os.environ.get("MAT_GEMINI_GIT_OPS_V1")
    if env:
        return Path(env).expanduser().resolve() / "manifest.json"
    root = repo_root or Path(__file__).resolve().parents[1]
    return (root / DEFAULT_MANIFEST_RELATIVE).resolve()


def op_to_tool_name(op: str) -> str:
    """Map MAT-1 op (``git.commit``) to MCP tool name (``git_commit``)."""
    return op.replace(".", "_")


def tool_name_to_op(tool_name: str) -> str:
    """Map MCP tool name back to MAT-1 op (first underscore → dot)."""
    if "_" not in tool_name:
        return tool_name
    prefix, rest = tool_name.split("_", 1)
    return f"{prefix}.{rest}"


def load_allowed_operations(manifest_path: Path | None = None) -> frozenset[str]:
    """Load ``allowed_operations`` from the MAT-1 manifest (deny-by-default source)."""
    path = manifest_path or default_manifest_path()
    data = json.loads(path.read_text(encoding="utf-8"))
    ops = data.get("allowed_operations")
    if not isinstance(ops, list) or not all(isinstance(o, str) for o in ops):
        raise ValueError(f"manifest missing allowed_operations list: {path}")
    # Invariant required for op_to_tool_name / tool_name_to_op roundtrip.
    for op in ops:
        if op.count(".") != 1:
            raise ValueError(
                f"MAT-1 op must have exactly one dot for MCP tool name roundtrip: {op!r}"
            )
    return frozenset(ops)


def expand_repo_root(repo_root: str) -> Path:
    """Expand ``~`` / ``~user`` and require an existing directory."""
    if not repo_root or not isinstance(repo_root, str):
        raise ValueError("repo_root is required")
    resolved = Path(repo_root).expanduser().resolve()
    if not resolved.is_dir():
        raise FileNotFoundError(f"repo_root does not exist: {resolved}")
    return resolved


def _require_safe_name(value: str, field: str) -> str:
    """Reject values that start with '-' to prevent git option injection."""
    if str(value).startswith("-"):
        raise ValueError(f"{field} must not start with '-': {value!r}")
    return str(value)


def build_git_argv(op: str, params: dict[str, Any] | None = None) -> list[str]:
    """Map a MAT-1 op + params to an explicit ``git`` argv (no shell)."""
    params = dict(params or {})

    if op == "git.status":
        cmd = ["git", "status", "--porcelain=v1", "-b"]
        pathspecs = params.get("pathspecs") or []
        if pathspecs:
            cmd.extend(["--", *pathspecs])
        return cmd

    if op == "git.fetch":
        cmd = ["git", "fetch"]
        if params.get("prune"):
            cmd.append("--prune")
        if params.get("remote"):
            cmd.append(_require_safe_name(params["remote"], "remote"))
        return cmd

    if op == "git.pull":
        cmd = ["git", "pull"]
        if params.get("rebase") is True:
            cmd.append("--rebase")
        elif params.get("rebase") is False:
            cmd.append("--no-rebase")
        if params.get("ff_only"):
            cmd.append("--ff-only")
        if params.get("remote"):
            cmd.append(_require_safe_name(params["remote"], "remote"))
        if params.get("refspec"):
            cmd.append(_require_safe_name(params["refspec"], "refspec"))
        return cmd

    if op == "git.checkout_new_branch":
        branch = params.get("branch")
        if not branch:
            raise ValueError("git.checkout_new_branch requires params.branch")
        cmd = ["git", "checkout", "-b", str(branch)]
        if params.get("start_point"):
            cmd.append(str(params["start_point"]))
        return cmd

    if op == "git.checkout_existing":
        branch = params.get("branch")
        if not branch:
            raise ValueError("git.checkout_existing requires params.branch")
        return ["git", "checkout", str(branch)]

    if op == "git.branch_list":
        cmd = ["git", "branch", "--list", "--format=%(refname:short)\t%(objectname:short)"]
        if params.get("include_remotes"):
            cmd.append("--all")
        return cmd

    if op == "git.worktree_add":
        path = params.get("path")
        branch = params.get("branch")
        if not path or not branch:
            raise ValueError("git.worktree_add requires params.path and params.branch")
        cmd = ["git", "worktree", "add", "-b", str(branch), str(path)]
        if params.get("base_ref"):
            cmd.append(str(params["base_ref"]))
        return cmd

    if op == "git.worktree_remove":
        path = params.get("path")
        if not path:
            raise ValueError("git.worktree_remove requires params.path")
        cmd = ["git", "worktree", "remove"]
        if params.get("force"):
            cmd.append("--force")
        cmd.append(str(path))
        return cmd

    if op == "git.worktree_list":
        return ["git", "worktree", "list", "--porcelain"]

    if op == "git.push":
        cmd = ["git", "push"]
        if params.get("force_with_lease"):
            cmd.append("--force-with-lease")
        if params.get("remote"):
            cmd.append(_require_safe_name(params["remote"], "remote"))
        if params.get("refspec"):
            cmd.append(_require_safe_name(params["refspec"], "refspec"))
        return cmd

    if op == "git.add":
        if params.get("all") is True:
            return ["git", "add", "-A"]
        pathspecs = params.get("pathspecs")
        if not pathspecs:
            raise ValueError("git.add requires params.pathspecs or params.all=true")
        return ["git", "add", "--", *[str(p) for p in pathspecs]]

    if op == "git.commit":
        message = params.get("message")
        if not message:
            raise ValueError("git.commit requires params.message")
        cmd = ["git", "commit", "-m", str(message)]
        if params.get("amend"):
            cmd.append("--amend")
        return cmd

    if op == "git.diff":
        cmd = ["git", "diff"]
        if params.get("cached"):
            cmd.append("--cached")
        pathspecs = params.get("pathspecs") or []
        if pathspecs:
            cmd.extend(["--", *[str(p) for p in pathspecs]])
        return cmd

    raise ValueError(f"no argv mapping for op: {op}")


@dataclass
class GitRunResult:
    """Outcome of an allowlisted git subprocess."""

    ok: bool
    stdout: str
    stderr: str
    return_code: int
    argv: list[str]
    timeout_exceeded: bool = False


def run_git(
    repo_root: Path,
    argv: list[str],
    *,
    timeout_ms: int | None = None,
) -> GitRunResult:
    """Run ``argv`` under ``repo_root`` via ``subprocess.run`` (never ``shell=True``)."""
    if not argv or argv[0] != "git":
        raise ValueError("argv must start with 'git'")
    timeout_sec = (timeout_ms if timeout_ms is not None else DEFAULT_TIMEOUT_MS) / 1000.0
    try:
        completed = subprocess.run(
            argv,
            cwd=str(repo_root),
            capture_output=True,
            text=True,
            timeout=timeout_sec,
            shell=False,
        )
        return GitRunResult(
            ok=completed.returncode == 0,
            stdout=completed.stdout or "",
            stderr=completed.stderr or "",
            return_code=completed.returncode,
            argv=list(argv),
            timeout_exceeded=False,
        )
    except subprocess.TimeoutExpired as exc:
        return GitRunResult(
            ok=False,
            stdout=exc.stdout or "",
            stderr=exc.stderr or "timeout",
            return_code=-1,
            argv=list(argv),
            timeout_exceeded=True,
        )


@dataclass
class MatGitExecutor:
    """Deny-by-default MAT-1 git executor used by the MCP server and unit tests."""

    manifest_path: Path
    allowed_operations: frozenset[str] = field(init=False)
    _runner: Any = field(default=None, repr=False)

    def __post_init__(self) -> None:
        self.allowed_operations = load_allowed_operations(self.manifest_path)
        if self._runner is None:
            self._runner = run_git

    @classmethod
    def from_manifest(cls, manifest_path: Path | None = None) -> MatGitExecutor:
        return cls(manifest_path=manifest_path or default_manifest_path())

    def reload_manifest(self) -> frozenset[str]:
        """Re-read the allowlist from disk (used by tests / hot reload)."""
        self.allowed_operations = load_allowed_operations(self.manifest_path)
        return self.allowed_operations

    def tool_names(self) -> list[str]:
        return sorted(op_to_tool_name(op) for op in self.allowed_operations)

    def call_tool(self, tool_name: str, arguments: dict[str, Any] | None = None) -> dict[str, Any]:
        """Execute an MCP tool by name with deny-by-default allowlist checks.

        Returns a structured dict. Never raises for unknown tools — returns
        ``{"ok": false, "error": "op_not_allowed"}``.
        """
        arguments = dict(arguments or {})
        op = tool_name_to_op(tool_name)

        if op not in self.allowed_operations:
            return {"ok": False, "error": "op_not_allowed", "op": op, "tool": tool_name}

        repo_root_raw = arguments.get("repo_root")
        params = arguments.get("params")
        if params is None:
            # Allow flat tool args: everything except envelope keys is params.
            params = {
                k: v
                for k, v in arguments.items()
                if k not in {"repo_root", "params", "timeout_ms"}
            }
        timeout_ms = arguments.get("timeout_ms")

        try:
            repo_root = expand_repo_root(str(repo_root_raw) if repo_root_raw is not None else "")
            argv = build_git_argv(op, params if isinstance(params, dict) else {})
        except (ValueError, FileNotFoundError) as exc:
            return {
                "ok": False,
                "error": "validation_error",
                "message": str(exc),
                "op": op,
            }

        result = self._runner(
            repo_root,
            argv,
            timeout_ms=int(timeout_ms) if timeout_ms is not None else None,
        )
        payload: dict[str, Any] = {
            "ok": result.ok,
            "op": op,
            "tool": tool_name,
            "argv": result.argv,
            "return_code": result.return_code,
            "stdout": result.stdout,
            "stderr": result.stderr,
        }
        if result.timeout_exceeded:
            payload["error"] = "timeout"
            payload["ok"] = False
        elif not result.ok:
            payload["error"] = "git_error"
        return payload


def create_mcp_server(
    manifest_path: Path | None = None,
    *,
    executor: MatGitExecutor | None = None,
) -> Any:
    """Build a FastMCP server with one tool per allowlisted MAT-1 op."""
    try:
        from mcp.server.fastmcp import FastMCP
    except ImportError as exc:  # pragma: no cover - optional extra
        raise ImportError(
            "The mcp package is required for the MAT-1 MCP git server. "
            "Install with: pip install '.[mcp]'"
        ) from exc

    exec_ = executor or MatGitExecutor.from_manifest(manifest_path)
    mcp = FastMCP(
        "mat-git-ops",
        instructions=(
            "MAT-1 deny-by-default git executor. Tools map 1:1 to "
            "schemas/gemini-git-ops/v1/manifest.json allowed_operations."
        ),
    )

    for op in sorted(exec_.allowed_operations):
        tool_name = op_to_tool_name(op)

        def _make_tool(bound_op: str, bound_name: str):
            def _tool(
                repo_root: str,
                params: dict[str, Any] | None = None,
                timeout_ms: int | None = None,
            ) -> dict[str, Any]:
                """Execute an allowlisted MAT-1 git operation (no shell)."""
                args: dict[str, Any] = {"repo_root": repo_root}
                if params is not None:
                    args["params"] = params
                if timeout_ms is not None:
                    args["timeout_ms"] = timeout_ms
                return exec_.call_tool(bound_name, args)

            _tool.__name__ = bound_name
            _tool.__doc__ = (
                f"MAT-1 `{bound_op}` — allowlisted git argv under repo_root. "
                "Params match schemas/gemini-git-ops/v1/request.schema.json."
            )
            return _tool

        mcp.add_tool(_make_tool(op, tool_name), name=tool_name)

    # Attach executor for tests / introspection (not part of MCP protocol).
    mcp.mat_git_executor = exec_  # type: ignore[attr-defined]
    return mcp


def main(argv: list[str] | None = None) -> None:
    """Start the MCP git server over stdio transport."""
    import argparse

    parser = argparse.ArgumentParser(
        prog="mat_runtime.mcp_git_server",
        description="MAT-1 git executor MCP server (stdio)",
    )
    parser.add_argument(
        "--manifest",
        type=Path,
        default=None,
        help="Path to MAT-1 manifest.json (default: schemas/gemini-git-ops/v1/manifest.json)",
    )
    args = parser.parse_args(argv)
    server = create_mcp_server(args.manifest)
    server.run(transport="stdio")


if __name__ == "__main__":
    main()
