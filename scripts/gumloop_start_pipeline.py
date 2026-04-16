#!/usr/bin/env python3
"""MAT-5: POST Gumloop start_pipeline (stdlib only). See docs/prototypes/mat-5-gumloop.md.

Environment:
  GUMLOOP_API_KEY   Bearer token (required)
  GUMLOOP_USER_ID   user_id field (required unless passed as --user-id)

Arguments:
  --saved-item-id   Gumloop saved flow id (required)
  --user-id         Overrides GUMLOOP_USER_ID
  --body            Path to JSON request body (default: examples/gumloop/start-pipeline.request.example.json)

Example:
  export GUMLOOP_API_KEY=...
  export GUMLOOP_USER_ID=...
  python scripts/gumloop_start_pipeline.py --saved-item-id YOUR_FLOW_ID
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path

API = "https://api.gumloop.com/api/v1/start_pipeline"
ROOT = Path(__file__).resolve().parents[1]
DEFAULT_BODY = ROOT / "examples" / "gumloop" / "start-pipeline.request.example.json"


def main() -> int:
    p = argparse.ArgumentParser(description="Start a Gumloop pipeline via public API.")
    p.add_argument("--saved-item-id", help="Gumloop saved_item_id (overrides body file if set)")
    p.add_argument("--user-id", default=os.environ.get("GUMLOOP_USER_ID", ""))
    p.add_argument("--body", type=Path, default=DEFAULT_BODY, help="JSON request path")
    args = p.parse_args()

    key = os.environ.get("GUMLOOP_API_KEY", "").strip()
    if not key:
        print("error: set GUMLOOP_API_KEY", file=sys.stderr)
        return 2

    user_id = (args.user_id or "").strip()
    if not user_id:
        print("error: set GUMLOOP_USER_ID or pass --user-id", file=sys.stderr)
        return 2

    if not args.body.is_file():
        print(f"error: body file not found: {args.body}", file=sys.stderr)
        return 2

    payload = json.loads(args.body.read_text(encoding="utf-8"))
    payload["user_id"] = user_id
    if args.saved_item_id:
        payload["saved_item_id"] = args.saved_item_id

    if not payload.get("saved_item_id"):
        print("error: saved_item_id missing (set in JSON or pass --saved-item-id)", file=sys.stderr)
        return 2

    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        API,
        data=data,
        headers={
            "Authorization": f"Bearer {key}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            out = resp.read().decode("utf-8")
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")
        print(f"HTTP {e.code}: {body}", file=sys.stderr)
        return 1
    except urllib.error.URLError as e:
        print(f"request failed: {e}", file=sys.stderr)
        return 1

    try:
        parsed = json.loads(out)
        print(json.dumps(parsed, indent=2))
    except json.JSONDecodeError:
        print(out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
