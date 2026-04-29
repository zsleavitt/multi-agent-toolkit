# mat_runtime/swarm/definition.py
"""Swarm definition loading and configuration types."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class ConstraintsConfig:
    """Swarm constraints configuration."""

    timeout_ms: int | None = None


@dataclass
class SwarmDefinition:
    """Parsed swarm definition."""

    name: str
    dispatch_mode: str
    candidates: list[str]
    consensus_strategy: str
    schema_version: str = "1.0.0"
    description: str | None = None
    constraints: ConstraintsConfig = field(default_factory=ConstraintsConfig)
    model_matrix: dict[str, str] = field(default_factory=dict)
    source_path: Path | None = None


def _parse_constraints(data: dict | None) -> ConstraintsConfig:
    """Parse constraints configuration."""
    if not data:
        return ConstraintsConfig()
    return ConstraintsConfig(
        timeout_ms=data.get("timeout_ms"),
    )


def load_swarm_definition(path: Path | str) -> SwarmDefinition:
    """
    Load and parse a swarm definition from JSON.

    Validates:
    - dispatch_mode is "parallel_model" or "variant"
    - consensus_strategy is valid for dispatch_mode:
      - parallel_model: "first-complete", "return-all" (majority-vote not implemented)
      - variant: "return-all"
    - candidates list has >= 2 items

    Args:
        path: Path to the swarm definition JSON file.

    Returns:
        Parsed SwarmDefinition.

    Raises:
        FileNotFoundError: If the file doesn't exist.
        ValueError: If the definition is invalid.
        json.JSONDecodeError: If the file isn't valid JSON.
    """
    path = Path(path)
    data = json.loads(path.read_text(encoding="utf-8"))

    # Validate required fields
    name = data.get("name")
    if not name:
        raise ValueError("Swarm definition missing required field: name")

    dispatch_mode = data.get("dispatch_mode")
    if not dispatch_mode:
        raise ValueError("Swarm definition missing required field: dispatch_mode")

    # Validate dispatch_mode
    valid_modes = {"parallel_model", "variant"}
    if dispatch_mode not in valid_modes:
        raise ValueError(
            f"dispatch_mode '{dispatch_mode}' not valid. "
            f"Use one of: {', '.join(sorted(valid_modes))}"
        )

    candidates = data.get("candidates", [])
    if not candidates:
        raise ValueError("Swarm definition missing required field: candidates")
    if len(candidates) < 2:
        raise ValueError(
            f"Swarm requires at least 2 candidates, got {len(candidates)}"
        )

    consensus_strategy = data.get("consensus_strategy")
    if not consensus_strategy:
        raise ValueError("Swarm definition missing required field: consensus_strategy")

    # Validate consensus_strategy based on dispatch_mode
    if dispatch_mode == "parallel_model":
        valid_strategies = {"first-complete", "majority-vote", "return-all"}
        if consensus_strategy not in valid_strategies:
            raise ValueError(
                f"consensus_strategy '{consensus_strategy}' not valid for parallel_model. "
                f"Use one of: {', '.join(sorted(valid_strategies))}"
            )
        # MAT-46: only first-complete and return-all implemented
        if consensus_strategy == "majority-vote":
            raise ValueError(
                "consensus_strategy 'majority-vote' not implemented. "
                "Use 'first-complete' or 'return-all'."
            )
    elif dispatch_mode == "variant":
        valid_strategies = {"return-all"}
        if consensus_strategy not in valid_strategies:
            raise ValueError(
                f"consensus_strategy '{consensus_strategy}' not valid for variant mode. "
                f"Use one of: {', '.join(sorted(valid_strategies))}"
            )

    schema_version = data.get("schema_version", "1.0.0")
    if schema_version not in {"1.0.0", "1.1.0"}:
        raise ValueError(
            f"Unsupported schema_version '{schema_version}'. Use '1.0.0' or '1.1.0'."
        )

    raw_matrix = data.get("model_matrix")
    model_matrix: dict[str, str] = {}
    if raw_matrix is not None:
        if not isinstance(raw_matrix, dict):
            raise ValueError("model_matrix must be an object mapping candidate names to model strings")
        for key, value in raw_matrix.items():
            if not isinstance(key, str) or not isinstance(value, str):
                raise ValueError("model_matrix keys and values must be strings")
            if key not in candidates:
                raise ValueError(
                    f"model_matrix key '{key}' is not a swarm candidate. "
                    f"Valid keys: {', '.join(sorted(candidates))}"
                )
            if not value.strip():
                raise ValueError(f"model_matrix value for '{key}' must be a non-empty string")
            model_matrix[key] = value
        if model_matrix and schema_version != "1.1.0":
            raise ValueError(
                "model_matrix requires schema_version '1.1.0' (MAT-54 per-candidate model hints)."
            )

    return SwarmDefinition(
        name=name,
        dispatch_mode=dispatch_mode,
        candidates=candidates,
        consensus_strategy=consensus_strategy,
        schema_version=schema_version,
        description=data.get("description"),
        constraints=_parse_constraints(data.get("constraints")),
        model_matrix=model_matrix,
        source_path=path,
    )
