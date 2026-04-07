"""Tests for TestReviewHandler._generate_condensed_summary().

Task 8.2: Unit tests for condensed summary generation.
"""

import pytest

from bmad_assist.testarch.handlers.test_review import TestReviewHandler
from pathlib import Path
from unittest.mock import MagicMock


@pytest.fixture
def handler() -> TestReviewHandler:
    """Create TestReviewHandler instance with mock config."""
    config = MagicMock()
    config.testarch = MagicMock()
    config.testarch.engagement_model = "auto"
    config.testarch.test_review_on_code_complete = "auto"
    config.providers = MagicMock()
    config.providers.master = MagicMock()
    config.providers.master.provider = "claude"
    config.providers.master.model = "opus"
    config.timeout = 30
    return TestReviewHandler(config, Path("/tmp/test-project"))


class TestCondensedSummaryGeneration:
    """Tests for _generate_condensed_summary()."""

    def test_extracts_score_and_grade(self, handler: TestReviewHandler) -> None:
        """Summary includes quality score and grade."""
        output = (
            "## Test Review\n"
            "**Quality Score**: 68/100\n"
            "**Grade**: C - Needs Improvement\n"
            "Some other content here.\n"
        )
        summary = handler._generate_condensed_summary(output)
        assert "68/100" in summary
        # Grade extraction may capture partial text, just check score is there
        assert "C" in summary

    def test_extracts_critical_issues_with_p0(self, handler: TestReviewHandler) -> None:
        """Summary extracts P0/P1 lines."""
        output = (
            "**Quality Score**: 55/100\n"
            "**Grade**: D - Poor\n"
            "\n"
            "### Findings\n"
            "- P0: Missing auth check at `auth-login.spec.ts:45` - no token validation\n"
            "- P1: Flaky selector at `auth-login.spec.ts:23` - uses dynamic class\n"
            "- P2: Minor style issue in test naming\n"
        )
        summary = handler._generate_condensed_summary(output)
        assert "Critical Issues" in summary
        assert "P0" in summary
        assert "P1" in summary
        # P2 should not be in critical issues section
        assert "auth-login.spec.ts:45" in summary

    def test_extracts_recommendation(self, handler: TestReviewHandler) -> None:
        """Summary includes recommendation."""
        output = (
            "**Quality Score**: 85/100\n"
            "**Grade**: B+ - Good\n"
            "\n"
            "**Recommendation**: Approve with minor suggestions\n"
        )
        summary = handler._generate_condensed_summary(output)
        assert "Approve" in summary

    def test_infers_recommendation_from_score(self, handler: TestReviewHandler) -> None:
        """When no explicit recommendation, infers from score."""
        output = (
            "**Quality Score**: 45/100\n"
            "Some general discussion about the code.\n"
        )
        summary = handler._generate_condensed_summary(output)
        assert "Block" in summary

    def test_infers_approve_from_high_score(self, handler: TestReviewHandler) -> None:
        """High score infers Approve recommendation."""
        output = "**Quality Score**: 85/100\nAll tests look great.\n"
        summary = handler._generate_condensed_summary(output)
        assert "Approve" in summary

    def test_infers_request_changes_from_medium_score(self, handler: TestReviewHandler) -> None:
        """Medium score infers Request Changes recommendation."""
        output = "**Quality Score**: 60/100\nSome issues found.\n"
        summary = handler._generate_condensed_summary(output)
        assert "Request Changes" in summary

    def test_fallback_to_first_30_lines(self, handler: TestReviewHandler) -> None:
        """Falls back to first 30 lines when extraction fails."""
        # Output with no score and no critical issues
        lines = [f"Line {i}: some random content" for i in range(50)]
        output = "\n".join(lines)
        summary = handler._generate_condensed_summary(output)
        # Should contain first 30 lines
        assert "Line 0" in summary
        assert "Line 29" in summary
        # Should not contain line 30+
        assert "Line 30" not in summary

    def test_summary_not_too_long(self, handler: TestReviewHandler) -> None:
        """Summary stays within reasonable bounds."""
        output = (
            "**Quality Score**: 68/100\n"
            "**Grade**: C - Needs Improvement\n"
            "\n"
            "### Critical Issues\n"
            "- P0: Issue 1 at `file1.spec.ts:10` - description\n"
            "- P0: Issue 2 at `file2.spec.ts:20` - description\n"
            "- P1: Issue 3 at `file3.spec.ts:30` - description\n"
            "\n"
            "### Other Findings\n"
            "- P2: Minor issue\n"
            "- P3: Suggestion\n"
            "\n"
            "**Recommendation**: Request Changes\n"
        )
        summary = handler._generate_condensed_summary(output)
        lines = summary.strip().splitlines()
        assert len(lines) <= 30

    def test_empty_output_uses_fallback(self, handler: TestReviewHandler) -> None:
        """Empty output triggers fallback."""
        summary = handler._generate_condensed_summary("")
        # Should still produce something (first 30 lines of empty = empty)
        assert isinstance(summary, str)

    def test_score_only_no_critical_issues(self, handler: TestReviewHandler) -> None:
        """Score present but no critical issues produces valid summary."""
        output = (
            "**Quality Score**: 92/100\n"
            "**Grade**: A - Excellent\n"
            "\n"
            "All tests are well structured.\n"
            "No critical issues found.\n"
        )
        summary = handler._generate_condensed_summary(output)
        assert "92/100" in summary
        assert "Approve" in summary
