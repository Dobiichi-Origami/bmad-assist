"""Tests for stall detection (idle timeout) functionality.

Tests cover:
- StallDetector class: update(), is_stalled() behavior
- TimeoutsConfig.get_idle_timeout(): defaults, validation
- Claude subprocess provider stall detection integration
- Retry path: stall-triggered ProviderTimeoutError handled by invoke_with_timeout_retry
"""

import time
from subprocess import TimeoutExpired
from unittest.mock import MagicMock, patch

import pytest

from bmad_assist.core.config import (
    Config,
    MasterProviderConfig,
    ProviderConfig,
    TimeoutsConfig,
    get_phase_idle_timeout,
)
from bmad_assist.core.exceptions import ProviderTimeoutError
from bmad_assist.core.retry import invoke_with_timeout_retry
from bmad_assist.providers.base import StallDetector

from .conftest import create_mock_process


# =============================================================================
# 5.1 StallDetector unit tests
# =============================================================================


class TestStallDetector:
    """Tests for StallDetector class."""

    def test_initial_state_not_stalled(self) -> None:
        """StallDetector is not stalled immediately after creation."""
        detector = StallDetector()
        assert not detector.is_stalled(30)

    def test_update_resets_timer(self) -> None:
        """update() resets the last output time so is_stalled returns False."""
        detector = StallDetector()
        # Manually set _last_output_time to the past
        with detector._lock:
            detector._last_output_time = time.perf_counter() - 100
        assert detector.is_stalled(30)  # Should be stalled
        detector.update()
        assert not detector.is_stalled(30)  # No longer stalled after update

    def test_is_stalled_returns_true_after_timeout(self) -> None:
        """is_stalled returns True when idle time exceeds threshold."""
        detector = StallDetector()
        with detector._lock:
            detector._last_output_time = time.perf_counter() - 60
        assert detector.is_stalled(30)  # 60s idle > 30s threshold

    def test_is_stalled_returns_false_within_timeout(self) -> None:
        """is_stalled returns False when idle time is within threshold."""
        detector = StallDetector()
        # Just created, so last_output_time is ~now
        assert not detector.is_stalled(30)

    def test_is_stalled_threshold_boundary(self) -> None:
        """is_stalled correctly handles boundary values."""
        detector = StallDetector()
        # Set to exactly 30 seconds ago - should be stalled with 30s threshold
        # (uses > not >=, but we add a small margin)
        with detector._lock:
            detector._last_output_time = time.perf_counter() - 31
        assert detector.is_stalled(30)

    def test_multiple_updates(self) -> None:
        """Multiple update() calls keep the detector fresh."""
        detector = StallDetector()
        for _ in range(10):
            detector.update()
        assert not detector.is_stalled(1)


# =============================================================================
# 5.2 TimeoutsConfig.get_idle_timeout() tests
# =============================================================================


class TestIdleTimeoutConfig:
    """Tests for idle_timeout configuration."""

    def test_idle_timeout_default_is_none(self) -> None:
        """idle_timeout defaults to None (disabled)."""
        tc = TimeoutsConfig()
        assert tc.idle_timeout is None

    def test_get_idle_timeout_returns_none_by_default(self) -> None:
        """get_idle_timeout returns None when not configured."""
        tc = TimeoutsConfig()
        assert tc.get_idle_timeout("dev_story") is None
        assert tc.get_idle_timeout("validate_story") is None

    def test_idle_timeout_can_be_set(self) -> None:
        """idle_timeout can be set to a valid value."""
        tc = TimeoutsConfig(idle_timeout=180)
        assert tc.idle_timeout == 180

    def test_get_idle_timeout_returns_configured_value(self) -> None:
        """get_idle_timeout returns configured value for any phase."""
        tc = TimeoutsConfig(idle_timeout=180)
        assert tc.get_idle_timeout("dev_story") == 180
        assert tc.get_idle_timeout("validate_story") == 180

    def test_idle_timeout_minimum_validation(self) -> None:
        """idle_timeout must be >= 30 seconds."""
        with pytest.raises(ValueError):
            TimeoutsConfig(idle_timeout=10)
        with pytest.raises(ValueError):
            TimeoutsConfig(idle_timeout=29)

    def test_idle_timeout_minimum_boundary(self) -> None:
        """idle_timeout=30 is the minimum allowed value."""
        tc = TimeoutsConfig(idle_timeout=30)
        assert tc.idle_timeout == 30

    def test_get_phase_idle_timeout_with_timeouts(self) -> None:
        """get_phase_idle_timeout returns value from TimeoutsConfig."""
        tc = TimeoutsConfig(idle_timeout=120)
        config = Config(
            providers=ProviderConfig(
                master=MasterProviderConfig(provider="claude", model="opus")
            ),
            timeouts=tc,
        )
        assert get_phase_idle_timeout(config, "dev_story") == 120

    def test_get_phase_idle_timeout_without_timeouts(self) -> None:
        """get_phase_idle_timeout returns None for legacy config."""
        config = Config(
            providers=ProviderConfig(
                master=MasterProviderConfig(provider="claude", model="opus")
            ),
            timeout=300,
            timeouts=None,
        )
        assert get_phase_idle_timeout(config, "dev_story") is None


