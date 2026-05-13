"""
Continuous evaluation runtime for SentinelOps Phase 47.

Runs evaluation loops, detects drift, and schedules replay sessions:
  continuous_evaluator    — Manages ongoing evaluation cycles
  drift_monitor           — Watches for accuracy/confidence drift
  operational_regression  — Detects and reports performance regressions
  replay_scheduler        — Schedules replay sessions based on drift signals
"""
