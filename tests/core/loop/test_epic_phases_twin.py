"""Tests for Twin orchestration in epic setup and teardown phases.

Verifies that _execute_phase_with_twin correctly handles:
- Twin guide → compass injection
- Twin reflect decisions: continue, halt, retry
- Twin disabled path (compass=None, no reflect)
- Twin guide/reflect exceptions (graceful degradation)
- retry_exhausted_action: halt vs continue

Task specifications from specs/twin-epic-phases/spec.md.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from bmad_assist.core.config import LoopConfig, load_config
from bmad_assist.core.loop.epic_phases import (
    _execute_epic_setup,
    _execute_epic_teardown,
    _execute_phase_with_twin,
)
from bmad_assist.core.loop.types import PhaseResult
from bmad_assist.core.state import Phase, State
from bmad_assist.twin.twin import DriftAssessment, TwinResult


def _make_config(*, twin_enabled: bool = False) -> "Config":
    """Create a minimal Config for testing."""
    data: dict = {
        "providers": {
            "master": {"provider": "claude", "model": "opus_4"},
        },
    }
    if twin_enabled:
        data["providers"]["twin"] = {
            "provider": "claude",
            "model": "mock",
            "enabled": True,
        }
    return load_config(data)


# =============================================================================
# TestEpicSetupTwin
# =============================================================================


class TestEpicSetupTwin:
    """Tests for Twin orchestration during epic setup phases."""

    def test_twin_guide_provides_compass(self, tmp_path: Path) -> None:
        """Twin enabled → guide returns compass → passed to execute_phase."""
        config = _make_config(twin_enabled=True)
        state = State(
            current_epic=1,
            current_phase=Phase.ATDD,
        )
        state_path = tmp_path / "state.yaml"

        test_loop_config = LoopConfig(
            epic_setup=["atdd"],
            story=["create_story"],
            epic_teardown=["retrospective"],
        )

        compass_seen: list[str | None] = []

        def mock_execute_phase(state: State, compass: str | None = None) -> PhaseResult:
            compass_seen.append(compass)
            return PhaseResult.ok()

        mock_twin = MagicMock()
        mock_twin.guide.return_value = "setup-compass"
        mock_twin.reflect.return_value = TwinResult(decision="continue", rationale="ok")

        with (
            patch("bmad_assist.core.loop.epic_phases.execute_phase", side_effect=mock_execute_phase),
            patch("bmad_assist.core.loop.epic_phases.resolve_twin_provider", return_value=MagicMock()),
            patch("bmad_assist.twin.twin.Twin", return_value=mock_twin),
            patch("bmad_assist.twin.wiki.init_wiki", return_value=Path("/tmp/wiki")),
            patch("bmad_assist.core.loop.epic_phases.save_state"),
            patch("bmad_assist.core.loop.epic_phases._print_phase_banner"),
            patch("bmad_assist.core.loop.epic_phases._dispatch_event"),
            patch("bmad_assist.core.config.get_loop_config", return_value=test_loop_config),
        ):
            new_state, success = _execute_epic_setup(state, state_path, tmp_path, config)

        assert success is True
        assert compass_seen[0] == "setup-compass"

    def test_twin_reflect_halt_returns_false(self, tmp_path: Path) -> None:
        """Twin reflect returns halt → _execute_epic_setup returns (state, False)."""
        config = _make_config(twin_enabled=True)
        state = State(
            current_epic=1,
            current_phase=Phase.ATDD,
        )
        state_path = tmp_path / "state.yaml"

        test_loop_config = LoopConfig(
            epic_setup=["atdd"],
            story=["create_story"],
            epic_teardown=["retrospective"],
        )

        mock_twin = MagicMock()
        mock_twin.guide.return_value = "compass"
        mock_twin.reflect.return_value = TwinResult(decision="halt", rationale="Critical drift")

        with (
            patch("bmad_assist.core.loop.epic_phases.execute_phase", return_value=PhaseResult.ok()),
            patch("bmad_assist.core.loop.epic_phases.resolve_twin_provider", return_value=MagicMock()),
            patch("bmad_assist.twin.twin.Twin", return_value=mock_twin),
            patch("bmad_assist.twin.wiki.init_wiki", return_value=Path("/tmp/wiki")),
            patch("bmad_assist.core.loop.epic_phases.save_state"),
            patch("bmad_assist.core.loop.epic_phases._print_phase_banner"),
            patch("bmad_assist.core.loop.epic_phases._dispatch_event"),
            patch("bmad_assist.core.config.get_loop_config", return_value=test_loop_config),
        ):
            new_state, success = _execute_epic_setup(state, state_path, tmp_path, config)

        assert success is False

    def test_twin_retry_then_continue(self, tmp_path: Path) -> None:
        """Twin reflect returns retry → phase re-executed → then continue."""
        config = _make_config(twin_enabled=True)
        state = State(
            current_epic=1,
            current_phase=Phase.ATDD,
        )
        state_path = tmp_path / "state.yaml"

        test_loop_config = LoopConfig(
            epic_setup=["atdd"],
            story=["create_story"],
            epic_teardown=["retrospective"],
        )

        compass_seen: list[str | None] = []

        def mock_execute_phase(state: State, compass: str | None = None) -> PhaseResult:
            compass_seen.append(compass)
            return PhaseResult.ok()

        mock_twin = MagicMock()
        mock_twin.guide.return_value = "guide-compass"
        mock_twin.config.max_retries = 2
        mock_twin.config.retry_exhausted_action = "halt"
        mock_twin.wiki_dir = Path("/tmp/wiki")

        # First reflect → retry, second reflect → continue
        reflect_responses = iter([
            TwinResult(
                decision="retry",
                rationale="Needs correction",
                drift_assessment=DriftAssessment(drifted=True, evidence="Off track", correction="Fix it"),
            ),
            TwinResult(decision="continue", rationale="Fixed"),
        ])
        mock_twin.reflect.side_effect = lambda *a, **k: next(reflect_responses)

        with (
            patch("bmad_assist.core.loop.epic_phases.execute_phase", side_effect=mock_execute_phase),
            patch("bmad_assist.core.loop.epic_phases.resolve_twin_provider", return_value=MagicMock()),
            patch("bmad_assist.twin.twin.Twin", return_value=mock_twin),
            patch("bmad_assist.twin.wiki.init_wiki", return_value=Path("/tmp/wiki")),
            patch("bmad_assist.core.loop.epic_phases.save_state"),
            patch("bmad_assist.core.loop.epic_phases._print_phase_banner"),
            patch("bmad_assist.core.loop.epic_phases._dispatch_event"),
            patch("bmad_assist.core.config.get_loop_config", return_value=test_loop_config),
        ):
            new_state, success = _execute_epic_setup(state, state_path, tmp_path, config)

        assert success is True
        # Should have 2 execute_phase calls: original + retry
        assert len(compass_seen) == 2
        assert compass_seen[0] == "guide-compass"
        assert "RETRY" in (compass_seen[1] or "")

    def test_twin_disabled_no_compass(self, tmp_path: Path) -> None:
        """Twin disabled → compass=None, no reflect."""
        config = _make_config(twin_enabled=False)
        state = State(
            current_epic=1,
            current_phase=Phase.ATDD,
        )
        state_path = tmp_path / "state.yaml"

        test_loop_config = LoopConfig(
            epic_setup=["atdd"],
            story=["create_story"],
            epic_teardown=["retrospective"],
        )

        compass_seen: list[str | None] = []

        def mock_execute_phase(state: State, compass: str | None = None) -> PhaseResult:
            compass_seen.append(compass)
            return PhaseResult.ok()

        with (
            patch("bmad_assist.core.loop.epic_phases.execute_phase", side_effect=mock_execute_phase),
            patch("bmad_assist.core.loop.epic_phases.save_state"),
            patch("bmad_assist.core.loop.epic_phases._print_phase_banner"),
            patch("bmad_assist.core.loop.epic_phases._dispatch_event"),
            patch("bmad_assist.core.config.get_loop_config", return_value=test_loop_config),
        ):
            new_state, success = _execute_epic_setup(state, state_path, tmp_path, config)

        assert success is True
        assert compass_seen[0] is None


# =============================================================================
# TestEpicTeardownTwin
# =============================================================================


class TestEpicTeardownTwin:
    """Tests for Twin orchestration during epic teardown phases."""

    def test_twin_guide_provides_compass(self, tmp_path: Path) -> None:
        """Twin enabled → guide returns compass → passed to execute_phase."""
        config = _make_config(twin_enabled=True)
        state = State(
            current_epic=1,
            current_phase=Phase.RETROSPECTIVE,
            epic_setup_complete=True,
        )
        state_path = tmp_path / "state.yaml"

        test_loop_config = LoopConfig(
            epic_setup=[],
            story=["create_story"],
            epic_teardown=["retrospective"],
        )

        compass_seen: list[str | None] = []

        def mock_execute_phase(state: State, compass: str | None = None) -> PhaseResult:
            compass_seen.append(compass)
            return PhaseResult.ok()

        mock_twin = MagicMock()
        mock_twin.guide.return_value = "teardown-compass"
        mock_twin.reflect.return_value = TwinResult(decision="continue", rationale="ok")

        with (
            patch("bmad_assist.core.loop.epic_phases.execute_phase", side_effect=mock_execute_phase),
            patch("bmad_assist.core.loop.epic_phases.resolve_twin_provider", return_value=MagicMock()),
            patch("bmad_assist.twin.twin.Twin", return_value=mock_twin),
            patch("bmad_assist.twin.wiki.init_wiki", return_value=Path("/tmp/wiki")),
            patch("bmad_assist.core.loop.epic_phases.save_state"),
            patch("bmad_assist.core.loop.epic_phases._print_phase_banner"),
            patch("bmad_assist.core.loop.epic_phases._dispatch_event"),
            patch("bmad_assist.core.config.get_loop_config", return_value=test_loop_config),
        ):
            new_state, last_result = _execute_epic_teardown(state, state_path, tmp_path, config)

        assert last_result is not None
        assert last_result.success is True
        assert compass_seen[0] == "teardown-compass"

    def test_twin_reflect_halt_continues(self, tmp_path: Path) -> None:
        """Twin reflect returns halt → teardown logs warning and continues (ADR-002)."""
        config = _make_config(twin_enabled=True)
        state = State(
            current_epic=1,
            current_phase=Phase.RETROSPECTIVE,
            epic_setup_complete=True,
        )
        state_path = tmp_path / "state.yaml"

        test_loop_config = LoopConfig(
            epic_setup=[],
            story=["create_story"],
            epic_teardown=["retrospective"],
        )

        mock_twin = MagicMock()
        mock_twin.guide.return_value = "compass"
        mock_twin.reflect.return_value = TwinResult(decision="halt", rationale="Critical drift")

        with (
            patch("bmad_assist.core.loop.epic_phases.execute_phase", return_value=PhaseResult.ok()),
            patch("bmad_assist.core.loop.epic_phases.resolve_twin_provider", return_value=MagicMock()),
            patch("bmad_assist.twin.twin.Twin", return_value=mock_twin),
            patch("bmad_assist.twin.wiki.init_wiki", return_value=Path("/tmp/wiki")),
            patch("bmad_assist.core.loop.epic_phases.save_state"),
            patch("bmad_assist.core.loop.epic_phases._print_phase_banner"),
            patch("bmad_assist.core.loop.epic_phases._dispatch_event"),
            patch("bmad_assist.core.config.get_loop_config", return_value=test_loop_config),
        ):
            new_state, last_result = _execute_epic_teardown(state, state_path, tmp_path, config)

        # Teardown should continue despite Twin halt (ADR-002)
        # last_result.success will be False because Twin halt returns PhaseResult.fail
        assert last_result is not None
        assert last_result.success is False
        assert "Twin HALT" in (last_result.error or "")

    def test_twin_retry_then_continue(self, tmp_path: Path) -> None:
        """Twin reflect returns retry → phase re-executed → then continue."""
        config = _make_config(twin_enabled=True)
        state = State(
            current_epic=1,
            current_phase=Phase.RETROSPECTIVE,
            epic_setup_complete=True,
        )
        state_path = tmp_path / "state.yaml"

        test_loop_config = LoopConfig(
            epic_setup=[],
            story=["create_story"],
            epic_teardown=["retrospective"],
        )

        compass_seen: list[str | None] = []

        def mock_execute_phase(state: State, compass: str | None = None) -> PhaseResult:
            compass_seen.append(compass)
            return PhaseResult.ok()

        mock_twin = MagicMock()
        mock_twin.guide.return_value = "guide-compass"
        mock_twin.config.max_retries = 2
        mock_twin.config.retry_exhausted_action = "continue"
        mock_twin.wiki_dir = Path("/tmp/wiki")

        reflect_responses = iter([
            TwinResult(
                decision="retry",
                rationale="Needs correction",
                drift_assessment=DriftAssessment(drifted=True, evidence="drift", correction="Fix it"),
            ),
            TwinResult(decision="continue", rationale="Fixed"),
        ])
        mock_twin.reflect.side_effect = lambda *a, **k: next(reflect_responses)

        with (
            patch("bmad_assist.core.loop.epic_phases.execute_phase", side_effect=mock_execute_phase),
            patch("bmad_assist.core.loop.epic_phases.resolve_twin_provider", return_value=MagicMock()),
            patch("bmad_assist.twin.twin.Twin", return_value=mock_twin),
            patch("bmad_assist.twin.wiki.init_wiki", return_value=Path("/tmp/wiki")),
            patch("bmad_assist.core.loop.epic_phases.save_state"),
            patch("bmad_assist.core.loop.epic_phases._print_phase_banner"),
            patch("bmad_assist.core.loop.epic_phases._dispatch_event"),
            patch("bmad_assist.core.config.get_loop_config", return_value=test_loop_config),
        ):
            new_state, last_result = _execute_epic_teardown(state, state_path, tmp_path, config)

        assert last_result is not None
        assert last_result.success is True
        assert len(compass_seen) == 2
        assert "RETRY" in (compass_seen[1] or "")

    def test_twin_disabled_no_compass(self, tmp_path: Path) -> None:
        """Twin disabled → compass=None, no reflect."""
        config = _make_config(twin_enabled=False)
        state = State(
            current_epic=1,
            current_phase=Phase.RETROSPECTIVE,
            epic_setup_complete=True,
        )
        state_path = tmp_path / "state.yaml"

        test_loop_config = LoopConfig(
            epic_setup=[],
            story=["create_story"],
            epic_teardown=["retrospective"],
        )

        compass_seen: list[str | None] = []

        def mock_execute_phase(state: State, compass: str | None = None) -> PhaseResult:
            compass_seen.append(compass)
            return PhaseResult.ok()

        with (
            patch("bmad_assist.core.loop.epic_phases.execute_phase", side_effect=mock_execute_phase),
            patch("bmad_assist.core.loop.epic_phases.save_state"),
            patch("bmad_assist.core.loop.epic_phases._print_phase_banner"),
            patch("bmad_assist.core.loop.epic_phases._dispatch_event"),
            patch("bmad_assist.core.config.get_loop_config", return_value=test_loop_config),
        ):
            new_state, last_result = _execute_epic_teardown(state, state_path, tmp_path, config)

        assert last_result is not None
        assert last_result.success is True
        assert compass_seen[0] is None


# =============================================================================
# TestExecutePhaseWithTwin
# =============================================================================


class TestExecutePhaseWithTwin:
    """Unit tests for _execute_phase_with_twin helper function."""

    def test_twin_disabled_executes_without_compass(self, tmp_path: Path) -> None:
        """Twin disabled → execute_phase called with compass=None."""
        config = _make_config(twin_enabled=False)
        state = State(current_epic=1, current_phase=Phase.ATDD)

        compass_seen: list[str | None] = []

        def mock_execute_phase(state: State, compass: str | None = None) -> PhaseResult:
            compass_seen.append(compass)
            return PhaseResult.ok()

        with patch("bmad_assist.core.loop.epic_phases.execute_phase", side_effect=mock_execute_phase):
            result = _execute_phase_with_twin(state, config, tmp_path, retry_exhausted_action="halt")

        assert result.success is True
        assert compass_seen[0] is None

    def test_twin_guide_exception_compass_none(self, tmp_path: Path) -> None:
        """Twin guide raises → compass=None, execution continues."""
        config = _make_config(twin_enabled=True)
        state = State(current_epic=1, current_phase=Phase.ATDD)

        compass_seen: list[str | None] = []

        def mock_execute_phase(state: State, compass: str | None = None) -> PhaseResult:
            compass_seen.append(compass)
            return PhaseResult.ok()

        with (
            patch("bmad_assist.core.loop.epic_phases.execute_phase", side_effect=mock_execute_phase),
            patch("bmad_assist.core.loop.epic_phases.resolve_twin_provider", return_value=MagicMock()),
            patch("bmad_assist.twin.twin.Twin", side_effect=RuntimeError("Twin init failed")),
            patch("bmad_assist.twin.wiki.init_wiki", return_value=Path("/tmp/wiki")),
        ):
            result = _execute_phase_with_twin(state, config, tmp_path, retry_exhausted_action="halt")

        assert result.success is True
        assert compass_seen[0] is None

    def test_twin_reflect_exception_continues(self, tmp_path: Path) -> None:
        """Twin reflect raises → caught, original result returned."""
        config = _make_config(twin_enabled=True)
        state = State(current_epic=1, current_phase=Phase.ATDD)

        mock_twin = MagicMock()
        mock_twin.guide.return_value = "compass"
        mock_twin.reflect.side_effect = RuntimeError("Reflect LLM call failed")

        with (
            patch("bmad_assist.core.loop.epic_phases.execute_phase", return_value=PhaseResult.ok()),
            patch("bmad_assist.core.loop.epic_phases.resolve_twin_provider", return_value=MagicMock()),
            patch("bmad_assist.twin.twin.Twin", return_value=mock_twin),
            patch("bmad_assist.twin.wiki.init_wiki", return_value=Path("/tmp/wiki")),
        ):
            result = _execute_phase_with_twin(state, config, tmp_path, retry_exhausted_action="halt")

        # Should still succeed despite reflect exception
        assert result.success is True

    def test_phase_failure_skips_reflect(self, tmp_path: Path) -> None:
        """Phase execution fails → no Twin reflect called."""
        config = _make_config(twin_enabled=True)
        state = State(current_epic=1, current_phase=Phase.ATDD)

        mock_twin = MagicMock()
        mock_twin.guide.return_value = "compass"

        with (
            patch(
                "bmad_assist.core.loop.epic_phases.execute_phase",
                return_value=PhaseResult.fail("Phase failed"),
            ),
            patch("bmad_assist.core.loop.epic_phases.resolve_twin_provider", return_value=MagicMock()),
            patch("bmad_assist.twin.twin.Twin", return_value=mock_twin),
            patch("bmad_assist.twin.wiki.init_wiki", return_value=Path("/tmp/wiki")),
        ):
            result = _execute_phase_with_twin(state, config, tmp_path, retry_exhausted_action="halt")

        assert result.success is False
        mock_twin.reflect.assert_not_called()

    def test_retry_exhausted_halt_action(self, tmp_path: Path) -> None:
        """Retry exhausted with halt → returns failed PhaseResult."""
        config = _make_config(twin_enabled=True)
        state = State(current_epic=1, current_phase=Phase.ATDD)

        mock_twin = MagicMock()
        mock_twin.guide.return_value = "compass"
        mock_twin.config.max_retries = 1
        mock_twin.config.retry_exhausted_action = "halt"
        mock_twin.wiki_dir = Path("/tmp/wiki")

        # Always retry (will exhaust max_retries=1)
        mock_twin.reflect.return_value = TwinResult(
            decision="retry",
            rationale="Still wrong",
            drift_assessment=DriftAssessment(drifted=True, evidence="drift", correction="fix again"),
        )

        with (
            patch("bmad_assist.core.loop.epic_phases.execute_phase", return_value=PhaseResult.ok()),
            patch("bmad_assist.core.loop.epic_phases.resolve_twin_provider", return_value=MagicMock()),
            patch("bmad_assist.twin.twin.Twin", return_value=mock_twin),
            patch("bmad_assist.twin.wiki.init_wiki", return_value=Path("/tmp/wiki")),
        ):
            result = _execute_phase_with_twin(state, config, tmp_path, retry_exhausted_action="halt")

        assert result.success is False
        assert "RETRY exhausted" in (result.error or "")

    def test_retry_exhausted_continue_action(self, tmp_path: Path) -> None:
        """Retry exhausted with continue → returns the last retry result, not the original."""
        config = _make_config(twin_enabled=True)
        state = State(current_epic=1, current_phase=Phase.ATDD)

        mock_twin = MagicMock()
        mock_twin.guide.return_value = "compass"
        mock_twin.config.max_retries = 1
        mock_twin.config.retry_exhausted_action = "continue"
        mock_twin.wiki_dir = Path("/tmp/wiki")

        # Always retry (will exhaust max_retries=1)
        mock_twin.reflect.return_value = TwinResult(
            decision="retry",
            rationale="Still wrong",
            drift_assessment=DriftAssessment(drifted=True, evidence="drift", correction="fix again"),
        )

        call_count = [0]

        def mock_execute_phase(state: State, compass: str | None = None) -> PhaseResult:
            call_count[0] += 1
            # Original call returns result with marker "original", retry returns "retry"
            marker = "original" if call_count[0] == 1 else "retry"
            return PhaseResult.ok(outputs={"response": marker})

        with (
            patch("bmad_assist.core.loop.epic_phases.execute_phase", side_effect=mock_execute_phase),
            patch("bmad_assist.core.loop.epic_phases.resolve_twin_provider", return_value=MagicMock()),
            patch("bmad_assist.twin.twin.Twin", return_value=mock_twin),
            patch("bmad_assist.twin.wiki.init_wiki", return_value=Path("/tmp/wiki")),
        ):
            result = _execute_phase_with_twin(state, config, tmp_path, retry_exhausted_action="continue")

        # Must return the retry result, not the original
        assert result.success is True
        assert result.outputs.get("response") == "retry"

    def test_multi_retry_updates_correction(self, tmp_path: Path) -> None:
        """Multiple retries: each retry's correction is updated from the latest reflect."""
        config = _make_config(twin_enabled=True)
        state = State(current_epic=1, current_phase=Phase.ATDD)

        mock_twin = MagicMock()
        mock_twin.guide.return_value = "guide-compass"
        mock_twin.config.max_retries = 3
        mock_twin.config.retry_exhausted_action = "halt"
        mock_twin.wiki_dir = Path("/tmp/wiki")

        # reflect returns: retry(with correction A) → retry(with correction B) → continue
        reflect_responses = iter([
            TwinResult(
                decision="retry",
                rationale="First correction",
                drift_assessment=DriftAssessment(drifted=True, evidence="drift", correction="fix-A"),
            ),
            TwinResult(
                decision="retry",
                rationale="Second correction",
                drift_assessment=DriftAssessment(drifted=True, evidence="drift", correction="fix-B"),
            ),
            TwinResult(decision="continue", rationale="Fixed"),
        ])
        mock_twin.reflect.side_effect = lambda *a, **k: next(reflect_responses)

        compass_seen: list[str | None] = []

        def mock_execute_phase(state: State, compass: str | None = None) -> PhaseResult:
            compass_seen.append(compass)
            return PhaseResult.ok()

        with (
            patch("bmad_assist.core.loop.epic_phases.execute_phase", side_effect=mock_execute_phase),
            patch("bmad_assist.core.loop.epic_phases.resolve_twin_provider", return_value=MagicMock()),
            patch("bmad_assist.twin.twin.Twin", return_value=mock_twin),
            patch("bmad_assist.twin.wiki.init_wiki", return_value=Path("/tmp/wiki")),
        ):
            result = _execute_phase_with_twin(state, config, tmp_path, retry_exhausted_action="halt")

        assert result.success is True
        # 3 execute_phase calls: original + retry1 + retry2
        assert len(compass_seen) == 3
        # First retry compass should contain fix-A
        assert "fix-A" in (compass_seen[1] or "")
        # Second retry compass should contain fix-B (updated correction), NOT fix-A
        assert "fix-B" in (compass_seen[2] or "")
        assert "fix-A" not in (compass_seen[2] or "")
