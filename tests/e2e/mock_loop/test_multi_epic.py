"""Multi-epic E2E tests for the mock loop harness.

Tasks 2.6-2.9: sequential epics, skipping completed epics, and retrospective count.
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


# Default story phases (no TEA/QA enabled)
DEFAULT_STORY_PHASES = [
    Phase.CREATE_STORY,
    Phase.VALIDATE_STORY,
    Phase.VALIDATE_STORY_SYNTHESIS,
    Phase.DEV_STORY,
    Phase.CODE_REVIEW,
    Phase.CODE_REVIEW_SYNTHESIS,
]


class TestTwoEpicsSequential:
    """Task 2.6: Two epics with one story each execute sequentially."""

    def test_two_epics_sequential(self, two_epic_project: MockProject) -> None:
        """Both epics run in order: epic 1 story + retro, then epic 2 story + retro."""
        executor = ScriptedPhaseExecutor()

        result = run_mock_loop(two_epic_project, executor)

        # Should complete normally
        assert result.exit_reason == LoopExitReason.COMPLETED

        # Both stories completed
        assert_stories_completed(result.final_state, ["1.1", "2.1"])

        # Both epics completed
        assert_epics_completed(result.final_state, [1, 2])

        # Verify phase execution order:
        # Epic 1: story 1.1 phases + RETROSPECTIVE, then Epic 2: story 2.1 phases + RETROSPECTIVE
        expected_invocations = (
            # Epic 1, story 1.1
            [(1, "1.1", phase) for phase in DEFAULT_STORY_PHASES]
            + [(1, "1.1", Phase.RETROSPECTIVE)]
            # Epic 2, story 2.1
            + [(2, "2.1", phase) for phase in DEFAULT_STORY_PHASES]
            + [(2, "2.1", Phase.RETROSPECTIVE)]
        )
        assert result.invocations == expected_invocations


class TestCompletedEpicSkipped:
    """Task 2.7: A completed epic is skipped on resume."""

    def test_completed_epic_skipped(self, two_epic_project: MockProject) -> None:
        """When epic 1 is already in completed_epics, only epic 2 phases execute."""
        executor = ScriptedPhaseExecutor()

        initial_state = State(
            completed_epics=[1],
            current_epic=2,
            current_story="2.1",
            current_phase=Phase.CREATE_STORY,
        )

        result = run_mock_loop(
            two_epic_project,
            executor,
            initial_state=initial_state,
        )

        # Should complete normally
        assert result.exit_reason == LoopExitReason.COMPLETED

        # Epic 2 story completed
        assert "2.1" in result.final_state.completed_stories

        # Both epics in completed list
        assert_epics_completed(result.final_state, [1, 2])

        # Verify only epic 2 phases were invoked (epic 1 not re-executed)
        epic_ids_invoked = {inv[0] for inv in result.invocations}
        assert 1 not in epic_ids_invoked, "Epic 1 should not be re-executed"
        assert 2 in epic_ids_invoked, "Epic 2 should be executed"


class TestEpicWithAllStoriesCompletedSkipped:
    """Task 2.8: An epic whose stories are all completed is skipped."""

    def test_epic_with_all_stories_completed_skipped(
        self, two_epic_project: MockProject
    ) -> None:
        """Epic 1 with all stories completed is skipped entirely."""
        executor = ScriptedPhaseExecutor()

        initial_state = State(
            completed_stories=["1.1"],
            completed_epics=[1],
            current_epic=2,
            current_story="2.1",
            current_phase=Phase.CREATE_STORY,
        )

        result = run_mock_loop(
            two_epic_project,
            executor,
            initial_state=initial_state,
        )

        # Should complete normally
        assert result.exit_reason == LoopExitReason.COMPLETED

        # Verify epic 1 was skipped entirely - no invocations for epic 1
        epic_ids_invoked = {inv[0] for inv in result.invocations}
        assert 1 not in epic_ids_invoked, "Epic 1 should be skipped entirely"

        # Epic 2 phases executed
        assert 2 in epic_ids_invoked, "Epic 2 should be executed"

        # Both epics completed
        assert_epics_completed(result.final_state, [1, 2])


class TestRetrospectiveRunsOncePerEpic:
    """Task 2.9: RETROSPECTIVE runs exactly once per epic, after the last story."""

    def test_retrospective_runs_once_per_epic(self, tmp_path) -> None:
        """1 epic with 2 stories: RETROSPECTIVE invoked exactly once."""
        project = create_mock_project(
            tmp_path, epics=[{"id": 1, "stories": ["1.1", "1.2"]}]
        )
        executor = ScriptedPhaseExecutor()

        result = run_mock_loop(project, executor)

        # Should complete normally
        assert result.exit_reason == LoopExitReason.COMPLETED

        # Both stories completed
        assert_stories_completed(result.final_state, ["1.1", "1.2"])

        # Count RETROSPECTIVE invocations
        retro_invocations = [
            inv for inv in executor.invocations if inv[2] == Phase.RETROSPECTIVE
        ]
        assert len(retro_invocations) == 1, (
            f"RETROSPECTIVE should run exactly once per epic, "
            f"but ran {len(retro_invocations)} times: {retro_invocations}"
        )

        # Verify it ran after the last story (1.2), not after 1.1
        retro_epic, retro_story, retro_phase = retro_invocations[0]
        assert retro_epic == 1
        assert retro_story == "1.2"
        assert retro_phase == Phase.RETROSPECTIVE
