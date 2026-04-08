"""E2E tests for signal handling and cancellation in the mock loop.

Tasks 3.9-3.12: Verify that SIGINT, SIGTERM, and CancellationContext
cause the loop to exit gracefully at phase boundaries with correct
exit reasons, and that state is saved before exit.
"""

from __future__ import annotations

import signal

import pytest

from tests.e2e.mock_loop.helpers import (
    MockProject,
    ScriptedPhaseExecutor,
    create_mock_project,
    run_mock_loop,
)
from bmad_assist.core.loop.cancellation import CancellationContext
from bmad_assist.core.loop.signals import request_shutdown, reset_shutdown
from bmad_assist.core.loop.types import LoopExitReason, PhaseResult
from bmad_assist.core.state import Phase, State


# ---------------------------------------------------------------------------
# Fixture: reset shutdown state before/after each test
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def reset_shutdown_state():
    """Reset shutdown state before and after each test.

    The autouse fixture in tests/core/loop/conftest.py does not apply here
    because we are in tests/e2e/mock_loop/, so we provide our own.
    """
    reset_shutdown()
    yield
    reset_shutdown()


def _make_initial_state(epic: int = 1, story: str = "1.1") -> State:
    """Create an initial State positioned at CREATE_STORY for the given epic/story."""
    return State(
        current_epic=epic,
        current_story=story,
        current_phase=Phase.CREATE_STORY,
    )


# ---------------------------------------------------------------------------
# Task 3.9: SIGINT graceful exit
# ---------------------------------------------------------------------------


def test_sigint_graceful_exit(tmp_path: object) -> None:
    """After request_shutdown(SIGINT) during a phase, the loop exits with INTERRUPTED_SIGINT.

    The on_call callback fires request_shutdown after DEV_STORY (call 4).
    The loop detects the shutdown flag before executing the next phase and
    returns INTERRUPTED_SIGINT.
    """
    project = create_mock_project(
        tmp_path,  # type: ignore[arg-type]
        epics=[{"id": 1, "stories": ["1.1"]}],
    )

    call_count = 0

    def trigger_sigint(state: State, executor: ScriptedPhaseExecutor) -> None:
        nonlocal call_count
        call_count += 1
        if call_count == 4:  # After DEV_STORY
            request_shutdown(signal.SIGINT)

    executor = ScriptedPhaseExecutor(on_call=trigger_sigint)
    result = run_mock_loop(
        project, executor, initial_state=_make_initial_state(),
    )

    assert result.exit_reason is LoopExitReason.INTERRUPTED_SIGINT
    # The loop should have executed exactly 4 phases before stopping
    assert len(executor.invocations) == 4
    assert executor.phases_called[-1] is Phase.DEV_STORY


# ---------------------------------------------------------------------------
# Task 3.10: SIGTERM graceful exit
# ---------------------------------------------------------------------------


def test_sigterm_graceful_exit(tmp_path: object) -> None:
    """After request_shutdown(SIGTERM) during a phase, the loop exits with INTERRUPTED_SIGTERM."""
    project = create_mock_project(
        tmp_path,  # type: ignore[arg-type]
        epics=[{"id": 1, "stories": ["1.1"]}],
    )

    call_count = 0

    def trigger_sigterm(state: State, executor: ScriptedPhaseExecutor) -> None:
        nonlocal call_count
        call_count += 1
        if call_count == 4:  # After DEV_STORY
            request_shutdown(signal.SIGTERM)

    executor = ScriptedPhaseExecutor(on_call=trigger_sigterm)
    result = run_mock_loop(
        project, executor, initial_state=_make_initial_state(),
    )

    assert result.exit_reason is LoopExitReason.INTERRUPTED_SIGTERM
    assert len(executor.invocations) == 4
    assert executor.phases_called[-1] is Phase.DEV_STORY


# ---------------------------------------------------------------------------
# Task 3.11: State saved before signal exit
# ---------------------------------------------------------------------------


def test_state_saved_before_signal_exit(tmp_path: object) -> None:
    """After signal exit, the final_state reflects the position at shutdown time.

    The loop saves state after each successful phase execution, so the
    captured final_state should show the phase that was executing when
    the shutdown was requested.
    """
    project = create_mock_project(
        tmp_path,  # type: ignore[arg-type]
        epics=[{"id": 1, "stories": ["1.1"]}],
    )

    call_count = 0

    def trigger_sigint(state: State, executor: ScriptedPhaseExecutor) -> None:
        nonlocal call_count
        call_count += 1
        if call_count == 4:  # After DEV_STORY
            request_shutdown(signal.SIGINT)

    executor = ScriptedPhaseExecutor(on_call=trigger_sigint)
    result = run_mock_loop(
        project, executor, initial_state=_make_initial_state(),
    )

    assert result.exit_reason is LoopExitReason.INTERRUPTED_SIGINT

    # State was saved -- final_state should be non-empty
    final = result.final_state
    assert final is not None

    # The state should reflect the current epic/story that was being processed
    assert final.current_epic == 1
    assert final.current_story == "1.1"


# ---------------------------------------------------------------------------
# Task 3.12: CancellationContext exit
# ---------------------------------------------------------------------------


def test_cancellation_context_exit(tmp_path: object) -> None:
    """CancellationContext.request_cancel() causes CANCELLED exit at next phase boundary."""
    project = create_mock_project(
        tmp_path,  # type: ignore[arg-type]
        epics=[{"id": 1, "stories": ["1.1"]}],
    )

    cancel_ctx = CancellationContext()

    call_count = 0

    def trigger_cancel(state: State, executor: ScriptedPhaseExecutor) -> None:
        nonlocal call_count
        call_count += 1
        if call_count == 4:  # After DEV_STORY
            cancel_ctx.request_cancel()

    executor = ScriptedPhaseExecutor(on_call=trigger_cancel)
    result = run_mock_loop(
        project, executor, initial_state=_make_initial_state(),
        cancel_ctx=cancel_ctx,
    )

    assert result.exit_reason is LoopExitReason.CANCELLED
    assert len(executor.invocations) == 4
    assert executor.phases_called[-1] is Phase.DEV_STORY
