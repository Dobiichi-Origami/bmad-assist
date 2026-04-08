"""E2E tests for phase failure scenarios.

Task 3: Verify that phase failures trigger guardian halt, prevent subsequent
story execution, and correctly reflect failure position in state.
"""

from __future__ import annotations

from tests.e2e.mock_loop.helpers import (
    MockProject,
    ScriptedPhaseExecutor,
    create_mock_project,
    run_mock_loop,
    assert_stories_completed,
)
from bmad_assist.core.loop.types import LoopExitReason, PhaseResult
from bmad_assist.core.state import Phase, State


# ---- Task 3.1 ----


def test_dev_story_failure_triggers_guardian_halt(single_story_project: MockProject) -> None:
    """DEV_STORY failure triggers guardian halt and state reflects the failed phase."""
    executor = ScriptedPhaseExecutor(script={
        (1, "1.1", Phase.DEV_STORY): PhaseResult.fail("dev failed"),
    })

    result = run_mock_loop(single_story_project, executor)

    assert result.exit_reason == LoopExitReason.GUARDIAN_HALT
    assert result.final_state.current_epic == 1
    assert result.final_state.current_story == "1.1"
    assert result.final_state.current_phase == Phase.DEV_STORY


# ---- Task 3.2 ----


def test_create_story_failure_triggers_guardian_halt(single_story_project: MockProject) -> None:
    """CREATE_STORY failure triggers guardian halt."""
    executor = ScriptedPhaseExecutor(script={
        (1, "1.1", Phase.CREATE_STORY): PhaseResult.fail("create failed"),
    })

    result = run_mock_loop(single_story_project, executor)

    assert result.exit_reason == LoopExitReason.GUARDIAN_HALT
    assert result.final_state.current_epic == 1
    assert result.final_state.current_story == "1.1"
    assert result.final_state.current_phase == Phase.CREATE_STORY


# ---- Task 3.3 ----


def test_failure_recorded_in_state(single_story_project: MockProject) -> None:
    """After a failure, state position reflects the failure point."""
    executor = ScriptedPhaseExecutor(script={
        (1, "1.1", Phase.DEV_STORY): PhaseResult.fail("dev failed"),
    })

    result = run_mock_loop(single_story_project, executor)

    assert result.exit_reason == LoopExitReason.GUARDIAN_HALT
    # State retains the failed phase position for resume
    assert result.final_state.current_epic == 1
    assert result.final_state.current_story == "1.1"
    assert result.final_state.current_phase == Phase.DEV_STORY
    # Story was not completed
    assert_stories_completed(result.final_state, [])


# ---- Task 3.4 ----


def test_first_story_fails_subsequent_skipped(three_story_project: MockProject) -> None:
    """When the first story fails, subsequent stories are never executed."""
    executor = ScriptedPhaseExecutor(script={
        (1, "1.1", Phase.DEV_STORY): PhaseResult.fail("dev failed"),
    })

    result = run_mock_loop(three_story_project, executor)

    assert result.exit_reason == LoopExitReason.GUARDIAN_HALT

    # Stories 1.2 and 1.3 should never have been invoked
    stories_invoked = {inv[1] for inv in executor.invocations}
    assert "1.2" not in stories_invoked, "Story 1.2 should not have been invoked after 1.1 failure"
    assert "1.3" not in stories_invoked, "Story 1.3 should not have been invoked after 1.1 failure"

    # No stories completed since 1.1 failed mid-way
    assert_stories_completed(result.final_state, [])
