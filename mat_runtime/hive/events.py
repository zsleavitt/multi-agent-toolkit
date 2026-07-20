"""Structured event/observability system for the Hive runtime (MAT-52).

This module provides a lightweight, dependency-free event bus so external
observers can subscribe to Crew and Swarm lifecycle events emitted by the
runtime. It is intentionally separate from the string-named lifecycle
``HookRunner`` (``mat_runtime/hive/hooks.py``): hooks run configured shell
scripts, whereas this system delivers structured, in-process ``Event`` objects
to registered observers.

Design notes:
- ``EventBus.emit`` is synchronous and defensive: a misbehaving observer never
  interrupts orchestration (exceptions are caught and logged).
- Built-in observers use only the standard library (``logging`` and
  ``urllib.request``) per the MAT-52 "no new dependencies" constraint.
- ``WebhookObserver`` POSTs on a background daemon thread by default so network
  latency does not block the orchestration event loop.
"""

from __future__ import annotations

import json
import logging
import threading
import time
import urllib.request
from collections.abc import Iterable
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Protocol, runtime_checkable

_bus_logger = logging.getLogger("mat_runtime.hive.events")


class EventType(str, Enum):
    """Structured event types emitted by the Hive/Swarm runtime."""

    CREW_STARTED = "crew_started"
    CREW_COMPLETED = "crew_completed"
    SWARM_DISPATCHED = "swarm_dispatched"
    SWARM_CONSENSUS_REACHED = "swarm_consensus_reached"


class Severity(str, Enum):
    """Event severity, ordered to mirror the stdlib ``logging`` levels."""

    INFO = "info"
    WARNING = "warning"
    ERROR = "error"

    @property
    def level(self) -> int:
        """Numeric ordering matching the corresponding ``logging`` module level."""
        return _SEVERITY_LEVELS[self]


_SEVERITY_LEVELS: dict[Severity, int] = {
    Severity.INFO: logging.INFO,
    Severity.WARNING: logging.WARNING,
    Severity.ERROR: logging.ERROR,
}


