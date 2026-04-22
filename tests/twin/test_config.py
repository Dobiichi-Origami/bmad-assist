"""Tests for TwinProviderConfig validation."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from bmad_assist.twin.config import TwinProviderConfig


class TestTwinProviderConfigDefaults:
    """Verify default values of TwinProviderConfig."""

    def test_default_provider(self) -> None:
        """Default provider is 'claude'."""
        config = TwinProviderConfig()
        assert config.provider == "claude"

    def test_default_model(self) -> None:
        """Default model is 'opus'."""
        config = TwinProviderConfig()
        assert config.model == "opus"

    def test_default_enabled(self) -> None:
        """Default enabled is True."""
        config = TwinProviderConfig()
        assert config.enabled is True

    def test_default_max_retries(self) -> None:
        """Default max_retries is 2."""
        config = TwinProviderConfig()
        assert config.max_retries == 2

    def test_default_retry_exhausted_action(self) -> None:
        """Default retry_exhausted_action is 'halt'."""
        config = TwinProviderConfig()
        assert config.retry_exhausted_action == "halt"


class TestTwinProviderConfigValidation:
    """Verify TwinProviderConfig validation rules."""

    def test_invalid_retry_exhausted_action(self) -> None:
        """retry_exhausted_action must be 'halt' or 'continue'."""
        with pytest.raises(ValidationError, match="retry_exhausted_action"):
            TwinProviderConfig(retry_exhausted_action="skip")

    def test_frozen_model(self) -> None:
        """Config is frozen (immutable)."""
        config = TwinProviderConfig()
        with pytest.raises(ValidationError, match="frozen"):
            config.provider = "openai"  # type: ignore[misc]

    def test_custom_values(self) -> None:
        """Custom values are accepted."""
        config = TwinProviderConfig(
            provider="openai",
            model="gpt-4",
            enabled=False,
            max_retries=5,
            retry_exhausted_action="continue",
        )
        assert config.provider == "openai"
        assert config.model == "gpt-4"
        assert config.enabled is False
        assert config.max_retries == 5
        assert config.retry_exhausted_action == "continue"
