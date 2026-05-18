"""Evaluation reproducibility layer — deterministic replay, fingerprinting, and drift detection."""

from .dataset_fingerprint import DatasetFingerprint, FingerprintRecord
from .deterministic_runtime import DeterministicRuntime, RuntimeSeed
from .environment_validator import EnvironmentReport, EnvironmentValidator
from .replay_consistency import ConsistencyResult, ReplayConsistencyChecker
from .replay_manifest import ManifestEntry, ReplayManifest

__all__ = [
    "DatasetFingerprint",
    "FingerprintRecord",
    "DeterministicRuntime",
    "RuntimeSeed",
    "EnvironmentValidator",
    "EnvironmentReport",
    "ReplayConsistencyChecker",
    "ConsistencyResult",
    "ReplayManifest",
    "ManifestEntry",
]
