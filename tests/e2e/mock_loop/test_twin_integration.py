"""E2E tests for Twin integration: full chain from runner entry through Twin guide/reflect.

Verifies that compass flows from Twin through dispatch into a handler across
the complete runner loop, not just isolated units.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from bmad_assist.core.loop.types import LoopExitReason, PhaseResult
from bmad_assist.core.state import Phase, State
from bmad_assist.twin.twin import DriftAssessment, PageUpdate, TwinResult
from tests.e2e.mock_loop.helpers import (
    MockProject,
    ScriptedPhaseExecutor,
    create_mock_project,
    create_e2e_config,
    run_mock_loop,
)


# =============================================================================
# TestTwinE2EGuideFlow
# =============================================================================


class TestTwinE2EGuideFlow:
    """E2E: verify compass flows from Twin.guide through dispatch to handler."""

    def test_compass_flows_from_twin_to_handler(self, tmp_path: Path) -> None:
        """Full chain: guide → compass → execute_phase → handler._compass set."""
        project = create_mock_project(tmp_path, epics=[{"id": 1, "stories": ["1.1"]}])
        executor = ScriptedPhaseExecutor()

        mock_twin = MagicMock()
        mock_twin.guide.return_value = "head-north"
        mock_twin.reflect.return_value = TwinResult(decision="continue", rationale="ok")

        with (
            patch("bmad_assist.core.loop.runner.resolve_twin_provider", return_value=MagicMock()),
            patch("bmad_assist.twin.twin.Twin", return_value=mock_twin),
            patch("bmad_assist.twin.wiki.init_wiki", return_value=Path("/tmp/wiki")),
        ):
            config = create_e2e_config(twin_enabled=True)
            result = run_mock_loop(project, executor, config=config)

        # Executor should have captured compass values
        # At least the first phase execution should have received compass
        compass_values = executor.compass_history
        assert len(compass_values) > 0
        # First invocation should have the guide compass
        assert compass_values[0] == "head-north"

    def test_no_compass_when_twin_disabled(self, tmp_path: Path) -> None:
        """Twin disabled → compass=None in all invocations."""
        project = create_mock_project(tmp_path, epics=[{"id": 1, "stories": ["1.1"]}])
        executor = ScriptedPhaseExecutor()

        # Config with Twin disabled (default)
        config = create_e2e_config(twin_enabled=False)
        result = run_mock_loop(project, executor, config=config)

        # All compass values should be None
        for compass_val in executor.compass_history:
            assert compass_val is None

    def test_compass_empty_when_guide_returns_none(self, tmp_path: Path) -> None:
        """Guide returns None → no compass in invocations."""
        project = create_mock_project(tmp_path, epics=[{"id": 1, "stories": ["1.1"]}])
        executor = ScriptedPhaseExecutor()

        mock_twin = MagicMock()
        mock_twin.guide.return_value = None  # Guide returns None
        mock_twin.reflect.return_value = TwinResult(decision="continue", rationale="ok")

        with (
            patch("bmad_assist.core.loop.runner.resolve_twin_provider", return_value=MagicMock()),
            patch("bmad_assist.twin.twin.Twin", return_value=mock_twin),
            patch("bmad_assist.twin.wiki.init_wiki", return_value=Path("/tmp/wiki")),
        ):
            config = create_e2e_config(twin_enabled=True)
            result = run_mock_loop(project, executor, config=config)

        # All compass values should be None when guide returns None
        for compass_val in executor.compass_history:
            assert compass_val is None


# =============================================================================
# TestTwinE2EReflectFlow
# =============================================================================


class TestTwinE2EReflectFlow:
    """E2E: verify Twin reflect decisions control loop flow."""

    def test_reflect_continue_completes_epic(self, tmp_path: Path) -> None:
        """reflect "continue" → epic completes normally."""
        project = create_mock_project(tmp_path, epics=[{"id": 1, "stories": ["1.1"]}])
        executor = ScriptedPhaseExecutor()

        mock_twin = MagicMock()
        mock_twin.guide.return_value = "compass-data"
        mock_twin.reflect.return_value = TwinResult(decision="continue", rationale="ok")

        with (
            patch("bmad_assist.core.loop.runner.resolve_twin_provider", return_value=MagicMock()),
            patch("bmad_assist.twin.twin.Twin", return_value=mock_twin),
            patch("bmad_assist.twin.wiki.init_wiki", return_value=Path("/tmp/wiki")),
        ):
            config = create_e2e_config(twin_enabled=True)
            result = run_mock_loop(project, executor, config=config)

        assert result.exit_reason == LoopExitReason.COMPLETED

    def test_reflect_halt_stops_loop(self, tmp_path: Path) -> None:
        """reflect "halt" → GUARDIAN_HALT."""
        project = create_mock_project(tmp_path, epics=[{"id": 1, "stories": ["1.1"]}])
        executor = ScriptedPhaseExecutor()

        mock_twin = MagicMock()
        mock_twin.guide.return_value = "compass-data"
        mock_twin.reflect.return_value = TwinResult(decision="halt", rationale="Dangerous drift")

        with (
            patch("bmad_assist.core.loop.runner.resolve_twin_provider", return_value=MagicMock()),
            patch("bmad_assist.twin.twin.Twin", return_value=mock_twin),
            patch("bmad_assist.twin.wiki.init_wiki", return_value=Path("/tmp/wiki")),
        ):
            config = create_e2e_config(twin_enabled=True)
            result = run_mock_loop(project, executor, config=config)

        assert result.exit_reason == LoopExitReason.GUARDIAN_HALT

    def test_reflect_retry_retries_phase(self, tmp_path: Path) -> None:
        """reflect "retry" → phase executed again."""
        project = create_mock_project(tmp_path, epics=[{"id": 1, "stories": ["1.1"]}])
        executor = ScriptedPhaseExecutor()

        mock_twin = MagicMock()
        mock_twin.guide.return_value = "compass-data"
        mock_twin.config.max_retries = 2
        mock_twin.config.retry_exhausted_action = "halt"
        mock_twin.wiki_dir = Path("/tmp/wiki")

        # Use an iterator for side_effect to avoid StopIteration after exhaustion
        reflect_responses = iter([
            TwinResult(
                decision="retry",
                rationale="Needs fix",
                drift_assessment=DriftAssessment(drifted=True, evidence="off", correction="correct it"),
            ),
            TwinResult(decision="continue", rationale="Fixed"),
            TwinResult(decision="continue", rationale="ok"),
            TwinResult(decision="continue", rationale="ok"),
            TwinResult(decision="continue", rationale="ok"),
            TwinResult(decision="continue", rationale="ok"),
            TwinResult(decision="continue", rationale="ok"),
            TwinResult(decision="continue", rationale="ok"),
        ])
        mock_twin.reflect.side_effect = lambda *a, **k: next(reflect_responses)

        with (
            patch("bmad_assist.core.loop.runner.resolve_twin_provider", return_value=MagicMock()),
            patch("bmad_assist.twin.twin.Twin", return_value=mock_twin),
            patch("bmad_assist.twin.wiki.init_wiki", return_value=Path("/tmp/wiki")),
        ):
            config = create_e2e_config(twin_enabled=True)
            result = run_mock_loop(project, executor, config=config)

        # Phase should be executed more than once (original + at least 1 retry)
        assert len(executor.invocations) > 1
        # Check that a retry compass was used (RETRY tag in compass history)
        retry_compasses = [c for c in executor.compass_history if c and "RETRY" in c]
        assert len(retry_compasses) > 0

    def test_reflect_page_updates_applied(self, tmp_path: Path) -> None:
        """reflect with page_updates → apply_page_updates called."""
        project = create_mock_project(tmp_path, epics=[{"id": 1, "stories": ["1.1"]}])
        executor = ScriptedPhaseExecutor()

        page_updates = [
            PageUpdate(page_name="patterns", action="update", content="new pattern"),
        ]

        mock_twin = MagicMock()
        mock_twin.guide.return_value = "compass-data"
        mock_twin.reflect.return_value = TwinResult(
            decision="continue",
            rationale="ok",
            page_updates=page_updates,
        )

        with (
            patch("bmad_assist.core.loop.runner.resolve_twin_provider", return_value=MagicMock()),
            patch("bmad_assist.twin.twin.Twin", return_value=mock_twin),
            patch("bmad_assist.twin.wiki.init_wiki", return_value=Path("/tmp/wiki")),
            patch("bmad_assist.twin.twin.apply_page_updates") as mock_apply,
        ):
            config = create_e2e_config(twin_enabled=True)
            result = run_mock_loop(project, executor, config=config)

        # apply_page_updates should have been called at least once
        assert mock_apply.call_count >= 1
