"""Tests for git commit automation (committer.py)."""

import pytest

from bmad_assist.core.state import Phase
from bmad_assist.git.committer import (
    _categorize_files,
    _generate_conventional_message,
    _summarize_changes,
    generate_commit_message,
    get_modified_files,
)


class TestAllPhasesAccepted:
    """Task 5.1: Verify all phases trigger commits (no whitelist)."""

    @pytest.mark.parametrize("phase", list(Phase))
    def test_every_phase_has_commit_type(self, phase: Phase) -> None:
        """Every Phase enum value should produce a valid commit message."""
        msg = generate_commit_message(phase, "1.2", ["src/foo.py"])
        assert msg  # Non-empty
        # Should follow conventional commit format: type(scope): description
        assert "(" in msg
        assert "):" in msg

    @pytest.mark.parametrize("phase", list(Phase))
    def test_auto_commit_phase_no_whitelist_gate(self, phase: Phase, monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
        """auto_commit_phase should not reject any phase (no whitelist gate).

        We test this by checking that with git enabled but no modified files,
        it returns True (skips gracefully) rather than short-circuiting.
        """
        from bmad_assist.git.committer import auto_commit_phase

        monkeypatch.setenv("BMAD_GIT_COMMIT", "1")
        # Mock _run_git to return no modified files
        monkeypatch.setattr(
            "bmad_assist.git.committer._run_git",
            lambda args, cwd: (0, "", ""),
        )
        result = auto_commit_phase(phase, "1.1", tmp_path)
        assert result is True


class TestCategorizeFiles:
    """Task 5.2: Tests for _categorize_files with mixed file types."""

    def test_source_files(self) -> None:
        files = ["src/app/main.ts", "src/lib/utils.py", "src/index.jsx"]
        categories = _categorize_files(files)
        assert len(categories["source"]) == 3
        assert categories["reports"] == []
        assert categories["tests"] == []
        assert categories["config"] == []

    def test_report_files(self) -> None:
        files = ["_bmad-output/validation.md", "docs/guide.md"]
        categories = _categorize_files(files)
        assert len(categories["reports"]) == 2
        assert categories["source"] == []

    def test_test_files(self) -> None:
        files = ["test_main.py", "spec_utils.ts", "tests/test_foo.py"]
        categories = _categorize_files(files)
        assert len(categories["tests"]) == 3

    def test_config_files(self) -> None:
        files = ["package.json", ".eslintrc.yaml", "Makefile"]
        categories = _categorize_files(files)
        assert len(categories["config"]) == 3

    def test_mixed_file_types(self) -> None:
        files = [
            "src/app/main.ts",
            "_bmad-output/validation.md",
            "test_main.py",
            "package.json",
        ]
        categories = _categorize_files(files)
        assert len(categories["source"]) == 1
        assert len(categories["reports"]) == 1
        assert len(categories["tests"]) == 1
        assert len(categories["config"]) == 1

    def test_empty_list(self) -> None:
        categories = _categorize_files([])
        assert all(v == [] for v in categories.values())


class TestSummarizeChanges:
    """Task 5.3: Tests for _summarize_changes."""

    def test_single_category_source(self) -> None:
        files = ["src/app/main.ts", "src/app/utils.ts"]
        summary = _summarize_changes(files)
        assert "source code" in summary
        assert "src/" in summary

    def test_single_category_reports(self) -> None:
        files = ["_bmad-output/validation.md"]
        summary = _summarize_changes(files)
        assert "report" in summary

    def test_multiple_categories(self) -> None:
        files = ["src/main.py", "_bmad-output/report.md", "test_main.py"]
        summary = _summarize_changes(files)
        assert "source code" in summary
        assert "report" in summary
        assert "test" in summary

    def test_empty_list(self) -> None:
        summary = _summarize_changes([])
        assert summary == "no changes"


class TestDynamicMessageGeneration:
    """Task 5.4: Tests for dynamic commit message generation."""

    def test_conventional_commit_format(self) -> None:
        msg = generate_commit_message(Phase.DEV_STORY, "1.2", ["src/main.ts"])
        # Should match: type(scope): description
        assert msg.startswith("feat(story-1.2):")

    def test_correct_scope_story(self) -> None:
        msg = generate_commit_message(Phase.DEV_STORY, "3.5", ["src/main.ts"])
        assert "story-3.5" in msg

    def test_correct_scope_epic(self) -> None:
        msg = generate_commit_message(Phase.RETROSPECTIVE, "22.11", ["docs/retro.md"])
        assert "epic-22" in msg

    def test_correct_commit_type_mapping(self) -> None:
        assert generate_commit_message(Phase.CREATE_STORY, "1.1", ["f"]).startswith("docs(")
        assert generate_commit_message(Phase.DEV_STORY, "1.1", ["f"]).startswith("feat(")
        assert generate_commit_message(Phase.VALIDATE_STORY, "1.1", ["f"]).startswith("test(")
        assert generate_commit_message(Phase.QA_PLAN_EXECUTE, "1.1", ["f"]).startswith("ci(")
        assert generate_commit_message(Phase.CODE_REVIEW_SYNTHESIS, "1.1", ["f"]).startswith("refactor(")

    def test_truncation_at_72_chars(self) -> None:
        # Create enough files to generate a long description
        files = [f"src/very/deep/nested/directory{i}/component{i}.tsx" for i in range(10)]
        msg = generate_commit_message(Phase.DEV_STORY, "1.2", files)
        subject = msg.split("\n")[0]
        assert len(subject) <= 72
        if len(subject) == 72:
            assert subject.endswith("...")

    def test_short_message_not_truncated(self) -> None:
        msg = generate_commit_message(Phase.DEV_STORY, "1.2", ["src/main.ts"])
        subject = msg.split("\n")[0]
        assert not subject.endswith("...")

    def test_fallback_scope_when_no_story_id(self) -> None:
        msg = generate_commit_message(Phase.DEV_STORY, None, ["src/main.ts"])
        assert "bmad" in msg


class TestBmadOutputInclusion:
    """Task 5.5: Verify _bmad-output/ files are no longer excluded."""

    def test_bmad_output_not_in_exclude_prefixes(self, monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
        """_bmad-output/ files should be returned by get_modified_files."""
        # Note: porcelain format is "XY filename" where X=index, Y=worktree status
        # Using "A " (added to index) to avoid leading-space stripping edge case
        porcelain_output = "A  _bmad-output/validation.md\n M src/main.ts\n M .bmad-assist/prompts/foo.txt\n M .bmad-assist/cache/bar.json\n M .bmad-assist/debug/baz.log\n"
        monkeypatch.setattr(
            "bmad_assist.git.committer._run_git",
            lambda args, cwd: (0, porcelain_output, ""),
        )
        files = get_modified_files(tmp_path)
        assert "_bmad-output/validation.md" in files
        assert "src/main.ts" in files
        # Ephemeral dirs should still be excluded
        assert not any(f.startswith(".bmad-assist/prompts/") for f in files)
        assert not any(f.startswith(".bmad-assist/cache/") for f in files)
        assert not any(f.startswith(".bmad-assist/debug/") for f in files)


class TestCommitBodyDirectoryGrouping:
    """Task 5.6: Verify commit body includes directory grouping when >3 files."""

    def test_body_present_when_more_than_3_files(self) -> None:
        files = [
            "src/app/main.ts",
            "src/app/utils.ts",
            "src/lib/helper.ts",
            "docs/readme.md",
            "tests/test_main.py",
        ]
        msg = generate_commit_message(Phase.DEV_STORY, "1.2", files)
        assert "\n\n" in msg
        body = msg.split("\n\n", 1)[1]
        assert "src/" in body
        assert "docs/" in body
        assert "tests/" in body

    def test_no_body_when_3_or_fewer_files(self) -> None:
        files = ["src/main.ts", "src/utils.ts"]
        msg = generate_commit_message(Phase.DEV_STORY, "1.2", files)
        assert "\n\n" not in msg

    def test_body_shows_file_counts(self) -> None:
        files = [
            "src/a.ts",
            "src/b.ts",
            "src/c.ts",
            "docs/x.md",
        ]
        msg = generate_commit_message(Phase.DEV_STORY, "1.2", files)
        body = msg.split("\n\n", 1)[1]
        assert "src/: 3 files" in body
        assert "docs/: 1 file" in body
