"""Tests for TestReviewResolver condensed mode.

Task 8.3: Unit tests for resolver condensed behavior.
"""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from bmad_assist.testarch.context.resolvers.test_review import TestReviewResolver


@pytest.fixture
def tmp_review_dir(tmp_path: Path) -> Path:
    """Create a temporary test-reviews directory with sample files."""
    review_dir = tmp_path / "test-reviews"
    review_dir.mkdir()

    # Full report
    full_report = review_dir / "test-review-1-1-20260408_1200.md"
    full_report.write_text(
        "# Full Test Review Report\n"
        "**Quality Score**: 68/100\n"
        "... 390 lines of detailed analysis ...\n"
    )

    # Condensed summary
    summary = review_dir / "test-review-summary-1-1-20260408_1200.md"
    summary.write_text(
        "# Test Review Summary\n"
        "**Quality Score:** 68/100 | **Grade:** C - Needs Improvement\n"
        "## Critical Issues\n"
        "- P0: Missing auth check\n"
    )

    return tmp_path


@pytest.fixture
def tmp_review_dir_no_summary(tmp_path: Path) -> Path:
    """Create test-reviews directory with only full report (no summary)."""
    review_dir = tmp_path / "test-reviews"
    review_dir.mkdir()

    full_report = review_dir / "test-review-1-1-20260408_1200.md"
    full_report.write_text("# Full Test Review Report\nDetailed content here.\n")

    return tmp_path


class TestResolverCondensedMode:
    """Tests for condensed mode in TestReviewResolver."""

    def test_condensed_true_loads_summary_file(self, tmp_review_dir: Path) -> None:
        """When condensed=True and summary exists, loads summary file."""
        resolver = TestReviewResolver(tmp_review_dir, max_tokens=4000)
        result = resolver.resolve(epic_id=1, story_id="1.1", condensed=True)

        assert len(result) == 1
        path = list(result.keys())[0]
        assert "summary" in path
        assert "Test Review Summary" in list(result.values())[0]

    def test_condensed_true_falls_back_to_full(
        self, tmp_review_dir_no_summary: Path
    ) -> None:
        """When condensed=True but no summary, falls back to full report."""
        resolver = TestReviewResolver(tmp_review_dir_no_summary, max_tokens=4000)
        result = resolver.resolve(epic_id=1, story_id="1.1", condensed=True)

        assert len(result) == 1
        path = list(result.keys())[0]
        assert "summary" not in path
        assert "Full Test Review Report" in list(result.values())[0]

    def test_condensed_false_loads_full_report(self, tmp_review_dir: Path) -> None:
        """When condensed=False (default), loads full report even if summary exists."""
        resolver = TestReviewResolver(tmp_review_dir, max_tokens=4000)
        result = resolver.resolve(epic_id=1, story_id="1.1", condensed=False)

        assert len(result) == 1
        path = list(result.keys())[0]
        assert "summary" not in path
        assert "Full Test Review Report" in list(result.values())[0]

    def test_default_is_not_condensed(self, tmp_review_dir: Path) -> None:
        """Default (no condensed arg) loads full report."""
        resolver = TestReviewResolver(tmp_review_dir, max_tokens=4000)
        result = resolver.resolve(epic_id=1, story_id="1.1")

        assert len(result) == 1
        path = list(result.keys())[0]
        assert "summary" not in path

    def test_no_story_id_returns_empty(self, tmp_review_dir: Path) -> None:
        """Missing story_id returns empty dict."""
        resolver = TestReviewResolver(tmp_review_dir, max_tokens=4000)
        result = resolver.resolve(epic_id=1, story_id=None, condensed=True)
        assert result == {}

    def test_no_files_returns_empty(self, tmp_path: Path) -> None:
        """No matching files returns empty dict."""
        # Empty test-reviews directory
        (tmp_path / "test-reviews").mkdir()
        resolver = TestReviewResolver(tmp_path, max_tokens=4000)
        result = resolver.resolve(epic_id=99, story_id="99.1", condensed=True)
        assert result == {}
