"""
MAT Runtime — Multi-Agent Toolkit runtime adapter layer.

Provides CLI-based agent invocation following the CLI delegation model (ADR 0002).
No direct API calls — each CLI tool manages its own authentication.
"""

from mat_runtime.router import AgentRouter
from mat_runtime.config import load_provider_config, load_agent_definitions

__all__ = ["AgentRouter", "load_provider_config", "load_agent_definitions"]
__version__ = "0.1.0"
