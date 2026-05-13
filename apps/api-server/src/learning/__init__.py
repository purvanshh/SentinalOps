"""
Adaptive Operational Learning module for SentinelOps Phase 46.

Provides bounded, auditable, transparent learning from:
  - operator feedback (approvals, rejections, overrides)
  - remediation execution outcomes (success, failure, rollback)
  - recurring incident patterns
  - confidence drift tracking
  - post-execution validation
  - reasoning self-critique

Modules:
  feedback_engine        — OperatorFeedbackEngine: capture and score operator signals
  outcome_memory         — ExecutionOutcomeMemory: remediation outcome tracking
  trust_adaptation       — TrustAdaptationEngine: mechanism/remediation trust scoring
  recurrence_analyzer    — FailureRecurrenceAnalyzer: recurring pattern detection
  post_execution         — PostExecutionValidator: predicted vs actual comparison
  calibration_tracker    — ConfidenceDriftTracker: calibration drift detection
  operator_trust_model   — OperatorTrustModel: per-mechanism/remediation trust
  self_critic            — ReasoningSelfCritic: evidence weakness self-critique
  incident_evolution     — IncidentEvolutionTracker: incident progression modeling
"""
