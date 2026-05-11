"""
Tests for operating mode management.
"""

import pytest

from core.resilience.operating_mode import OperatingMode, OperatingModeManager


@pytest.fixture(autouse=True)
def reset_singleton():
    """Reset the singleton between tests."""
    manager = OperatingModeManager()
    manager.reset()
    yield
    manager.reset()


class TestOperatingMode:
    def test_full_mode_properties(self):
        assert OperatingMode.FULL.allows_llm_calls is True
        assert OperatingMode.FULL.allows_automated_actions is True
        assert OperatingMode.FULL.is_degraded is False

    def test_degraded_mode_properties(self):
        assert OperatingMode.DEGRADED.allows_llm_calls is True
        assert OperatingMode.DEGRADED.allows_automated_actions is True
        assert OperatingMode.DEGRADED.is_degraded is True

    def test_local_only_mode_properties(self):
        assert OperatingMode.LOCAL_ONLY.allows_llm_calls is True
        assert OperatingMode.LOCAL_ONLY.allows_automated_actions is True
        assert OperatingMode.LOCAL_ONLY.is_degraded is True

    def test_safe_mode_properties(self):
        assert OperatingMode.SAFE_MODE.allows_llm_calls is False
        assert OperatingMode.SAFE_MODE.allows_automated_actions is True
        assert OperatingMode.SAFE_MODE.is_degraded is True

    def test_observe_only_mode_properties(self):
        assert OperatingMode.OBSERVE_ONLY.allows_llm_calls is False
        assert OperatingMode.OBSERVE_ONLY.allows_automated_actions is False
        assert OperatingMode.OBSERVE_ONLY.is_degraded is True


class TestOperatingModeManager:
    def test_starts_in_full_mode(self):
        manager = OperatingModeManager()
        assert manager.current_mode == OperatingMode.FULL

    def test_transition_to_degraded(self):
        manager = OperatingModeManager()
        manager.transition_to(OperatingMode.DEGRADED, "test reason")
        assert manager.current_mode == OperatingMode.DEGRADED
        assert len(manager.transitions) == 1
        assert manager.transitions[0].reason == "test reason"

    def test_no_op_transition_to_same_mode(self):
        manager = OperatingModeManager()
        manager.transition_to(OperatingMode.FULL, "no change")
        assert len(manager.transitions) == 0

    def test_on_provider_failure_layer_1(self):
        manager = OperatingModeManager()
        manager.on_provider_failure("openai", layer=1)
        assert manager.current_mode == OperatingMode.DEGRADED

    def test_on_provider_failure_layer_2(self):
        manager = OperatingModeManager()
        manager.on_provider_failure("openai", layer=1)
        manager.on_provider_failure("anthropic", layer=2)
        assert manager.current_mode == OperatingMode.LOCAL_ONLY

    def test_on_provider_failure_layer_3(self):
        manager = OperatingModeManager()
        manager.on_provider_failure("openai", layer=1)
        manager.on_provider_failure("anthropic", layer=2)
        manager.on_provider_failure("ollama", layer=3)
        assert manager.current_mode == OperatingMode.SAFE_MODE

    def test_on_provider_recovery(self):
        manager = OperatingModeManager()
        manager.on_provider_failure("openai", layer=1)
        assert manager.current_mode == OperatingMode.DEGRADED
        manager.on_provider_recovery("openai", layer=1)
        assert manager.current_mode == OperatingMode.FULL

    def test_to_dict(self):
        manager = OperatingModeManager()
        info = manager.to_dict()
        assert info["current_mode"] == "FULL"
        assert info["is_degraded"] is False
        assert info["allows_llm_calls"] is True
