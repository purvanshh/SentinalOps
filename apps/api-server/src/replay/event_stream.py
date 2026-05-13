"""
Event stream reader for SentinelOps Phase 47 replay.

Reads TelemetryEvent records from:
  - JSON list files
  - NDJSON (newline-delimited JSON) files
  - Gzip-compressed archives of either format

Guarantees deterministic ordering: events are sorted by
(timestamp_iso, sequence_number, event_id) to resolve ties.

All malformed events are quarantined rather than dropped silently.
"""

from __future__ import annotations

import gzip
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from replay.replay_models import EventKind, TelemetryEvent


@dataclass
class ParseError:
    """A quarantined event that could not be parsed."""

    raw: str
    reason: str
    line_number: int


@dataclass
class StreamReadResult:
    """Result of reading an event stream from a source."""

    events: list[TelemetryEvent]
    quarantined: list[ParseError]
    source_path: str
    format_detected: str  # "json", "ndjson", "json.gz", "ndjson.gz"

    @property
    def total_attempted(self) -> int:
        return len(self.events) + len(self.quarantined)

    @property
    def parse_success_rate(self) -> float:
        if self.total_attempted == 0:
            return 1.0
        return round(len(self.events) / self.total_attempted, 4)


def _parse_event(raw: dict[str, Any], line_num: int) -> TelemetryEvent | ParseError:
    """Parse a raw dict into a TelemetryEvent or a ParseError."""
    try:
        kind_str = raw.get("kind", "")
        try:
            kind = EventKind(kind_str)
        except ValueError:
            kind = EventKind.LOG

        return TelemetryEvent(
            event_id=str(raw.get("event_id", f"auto_{line_num}")),
            kind=kind,
            timestamp_iso=str(raw.get("timestamp_iso", raw.get("timestamp", ""))),
            service=str(raw.get("service", "")),
            payload=raw.get("payload", {}),
            source=str(raw.get("source", "")),
            severity=str(raw.get("severity", "info")),
            labels=raw.get("labels", {}),
            incident_id=raw.get("incident_id"),
            sequence_number=int(raw.get("sequence_number", line_num)),
        )
    except Exception as exc:
        return ParseError(
            raw=json.dumps(raw)[:200],
            reason=str(exc),
            line_number=line_num,
        )


def _sort_events(events: list[TelemetryEvent]) -> list[TelemetryEvent]:
    """Sort events deterministically: timestamp, then sequence_number, then event_id."""
    return sorted(events, key=lambda e: (e.timestamp_iso, e.sequence_number, e.event_id))


def read_from_path(path: str | Path) -> StreamReadResult:
    """
    Read a TelemetryEvent stream from a file path.

    Supports: .json, .ndjson, .json.gz, .ndjson.gz
    """
    p = Path(path)
    name = p.name.lower()

    if name.endswith(".json.gz") or name.endswith(".ndjson.gz"):
        opener = gzip.open
        is_ndjson = name.endswith(".ndjson.gz")
    else:
        opener = open  # type: ignore[assignment]
        is_ndjson = name.endswith(".ndjson")

    format_name = (
        ("ndjson.gz" if is_ndjson else "json.gz")
        if ".gz" in name
        else ("ndjson" if is_ndjson else "json")
    )

    events: list[TelemetryEvent] = []
    quarantined: list[ParseError] = []

    with opener(p, "rt", encoding="utf-8") as fh:
        content = fh.read()

    if is_ndjson:
        for line_num, line in enumerate(content.splitlines(), start=1):
            line = line.strip()
            if not line:
                continue
            try:
                raw = json.loads(line)
                result = _parse_event(raw, line_num)
            except json.JSONDecodeError as exc:
                result = ParseError(raw=line[:200], reason=str(exc), line_number=line_num)

            if isinstance(result, TelemetryEvent):
                events.append(result)
            else:
                quarantined.append(result)
    else:
        try:
            data = json.loads(content)
        except json.JSONDecodeError as exc:
            return StreamReadResult(
                events=[],
                quarantined=[ParseError(raw=content[:200], reason=str(exc), line_number=0)],
                source_path=str(path),
                format_detected=format_name,
            )
        if not isinstance(data, list):
            data = [data]
        for line_num, raw in enumerate(data, start=1):
            if not isinstance(raw, dict):
                quarantined.append(
                    ParseError(
                        raw=str(raw)[:200],
                        reason="expected dict",
                        line_number=line_num,
                    )
                )
                continue
            result = _parse_event(raw, line_num)
            if isinstance(result, TelemetryEvent):
                events.append(result)
            else:
                quarantined.append(result)

    return StreamReadResult(
        events=_sort_events(events),
        quarantined=quarantined,
        source_path=str(path),
        format_detected=format_name,
    )


def read_from_list(raw_events: list[dict[str, Any]]) -> StreamReadResult:
    """Read a TelemetryEvent stream from an in-memory list of dicts."""
    events: list[TelemetryEvent] = []
    quarantined: list[ParseError] = []
    for line_num, raw in enumerate(raw_events, start=1):
        result = _parse_event(raw, line_num)
        if isinstance(result, TelemetryEvent):
            events.append(result)
        else:
            quarantined.append(result)
    return StreamReadResult(
        events=_sort_events(events),
        quarantined=quarantined,
        source_path="<memory>",
        format_detected="json",
    )
