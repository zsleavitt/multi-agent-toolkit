#!/usr/bin/env python3
"""Entry point for the MAT-1 MCP git server (MAT-101).

Usage::

    python scripts/run_mcp_git_server.py
    python -m mat_runtime.mcp_git_server

Requires the optional ``mcp`` extra::

    pip install '.[mcp]'
"""

from __future__ import annotations

import sys
from pathlib import Path

# Allow running from a checkout without an editable install.
_REPO_ROOT = Path(__file__).resolve().parents[1]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from mat_runtime.mcp_git_server import main

if __name__ == "__main__":
    main()
