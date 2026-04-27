"""Tests for ExecutionRecord and format_self_audit."""

from __future__ import annotations

import subprocess
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

    def test_no_files_diff_attribute(self) -> None:
        """ExecutionRecord does NOT have a files_diff attribute."""
        record = ExecutionRecord(
            phase="dev_story",
            mission="m",
            llm_output="o",
            self_audit=None,
            success=True,
            duration_ms=100,
            error=None,
        )
        assert not hasattr(record, "files_diff")


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
        """When project_path is None, files_modified is empty."""
        record = build_execution_record(
            phase="dev_story",
            mission="m",
            llm_output="output",
            success=True,
            duration_ms=100,
        )
        assert record.files_modified == []

    @patch("bmad_assist.twin.execution_record._capture_files_modified")
    def test_files_modified_capture_on_success(self, mock_capture: pytest.MonkeyPatch) -> None:
        """Captures files_modified when project_path is provided and success=True."""
        mock_capture.return_value = ["file1.ts", "new_file.py"]
        record = build_execution_record(
            phase="dev_story",
            mission="m",
            llm_output="output",
            success=True,
            duration_ms=100,
            project_path=Path("/project"),
        )
        assert record.files_modified == ["file1.ts", "new_file.py"]

    @patch("bmad_assist.twin.execution_record._capture_files_modified")
    def test_no_capture_on_failure(self, mock_capture: pytest.MonkeyPatch) -> None:
        """Does NOT capture files_modified when success=False."""
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
        assert record.files_modified == []


class TestCaptureFilesModified:
    """Tests for _capture_files_modified using git status --porcelain."""

    def test_tracked_modifications(self, tmp_path: Path) -> None:
        """Captures modified tracked files."""
        from bmad_assist.twin.execution_record import _capture_files_modified

        # Create a git repo with a tracked file
        subprocess.run(["git", "init"], cwd=str(tmp_path), capture_output=True, check=True)
        (tmp_path / "tracked.txt").write_text("original")
        subprocess.run(["git", "add", "."], cwd=str(tmp_path), capture_output=True, check=True)
        subprocess.run(
            ["git", "commit", "-m", "init"],
            cwd=str(tmp_path), capture_output=True, check=True,
        )
        # Modify the tracked file
        (tmp_path / "tracked.txt").write_text("modified")

        files = _capture_files_modified(tmp_path)
        assert "tracked.txt" in files

    def test_untracked_new_files(self, tmp_path: Path) -> None:
        """Captures untracked new files not in .gitignore."""
        from bmad_assist.twin.execution_record import _capture_files_modified

        subprocess.run(["git", "init"], cwd=str(tmp_path), capture_output=True, check=True)
        (tmp_path / "new_file.py").write_text("new")

        files = _capture_files_modified(tmp_path)
        assert "new_file.py" in files

    def test_staged_new_files(self, tmp_path: Path) -> None:
        """Captures newly created files that have been git add-ed."""
        from bmad_assist.twin.execution_record import _capture_files_modified

        subprocess.run(["git", "init"], cwd=str(tmp_path), capture_output=True, check=True)
        (tmp_path / "staged_file.py").write_text("staged")
        subprocess.run(["git", "add", "."], cwd=str(tmp_path), capture_output=True, check=True)

        files = _capture_files_modified(tmp_path)
        assert "staged_file.py" in files

    def test_mixed_changes(self, tmp_path: Path) -> None:
        """Captures tracked modifications, staged, and untracked files."""
        from bmad_assist.twin.execution_record import _capture_files_modified

        subprocess.run(["git", "init"], cwd=str(tmp_path), capture_output=True, check=True)
        (tmp_path / "existing.txt").write_text("original")
        subprocess.run(["git", "add", "."], cwd=str(tmp_path), capture_output=True, check=True)
        subprocess.run(
            ["git", "commit", "-m", "init"],
            cwd=str(tmp_path), capture_output=True, check=True,
        )
        # Tracked modification
        (tmp_path / "existing.txt").write_text("modified")
        # Staged new file
        (tmp_path / "staged_new.py").write_text("staged")
        subprocess.run(["git", "add", "staged_new.py"], cwd=str(tmp_path), capture_output=True, check=True)
        # Untracked new file
        (tmp_path / "untracked.py").write_text("untracked")

        files = _capture_files_modified(tmp_path)
        assert "existing.txt" in files
        assert "staged_new.py" in files
        assert "untracked.py" in files
        # No duplicates
        assert len(files) == len(set(files))

    def test_gitignore_excluded(self, tmp_path: Path) -> None:
        """Files matching .gitignore are NOT captured."""
        from bmad_assist.twin.execution_record import _capture_files_modified

        subprocess.run(["git", "init"], cwd=str(tmp_path), capture_output=True, check=True)
        (tmp_path / ".gitignore").write_text("node_modules/\n*.log\n")
        subprocess.run(["git", "add", ".gitignore"], cwd=str(tmp_path), capture_output=True, check=True)
        subprocess.run(
            ["git", "commit", "-m", "init"],
            cwd=str(tmp_path), capture_output=True, check=True,
        )
        # Create ignored files
        (tmp_path / "node_modules").mkdir()
        (tmp_path / "node_modules" / "package.js").write_text("pkg")
        (tmp_path / "debug.log").write_text("log")
        # Create a non-ignored file
        (tmp_path / "real_code.py").write_text("code")

        files = _capture_files_modified(tmp_path)
        assert "real_code.py" in files
        assert "debug.log" not in files
        assert "package.js" not in files

    def test_non_git_directory_returns_empty(self, tmp_path: Path) -> None:
        """Returns empty list for non-git directory."""
        from bmad_assist.twin.execution_record import _capture_files_modified

        files = _capture_files_modified(tmp_path)
        assert files == []
