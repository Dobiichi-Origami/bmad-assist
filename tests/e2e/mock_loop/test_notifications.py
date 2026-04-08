"""E2E tests for notification dispatch during loop execution."""

from __future__ import annotations

from unittest.mock import MagicMock, call, patch

import pytest

from tests.e2e.mock_loop.helpers import (
    ScriptedPhaseExecutor,
    create_mock_project,
    run_mock_loop,
)
from bmad_assist.core.loop.types import LoopExitReason, PhaseResult
from bmad_assist.core.state import Phase, State


class TestNotifications:
    """Notification dispatcher is called at lifecycle events."""

    def test_notifications_dispatched_on_story_and_epic_completion(self, tmp_path):
        """4.8: story/epic completion and guardian halt trigger dispatch events."""
        project = create_mock_project(
            tmp_path,
            epics=[{"id": 1, "stories": ["1.1"]}],
        )
        executor = ScriptedPhaseExecutor()

        dispatch_mock = MagicMock()

        with patch(
            "bmad_assist.core.loop.runner._dispatch_event",
            side_effect=dispatch_mock,
        ):
            result = run_mock_loop(project, executor)

        assert result.exit_reason == LoopExitReason.COMPLETED

        # Collect all event types dispatched
        event_types = [c.args[0] for c in dispatch_mock.call_args_list if c.args]

        # story_completed should be dispatched for story 1.1
        assert "story_completed" in event_types
        # epic_completed should be dispatched for epic 1
        assert "epic_completed" in event_types

    def test_guardian_halt_triggers_notification(self, tmp_path):
        """4.8b: guardian halt triggers queue_blocked event."""
        project = create_mock_project(
            tmp_path,
            epics=[{"id": 1, "stories": ["1.1"]}],
        )
        executor = ScriptedPhaseExecutor(
            script={(1, "1.1", Phase.DEV_STORY): PhaseResult.fail("test failure")}
        )

        dispatch_mock = MagicMock()

        with patch(
            "bmad_assist.core.loop.runner._dispatch_event",
            side_effect=dispatch_mock,
        ):
            result = run_mock_loop(project, executor)

        assert result.exit_reason == LoopExitReason.GUARDIAN_HALT

        event_types = [c.args[0] for c in dispatch_mock.call_args_list if c.args]
        # error_occurred and queue_blocked should be dispatched on guardian halt
        assert "error_occurred" in event_types
        assert "queue_blocked" in event_types
