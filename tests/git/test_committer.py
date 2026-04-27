"""Tests for git commit automation (committer.py)."""

import pytest

from bmad_assist.core.state import Phase
from bmad_assist.git.committer import (
    _categorize_files,
    _generate_conventional_message,
    _summarize_changes,
    generate_commit_message,
    get_modified_files,
    stash_working_changes,
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


class TestStashWorkingChanges:
    """Tests for stash_working_changes selective stash logic."""

    def test_preserves_experience_files_by_default(self, monkeypatch, tmp_path):
        """Experience files should NOT be stashed — they survive retry."""
        porcelain = (
            " M src/main.ts\n"
            " M _bmad-output/implementation-artifacts/experiences/patterns.md\n"
            " M _bmad-output/validation.md\n"
        )
        calls = []

        def mock_run_git(args, cwd):
            calls.append(args)
            if args[0] == "status":
                return (0, porcelain, "")
            # stash push
            return (0, "Saved working directory", "")

        monkeypatch.setattr("bmad_assist.git.committer._run_git", mock_run_git)
        result = stash_working_changes(tmp_path)
        assert result is True

        # The stash push call should include src/ and _bmad-output/validation.md
        # but NOT the experiences/ file
        stash_call = calls[-1]
        assert "stash" in stash_call
        assert "push" in stash_call
        assert "src/main.ts" in stash_call
        assert "_bmad-output/validation.md" in stash_call
        assert "_bmad-output/implementation-artifacts/experiences/patterns.md" not in stash_call

    def test_custom_keep_prefixes(self, monkeypatch, tmp_path):
        """Caller can specify different keep_prefixes."""
        porcelain = " M src/a.py\n M docs/guide.md\n M config.yaml\n"
        calls = []

        def mock_run_git(args, cwd):
            calls.append(args)
            if args[0] == "status":
                return (0, porcelain, "")
            return (0, "Saved working directory", "")

        monkeypatch.setattr("bmad_assist.git.committer._run_git", mock_run_git)
        result = stash_working_changes(tmp_path, keep_prefixes=("docs/",))
        assert result is True

        stash_call = calls[-1]
        assert "src/a.py" in stash_call
        assert "config.yaml" in stash_call
        assert "docs/guide.md" not in stash_call

    def test_no_stashable_changes_returns_true(self, monkeypatch, tmp_path):
        """If only experience files changed, stash is a no-op and returns True."""
        porcelain = " M _bmad-output/implementation-artifacts/experiences/patterns.md\n"
        calls = []

        def mock_run_git(args, cwd):
            calls.append(args)
            return (0, porcelain, "")

        monkeypatch.setattr("bmad_assist.git.committer._run_git", mock_run_git)
        result = stash_working_changes(tmp_path)
        assert result is True
        # Only status call, no stash push
        assert len(calls) == 1
        assert calls[0][0] == "status"

    def test_empty_working_dir_returns_true(self, monkeypatch, tmp_path):
        """Clean working directory — nothing to stash."""
        calls = []

        def mock_run_git(args, cwd):
            calls.append(args)
            return (0, "", "")

        monkeypatch.setattr("bmad_assist.git.committer._run_git", mock_run_git)
        result = stash_working_changes(tmp_path)
        assert result is True
        assert len(calls) == 1  # Only status call

    def test_git_status_failure_returns_false(self, monkeypatch, tmp_path):
        """If git status fails, return False."""
        monkeypatch.setattr(
            "bmad_assist.git.committer._run_git",
            lambda args, cwd: (1, "", "fatal: not a git repository"),
        )
        result = stash_working_changes(tmp_path)
        assert result is False

    def test_git_stash_push_failure_returns_false(self, monkeypatch, tmp_path):
        """If git stash push fails, return False."""
        porcelain = " M src/main.ts\n"

        def mock_run_git(args, cwd):
            if args[0] == "status":
                return (0, porcelain, "")
            return (1, "", "error: stash failed")

        monkeypatch.setattr("bmad_assist.git.committer._run_git", mock_run_git)
        result = stash_working_changes(tmp_path)
        assert result is False

    def test_strips_quoted_filenames(self, monkeypatch, tmp_path):
        """Git quotes filenames with unusual chars — quotes should be stripped."""
        porcelain = ' M "src/weird name.ts"\n M src/normal.ts\n'
        calls = []

        def mock_run_git(args, cwd):
            calls.append(args)
            if args[0] == "status":
                return (0, porcelain, "")
            return (0, "Saved working directory", "")

        monkeypatch.setattr("bmad_assist.git.committer._run_git", mock_run_git)
        result = stash_working_changes(tmp_path)
        assert result is True

        stash_call = calls[-1]
        # Quotes should be stripped from the path
        assert "src/weird name.ts" in stash_call
        assert "src/normal.ts" in stash_call

    def test_porcelain_renamed_file_format(self, monkeypatch, tmp_path):
        """Porcelain format for renames is 'XY old -> new' — new name used."""
        porcelain = "R  src/old.ts -> src/new.ts\n M src/other.ts\n"
        calls = []

        def mock_run_git(args, cwd):
            calls.append(args)
            if args[0] == "status":
                return (0, porcelain, "")
            return (0, "Saved working directory", "")

        monkeypatch.setattr("bmad_assist.git.committer._run_git", mock_run_git)
        result = stash_working_changes(tmp_path)
        assert result is True

        stash_call = calls[-1]
        assert "src/other.ts" in stash_call

    def test_untracked_files_are_staged_before_stash(self, monkeypatch, tmp_path):
        """Untracked files (??) must be git-add'd before stash push can see them."""
        porcelain = (
            " M src/main.ts\n"
            "?? f1-esports/backend/handler_test.go\n"
            "?? f1-esports/tests/e2e/api.spec.ts\n"
        )
        calls = []

        def mock_run_git(args, cwd):
            calls.append(args)
            if args[0] == "status":
                return (0, porcelain, "")
            return (0, "Saved working directory", "")

        monkeypatch.setattr("bmad_assist.git.committer._run_git", mock_run_git)
        result = stash_working_changes(tmp_path)
        assert result is True

        # Expect 3 calls: status, add (untracked), stash push
        assert len(calls) == 3
        add_call = calls[1]
        stash_call = calls[2]

        # git add should include only the untracked paths
        assert add_call[0] == "add"
        assert "f1-esports/backend/handler_test.go" in add_call
        assert "f1-esports/tests/e2e/api.spec.ts" in add_call
        assert "src/main.ts" not in add_call

        # stash push should include all paths
        assert "src/main.ts" in stash_call
        assert "f1-esports/backend/handler_test.go" in stash_call
        assert "f1-esports/tests/e2e/api.spec.ts" in stash_call

    def test_untracked_experience_files_not_staged(self, monkeypatch, tmp_path):
        """Untracked experience files should not be stashed or staged."""
        porcelain = (
            "?? _bmad-output/implementation-artifacts/experiences/patterns.md\n"
            "?? src/new_file.ts\n"
        )
        calls = []

        def mock_run_git(args, cwd):
            calls.append(args)
            if args[0] == "status":
                return (0, porcelain, "")
            return (0, "Saved working directory", "")

        monkeypatch.setattr("bmad_assist.git.committer._run_git", mock_run_git)
        result = stash_working_changes(tmp_path)
        assert result is True

        add_call = calls[1]
        stash_call = calls[2]
        assert "_bmad-output/implementation-artifacts/experiences/patterns.md" not in add_call
        assert "_bmad-output/implementation-artifacts/experiences/patterns.md" not in stash_call
        assert "src/new_file.ts" in add_call
        assert "src/new_file.ts" in stash_call

    def test_git_add_failure_returns_false(self, monkeypatch, tmp_path):
        """If git add for untracked files fails, return False."""
        porcelain = "?? src/new_file.ts\n"

        def mock_run_git(args, cwd):
            if args[0] == "status":
                return (0, porcelain, "")
            if args[0] == "add":
                return (1, "", "error: add failed")
            return (0, "", "")

        monkeypatch.setattr("bmad_assist.git.committer._run_git", mock_run_git)
        result = stash_working_changes(tmp_path)
        assert result is False
