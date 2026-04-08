"""Multi-story E2E flow tests (Tasks 2.3, 2.4, 2.5).

Validates that the loop correctly sequences phases across multiple stories
within an epic, runs RETROSPECTIVE once at the end, and resumes correctly
when stories have already been completed.
"""

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

# Phase sequence every story goes through (from DEFAULT_LOOP_CONFIG)
STORY_PHASES = [
    Phase.CREATE_STORY,
    Phase.VALIDATE_STORY,
    Phase.VALIDATE_STORY_SYNTHESIS,
    Phase.DEV_STORY,
    Phase.CODE_REVIEW,
    Phase.CODE_REVIEW_SYNTHESIS,
]


class TestTwoStoriesSequential:
    """Task 2.3: One epic with two stories completes both in order."""

    def test_two_stories_sequential(self, two_story_project: MockProject) -> None:
        executor = ScriptedPhaseExecutor()
        result = run_mock_loop(two_story_project, executor)

        # Loop should complete successfully
        assert result.exit_reason == LoopExitReason.COMPLETED

        # Both stories should be marked completed
        assert_stories_completed(result.final_state, ["1.1", "1.2"])

        # Epic 1 should be completed
        assert_epics_completed(result.final_state, [1])

        # Phase order: all story phases for 1.1, then all for 1.2, then RETROSPECTIVE once
        expected_phases = (
            STORY_PHASES  # story 1.1
            + STORY_PHASES  # story 1.2
            + [Phase.RETROSPECTIVE]  # epic teardown (once)
        )
        assert_phase_order(executor, expected_phases)


class TestThreeStoriesCorrectPhaseSequences:
    """Task 2.4: One epic with three stories gets correct phase sequences."""

    def test_three_stories_correct_phase_sequences(
        self, three_story_project: MockProject
    ) -> None:
        executor = ScriptedPhaseExecutor()
        result = run_mock_loop(three_story_project, executor)

        # Loop should complete successfully
        assert result.exit_reason == LoopExitReason.COMPLETED

        # All three stories should be marked completed
        assert_stories_completed(result.final_state, ["1.1", "1.2", "1.3"])

        # Epic 1 should be completed
        assert_epics_completed(result.final_state, [1])

        # Each story gets the full phase sequence, RETROSPECTIVE once at the end
        expected_phases = (
            STORY_PHASES  # story 1.1
            + STORY_PHASES  # story 1.2
            + STORY_PHASES  # story 1.3
            + [Phase.RETROSPECTIVE]  # epic teardown (once)
        )
        assert_phase_order(executor, expected_phases)


class TestCompletedStoriesSkippedOnResume:
    """Task 2.5: Resuming with a completed story skips it entirely."""

    def test_completed_stories_skipped_on_resume(
        self, two_story_project: MockProject
    ) -> None:
        # Simulate resume: story 1.1 already completed, starting at 1.2
        initial_state = State(
            current_epic=1,
            current_story="1.2",
            current_phase=Phase.CREATE_STORY,
            completed_stories=["1.1"],
        )

        executor = ScriptedPhaseExecutor()
        result = run_mock_loop(
            two_story_project,
            executor,
            initial_state=initial_state,
        )

        # Loop should complete successfully
        assert result.exit_reason == LoopExitReason.COMPLETED

        # Both stories should be in completed_stories
        assert_stories_completed(result.final_state, ["1.1", "1.2"])

        # No invocations should reference story 1.1
        for epic_id, story_id, phase in result.invocations:
            assert story_id != "1.1", (
                f"Story 1.1 should be skipped on resume, but phase {phase} was invoked for it"
            )

        # Only story 1.2 phases + RETROSPECTIVE should have been executed
        expected_phases = STORY_PHASES + [Phase.RETROSPECTIVE]
        assert_phase_order(executor, expected_phases)
