"""E2E tests for single-story flow through the mock loop."""

from __future__ import annotations

from tests.e2e.mock_loop.helpers import (
    MockProject,
    ScriptedPhaseExecutor,
    create_mock_project,
    run_mock_loop,
    assert_stories_completed,
    assert_epics_completed,
    assert_phase_order,
)
from bmad_assist.core.loop.types import LoopExitReason, PhaseResult
from bmad_assist.core.state import Phase, State


# ---------------------------------------------------------------------------
# Task 2.1: Single story completes the full phase pipeline
# ---------------------------------------------------------------------------


def test_single_story_complete_flow(tmp_path: object) -> None:
    """Single epic, single story runs all story phases + retrospective and completes."""
    project = create_mock_project(tmp_path, epics=[{"id": 1, "stories": ["1.1"]}])  # type: ignore[arg-type]
    executor = ScriptedPhaseExecutor()

    result = run_mock_loop(project, executor)

    # Loop should exit with COMPLETED
    assert result.exit_reason is LoopExitReason.COMPLETED

    # Phase order: all story phases then epic teardown (retrospective)
    expected_phases = [
        Phase.CREATE_STORY,
        Phase.VALIDATE_STORY,
        Phase.VALIDATE_STORY_SYNTHESIS,
        Phase.DEV_STORY,
        Phase.CODE_REVIEW,
        Phase.CODE_REVIEW_SYNTHESIS,
        Phase.RETROSPECTIVE,
    ]
    assert_phase_order(executor, expected_phases)

    # Story 1.1 should be completed
    assert_stories_completed(result.final_state, ["1.1"])

    # Epic 1 should be completed
    assert_epics_completed(result.final_state, [1])


# ---------------------------------------------------------------------------
# Task 2.2: State is persisted to disk after completion
# ---------------------------------------------------------------------------


def test_state_persisted_after_completion(tmp_path: object) -> None:
    """After single-story flow completes, state.yaml exists on disk with completed data."""
    project = create_mock_project(tmp_path, epics=[{"id": 1, "stories": ["1.1"]}])  # type: ignore[arg-type]
    executor = ScriptedPhaseExecutor()

    result = run_mock_loop(project, executor)

    # Verify the loop completed successfully
    assert result.exit_reason is LoopExitReason.COMPLETED

    # Verify state.yaml exists on disk at the expected path
    from bmad_assist.core.state import load_state, get_state_path

    state_path = project.project_path / ".bmad-assist" / "state.yaml"
    assert state_path.exists(), f"state.yaml should exist at {state_path}"

    # Load the persisted state and verify it contains completed data
    persisted_state = load_state(state_path)
    assert "1.1" in persisted_state.completed_stories, (
        f"Persisted state should contain story 1.1 in completed_stories, "
        f"got: {persisted_state.completed_stories}"
    )
    assert 1 in persisted_state.completed_epics, (
        f"Persisted state should contain epic 1 in completed_epics, "
        f"got: {persisted_state.completed_epics}"
    )
