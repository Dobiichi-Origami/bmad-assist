"""Tests for Twin production code paths using mock components.

Covers paths that existing tests miss by mocking execute_phase and Twin:
- build_execution_record called with real PhaseResult.outputs
- reflect block exception handling (build_execution_record error, reflect error)
- apply_page_updates real file I/O (create, update)
- Bound method compass end-to-end injection
- Twin guide returns None edge case (reflect still called)
"""

from __future__ import annotations

import logging
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from bmad_assist.core.config import load_config
from bmad_assist.core.loop.epic_phases import _execute_phase_with_twin
from bmad_assist.core.state import Phase, State
from bmad_assist.twin.twin import DriftAssessment, PageUpdate, TwinResult

from .mock_twin import FakeHandler, FakeTwin, FakeWikiDir, install_fake_handler


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
# 2. build_execution_record production path tests
# =============================================================================


class TestBuildExecutionRecordPath:
    """Test that _execute_phase_with_twin calls build_execution_record
    with values extracted from real PhaseResult.outputs."""

    def test_record_receives_response_and_duration(self, tmp_path: Path) -> None:
        """build_execution_record called with real response and duration_ms
        from PhaseResult.outputs — verify via FakeTwin.last_record.

        Note: we patch execute_phase to control outputs precisely, because
        the real execute_phase overwrites duration_ms with wall-clock timing.
        """
        config = _make_config(twin_enabled=True)
        state = State(current_epic=1, current_phase=Phase.ATDD)

        fake_twin = FakeTwin(
            guide_return="compass",
            reflect_sequence=[TwinResult(decision="continue", rationale="ok")],
        )

        from bmad_assist.core.loop.types import PhaseResult

        with (
            patch(
                "bmad_assist.core.loop.epic_phases.execute_phase",
                return_value=PhaseResult.ok(outputs={"response": "actual output", "duration_ms": 150}),
            ),
            patch("bmad_assist.core.loop.epic_phases.resolve_twin_provider", return_value=MagicMock()),
            patch("bmad_assist.twin.twin.Twin", return_value=fake_twin),
            patch("bmad_assist.twin.wiki.init_wiki", return_value=fake_twin.wiki_dir),
        ):
            result = _execute_phase_with_twin(state, config, tmp_path)

        assert result.success is True
        # FakeTwin captured the real ExecutionRecord from reflect
        assert fake_twin.last_record is not None
        assert fake_twin.last_record.llm_output == "actual output"
        assert fake_twin.last_record.duration_ms == 150

    def test_record_receives_empty_defaults_when_outputs_lack_keys(self, tmp_path: Path) -> None:
        """build_execution_record called with llm_output='' and duration_ms=0
        when PhaseResult.outputs has no 'response' key."""
        config = _make_config(twin_enabled=True)
        state = State(current_epic=1, current_phase=Phase.ATDD)

        fake_twin = FakeTwin(
            guide_return="compass",
            reflect_sequence=[TwinResult(decision="continue", rationale="ok")],
        )

        from bmad_assist.core.loop.types import PhaseResult

        # Patch execute_phase to return result without "response" or "duration_ms"
        with (
            patch(
                "bmad_assist.core.loop.epic_phases.execute_phase",
                return_value=PhaseResult.ok(),
            ),
            patch("bmad_assist.core.loop.epic_phases.resolve_twin_provider", return_value=MagicMock()),
            patch("bmad_assist.twin.twin.Twin", return_value=fake_twin),
            patch("bmad_assist.twin.wiki.init_wiki", return_value=fake_twin.wiki_dir),
        ):
            result = _execute_phase_with_twin(state, config, tmp_path)

        assert result.success is True
        assert fake_twin.last_record is not None
        assert fake_twin.last_record.llm_output == ""
        assert fake_twin.last_record.duration_ms == 0

    def test_non_int_duration_ms_coerced_to_zero(self, tmp_path: Path) -> None:
        """Non-int duration_ms in outputs is coerced to 0 in build_execution_record call."""
        config = _make_config(twin_enabled=True)
        state = State(current_epic=1, current_phase=Phase.ATDD)

        fake_twin = FakeTwin(
            guide_return="compass",
            reflect_sequence=[TwinResult(decision="continue", rationale="ok")],
        )

        from bmad_assist.core.loop.types import PhaseResult

        # PhaseResult.ok() with duration_ms as string (not int)
        with (
            patch(
                "bmad_assist.core.loop.epic_phases.execute_phase",
                return_value=PhaseResult.ok(outputs={"response": "output", "duration_ms": "slow"}),
            ),
            patch("bmad_assist.core.loop.epic_phases.resolve_twin_provider", return_value=MagicMock()),
            patch("bmad_assist.twin.twin.Twin", return_value=fake_twin),
            patch("bmad_assist.twin.wiki.init_wiki", return_value=fake_twin.wiki_dir),
        ):
            result = _execute_phase_with_twin(state, config, tmp_path)

        assert result.success is True
        assert fake_twin.last_record is not None
        assert fake_twin.last_record.duration_ms == 0


