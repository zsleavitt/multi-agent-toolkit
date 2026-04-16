"""CLI entry point for MAT runtime."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

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
            }
            for name, agent in router.agents.items()
        }
        print(json.dumps(agents_data, indent=2))
    else:
        if not router.agents:
            print("No agents found.")
            return 0

        print(f"Found {len(router.agents)} agent(s):\n")
        for name, agent in sorted(router.agents.items()):
            print(f"  {name}")
            print(f"    Description: {agent.description}")
            print(f"    Role: {agent.role}")
            print(f"    CLI: {agent.cli}")
            if agent.allowed_mat_ops:
                print(f"    MAT ops: {', '.join(agent.allowed_mat_ops)}")
            print()

    return 0


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

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return 0

    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
