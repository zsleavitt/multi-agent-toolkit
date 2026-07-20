"""Tests for the Hive/Swarm observability event system (MAT-52)."""

from __future__ import annotations

import logging
from unittest.mock import MagicMock, patch

import pytest

from mat_runtime.hive.events import (
    Event,
    EventBus,
    EventFilter,
    EventType,
    LoggingObserver,
    Severity,
    WebhookObserver,
    build_event_bus,
)


def _event(
    event_type: EventType = EventType.CREW_STARTED,
    *,
    severity: Severity = Severity.INFO,
    crew: str | None = None,
    correlation_id: str = "corr-1",
) -> Event:
    return Event(
        event_type=event_type,
        correlation_id=correlation_id,
        severity=severity,
        crew=crew,
    )


class _RecordingObserver:
    def __init__(self) -> None:
        self.events: list[Event] = []

    def handle(self, event: Event) -> None:
        self.events.append(event)


class TestEvent:
    def test_to_dict_is_json_safe(self) -> None:
        import json

        event = _event(EventType.CREW_COMPLETED, crew="dev-crew")
        event.duration_ms = 42
        event.outcome = {"ok": True}
        payload = event.to_dict()

        # Round-trips through JSON without error.
        restored = json.loads(json.dumps(payload))
        assert restored["event_type"] == "crew_completed"
        assert restored["severity"] == "info"
        assert restored["crew"] == "dev-crew"
        assert restored["duration_ms"] == 42
        assert restored["outcome"] == {"ok": True}
        assert "timestamp_iso" in restored


class TestEventBus:
    def test_emit_delivers_to_all_observers(self) -> None:
        bus = EventBus()
        obs_a = _RecordingObserver()
        obs_b = _RecordingObserver()
        bus.subscribe(obs_a)
        bus.subscribe(obs_b)

        event = _event()
        bus.emit(event)

        assert obs_a.events == [event]
        assert obs_b.events == [event]

    def test_unsubscribe_stops_delivery(self) -> None:
        bus = EventBus()
        obs = _RecordingObserver()
        bus.subscribe(obs)
        bus.unsubscribe(obs)

        bus.emit(_event())

        assert obs.events == []

    def test_observer_exception_does_not_break_emit(self) -> None:
        bus = EventBus()
        good = _RecordingObserver()

        broken = MagicMock()
        broken.handle.side_effect = RuntimeError("boom")

        bus.subscribe(broken)
        bus.subscribe(good)

        # Should not raise even though the first observer explodes.
        bus.emit(_event())

        assert len(good.events) == 1
        broken.handle.assert_called_once()

    def test_build_event_bus_registers_observers(self) -> None:
        obs = _RecordingObserver()
        bus = build_event_bus([obs])
        bus.emit(_event())
        assert len(obs.events) == 1


class TestEventFilter:
    def test_filter_by_event_type(self) -> None:
        bus = EventBus()
        obs = _RecordingObserver()
        bus.subscribe(
            obs,
            event_filter=EventFilter(event_types={EventType.CREW_COMPLETED}),
        )

        bus.emit(_event(EventType.CREW_STARTED))
        bus.emit(_event(EventType.CREW_COMPLETED))

        assert [e.event_type for e in obs.events] == [EventType.CREW_COMPLETED]

    def test_filter_by_crew(self) -> None:
        bus = EventBus()
        obs = _RecordingObserver()
        bus.subscribe(obs, event_filter=EventFilter(crews={"review-crew"}))

        bus.emit(_event(crew="dev-crew"))
        bus.emit(_event(crew="review-crew"))
        bus.emit(_event(crew=None))

        assert [e.crew for e in obs.events] == ["review-crew"]

    def test_filter_by_min_severity(self) -> None:
        bus = EventBus()
        obs = _RecordingObserver()
        bus.subscribe(obs, event_filter=EventFilter(min_severity=Severity.WARNING))

        bus.emit(_event(severity=Severity.INFO))
        bus.emit(_event(severity=Severity.WARNING))
        bus.emit(_event(severity=Severity.ERROR))

        assert [e.severity for e in obs.events] == [
            Severity.WARNING,
            Severity.ERROR,
        ]

    def test_combined_filters_are_anded(self) -> None:
        bus = EventBus()
        obs = _RecordingObserver()
        bus.subscribe(
            obs,
            event_filter=EventFilter(
                event_types={EventType.CREW_COMPLETED},
                crews={"dev-crew"},
                min_severity=Severity.ERROR,
            ),
        )

        # Wrong severity.
        bus.emit(_event(EventType.CREW_COMPLETED, crew="dev-crew"))
        # Wrong crew.
        bus.emit(
            _event(EventType.CREW_COMPLETED, crew="other", severity=Severity.ERROR)
        )
        # Matches all three constraints.
        match = _event(
            EventType.CREW_COMPLETED, crew="dev-crew", severity=Severity.ERROR
        )
        bus.emit(match)

        assert obs.events == [match]


class TestLoggingObserver:
    def test_logs_event_at_severity_level(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        observer = LoggingObserver("mat_runtime.hive.events.test")
        event = _event(EventType.CREW_COMPLETED, severity=Severity.ERROR, crew="dev")

        with caplog.at_level(logging.INFO, logger="mat_runtime.hive.events.test"):
            observer.handle(event)

        assert len(caplog.records) == 1
        record = caplog.records[0]
        assert record.levelno == logging.ERROR
        assert record.mat_event["event_type"] == "crew_completed"
        assert record.mat_event["crew"] == "dev"

    def test_accepts_logger_instance(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        logger = logging.getLogger("mat_runtime.hive.events.custom")
        observer = LoggingObserver(logger)

        with caplog.at_level(logging.INFO, logger="mat_runtime.hive.events.custom"):
            observer.handle(_event())

        assert len(caplog.records) == 1


class TestWebhookObserver:
    def test_posts_json_payload_synchronously(self) -> None:
        observer = WebhookObserver("https://example.test/hook", background=False)
        event = _event(EventType.SWARM_CONSENSUS_REACHED)

        with patch("urllib.request.urlopen") as mock_urlopen:
            mock_urlopen.return_value.__enter__ = lambda s: s
            mock_urlopen.return_value.__exit__ = lambda s, *a: False
            observer.handle(event)

        assert mock_urlopen.call_count == 1
        request = mock_urlopen.call_args.args[0]
        assert request.full_url == "https://example.test/hook"
        assert request.method == "POST"
        assert request.get_header("Content-type") == "application/json"

        import json

        body = json.loads(request.data.decode("utf-8"))
        assert body["event_type"] == "swarm_consensus_reached"

    def test_delivery_failure_is_swallowed(self) -> None:
        observer = WebhookObserver("https://example.test/hook", background=False)

        with patch("urllib.request.urlopen", side_effect=OSError("network down")):
            # Best-effort delivery: must not raise.
            observer.handle(_event())

    def test_background_delivery_uses_thread(self) -> None:
        observer = WebhookObserver("https://example.test/hook", background=True)

        with patch("threading.Thread") as mock_thread:
            observer.handle(_event())

        mock_thread.assert_called_once()
        mock_thread.return_value.start.assert_called_once()