# =============================================================================
# 3. Reflect block exception handling tests
# =============================================================================


class TestReflectExceptionHandling:
    """Test that reflect block exceptions preserve the original PhaseResult."""

    def test_build_execution_record_typeerror_returns_original_result(self, tmp_path: Path) -> None:
        """build_execution_record raises TypeError → original successful PhaseResult returned."""
        config = _make_config(twin_enabled=True)
        state = State(current_epic=1, current_phase=Phase.ATDD)

        fake_twin = FakeTwin(
            guide_return="compass",
            reflect_sequence=[TwinResult(decision="continue", rationale="ok")],
        )

        from bmad_assist.core.loop.types import PhaseResult

        original_result = PhaseResult.ok(outputs={"response": "original output", "duration_ms": 200})

        with (
            patch("bmad_assist.core.loop.epic_phases.execute_phase", return_value=original_result),
            patch("bmad_assist.core.loop.epic_phases.resolve_twin_provider", return_value=MagicMock()),
            patch("bmad_assist.twin.twin.Twin", return_value=fake_twin),
            patch("bmad_assist.twin.wiki.init_wiki", return_value=fake_twin.wiki_dir),
            patch(
                "bmad_assist.twin.execution_record.build_execution_record",
                side_effect=TypeError("bad record"),
            ),
        ):
            result = _execute_phase_with_twin(state, config, tmp_path)

        # Original result should be returned despite TypeError
        assert result.success is True
        assert result.outputs.get("response") == "original output"

    def test_build_execution_record_typeerror_logs_warning(self, tmp_path: Path, caplog) -> None:
        """build_execution_record raises TypeError → warning logged."""
        config = _make_config(twin_enabled=True)
        state = State(current_epic=1, current_phase=Phase.ATDD)

        fake_twin = FakeTwin(
            guide_return="compass",
            reflect_sequence=[TwinResult(decision="continue", rationale="ok")],
        )

        from bmad_assist.core.loop.types import PhaseResult

        with (
            patch("bmad_assist.core.loop.epic_phases.execute_phase", return_value=PhaseResult.ok()),
            patch("bmad_assist.core.loop.epic_phases.resolve_twin_provider", return_value=MagicMock()),
            patch("bmad_assist.twin.twin.Twin", return_value=fake_twin),
            patch("bmad_assist.twin.wiki.init_wiki", return_value=fake_twin.wiki_dir),
            patch(
                "bmad_assist.twin.execution_record.build_execution_record",
                side_effect=TypeError("bad record"),
            ),
        ):
            with caplog.at_level(logging.WARNING, logger="bmad_assist.core.loop.epic_phases"):
                result = _execute_phase_with_twin(state, config, tmp_path)

        assert result.success is True
        assert any("Twin reflect failed" in r.message for r in caplog.records)

    def test_twin_reflect_runtimeerror_returns_original_result(self, tmp_path: Path) -> None:
        """Twin.reflect() raises RuntimeError → original successful PhaseResult returned."""
        config = _make_config(twin_enabled=True)
        state = State(current_epic=1, current_phase=Phase.ATDD)

        fake_twin = FakeTwin(
            guide_return="compass",
            reflect_exception=RuntimeError("LLM call failed"),
        )

        from bmad_assist.core.loop.types import PhaseResult

        original_result = PhaseResult.ok(outputs={"response": "original", "duration_ms": 100})

        with (
            patch("bmad_assist.core.loop.epic_phases.execute_phase", return_value=original_result),
            patch("bmad_assist.core.loop.epic_phases.resolve_twin_provider", return_value=MagicMock()),
            patch("bmad_assist.twin.twin.Twin", return_value=fake_twin),
            patch("bmad_assist.twin.wiki.init_wiki", return_value=fake_twin.wiki_dir),
        ):
            result = _execute_phase_with_twin(state, config, tmp_path)

        assert result.success is True
        assert result.outputs.get("response") == "original"

    def test_twin_reflect_runtimeerror_logs_warning(self, tmp_path: Path, caplog) -> None:
        """Twin.reflect() raises RuntimeError → warning logged."""
        config = _make_config(twin_enabled=True)
        state = State(current_epic=1, current_phase=Phase.ATDD)

        fake_twin = FakeTwin(
            guide_return="compass",
            reflect_exception=RuntimeError("LLM call failed"),
        )

        from bmad_assist.core.loop.types import PhaseResult

        with (
            patch("bmad_assist.core.loop.epic_phases.execute_phase", return_value=PhaseResult.ok()),
            patch("bmad_assist.core.loop.epic_phases.resolve_twin_provider", return_value=MagicMock()),
            patch("bmad_assist.twin.twin.Twin", return_value=fake_twin),
            patch("bmad_assist.twin.wiki.init_wiki", return_value=fake_twin.wiki_dir),
        ):
            with caplog.at_level(logging.WARNING, logger="bmad_assist.core.loop.epic_phases"):
                result = _execute_phase_with_twin(state, config, tmp_path)

        assert result.success is True
        assert any("Twin reflect failed" in r.message for r in caplog.records)


