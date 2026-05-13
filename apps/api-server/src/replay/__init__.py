"""
Telemetry Replay module for SentinelOps Phase 47.

Provides deterministic replay of telemetry event streams:
  telemetry_replay     — ReplayEngine: seedable, pauseable, seekable
  timeline_reconstructor — Builds IncidentTimeline from event streams
  event_stream         — Reads JSON/NDJSON/gz event files
  replay_models        — TelemetryEvent, ReplaySession, IncidentTimeline
"""
