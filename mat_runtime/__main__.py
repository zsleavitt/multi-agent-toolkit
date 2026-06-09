"""CLI entry point for MAT runtime."""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path

from mat_runtime.crew import Crew, CrewTask
from mat_runtime.router import AgentRouter, MAT2Request


def cmd_invoke(args: argparse.Namespace) -> int:
    """Handle the invoke command."""
    router = AgentRouter(repo_root=args.repo_root)

    # Load request
    if args.request:
        request = MAT2Request.from_file(args.request)
    elif args.instruction:
        request = MAT2Request(
            schema_version="1.2.0",
            correlation_id=args.correlation_id or "",
            idempotency_key=args.idempotency_key or "",
            op=args.op or "codex.implement",
            repo_root=str(args.repo_root or Path.cwd()),
            instruction=args.instruction,
            scope_paths=args.scope_paths or [],
            timeout_ms=args.timeout_ms,
        )
    else:
        print("Error: Either --request or --instruction is required", file=sys.stderr)
        return 1

    # Invoke
    if args.agent:
        response = router.invoke(args.agent, request)
    else:
        response = router.invoke_op(request)

    # Output
    print(response.to_json(indent=2 if args.pretty else None))
    return 0 if response.ok else 1


def cmd_list_agents(args: argparse.Namespace) -> int:
    """Handle the list-agents command."""
    router = AgentRouter(repo_root=args.repo_root)

    if args.json:
        agents_data = {
            name: {
                "description": agent.description,
                "role": agent.role,
                "cli": agent.cli,
                "allowed_mat_ops": agent.allowed_mat_ops,
                "variant_of": agent.variant_of,
                "specialization": agent.specialization,
            }
            for name, agent in router.agents.items()
        }
        print(json.dumps(agents_data, indent=2))
    else:
        if not router.agents:
            print("No agents found.")
            return 0

        # Separate base agents from variants
        base_agents = {k: v for k, v in router.agents.items() if not v.variant_of}
        variants = {k: v for k, v in router.agents.items() if v.variant_of}

        print(f"Found {len(router.agents)} agent(s) ({len(base_agents)} base, {len(variants)} variants):\n")

        for name, agent in sorted(router.agents.items()):
            if agent.variant_of:
                print(f"  {name} (variant of {agent.variant_of})")
            else:
                print(f"  {name}")
            print(f"    Description: {agent.description}")
            print(f"    Role: {agent.role}")
            print(f"    CLI: {agent.cli}")
            if agent.allowed_mat_ops:
                print(f"    MAT ops: {', '.join(agent.allowed_mat_ops)}")
            if agent.specialization:
                spec = agent.specialization
                if spec.get("domain"):
                    print(f"    Domain: {spec['domain']}")
                if spec.get("languages"):
                    print(f"    Languages: {', '.join(spec['languages'])}")
                if spec.get("frameworks"):
                    print(f"    Frameworks: {', '.join(spec['frameworks'])}")
                if spec.get("tags"):
                    print(f"    Tags: {', '.join(spec['tags'])}")
            print()

    return 0


async def cmd_invoke_crew_async(args: argparse.Namespace) -> int:
    """Handle the invoke-crew command (async implementation)."""
    crew = Crew(
        definition_path=args.crew,
        repo_root=args.repo_root,
    )

    await crew.start()

    try:
        task = CrewTask(
            instruction=args.instruction,
            op=args.op,
            scope_paths=args.scope_paths or [],
            timeout_ms=args.timeout_ms,
        )

        result = await crew.submit(task)

        # Output result
        output = {
            "ok": result.ok,
            "agent_used": result.agent_used,
            "correlation_id": result.correlation_id,
            "duration_ms": result.duration_ms,
            "attempts": result.attempts,
        }
        if result.ok:
            output["output"] = result.output
        else:
            output["error"] = result.error
            if result.retry_reasons:
                output["retry_reasons"] = result.retry_reasons

        print(json.dumps(output, indent=2 if args.pretty else None))
        return 0 if result.ok else 1

    finally:
        await crew.shutdown()


