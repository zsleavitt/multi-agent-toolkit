#!/usr/bin/env python3
"""
/ticket skill — create, list, and update tickets via configured adapter.

Usage:
    python ticket.py create <title> [--priority P0|P1|P2] [--status STATUS] [--description DESC]
    python ticket.py list [--status STATUS] [--limit N]
    python ticket.py update <id> [--status STATUS] [--priority PRIORITY]

This script outputs structured JSON that the orchestrator uses with MCP tools.
The orchestrator (Claude Code) makes the actual MCP calls.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(REPO_ROOT))

from mat_runtime.work_items import WorkItem, get_adapter_from_profile


def cmd_create(args: argparse.Namespace) -> dict:
    """Build payload for creating a ticket."""
    try:
        adapter = get_adapter_from_profile(args.repo_root)
    except FileNotFoundError:
        return {
            "error": "ai-team.repo.json not found. Run setup wizard or create manually.",
            "suggestion": "bin/setup --init",
        }

    if adapter is None:
        return {
            "error": "No ticket system configured (adapter: none).",
            "suggestion": "Update ai-team.repo.json work_item_source",
        }

    item = WorkItem(
        title=args.title,
        status=args.status or "Backlog",
        priority=args.priority,
        description=args.description or "",
    )

    payload = adapter.build_create_payload(item)

    return {
        "action": "create",
        "adapter": adapter.adapter_name,
        "mcp_tool": getattr(adapter, "MCP_TOOL_CREATE", None),
        "payload": {
            "parent": {
                "type": "data_source_id",
                "data_source_id": adapter.data_source_id or adapter.database_id,
            },
            "pages": [payload],
        },
        "item": {
            "title": item.title,
            "status": item.status,
            "priority": item.priority,
            "description": item.description,
        },
    }


def cmd_list(args: argparse.Namespace) -> dict:
    """Build payload for listing tickets."""
    try:
        adapter = get_adapter_from_profile(args.repo_root)
    except FileNotFoundError:
        return {
            "error": "ai-team.repo.json not found.",
            "suggestion": "bin/setup --init",
        }

    if adapter is None:
        return {
            "error": "No ticket system configured (adapter: none).",
        }

    query_payload = adapter.build_query(status=args.status, limit=args.limit)

    return {
        "action": "list",
        "adapter": adapter.adapter_name,
        "mcp_tool": getattr(adapter, "MCP_TOOL_QUERY", None),
        "payload": query_payload,
        "filters": {
            "status": args.status,
            "limit": args.limit,
        },
    }


def cmd_update(args: argparse.Namespace) -> dict:
    """Build payload for updating a ticket."""
    try:
        adapter = get_adapter_from_profile(args.repo_root)
    except FileNotFoundError:
        return {
            "error": "ai-team.repo.json not found.",
            "suggestion": "bin/setup --init",
        }

    if adapter is None:
        return {
            "error": "No ticket system configured (adapter: none).",
        }

    item = WorkItem(
        id=args.id,
        status=args.status,
        priority=args.priority,
    )

    payload = adapter.build_update_payload(item)

    return {
        "action": "update",
        "adapter": adapter.adapter_name,
        "mcp_tool": getattr(adapter, "MCP_TOOL_UPDATE", None),
        "payload": payload,
        "item": {
            "id": item.id,
            "status": item.status,
            "priority": item.priority,
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Create, list, and update tickets via configured adapter"
    )
    parser.add_argument(
        "--repo-root",
        "-r",
        type=Path,
        default=Path.cwd(),
        help="Repository root (default: current directory)",
    )

    subparsers = parser.add_subparsers(dest="command", required=True)

    # create subcommand
    create_parser = subparsers.add_parser("create", help="Create a new ticket")
    create_parser.add_argument("title", help="Ticket title")
    create_parser.add_argument("--priority", "-p", help="Priority (e.g., P0, P1, P2)")
    create_parser.add_argument("--status", "-s", help="Status (default: Backlog)")
    create_parser.add_argument("--description", "-d", help="Ticket description")

    # list subcommand
    list_parser = subparsers.add_parser("list", help="List tickets")
    list_parser.add_argument("--status", "-s", help="Filter by status")
    list_parser.add_argument(
        "--limit", "-l", type=int, default=50, help="Max tickets to return"
    )

    # update subcommand
    update_parser = subparsers.add_parser("update", help="Update a ticket")
    update_parser.add_argument("id", help="Ticket page ID or URL")
    update_parser.add_argument("--status", "-s", help="New status")
    update_parser.add_argument("--priority", "-p", help="New priority")

    args = parser.parse_args()

    if args.command == "create":
        result = cmd_create(args)
    elif args.command == "list":
        result = cmd_list(args)
    elif args.command == "update":
        result = cmd_update(args)
    else:
        result = {"error": f"Unknown command: {args.command}"}

    print(json.dumps(result, indent=2))

    return 1 if "error" in result else 0


if __name__ == "__main__":
    sys.exit(main())
