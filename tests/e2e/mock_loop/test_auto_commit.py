"""E2E tests for git auto-commit integration."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from tests.e2e.mock_loop.helpers import (
    ScriptedPhaseExecutor,
    create_mock_project,
    run_mock_loop,
)
from bmad_assist.core.loop.types import LoopExitReason, PhaseResult
from bmad_assist.core.state import Phase, State


class TestAutoCommitEnabled:
    """Git committer is invoked at correct phases when enabled."""

    def test_committer_called_when_enabled(self, tmp_path):
        """4.9: git-commit enabled → committer invoked after commit-eligible phases."""
        project = create_mock_project(
            tmp_path,
            epics=[{"id": 1, "stories": ["1.1"]}],
        )
        executor = ScriptedPhaseExecutor()
        commit_mock = MagicMock(return_value=False)

        # auto_commit_phase is lazily imported inside runner's main loop via
        # `from bmad_assist.git import auto_commit_phase`, so we must patch
        # the function at its origin module.
        with patch(
            "bmad_assist.git.committer.auto_commit_phase",
            side_effect=commit_mock,
        ), patch(
            "bmad_assist.git.auto_commit_phase",
            side_effect=commit_mock,
        ):
            result = run_mock_loop(project, executor)

        assert result.exit_reason == LoopExitReason.COMPLETED
        # auto_commit_phase is called after every successful story phase
        assert commit_mock.call_count > 0


class TestAutoCommitDisabled:
    """Git committer behavior when disabled."""

    def test_committer_not_triggered_when_disabled(self, tmp_path):
        """4.10: git-commit disabled → committer called but returns False."""
        project = create_mock_project(
            tmp_path,
            epics=[{"id": 1, "stories": ["1.1"]}],
        )
        executor = ScriptedPhaseExecutor()
        commit_mock = MagicMock(return_value=False)

        with patch(
            "bmad_assist.git.committer.auto_commit_phase",
            side_effect=commit_mock,
        ), patch(
            "bmad_assist.git.auto_commit_phase",
            side_effect=commit_mock,
        ):
            result = run_mock_loop(project, executor)

        assert result.exit_reason == LoopExitReason.COMPLETED
        assert commit_mock.call_count > 0


class TestAutoCommitOnFailure:
    """Git committer is not invoked for failed phases."""

    def test_committer_not_called_on_phase_failure(self, tmp_path):
        """4.11: phase failure → committer not invoked for that phase."""
        project = create_mock_project(
            tmp_path,
            epics=[{"id": 1, "stories": ["1.1"]}],
        )
        executor = ScriptedPhaseExecutor(
            script={(1, "1.1", Phase.DEV_STORY): PhaseResult.fail("dev failed")}
        )

        commit_calls: list = []

        def track_commit(phase=None, story_id=None, project_path=None, **kwargs):
            commit_calls.append(phase)
            return False

        with patch(
            "bmad_assist.git.committer.auto_commit_phase",
            side_effect=track_commit,
        ), patch(
            "bmad_assist.git.auto_commit_phase",
            side_effect=track_commit,
        ):
            result = run_mock_loop(project, executor)

        assert result.exit_reason == LoopExitReason.GUARDIAN_HALT
        # DEV_STORY failed → auto_commit is only called on success path
        assert Phase.DEV_STORY not in commit_calls
