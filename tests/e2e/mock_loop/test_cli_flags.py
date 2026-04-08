"""E2E tests for CLI flag behavior."""

from __future__ import annotations

import pytest

from tests.e2e.mock_loop.helpers import (
    ScriptedPhaseExecutor,
    create_mock_project,
    run_mock_loop,
    assert_stories_completed,
    assert_epics_completed,
)
from bmad_assist.core.loop.types import LoopExitReason, PhaseResult
from bmad_assist.core.state import Phase, State


class TestEpicFlag:
    """--epic flag limits execution to specified epic."""

    def test_epic_flag_runs_only_specified_epic(self, tmp_path):
        """4.3: --epic=2 → only epic 2 executes."""
        project = create_mock_project(
            tmp_path,
            epics=[
                {"id": 1, "stories": ["1.1"]},
                {"id": 2, "stories": ["2.1"]},
                {"id": 3, "stories": ["3.1"]},
            ],
        )
        executor = ScriptedPhaseExecutor()

        result = run_mock_loop(project, executor, start_epic=2)

        assert result.exit_reason == LoopExitReason.COMPLETED

        # Only epic 2's stories should have been executed
        epics_in_invocations = {inv[0] for inv in result.invocations}
        assert 1 not in epics_in_invocations
        assert 2 in epics_in_invocations
        assert 3 not in epics_in_invocations

        assert_stories_completed(result.final_state, ["2.1"])


class TestStoryFlag:
    """--story flag starts from specified story."""

    def test_story_flag_starts_from_specified_story(self, tmp_path):
        """4.4: --story="1.2" → skip story 1.1, start from 1.2."""
        project = create_mock_project(
            tmp_path,
            epics=[{"id": 1, "stories": ["1.1", "1.2", "1.3"]}],
        )
        executor = ScriptedPhaseExecutor()

        result = run_mock_loop(project, executor, start_story="1.2")

        assert result.exit_reason == LoopExitReason.COMPLETED

        # Story 1.1 should not be in invocations
        stories_in_invocations = {inv[1] for inv in result.invocations if inv[1] is not None}
        assert "1.1" not in stories_in_invocations
        assert "1.2" in stories_in_invocations
        assert "1.3" in stories_in_invocations


class TestStopAfterEpicFlag:
    """--stop-after-epic flag stops after completing specified epic."""

    def test_stop_after_epic(self, tmp_path):
        """4.5: --stop-after-epic=1 → complete epic 1 then exit."""
        project = create_mock_project(
            tmp_path,
            epics=[
                {"id": 1, "stories": ["1.1"]},
                {"id": 2, "stories": ["2.1"]},
                {"id": 3, "stories": ["3.1"]},
            ],
        )
        executor = ScriptedPhaseExecutor()

        result = run_mock_loop(project, executor, stop_after_epic=1)

        assert result.exit_reason == LoopExitReason.COMPLETED

        # Only epic 1 should have executed
        epics_in_invocations = {inv[0] for inv in result.invocations}
        assert 1 in epics_in_invocations
        assert 2 not in epics_in_invocations
        assert 3 not in epics_in_invocations

        assert_stories_completed(result.final_state, ["1.1"])
