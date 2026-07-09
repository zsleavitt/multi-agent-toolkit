"""Hive runtime - multi-crew orchestration layer."""

from mat_runtime.hive.types import (
    CrewStageResult,
    HandoffContext,
    HiveResult,
    HiveSession,
    HiveTask,
)
from mat_runtime.hive.definition import (
    CrewEntry,
    GlobalConfig,
    HiveDefinition,
    InterCrewRoutingConfig,
    QuotasConfig,
    RoutingRule,
    SharedMemoryConfig,
    load_hive_definition,
)
from mat_runtime.hive.hooks import HookResult, HookRunner
from mat_runtime.hive.routing import (
    CapabilityStrategy,
    DependencyStrategy,
    InterCrewRoutingStrategy,
    ManualStrategy,
    SequentialStrategy,
    create_routing_strategy,
    dependencies_satisfied,
    evaluate_handoff,
    evaluate_handoff_context,
    get_crew_entry,
)
from mat_runtime.hive.memory import (
    HiveMemoryStore,
    NamespacePermissions,
    ScopedHiveMemoryView,
    create_hive_memory_store,
)
from mat_runtime.hive.hive import Hive
from mat_runtime.hive.registry import HiveRegistry

__all__ = [
    # Types
    "HiveTask",
    "CrewStageResult",
    "HiveResult",
    "HiveSession",
    "HandoffContext",
    # Definition
    "CrewEntry",
    "GlobalConfig",
    "QuotasConfig",
    "SharedMemoryConfig",
    "InterCrewRoutingConfig",
    "RoutingRule",
    "HiveDefinition",
    "load_hive_definition",
    # Hooks
    "HookRunner",
    "HookResult",
    # Routing
    "InterCrewRoutingStrategy",
    "SequentialStrategy",
    "DependencyStrategy",
    "CapabilityStrategy",
    "ManualStrategy",
    "create_routing_strategy",
    "dependencies_satisfied",
    "evaluate_handoff",
    "evaluate_handoff_context",
    "get_crew_entry",
    # Hive
    "Hive",
    "HiveRegistry",
    # Memory
    "HiveMemoryStore",
    "ScopedHiveMemoryView",
    "NamespacePermissions",
    "create_hive_memory_store",
]
