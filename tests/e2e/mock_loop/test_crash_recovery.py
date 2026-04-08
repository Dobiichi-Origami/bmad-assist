"""E2E tests for crash recovery scenarios.

Tasks 3.5-3.8: Verify loop resume from persisted state at various points
(mid-story phase, story boundary, epic boundary) and fresh start behavior.
"""

from __future__ import annotations

import pytest

from tests.e2e.mock_loop.helpers import (
    MockProject,
    ScriptedPhaseExecutor,
    create_mock_project,
    run_mock_loop,
    assert_stories_completed,
    assert_epics_completed,
)
from bmad_assist.core.loop.types import LoopExitReason, PhaseResult
from bmad_assist.core.state import Phase, State


# Default story phases for reference:
#   CREATE_STORY, VALIDATE_STORY, VALIDATE_STORY_SYNTHESIS,
#   DEV_STORY, CODE_REVIEW, CODE_REVIEW_SYNTHESIS
# After last story in an epic: RETROSPECTIVE


class TestResumeFromMidStoryPhase:
    """Task 3.5: Resume from mid-story phase after simulated crash."""

    def test_resume_from_mid_story_phase(self, tmp_path):
        """Crash after VALIDATE_STORY_SYNTHESIS, resume at DEV_STORY.

        The loop should pick up at DEV_STORY for story 1.1 and NOT re-run
        CREATE_STORY, VALIDATE_STORY, or VALIDATE_STORY_SYNTHESIS.
        Expected phases executed: DEV_STORY, CODE_REVIEW, CODE_REVIEW_SYNTHESIS,
        then RETROSPECTIVE (end of epic).
        """
        project = create_mock_project(
            tmp_path,
            epics=[{"id": 1, "stories": ["1.1"]}],
        )
        executor = ScriptedPhaseExecutor()

        # Simulate persisted state: crashed after VALIDATE_STORY_SYNTHESIS
        initial_state = State(
            current_epic=1,
            current_story="1.1",
            current_phase=Phase.DEV_STORY,
        )

        result = run_mock_loop(project, executor, initial_state=initial_state)

        assert result.exit_reason == LoopExitReason.COMPLETED

        # Verify early phases were NOT executed
        phases_run = executor.phases_called
        assert Phase.CREATE_STORY not in phases_run
        assert Phase.VALIDATE_STORY not in phases_run
        assert Phase.VALIDATE_STORY_SYNTHESIS not in phases_run

        # Verify remaining story phases + retrospective ran
        assert Phase.DEV_STORY in phases_run
        assert Phase.CODE_REVIEW in phases_run
        assert Phase.CODE_REVIEW_SYNTHESIS in phases_run
        assert Phase.RETROSPECTIVE in phases_run

        # Story 1.1 should be completed
        assert_stories_completed(result.final_state, ["1.1"])
        assert_epics_completed(result.final_state, [1])


class TestResumeFromStoryBoundary:
    """Task 3.6: Resume at a story boundary (first story already done)."""

    def test_resume_from_story_boundary(self, tmp_path):
        """Story 1.1 already completed, resume at story 1.2 CREATE_STORY.

        The loop should NOT re-execute any phases for story 1.1.
        It should start story 1.2 from CREATE_STORY and run through
        the full phase sequence.
        """
        project = create_mock_project(
            tmp_path,
            epics=[{"id": 1, "stories": ["1.1", "1.2"]}],
        )
        executor = ScriptedPhaseExecutor()

        initial_state = State(
            completed_stories=["1.1"],
            current_epic=1,
            current_story="1.2",
            current_phase=Phase.CREATE_STORY,
        )

        result = run_mock_loop(project, executor, initial_state=initial_state)

        assert result.exit_reason == LoopExitReason.COMPLETED

        # Verify story 1.1 was NOT re-executed: no invocation should have story "1.1"
        for epic_id, story_id, phase in executor.invocations:
            assert story_id != "1.1", (
                f"Story 1.1 should not have been re-executed, "
                f"but phase {phase} was invoked for it"
            )

        # Story 1.2 should have started from CREATE_STORY
        story_1_2_phases = [
            phase for epic_id, story_id, phase in executor.invocations
            if story_id == "1.2"
        ]
        assert Phase.CREATE_STORY in story_1_2_phases

        # Both stories should be completed
        assert_stories_completed(result.final_state, ["1.1", "1.2"])
        assert_epics_completed(result.final_state, [1])


class TestResumeFromEpicBoundary:
    """Task 3.7: Resume at an epic boundary (first epic already done)."""

    def test_resume_from_epic_boundary(self, tmp_path):
        """Epic 1 already completed, resume at epic 2, story 2.1, CREATE_STORY.

        The loop should NOT re-execute any phases for epic 1.
        It should process epic 2 starting from story 2.1 CREATE_STORY.
        """
        project = create_mock_project(
            tmp_path,
            epics=[
                {"id": 1, "stories": ["1.1"]},
                {"id": 2, "stories": ["2.1"]},
            ],
        )
        executor = ScriptedPhaseExecutor()

        initial_state = State(
            completed_stories=["1.1"],
            completed_epics=[1],
            current_epic=2,
            current_story="2.1",
            current_phase=Phase.CREATE_STORY,
        )

        result = run_mock_loop(project, executor, initial_state=initial_state)

        assert result.exit_reason == LoopExitReason.COMPLETED

        # Verify epic 1 was NOT re-executed
        for epic_id, story_id, phase in executor.invocations:
            assert epic_id != 1, (
                f"Epic 1 should not have been re-executed, "
                f"but phase {phase} was invoked for epic 1, story {story_id}"
            )

        # Epic 2 story 2.1 should have run from CREATE_STORY
        epic_2_phases = [
            phase for epic_id, story_id, phase in executor.invocations
            if epic_id == 2 and story_id == "2.1"
        ]
        assert Phase.CREATE_STORY in epic_2_phases

        # Final state: both epics completed
        assert_stories_completed(result.final_state, ["1.1", "2.1"])
        assert_epics_completed(result.final_state, [1, 2])


class TestFreshStartWithNoState:
    """Task 3.8: Fresh start with no initial state."""

    def test_fresh_start_with_no_state(self, tmp_path):
        """No initial_state provided -- loop starts from the very beginning.

        For a simple 1-epic, 1-story project the loop should run all
        default story phases plus RETROSPECTIVE and return COMPLETED.
        """
        project = create_mock_project(
            tmp_path,
            epics=[{"id": 1, "stories": ["1.1"]}],
        )
        executor = ScriptedPhaseExecutor()

        result = run_mock_loop(project, executor, initial_state=None)

        assert result.exit_reason == LoopExitReason.COMPLETED

        # Verify all default story phases were executed in order
        phases_run = executor.phases_called
        assert Phase.CREATE_STORY in phases_run
        assert Phase.VALIDATE_STORY in phases_run
        assert Phase.VALIDATE_STORY_SYNTHESIS in phases_run
        assert Phase.DEV_STORY in phases_run
        assert Phase.CODE_REVIEW in phases_run
        assert Phase.CODE_REVIEW_SYNTHESIS in phases_run
        assert Phase.RETROSPECTIVE in phases_run

        # All invocations should be for epic 1, story 1.1 (except RETROSPECTIVE)
        for epic_id, story_id, phase in executor.invocations:
            assert epic_id == 1, f"Expected epic 1, got {epic_id}"
            if phase != Phase.RETROSPECTIVE:
                assert story_id == "1.1", f"Expected story 1.1, got {story_id}"

        assert_stories_completed(result.final_state, ["1.1"])
        assert_epics_completed(result.final_state, [1])
