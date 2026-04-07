"""Tests for synthesis quality gate injection.

Task 8.5: Unit tests for _build_quality_gate_directive in the
code_review_synthesis compiler.
"""

import pytest

from bmad_assist.compiler.workflows.code_review_synthesis import (
    CodeReviewSynthesisCompiler,
)


@pytest.fixture
def compiler() -> CodeReviewSynthesisCompiler:
    """Create a CodeReviewSynthesisCompiler instance."""
    return CodeReviewSynthesisCompiler()


class TestQualityGateDirective:
    """Tests for _build_quality_gate_directive()."""

    def test_soft_signal_when_below_quality_threshold(
        self, compiler: CodeReviewSynthesisCompiler
    ) -> None:
        """Injects soft signal when score < quality_threshold."""
        resolved = {
            "test_review_quality_score": 65,
            "test_review_quality_threshold": 70,
            "test_review_block_threshold": 50,
        }
        directive = compiler._build_quality_gate_directive(resolved)
        assert "65/100" in directive
        assert "quality threshold 70" in directive
        assert "Consider" in directive
        assert "CRITICAL" not in directive

    def test_hard_signal_when_below_block_threshold(
        self, compiler: CodeReviewSynthesisCompiler
    ) -> None:
        """Injects hard signal when score < block_threshold."""
        resolved = {
            "test_review_quality_score": 42,
            "test_review_quality_threshold": 70,
            "test_review_block_threshold": 50,
        }
        directive = compiler._build_quality_gate_directive(resolved)
        assert "42/100" in directive
        assert "CRITICAL" in directive
        assert "MUST" in directive
        assert "block threshold 50" in directive

    def test_no_signal_when_above_quality_threshold(
        self, compiler: CodeReviewSynthesisCompiler
    ) -> None:
        """No injection when score >= quality_threshold."""
        resolved = {
            "test_review_quality_score": 85,
            "test_review_quality_threshold": 70,
            "test_review_block_threshold": 50,
        }
        directive = compiler._build_quality_gate_directive(resolved)
        assert directive == ""

    def test_no_signal_when_score_is_none(
        self, compiler: CodeReviewSynthesisCompiler
    ) -> None:
        """No injection when score is None (review skipped)."""
        resolved = {
            "test_review_quality_score": None,
            "test_review_quality_threshold": 70,
            "test_review_block_threshold": 50,
        }
        directive = compiler._build_quality_gate_directive(resolved)
        assert directive == ""

    def test_no_signal_when_score_missing(
        self, compiler: CodeReviewSynthesisCompiler
    ) -> None:
        """No injection when score key is missing entirely."""
        resolved = {
            "test_review_quality_threshold": 70,
            "test_review_block_threshold": 50,
        }
        directive = compiler._build_quality_gate_directive(resolved)
        assert directive == ""

    def test_exact_quality_threshold_no_signal(
        self, compiler: CodeReviewSynthesisCompiler
    ) -> None:
        """Score exactly at quality_threshold produces no signal."""
        resolved = {
            "test_review_quality_score": 70,
            "test_review_quality_threshold": 70,
            "test_review_block_threshold": 50,
        }
        directive = compiler._build_quality_gate_directive(resolved)
        assert directive == ""

    def test_exact_block_threshold_soft_signal(
        self, compiler: CodeReviewSynthesisCompiler
    ) -> None:
        """Score exactly at block_threshold gets soft signal (not hard)."""
        resolved = {
            "test_review_quality_score": 50,
            "test_review_quality_threshold": 70,
            "test_review_block_threshold": 50,
        }
        directive = compiler._build_quality_gate_directive(resolved)
        # Exactly at block threshold means score < quality_threshold (soft)
        # but NOT < block_threshold (not hard)
        assert "Consider" in directive
        assert "CRITICAL" not in directive

    def test_mission_includes_quality_gate_when_below(
        self, compiler: CodeReviewSynthesisCompiler
    ) -> None:
        """_build_synthesis_mission includes quality gate section."""
        resolved = {
            "epic_num": 1,
            "story_num": "1",
            "reviewer_count": 3,
            "test_review_quality_score": 42,
            "test_review_quality_threshold": 70,
            "test_review_block_threshold": 50,
        }
        mission = compiler._build_synthesis_mission(resolved)
        assert "TEST QUALITY GATE" in mission
        assert "CRITICAL" in mission

    def test_mission_no_quality_gate_when_above(
        self, compiler: CodeReviewSynthesisCompiler
    ) -> None:
        """_build_synthesis_mission excludes quality gate when score high."""
        resolved = {
            "epic_num": 1,
            "story_num": "1",
            "reviewer_count": 3,
            "test_review_quality_score": 85,
            "test_review_quality_threshold": 70,
            "test_review_block_threshold": 50,
        }
        mission = compiler._build_synthesis_mission(resolved)
        assert "TEST QUALITY GATE" not in mission

    def test_uses_default_thresholds_when_not_provided(
        self, compiler: CodeReviewSynthesisCompiler
    ) -> None:
        """Uses default thresholds (70/50) when not in resolved vars."""
        resolved = {
            "test_review_quality_score": 65,
        }
        directive = compiler._build_quality_gate_directive(resolved)
        assert "quality threshold 70" in directive  # default
