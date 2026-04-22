"""Tests for ExecutionRecord and format_self_audit."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

from bmad_assist.twin.execution_record import (
    ExecutionRecord,
    build_execution_record,
    format_self_audit,
)


class TestExecutionRecord:
    """Tests for ExecutionRecord dataclass."""

    def test_creation(self) -> None:
        """Creates an ExecutionRecord with all fields."""
        record = ExecutionRecord(
            phase="dev_story",
            mission="Build feature",
            llm_output="output",
            self_audit="audit",
            success=True,
            duration_ms=5000,
            error=None,
        )
        assert record.phase == "dev_story"
        assert record.success is True

    def test_defaults(self) -> None:
        """Default values for optional fields."""
        record = ExecutionRecord(
            phase="dev_story",
            mission="m",
            llm_output="o",
            self_audit=None,
            success=True,
            duration_ms=100,
            error=None,
        )
        assert record.phase_outputs == {}
        assert record.files_modified == []
        assert record.files_diff == ""

    def test_field_names_match_design(self) -> None:
        """Field names match the design spec (files_diff, not files_stat)."""
        record = ExecutionRecord(
            phase="dev_story",
            mission="m",
            llm_output="o",
            self_audit=None,
            success=True,
            duration_ms=100,
            error=None,
        )
        assert hasattr(record, "files_diff")
        assert not hasattr(record, "files_stat")


class TestFormatSelfAudit:
    """Tests for format_self_audit heading format variants."""

    def test_self_audit_with_hyphen(self) -> None:
        """## Self-Audit heading is recognized."""
        output = "## Self-Audit\n\n- Item 1\n- Item 2\n\n## Other\nstuff"
        result = format_self_audit(output)
        assert result is not None
        assert "Item 1" in result

    def test_execution_self_audit(self) -> None:
        """## Execution Self-Audit heading is recognized."""
        output = "## Execution Self-Audit\n\n- Checked all ACs\n\n## Next\n..."
        result = format_self_audit(output)
        assert result is not None
        assert "Checked" in result

    def test_self_audit_with_space(self) -> None:
        """## Self Audit (space, no hyphen) heading is recognized."""
        output = "## Self Audit\n\n- Done\n\n## More\n..."
        result = format_self_audit(output)
        assert result is not None
        assert "Done" in result

    def test_no_self_audit_section(self) -> None:
        """Returns None when no Self-Audit heading is found."""
        output = "## Other Section\n\nNo audit here"
        assert format_self_audit(output) is None

    def test_empty_llm_output(self) -> None:
        """Returns None for empty string."""
        assert format_self_audit("") is None


class TestBuildExecutionRecord:
    """Tests for build_execution_record."""

    def test_self_audit_extraction(self) -> None:
        """Extracts self_audit from llm_output."""
        record = build_execution_record(
            phase="dev_story",
            mission="Build feature",
            llm_output="## Self-Audit\n\n- All good\n\n## Other\nstuff",
            success=True,
            duration_ms=5000,
        )
        assert record.self_audit is not None
        assert "All good" in record.self_audit

    def test_no_project_path_skips_git(self) -> None:
        """When project_path is None, files_diff is empty."""
        record = build_execution_record(
            phase="dev_story",
            mission="m",
            llm_output="output",
            success=True,
            duration_ms=100,
        )
        assert record.files_diff == ""
        assert record.files_modified == []

    @patch("bmad_assist.twin.execution_record._capture_git_diff")
    def test_git_diff_capture_on_success(self, mock_capture: pytest.MonkeyPatch) -> None:
        """Captures git diff when project_path is provided and success=True."""
        mock_capture.return_value = (["file1.ts"], "diff content")
        record = build_execution_record(
            phase="dev_story",
            mission="m",
            llm_output="output",
            success=True,
            duration_ms=100,
            project_path=Path("/project"),
        )
        assert record.files_modified == ["file1.ts"]
        assert record.files_diff == "diff content"

    @patch("bmad_assist.twin.execution_record._capture_git_diff")
    def test_no_git_diff_on_failure(self, mock_capture: pytest.MonkeyPatch) -> None:
        """Does NOT capture git diff when success=False."""
        record = build_execution_record(
            phase="dev_story",
            mission="m",
            llm_output="output",
            success=False,
            duration_ms=100,
            error="Failed",
            project_path=Path("/project"),
        )
        mock_capture.assert_not_called()
        assert record.files_diff == ""