# =============================================================================
# 5.3 Claude subprocess provider stall detection integration test
# =============================================================================


class TestClaudeSubprocessStallDetection:
    """Integration test: stall detection triggers ProviderTimeoutError in Claude provider."""

    @pytest.fixture
    def provider(self):
        from bmad_assist.providers import ClaudeSubprocessProvider

        return ClaudeSubprocessProvider()

    def test_idle_timeout_triggers_provider_timeout_error(
        self, provider, accelerated_time
    ) -> None:
        """Stalling process triggers ProviderTimeoutError with idle timeout message."""
        with patch("bmad_assist.providers.claude.Popen") as mock_popen:
            mock_popen.return_value = create_mock_process(never_finish=True)

            with pytest.raises(ProviderTimeoutError, match="idle timeout"):
                provider.invoke("Hello", timeout=3600, idle_timeout=30)

    def test_no_idle_timeout_when_disabled(
        self, provider, accelerated_time
    ) -> None:
        """With idle_timeout=None, regular timeout still works (no idle detection)."""
        with patch("bmad_assist.providers.claude.Popen") as mock_popen:
            mock_popen.return_value = create_mock_process(never_finish=True)

            with pytest.raises(ProviderTimeoutError) as exc_info:
                provider.invoke("Hello", timeout=5, idle_timeout=None)

            # Should be a regular timeout, not idle timeout
            assert "idle timeout" not in str(exc_info.value).lower() or "timeout" in str(
                exc_info.value
            ).lower()


# =============================================================================
# 5.4 Retry path test
# =============================================================================


class TestStallRetryIntegration:
    """Test that stall-triggered ProviderTimeoutError is retried by invoke_with_timeout_retry."""

    def test_stall_timeout_is_retried(self) -> None:
        """ProviderTimeoutError from stall is retried by invoke_with_timeout_retry."""
        call_count = [0]

        def mock_invoke(**kwargs):
            call_count[0] += 1
            if call_count[0] <= 2:
                raise ProviderTimeoutError(
                    f"idle timeout after 30s with no output (attempt {call_count[0]})"
                )
            return "success"

        result = invoke_with_timeout_retry(
            mock_invoke,
            timeout_retries=3,
            phase_name="test_phase",
            prompt="Hello",
            timeout=60,
        )

        assert result == "success"
        assert call_count[0] == 3  # 2 failures + 1 success

    def test_stall_timeout_exhausts_retries(self) -> None:
        """ProviderTimeoutError from stall exhausts retries and re-raises."""

        def always_stall(**kwargs):
            raise ProviderTimeoutError("idle timeout after 30s with no output")

        with pytest.raises(ProviderTimeoutError, match="idle timeout"):
            invoke_with_timeout_retry(
                always_stall,
                timeout_retries=2,
                phase_name="test_phase",
                prompt="Hello",
                timeout=60,
            )

    def test_stall_timeout_no_retry_when_retries_none(self) -> None:
        """ProviderTimeoutError from stall is not retried when timeout_retries is None."""
        call_count = [0]

        def stall_once(**kwargs):
            call_count[0] += 1
            raise ProviderTimeoutError("idle timeout after 30s with no output")

        with pytest.raises(ProviderTimeoutError):
            invoke_with_timeout_retry(
                stall_once,
                timeout_retries=None,
                phase_name="test_phase",
                prompt="Hello",
                timeout=60,
            )

        assert call_count[0] == 1  # Only called once, no retry

    def test_stall_timeout_with_fallback(self) -> None:
        """Stall-triggered timeout falls back to secondary provider after retries."""
        primary_calls = [0]
        fallback_calls = [0]

        def primary_invoke(**kwargs):
            primary_calls[0] += 1
            raise ProviderTimeoutError("idle timeout after 30s")

        def fallback_invoke(**kwargs):
            fallback_calls[0] += 1
            return "fallback_result"

        result = invoke_with_timeout_retry(
            primary_invoke,
            timeout_retries=1,
            phase_name="test_phase",
            fallback_invoke_fn=fallback_invoke,
            fallback_timeout_retries=1,
            prompt="Hello",
            timeout=60,
        )

        assert result == "fallback_result"
        assert primary_calls[0] == 2  # 1 initial + 1 retry
        assert fallback_calls[0] == 1