# =============================================================================
# 4. apply_page_updates real I/O tests
# =============================================================================


class TestApplyPageUpdatesIO:
    """Test that apply_page_updates performs real file I/O on the wiki directory."""

    def test_page_create_writes_new_file(self, tmp_path: Path) -> None:
        """PageUpdate(action='create') writes new file in wiki directory."""
        wiki_dir = FakeWikiDir.create(tmp_path)

        from bmad_assist.twin.twin import apply_page_updates

        page_updates = [
            PageUpdate(
                page_name="pattern-negative",
                action="create",
                content="# Negative Patterns\n\n## Skip Justification\n\nSome pattern here.\n",
            )
        ]

        apply_page_updates(page_updates, wiki_dir, epic_id="1")

        # File should be created
        patterns_file = wiki_dir / "pattern-negative.md"
        assert patterns_file.exists()
        content = patterns_file.read_text()
        assert "Negative Patterns" in content

    def test_page_update_modifies_existing_file(self, tmp_path: Path) -> None:
        """PageUpdate(action='update') modifies existing file in wiki directory."""
        wiki_dir = FakeWikiDir.create(tmp_path)

        # First create a page
        from bmad_assist.twin.wiki import write_page

        write_page(
            wiki_dir,
            "pattern-negative",
            "---\ncategory: pattern\nconfidence: tentative\noccurrences: 1\nsource_epics:\n  - '1'\n---\n\n# Negative Patterns\n\n## Evidence\n\n| Issue | Evidence | Epic |\n|-------|----------|------|\n| old issue | old evidence | 1 |\n",
        )

        # Now update it with append_evidence
        from bmad_assist.twin.twin import apply_page_updates

        page_updates = [
            PageUpdate(
                page_name="pattern-negative",
                action="update",
                append_evidence={"issue": "new issue", "evidence": "new evidence"},
            )
        ]

        apply_page_updates(page_updates, wiki_dir, epic_id="2")

        # File should be updated
        patterns_file = wiki_dir / "pattern-negative.md"
        assert patterns_file.exists()
        content = patterns_file.read_text()
        # The evidence row should be appended
        assert "new issue" in content


