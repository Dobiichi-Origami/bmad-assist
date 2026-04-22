"""Type definitions for the loop package.

Story 6.1: PhaseResult, PhaseHandler, WORKFLOW_HANDLERS, get_handler().
Story 6.5: GuardianDecision enum.
Story 6.6: LoopExitReason enum.

"""

from collections.abc import Callable
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, TypeAlias, TypedDict

from bmad_assist.core.state import Phase, State
from bmad_assist.core.types import EpicId

__all__ = [
    "LoopExitReason",
    "LoopStatus",
    "GuardianDecision",
    "PhaseResult",
    "PhaseHandler",
]


# =============================================================================
# LoopExitReason Enum - Story 6.6
# =============================================================================


class LoopExitReason(str, Enum):
    """Reason for run_loop() exit - caller uses this to determine exit code.

    This enum is returned by run_loop() and tells the CLI layer how to exit.
    The CLI layer handles sys.exit() based on these values.

    Attributes:
        COMPLETED: Normal completion - project finished (exit code 0).
        INTERRUPTED_SIGINT: Loop interrupted by SIGINT/Ctrl+C (exit code 130).
        INTERRUPTED_SIGTERM: Loop interrupted by SIGTERM/kill (exit code 143).
        GUARDIAN_HALT: Loop halted by Guardian for user intervention (exit code 0).
        CANCELLED: Loop cancelled via CancellationContext (dashboard stop).
        ERROR: Loop crashed due to unhandled exception (exit code 1).

    """

    COMPLETED = "completed"
    INTERRUPTED_SIGINT = "interrupted_sigint"
    INTERRUPTED_SIGTERM = "interrupted_sigterm"
    GUARDIAN_HALT = "guardian_halt"
    CANCELLED = "cancelled"
    ERROR = "error"


# =============================================================================
# LoopStatus TypedDict - Dashboard Integration
# =============================================================================


class LoopStatus(TypedDict):
    """Status returned by LoopController.get_status().

    Used by REST API /api/loop/status endpoint to report loop state.

    Attributes:
        state: Current controller state ("idle", "starting", "running", "paused", "stopping").
        running: True if loop is actively running (starting or running state).
        paused: True if loop is paused (waiting for resume).
        current_epic: Current epic ID or None if not running.
        current_story: Current story ID or None if not running.
        current_phase: Current phase name or None if not running.
        error: Last error message if failed, None otherwise.

    """

    state: str
    running: bool
    paused: bool
    current_epic: EpicId | None
    current_story: str | None
    current_phase: str | None
    error: str | None


# =============================================================================
# GuardianDecision Enum - Story 6.5 (Code Review Fix)
# =============================================================================


class GuardianDecision(str, Enum):
    """Guardian anomaly detection decisions.

    str subclass for backward compatibility with string comparisons.
    """

    CONTINUE = "continue"
    HALT = "halt"
    # RETRY = "retry"  # Future Epic 8


# =============================================================================
# PhaseResult - Story 6.1
# =============================================================================


@dataclass(frozen=True)
class PhaseResult:
    """Result of executing a workflow phase handler.

    Captures the outcome of a phase execution including success status,
    optional next phase override, error information, and phase-specific outputs.

    Attributes:
        success: True if phase completed successfully.
        next_phase: Explicit next phase override, or None for default progression.
        error: Error message if success=False, None otherwise.
        outputs: Phase-specific outputs (file paths, reports, etc.).

    Example:
        >>> result = PhaseResult.ok({"report": "validation.md"})
        >>> result.success
        True

        >>> result = PhaseResult.fail("Validation failed")
        >>> result.error
        'Validation failed'

    """

    success: bool
    next_phase: Phase | None = None
    error: str | None = None
    outputs: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def ok(cls, outputs: dict[str, Any] | None = None, *, response: str | None = None, **kwargs: Any) -> "PhaseResult":
        """Create a successful phase result.

        Args:
            outputs: Optional phase-specific outputs. Defaults to empty dict.
            response: Optional primary LLM response content.
            **kwargs: Additional outputs to merge.

        Returns:
            PhaseResult with success=True and provided outputs.

        Example:
            >>> result = PhaseResult.ok({"file": "story.md"})
            >>> result.success
            True

        """
        merged = dict(outputs) if outputs is not None else {}
        if response is not None:
            merged["response"] = response
        merged.update(kwargs)
        return cls(success=True, outputs=merged)

    @classmethod
    def fail(cls, error: str) -> "PhaseResult":
        """Create a failed phase result.

        Args:
            error: Error message describing the failure.

        Returns:
            PhaseResult with success=False and error message.

        Example:
            >>> result = PhaseResult.fail("Something went wrong")
            >>> result.error
            'Something went wrong'

        """
        return cls(success=False, error=error)


# =============================================================================
# PhaseHandler Type Alias - Story 6.1
# =============================================================================

# PhaseHandler is a callable that receives State and returns PhaseResult.
# Handlers must not raise exceptions - they should return PhaseResult.fail() on error.
# The handler contract:
#   - Input: Current State with loop position information
#   - Output: PhaseResult indicating success/failure and any outputs
#   - Side effects: May invoke LLM providers, write files, update state
PhaseHandler: TypeAlias = Callable[[State], PhaseResult]
