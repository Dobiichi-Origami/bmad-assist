"""Twin provider configuration for the Digital Twin.

Defines TwinProviderConfig with provider/model/enabled/max_retries/
retry_exhausted_action/timeout, and integrates with the providers config system.
Also provides resolve_retry_mode() for auto-mode time-based selection.
"""

from __future__ import annotations

import logging
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

__all__ = ["TwinProviderConfig", "resolve_retry_mode"]

logger = logging.getLogger(__name__)


class TwinProviderConfig(BaseModel):
    """Configuration for the Digital Twin LLM provider.

    The Twin uses a separate provider/model from the main execution LLM
    to provide independent review and guidance.

    Attributes:
        provider: Provider name (e.g., "claude").
        model: Model identifier (e.g., "opus").
        enabled: Whether the Twin is active.
        max_retries: Maximum RETRY attempts before exhausting.
        retry_exhausted_action: What to do when retries are exhausted.
            "halt" stops the loop; "continue" proceeds to next phase.
        retry_mode: How the runner handles a retry decision.
            "stash_retry" performs git stash + re-execute.
            "quick_correct" re-invokes phase with correction compass without stash.
            "auto" dynamically selects based on duration_ms vs threshold.
        max_quick_corrections: Maximum quick correction cycles when retry_mode
            resolves to quick_correct. Independent of max_retries.
        retry_mode_threshold_seconds: Minimum phase duration (seconds) above
            which auto mode selects quick_correct. Only used when retry_mode="auto".
        audit_extract_model: Model for LLM-based self-audit extraction.
            None falls back to the main model.
        timeout: Timeout duration in seconds for Twin LLM provider invocations.
            Default 300s matches the provider's hardcoded DEFAULT_TIMEOUT.
    """

    model_config = ConfigDict(frozen=True)

    provider: str = Field(
        default="claude",
        description="Provider name for Twin LLM calls",
    )
    model: str = Field(
        default="opus",
        description="Model identifier for Twin LLM calls",
    )
    enabled: bool = Field(
        default=False,
        description="Whether the Digital Twin is active",
    )
    max_retries: int = Field(
        default=2,
        description="Maximum RETRY attempts before exhausting",
    )
    retry_exhausted_action: Literal["halt", "continue"] = Field(
        default="halt",
        description='Action when retries exhausted: "halt" or "continue"',
    )
    audit_extract_model: str | None = Field(
        default=None,
        description="Model for LLM-based self-audit extraction; None falls back to model",
    )
    timeout_retries: int | None = Field(
        default=2,
        description="Max timeout retry attempts for Twin LLM calls. "
        "None disables retry (first ProviderTimeoutError propagates). "
        "Separate from max_retries which controls the RETRY decision loop.",
    )
    retry_mode: Literal["stash_retry", "quick_correct", "auto"] = Field(
        default="stash_retry",
        description='Retry mode: "stash_retry" (git stash + re-execute), '
        '"quick_correct" (in-place correction without stash), '
        '"auto" (time-based dynamic selection)',
    )
    max_quick_corrections: int = Field(
        default=1,
        description="Maximum quick correction cycles when retry_mode resolves to quick_correct",
    )
    retry_mode_threshold_seconds: int = Field(
        default=120,
        description="Min phase duration (seconds) above which auto mode selects quick_correct",
    )
    timeout: int = Field(
        default=300,
        description="Timeout duration in seconds for Twin LLM calls (reflect and audit_extract)",
    )


def resolve_retry_mode(
    config: TwinProviderConfig,
    duration_ms: int,
    phase_name: str = "",
) -> Literal["stash_retry", "quick_correct"]:
    """Resolve the retry mode based on config and phase duration.

    If config.retry_mode is "auto", compares duration_ms / 1000 against
    retry_mode_threshold_seconds to select the mode. Otherwise returns
    the explicit retry_mode value.

    Args:
        config: TwinProviderConfig instance.
        duration_ms: Phase execution duration in milliseconds.
        phase_name: Phase name for logging (optional).

    Returns:
        "stash_retry" or "quick_correct".
    """
    if config.retry_mode != "auto":
        return config.retry_mode

    duration_s = duration_ms / 1000
    threshold = config.retry_mode_threshold_seconds

    if duration_s >= threshold:
        selected: Literal["stash_retry", "quick_correct"] = "quick_correct"
    else:
        selected = "stash_retry"

    logger.info(
        "auto-selected %s for phase %s (duration=%.1fs %s threshold=%ds)",
        selected,
        phase_name,
        duration_s,
        ">=" if duration_s >= threshold else "<",
        threshold,
    )

    return selected
