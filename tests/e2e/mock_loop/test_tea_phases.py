"""E2E tests for TEA (Test Engineering Architect) phases integration."""

from __future__ import annotations

from unittest.mock import patch

import pytest

from tests.e2e.mock_loop.helpers import (
    ScriptedPhaseExecutor,
    create_mock_project,
    run_mock_loop,
)
from bmad_assist.core.config.models.loop import TEA_FULL_LOOP_CONFIG
from bmad_assist.core.loop.types import LoopExitReason, PhaseResult
from bmad_assist.core.state import Phase, State


class TestTEAEnabled:
    """TEA phases execute when TEA is enabled in config."""

    def test_tea_phases_included_when_enabled(self, tmp_path):
        """4.12: TEA enabled → ATDD and TEA phases are executed."""
        project = create_mock_project(
            tmp_path,
            epics=[{"id": 1, "stories": ["1.1"]}],
        )
        executor = ScriptedPhaseExecutor()

        # Patch load_loop_config at its source (lazily imported in run_loop)
        with patch(
            "bmad_assist.core.config.load_loop_config",
            return_value=TEA_FULL_LOOP_CONFIG,
        ):
            result = run_mock_loop(project, executor, tea_enabled=True)

        assert result.exit_reason == LoopExitReason.COMPLETED

        phases_called = [inv[2] for inv in result.invocations]

        # TEA epic_setup phases
        assert Phase.TEA_FRAMEWORK in phases_called
        assert Phase.TEA_CI in phases_called

        # ATDD in story phase sequence
        assert Phase.ATDD in phases_called

        # TEST_REVIEW in story phase sequence
        assert Phase.TEST_REVIEW in phases_called


class TestTEADisabled:
    """TEA phases do not execute when TEA is disabled."""

    def test_tea_phases_skipped_when_disabled(self, tmp_path):
        """4.13: TEA not enabled → no TEA phases execute."""
        project = create_mock_project(
            tmp_path,
            epics=[{"id": 1, "stories": ["1.1"]}],
        )
        executor = ScriptedPhaseExecutor()

        result = run_mock_loop(project, executor, tea_enabled=False)

        assert result.exit_reason == LoopExitReason.COMPLETED

        phases_called = [inv[2] for inv in result.invocations]

        assert Phase.ATDD not in phases_called
        assert Phase.TEA_FRAMEWORK not in phases_called
        assert Phase.TEA_CI not in phases_called
        assert Phase.TEA_TEST_DESIGN not in phases_called
        assert Phase.TEA_AUTOMATE not in phases_called
        assert Phase.TEA_NFR_ASSESS not in phases_called
        assert Phase.TEST_REVIEW not in phases_called