# =============================================================================
# 5. Bound method compass end-to-end tests
# =============================================================================


class TestCompassEndToEnd:
    """Test compass injection through the full bound method handler path."""

    def test_execute_phase_compass_injection_via_bound_method(self, tmp_path: Path) -> None:
        """execute_phase(state, compass=X) → FakeHandler.compass_seen == X,
        verifying _compass injection through bound method."""
        from bmad_assist.core.loop.dispatch import execute_phase

        fake_handler = FakeHandler()
        install_fake_handler(Phase.ATDD, fake_handler)

        state = State(current_epic=1, current_phase=Phase.ATDD)

        result = execute_phase(state, compass="real-compass")

        assert result.success is True
        assert fake_handler.compass_seen == "real-compass"

    def test_compass_flows_from_twin_guide_to_handler(self, tmp_path: Path) -> None:
        """_execute_phase_with_twin with FakeTwin guide + FakeHandler →
        compass flows from Twin guide to FakeHandler.compass_seen."""
        config = _make_config(twin_enabled=True)
        state = State(current_epic=1, current_phase=Phase.ATDD)

        fake_handler = FakeHandler(response="handler output", duration_ms=100)
        install_fake_handler(Phase.ATDD, fake_handler)

        fake_twin = FakeTwin(
            guide_return="twin-compass",
            reflect_sequence=[TwinResult(decision="continue", rationale="ok")],
        )

        with (
            patch("bmad_assist.core.loop.epic_phases.resolve_twin_provider", return_value=MagicMock()),
            patch("bmad_assist.twin.twin.Twin", return_value=fake_twin),
            patch("bmad_assist.twin.wiki.init_wiki", return_value=fake_twin.wiki_dir),
        ):
            result = _execute_phase_with_twin(state, config, tmp_path)

        assert result.success is True
        assert fake_handler.compass_seen == "twin-compass"


# =============================================================================
# 6. Twin guide returns None edge case
# =============================================================================


class TestGuideReturnsNone:
    """Test that Twin guide returning None still triggers reflect."""

    def test_guide_returns_none_reflect_still_called(self, tmp_path: Path) -> None:
        """FakeTwin guide returns None, phase succeeds → reflect is still called."""
        config = _make_config(twin_enabled=True)
        state = State(current_epic=1, current_phase=Phase.ATDD)

        fake_twin = FakeTwin(
            guide_return=None,
            reflect_sequence=[TwinResult(decision="continue", rationale="ok")],
        )

        from bmad_assist.core.loop.types import PhaseResult

        with (
            patch(
                "bmad_assist.core.loop.epic_phases.execute_phase",
                return_value=PhaseResult.ok(outputs={"response": "done"}),
            ),
            patch("bmad_assist.core.loop.epic_phases.resolve_twin_provider", return_value=MagicMock()),
            patch("bmad_assist.twin.twin.Twin", return_value=fake_twin),
            patch("bmad_assist.twin.wiki.init_wiki", return_value=fake_twin.wiki_dir),
        ):
            result = _execute_phase_with_twin(state, config, tmp_path)

        # Phase should succeed and reflect should have been called
        assert result.success is True
        assert fake_twin.reflect_call_count == 1
        assert fake_twin.last_record is not None