def cmd_invoke_crew(args: argparse.Namespace) -> int:
    """Handle the invoke-crew command."""
    return asyncio.run(cmd_invoke_crew_async(args))


async def cmd_invoke_swarm_async(args: argparse.Namespace) -> int:
    """Handle the invoke-swarm command (async implementation)."""
    from mat_runtime.swarm import Swarm, SwarmTask

    swarm = Swarm(
        definition_path=args.swarm,
        repo_root=args.repo_root,
    )

    task = SwarmTask(
        instruction=args.instruction,
        op=args.op,
        timeout_ms=args.timeout_ms,
    )

    result = await swarm.dispatch(task)

    # Output result
    output = {
        "ok": result.ok,
        "consensus_strategy": result.consensus_strategy,
        "winning_candidate": result.winning_candidate,
        "correlation_id": result.correlation_id,
        "duration_ms": result.duration_ms,
        "candidate_results": [
            {
                "candidate": cr.candidate,
                "ok": cr.ok,
                "duration_ms": cr.duration_ms,
                "error": cr.error,
            }
            for cr in result.candidate_results
        ],
    }
    if result.ok:
        output["output"] = result.output
    else:
        output["error"] = result.error

    print(json.dumps(output, indent=2 if args.pretty else None))
    return 0 if result.ok else 1


def cmd_invoke_swarm(args: argparse.Namespace) -> int:
    """Handle the invoke-swarm command."""
    return asyncio.run(cmd_invoke_swarm_async(args))


def _resolve_hive_path(repo_root: Path, hive: str) -> Path:
    """Resolve hive name or path to a definition file."""
    candidate = Path(hive)
    if candidate.is_file():
        return candidate.resolve()

    named = repo_root / "hives" / f"{hive}.json"
    if named.is_file():
        return named.resolve()

    if candidate.suffix == ".json" and (repo_root / "hives" / candidate.name).is_file():
        return (repo_root / "hives" / candidate.name).resolve()

    raise FileNotFoundError(
        f"Hive definition not found for '{hive}'. "
        f"Expected hives/{hive}.json under {repo_root}"
    )


async def cmd_invoke_hive_async(args: argparse.Namespace) -> int:
    """Handle the invoke-hive command (async implementation)."""
    from mat_runtime.hive import Hive, HiveTask

    repo_root = (args.repo_root or Path.cwd()).resolve()
    hive_path = _resolve_hive_path(repo_root, args.hive)

    hive = Hive(
        definition_path=hive_path,
        repo_root=repo_root,
    )

    await hive.start()

    try:
        task_kwargs: dict = {
            "instruction": args.instruction,
            "op": args.op,
            "scope_paths": args.scope_paths or [],
            "timeout_ms": args.timeout_ms,
        }
        if args.correlation_id:
            task_kwargs["correlation_id"] = args.correlation_id
        if args.role:
            task_kwargs["role"] = args.role

        task = HiveTask(**task_kwargs)

        result = await hive.submit(task)

        output = {
            "ok": result.ok,
            "correlation_id": result.correlation_id,
            "final_crew": result.final_crew,
            "total_duration_ms": result.total_duration_ms,
            "agent_invocations": result.agent_invocations,
            "stages": [
                {
                    "crew_ref": stage.crew_ref,
                    "ok": stage.ok,
                    "duration_ms": stage.duration_ms,
                    "agent_used": stage.crew_result.agent_used,
                }
                for stage in result.stages
            ],
        }
        if result.ok:
            if result.stages:
                output["output"] = result.stages[-1].crew_result.output
        else:
            output["error"] = result.error or (
                result.stages[-1].crew_result.error if result.stages else None
            )

        print(json.dumps(output, indent=2 if args.pretty else None))
        return 0 if result.ok else 1

    finally:
        await hive.shutdown()


