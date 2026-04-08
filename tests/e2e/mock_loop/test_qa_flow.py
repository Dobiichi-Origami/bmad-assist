"""E2E tests for QA flow integration."""

from __future__ import annotations

from unittest.mock import patch

import pytest

from tests.e2e.mock_loop.helpers import (
    ScriptedPhaseExecutor,
    create_mock_project,
    run_mock_loop,
)
from bmad_assist.core.config.models.loop import LoopConfig
from bmad_assist.core.loop.types import LoopExitReason, PhaseResult
from bmad_assist.core.state import Phase, State


class TestQAFlowEnabled:
    """QA phases execute when QA is enabled."""

    def test_qa_phases_execute_when_enabled(self, tmp_path):
        """4.1: QA enabled → QA_PLAN_GENERATE, QA_PLAN_EXECUTE, QA_REMEDIATE run in teardown."""
        project = create_mock_project(tmp_path, epics=[{"id": 1, "stories": ["1.1"]}])
        executor = ScriptedPhaseExecutor()

        qa_loop_config = LoopConfig(
            epic_setup=[],
            story=[
                "create_story",
                "validate_story",
                "validate_story_synthesis",
                "dev_story",
                "code_review",
                "code_review_synthesis",
            ],
            epic_teardown=[
                "retrospective",
                "qa_plan_generate",
                "qa_plan_execute",
                "qa_remediate",
            ],
        )

        # Patch load_loop_config at its source (lazily imported in run_loop)
        with patch(
            "bmad_assist.core.config.load_loop_config",
            return_value=qa_loop_config,
        ):
            result = run_mock_loop(project, executor, qa_enabled=True)

        assert result.exit_reason == LoopExitReason.COMPLETED

        phases_called = [inv[2] for inv in result.invocations]
        assert Phase.QA_PLAN_GENERATE in phases_called
        assert Phase.QA_PLAN_EXECUTE in phases_called
        assert Phase.QA_REMEDIATE in phases_called

        # Verify order: RETROSPECTIVE before QA phases
        retro_idx = phases_called.index(Phase.RETROSPECTIVE)
        qa_gen_idx = phases_called.index(Phase.QA_PLAN_GENERATE)
        qa_exec_idx = phases_called.index(Phase.QA_PLAN_EXECUTE)
        qa_rem_idx = phases_called.index(Phase.QA_REMEDIATE)
        assert retro_idx < qa_gen_idx < qa_exec_idx < qa_rem_idx


class TestQAFlowDisabled:
    """QA phases do not execute when QA is disabled."""

    def test_qa_phases_skipped_when_disabled(self, tmp_path):
        """4.2: QA not enabled → no QA phases execute."""
        project = create_mock_project(tmp_path, epics=[{"id": 1, "stories": ["1.1"]}])
        executor = ScriptedPhaseExecutor()

        result = run_mock_loop(project, executor, qa_enabled=False)

        assert result.exit_reason == LoopExitReason.COMPLETED

        phases_called = [inv[2] for inv in result.invocations]
        assert Phase.QA_PLAN_GENERATE not in phases_called
        assert Phase.QA_PLAN_EXECUTE not in phases_called
        assert Phase.QA_REMEDIATE not in phases_called
