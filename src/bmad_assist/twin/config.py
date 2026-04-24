"""Twin provider configuration for the Digital Twin.

Defines TwinProviderConfig with provider/model/enabled/max_retries/
retry_exhausted_action, and integrates with the providers config system.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

__all__ = ["TwinProviderConfig"]


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
        audit_extract_model: Model for LLM-based self-audit extraction.
            None falls back to the main model.
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