def cmd_invoke_hive(args: argparse.Namespace) -> int:
    """Handle the invoke-hive command."""
    try:
        return asyncio.run(cmd_invoke_hive_async(args))
    except FileNotFoundError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1


def cmd_smoke(args: argparse.Namespace) -> int:
    """Handle the smoke command — adapter preflight; optional real MAT-2 with MAT_SMOKE_REAL_CLI=1."""
    from mat_runtime.smoke import SMOKE_INSTRUCTION, run_smoke

    return run_smoke(
        Path(args.repo_root) if args.repo_root else Path.cwd(),
        real=args.real,
        per_cli=args.per_cli,
        agent=args.agent,
        instruction=(args.instruction or SMOKE_INSTRUCTION),
        timeout_ms=args.timeout_ms,
        strict=args.strict,
        as_json=args.json,
    )


def main() -> int:
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        prog="mat_runtime",
        description="MAT Runtime — Multi-Agent Toolkit runtime adapter layer",
    )
    parser.add_argument(
        "--repo-root",
        type=Path,
        default=None,
        help="Repository root (default: auto-detect from cwd)",
    )

    subparsers = parser.add_subparsers(dest="command", help="Commands")

    # invoke command
    invoke_parser = subparsers.add_parser(
        "invoke", help="Invoke an agent with a MAT-2 request"
    )
    invoke_parser.add_argument(
        "--agent",
        "-a",
        help="Agent name (if omitted, routes based on operation)",
    )
    invoke_parser.add_argument(
        "--request",
        "-r",
        type=Path,
        help="Path to MAT-2 request JSON file",
    )
    invoke_parser.add_argument(
        "--instruction",
        "-i",
        help="Instruction text (alternative to --request)",
    )
    invoke_parser.add_argument(
        "--op",
        "-o",
        default="codex.implement",
        help="Operation (default: codex.implement)",
    )
    invoke_parser.add_argument(
        "--scope-paths",
        "-s",
        nargs="*",
        help="Scope paths",
    )
    invoke_parser.add_argument(
        "--timeout-ms",
        "-t",
        type=int,
        help="Timeout in milliseconds",
    )
    invoke_parser.add_argument(
        "--correlation-id",
        help="Correlation ID",
    )
    invoke_parser.add_argument(
        "--idempotency-key",
        help="Idempotency key",
    )
    invoke_parser.add_argument(
        "--pretty",
        "-p",
        action="store_true",
        default=True,
        help="Pretty-print JSON output (default: true)",
    )
    invoke_parser.set_defaults(func=cmd_invoke)

    # list-agents command
    list_parser = subparsers.add_parser(
        "list-agents", help="List available agents"
    )
    list_parser.add_argument(
        "--json",
        "-j",
        action="store_true",
        help="Output as JSON",
    )
    list_parser.set_defaults(func=cmd_list_agents)

    # invoke-crew command
    invoke_crew_parser = subparsers.add_parser(
        "invoke-crew", help="Submit a task to a crew"
    )
    invoke_crew_parser.add_argument(
        "--crew",
        "-c",
        type=Path,
        required=True,
        help="Path to crew definition JSON file",
    )
    invoke_crew_parser.add_argument(
        "--instruction",
        "-i",
        required=True,
        help="Task instruction",
    )
    invoke_crew_parser.add_argument(
        "--op",
        "-o",
        default="codex.implement",
        help="Operation (default: codex.implement)",
    )
    invoke_crew_parser.add_argument(
        "--scope-paths",
        "-s",
        nargs="*",
        help="Scope paths",
    )
    invoke_crew_parser.add_argument(
        "--timeout-ms",
        "-t",
        type=int,
        help="Task timeout in milliseconds",
    )
    invoke_crew_parser.add_argument(
        "--pretty",
        "-p",
        action="store_true",
        default=True,
        help="Pretty-print JSON output (default: true)",
    )
    invoke_crew_parser.set_defaults(func=cmd_invoke_crew)

    # invoke-swarm command
    invoke_swarm_parser = subparsers.add_parser(
        "invoke-swarm", help="Dispatch a task to a swarm"
    )
    invoke_swarm_parser.add_argument(
        "--swarm",
        "-s",
        type=Path,
        required=True,
        help="Path to swarm definition JSON file",
    )
    invoke_swarm_parser.add_argument(
        "--instruction",
        "-i",
        required=True,
        help="Task instruction",
    )
    invoke_swarm_parser.add_argument(
        "--op",
        "-o",
        default="codex.implement",
        help="Operation (default: codex.implement)",
    )
    invoke_swarm_parser.add_argument(
        "--timeout-ms",
        "-t",
        type=int,
        help="Task timeout in milliseconds",
    )
    invoke_swarm_parser.add_argument(
        "--pretty",
        "-p",
        action="store_true",
        default=True,
        help="Pretty-print JSON output (default: true)",
    )
    invoke_swarm_parser.set_defaults(func=cmd_invoke_swarm)

    # invoke-hive command
    invoke_hive_parser = subparsers.add_parser(
        "invoke-hive", help="Submit a task to a hive"
    )
    invoke_hive_parser.add_argument(
        "--hive",
        required=True,
        help="Hive name (hives/{name}.json) or path to hive definition JSON",
    )
    invoke_hive_parser.add_argument(
        "--instruction",
        "-i",
        required=True,
        help="Task instruction",
    )
    invoke_hive_parser.add_argument(
        "--op",
        "-o",
        default="codex.implement",
        help="Operation (default: codex.implement)",
    )
    invoke_hive_parser.add_argument(
        "--role",
        help="Crew role hint for capability routing",
    )
    invoke_hive_parser.add_argument(
        "--correlation-id",
        help="Correlation ID for session threading",
    )
    invoke_hive_parser.add_argument(
        "--scope-paths",
        "-s",
        nargs="*",
        help="Scope paths",
    )
    invoke_hive_parser.add_argument(
        "--timeout-ms",
        "-t",
        type=int,
        help="Task timeout in milliseconds",
    )
    invoke_hive_parser.add_argument(
        "--pretty",
        "-p",
        action="store_true",
        default=True,
        help="Pretty-print JSON output (default: true)",
    )
    invoke_hive_parser.set_defaults(func=cmd_invoke_hive)

    # smoke — preflight and optional live MAT-2 checks (see docs/adr/0005-smoke-cli-verification.md)
    smoke_parser = subparsers.add_parser(
        "smoke",
        help="Preflight local CLI toolchains; optional --real with MAT_SMOKE_REAL_CLI=1",
    )
    smoke_parser.add_argument(
        "--real",
        action="store_true",
        help="Run live MAT-2 invocations (requires MAT_SMOKE_REAL_CLI=1)",
    )
    smoke_parser.add_argument(
        "--per-cli",
        action="store_true",
        help="With --real: one representative agent per unique CLI (codex, gemini, claude, …)",
    )
    smoke_parser.add_argument(
        "--agent",
        "-a",
        help="With --real: single agent to invoke (e.g. reviewer)",
    )
    smoke_parser.add_argument(
        "--instruction",
        "-i",
        help="Override default tiny smoke instruction (still keep it minimal)",
    )
    smoke_parser.add_argument(
        "--timeout-ms",
        "-t",
        type=int,
        default=120_000,
        help="Timeout for each real invoke (default: 120000)",
    )
    smoke_parser.add_argument(
        "--strict",
        action="store_true",
        help="On dry preflight, exit 1 if any adapter CLI is missing or broken",
    )
    smoke_parser.add_argument(
        "--json",
        "-j",
        action="store_true",
        help="Machine-readable output (JSON rows)",
    )
    smoke_parser.set_defaults(func=cmd_smoke)

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return 0

    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