@dataclass
class Event:
    """A structured observability event.

    Attributes:
        event_type: The kind of event (see :class:`EventType`).
        correlation_id: Task correlation id, for tracing across the pipeline.
        severity: Event severity (see :class:`Severity`).
        timestamp: Wall-clock epoch seconds when the event was created.
        crew: Crew ref associated with the event, if any.
        swarm: Swarm name associated with the event, if any.
        hive: Hive name associated with the event, if any.
        duration_ms: Elapsed time associated with the event, if known.
        task_metadata: Task-level metadata (op, capabilities, custom fields).
        outcome: Outcome detail (ok, winning_candidate, error, ...).
        source: Human-readable source of the event (e.g. "hive", "swarm").
    """

    event_type: EventType
    correlation_id: str
    severity: Severity = Severity.INFO
    timestamp: float = field(default_factory=time.time)
    crew: str | None = None
    swarm: str | None = None
    hive: str | None = None
    duration_ms: int | None = None
    task_metadata: dict[str, Any] = field(default_factory=dict)
    outcome: dict[str, Any] = field(default_factory=dict)
    source: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Serialize the event to a JSON-safe dictionary."""
        return {
            "event_type": self.event_type.value,
            "severity": self.severity.value,
            "correlation_id": self.correlation_id,
            "timestamp": self.timestamp,
            "timestamp_iso": datetime.fromtimestamp(
                self.timestamp, tz=timezone.utc
            ).isoformat(),
            "crew": self.crew,
            "swarm": self.swarm,
            "hive": self.hive,
            "duration_ms": self.duration_ms,
            "task_metadata": self.task_metadata,
            "outcome": self.outcome,
            "source": self.source,
        }


@dataclass
class EventFilter:
    """Filter controlling which events an observer receives.

    All configured constraints must match (logical AND). Unset constraints
    (``None``) match everything.

    Attributes:
        event_types: Only deliver these event types.
        crews: Only deliver events for these crew refs. An event with no crew
            is excluded when this constraint is set.
        min_severity: Only deliver events at or above this severity.
    """

    event_types: set[EventType] | None = None
    crews: set[str] | None = None
    min_severity: Severity | None = None

    def matches(self, event: Event) -> bool:
        """Return True if ``event`` passes all configured constraints."""
        if self.event_types is not None and event.event_type not in self.event_types:
            return False
        if self.crews is not None and (
            event.crew is None or event.crew not in self.crews
        ):
            return False
        if (
            self.min_severity is not None
            and event.severity.level < self.min_severity.level
        ):
            return False
        return True


@runtime_checkable
class EventObserver(Protocol):
    """Protocol for objects that receive events from an :class:`EventBus`."""

    def handle(self, event: Event) -> None:
        """Handle a single event. Must not raise for normal operation."""
        ...


@dataclass
class _Subscription:
    observer: EventObserver
    event_filter: EventFilter | None


class EventBus:
    """In-process publish/subscribe hub for runtime observability events.

    Registration is the public API for external observers:

        bus = EventBus()
        bus.subscribe(LoggingObserver())
        bus.subscribe(
            WebhookObserver("https://example.test/hook"),
            event_filter=EventFilter(min_severity=Severity.ERROR),
        )

    Emission is defensive: an observer that raises does not interrupt the
    orchestrator or other observers.
    """

    def __init__(self) -> None:
        self._subscriptions: list[_Subscription] = []
        self._lock = threading.Lock()

    def subscribe(
        self,
        observer: EventObserver,
        *,
        event_filter: EventFilter | None = None,
    ) -> EventObserver:
        """Register ``observer`` to receive events matching ``event_filter``.

        Returns the observer so callers can unsubscribe it later.
        """
        with self._lock:
            self._subscriptions.append(_Subscription(observer, event_filter))
        return observer

    def unsubscribe(self, observer: EventObserver) -> None:
        """Remove all subscriptions for ``observer`` (no error if absent)."""
        with self._lock:
            self._subscriptions = [
                sub for sub in self._subscriptions if sub.observer is not observer
            ]

    def clear(self) -> None:
        """Remove all subscriptions."""
        with self._lock:
            self._subscriptions.clear()

    def emit(self, event: Event) -> None:
        """Deliver ``event`` to every subscribed observer whose filter matches.

        Observer exceptions are caught and logged so a faulty observer can
        never break orchestration or block sibling observers.
        """
        with self._lock:
            subscriptions = list(self._subscriptions)

        for sub in subscriptions:
            if sub.event_filter is not None and not sub.event_filter.matches(event):
                continue
            try:
                sub.observer.handle(event)
            except Exception:  # noqa: BLE001 - observers must never break emit
                _bus_logger.exception(
                    "Event observer %r raised handling %s",
                    sub.observer,
                    event.event_type.value,
                )


class LoggingObserver:
    """Observer that writes structured events to the stdlib ``logging`` module.

    Each event is logged at the level corresponding to its severity. The event
    payload is attached as ``extra={"mat_event": event.to_dict()}`` so
    structured-logging handlers can consume the full record.
    """

    def __init__(
        self,
        logger: logging.Logger | str | None = None,
    ) -> None:
        if isinstance(logger, logging.Logger):
            self._logger = logger
        else:
            self._logger = logging.getLogger(logger or "mat_runtime.hive.events")

    def handle(self, event: Event) -> None:
        payload = event.to_dict()
        self._logger.log(
            event.severity.level,
            "mat_event %s crew=%s swarm=%s ok=%s duration_ms=%s",
            event.event_type.value,
            event.crew,
            event.swarm,
            event.outcome.get("ok"),
            event.duration_ms,
            extra={"mat_event": payload},
        )


class WebhookObserver:
    """Observer that POSTs a JSON event payload to an HTTP endpoint.

    Uses ``urllib.request`` (stdlib only). By default the POST runs on a
    background daemon thread so network latency never blocks orchestration.
    Set ``background=False`` for synchronous delivery (useful in tests).
    """

    def __init__(
        self,
        url: str,
        *,
        timeout_s: float = 5.0,
        headers: dict[str, str] | None = None,
        background: bool = True,
    ) -> None:
        self._url = url
        self._timeout_s = timeout_s
        self._headers = {"Content-Type": "application/json", **(headers or {})}
        self._background = background

    def handle(self, event: Event) -> None:
        if self._background:
            thread = threading.Thread(
                target=self._post,
                args=(event.to_dict(),),
                name="mat-webhook-observer",
                daemon=True,
            )
            thread.start()
        else:
            self._post(event.to_dict())

    def _post(self, payload: dict[str, Any]) -> None:
        data = json.dumps(payload).encode("utf-8")
        request = urllib.request.Request(
            self._url,
            data=data,
            headers=self._headers,
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=self._timeout_s):
                pass
        except Exception:  # noqa: BLE001 - webhook delivery is best-effort
            _bus_logger.exception("Webhook delivery to %s failed", self._url)


def build_event_bus(
    observers: Iterable[EventObserver] | None = None,
) -> EventBus:
    """Convenience factory building an :class:`EventBus` with ``observers``."""
    bus = EventBus()
    for observer in observers or ():
        bus.subscribe(observer)
    return bus


__all__ = [
    "EventType",
    "Severity",
    "Event",
    "EventFilter",
    "EventObserver",
    "EventBus",
    "LoggingObserver",
    "WebhookObserver",
    "build_event_bus",
]
