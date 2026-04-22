"""Tests for reflect/guide prompt assembly."""

from __future__ import annotations

from pathlib import Path

import pytest

from bmad_assist.twin.prompts import (
    PHASE_REVIEW_GUIDANCE,
    _CHALLENGE_MODE,
    _FORCED_CHECKLIST,
    _GENERIC_REVIEW_GUIDANCE,
    _INITIALIZATION_GUIDANCE,
    _WATCHOUTS_LIMIT,
    build_guide_prompt,
    build_reflect_prompt,
)
from bmad_assist.twin.wiki import write_page


class TestPhaseReviewGuidance:
    """Tests for PHASE_REVIEW_GUIDANCE dict."""

    def test_dev_story_entry(self) -> None:
        """dev_story has phase-specific review guidance."""
        assert "dev_story" in PHASE_REVIEW_GUIDANCE
        assert "acceptance criteria" in PHASE_REVIEW_GUIDANCE["dev_story"].lower()

    def test_qa_remediate_entry(self) -> None:
        """qa_remediate has phase-specific review guidance."""
        assert "qa_remediate" in PHASE_REVIEW_GUIDANCE

    def test_atdd_entry(self) -> None:
        """atdd has phase-specific review guidance."""
        assert "atdd" in PHASE_REVIEW_GUIDANCE

    def test_create_story_entry(self) -> None:
        """create_story has phase-specific review guidance."""
        assert "create_story" in PHASE_REVIEW_GUIDANCE

    def test_code_review_synthesis_entry(self) -> None:
        """code_review_synthesis has phase-specific review guidance."""
        assert "code_review_synthesis" in PHASE_REVIEW_GUIDANCE

    def test_retrospective_entry(self) -> None:
        """retrospective has phase-specific review guidance."""
        assert "retrospective" in PHASE_REVIEW_GUIDANCE


class TestBuildReflectPrompt:
    """Tests for build_reflect_prompt."""

    def test_contains_phase(self) -> None:
        """Prompt contains the phase name."""
        prompt = build_reflect_prompt(
            phase="dev_story",
            mission="Build feature",
            success=True,
            duration_ms=5000,
            error=None,
            files_modified=[],
            self_audit="All good",
            index_content="INDEX content",
            guide_content="Guide content",
        )
        assert "dev_story" in prompt

    def test_mission_summary_truncation(self) -> None:
        """Mission longer than 200 chars is truncated with '...'."""
        long_mission = "A" * 300
        prompt = build_reflect_prompt(
            phase="dev_story",
            mission=long_mission,
            success=True,
            duration_ms=5000,
            error=None,
            files_modified=[],
            self_audit=None,
            index_content="INDEX",
            guide_content="Guide",
        )
        assert "..." in prompt
        # The mission_summary should be 200 chars + "..."
        assert "AAAAAA..." in prompt

    def test_initialization_guidance_sparse_wiki(self) -> None:
        """Initialization guidance injected when INDEX < 3 pages."""
        # 2 pages = sparse
        index_with_2 = "- **page1**: title\n- **page2**: title\n"
        prompt = build_reflect_prompt(
            phase="dev_story",
            mission="m",
            success=True,
            duration_ms=100,
            error=None,
            files_modified=[],
            self_audit=None,
            index_content=index_with_2,
            guide_content=None,
        )
        assert "Wiki Initialization" in prompt

    def test_no_initialization_guidance_dense_wiki(self) -> None:
        """Initialization guidance NOT injected when INDEX >= 3 pages."""
        index_with_3 = "- **p1**: t\n- **p2**: t\n- **p3**: t\n"
        prompt = build_reflect_prompt(
            phase="dev_story",
            mission="m",
            success=True,
            duration_ms=100,
            error=None,
            files_modified=[],
            self_audit=None,
            index_content=index_with_3,
            guide_content="Guide",
        )
        assert "Wiki Initialization" not in prompt

    def test_initialization_guidance_none_index(self) -> None:
        """Initialization guidance injected when index_content is None."""
        prompt = build_reflect_prompt(
            phase="dev_story",
            mission="m",
            success=True,
            duration_ms=100,
            error=None,
            files_modified=[],
            self_audit=None,
            index_content=None,
            guide_content=None,
        )
        assert "Wiki Initialization" in prompt

    def test_challenge_mode_triggered(self, initialized_wiki: Path) -> None:
        """Challenge mode triggered when negative page has source_epics % 5 == 0."""
        # Write a negative page with 5 source_epics
        fm = (
            "category: pattern\nsentiment: negative\nconfidence: established\n"
            "occurrences: 5\nlast_updated: EPIC-005\n"
            "source_epics: [EPIC-001, EPIC-002, EPIC-003, EPIC-004, EPIC-005]\nlinks_to: []\n"
        )
        write_page(initialized_wiki, "pattern-5epic", f"---\n{fm}---\n\n# 5-Epic Negative")
        from bmad_assist.twin.wiki import rebuild_index
        rebuild_index(initialized_wiki)

        prompt = build_reflect_prompt(
            phase="dev_story",
            mission="m",
            success=True,
            duration_ms=100,
            error=None,
            files_modified=[],
            self_audit=None,
            index_content="INDEX",
            guide_content="Guide",
            epic_id="EPIC-006",
            wiki_dir=initialized_wiki,
        )
        assert "Challenge Mode" in prompt

    def test_challenge_mode_not_triggered(self, initialized_wiki: Path) -> None:
        """Challenge mode NOT triggered when negative page has 4 source_epics."""
        fm = (
            "category: pattern\nsentiment: negative\nconfidence: tentative\n"
            "occurrences: 4\nlast_updated: EPIC-004\n"
            "source_epics: [EPIC-001, EPIC-002, EPIC-003, EPIC-004]\nlinks_to: []\n"
        )
        write_page(initialized_wiki, "pattern-4epic", f"---\n{fm}---\n\n# 4-Epic Negative")
        from bmad_assist.twin.wiki import rebuild_index
        rebuild_index(initialized_wiki)

        prompt = build_reflect_prompt(
            phase="dev_story",
            mission="m",
            success=True,
            duration_ms=100,
            error=None,
            files_modified=[],
            self_audit=None,
            index_content="INDEX",
            guide_content="Guide",
            epic_id="EPIC-005",
            wiki_dir=initialized_wiki,
        )
        assert "Challenge Mode" not in prompt

    def test_phase_specific_guidance(self) -> None:
        """Known phase uses phase-specific guidance, not generic."""
        prompt = build_reflect_prompt(
            phase="dev_story",
            mission="m",
            success=True,
            duration_ms=100,
            error=None,
            files_modified=[],
            self_audit=None,
            index_content="INDEX",
            guide_content="Guide",
        )
        assert "Phase-Specific Review: dev_story" in prompt

    def test_generic_guidance_for_unknown_phase(self) -> None:
        """Unknown phase uses generic review guidance."""
        prompt = build_reflect_prompt(
            phase="unknown_phase",
            mission="m",
            success=True,
            duration_ms=100,
            error=None,
            files_modified=[],
            self_audit=None,
            index_content="INDEX",
            guide_content="Guide",
        )
        assert "Generic Review Guidance" in prompt

    def test_forced_checklist_present(self) -> None:
        """Forced checklist is always included."""
        prompt = build_reflect_prompt(
            phase="dev_story",
            mission="m",
            success=True,
            duration_ms=100,
            error=None,
            files_modified=[],
            self_audit=None,
            index_content="INDEX",
            guide_content="Guide",
        )
        assert "Before deciding" in prompt

    def test_watchouts_limit_present(self) -> None:
        """Watch-outs limit is always included."""
        prompt = build_reflect_prompt(
            phase="dev_story",
            mission="m",
            success=True,
            duration_ms=100,
            error=None,
            files_modified=[],
            self_audit=None,
            index_content="INDEX",
            guide_content="Guide",
        )
        assert "more than 5 watch-out" in prompt

    def test_self_audit_section(self) -> None:
        """Self-audit content is included in prompt."""
        prompt = build_reflect_prompt(
            phase="dev_story",
            mission="m",
            success=True,
            duration_ms=100,
            error=None,
            files_modified=[],
            self_audit="- ACs checked\n- Tests pass",
            index_content="INDEX",
            guide_content="Guide",
        )
        assert "ACs checked" in prompt

    def test_no_self_audit_fallback(self) -> None:
        """Falls back when self_audit is None."""
        prompt = build_reflect_prompt(
            phase="dev_story",
            mission="m",
            success=True,
            duration_ms=100,
            error=None,
            files_modified=[],
            self_audit=None,
            index_content="INDEX",
            guide_content="Guide",
        )
        assert "No Self-Audit section found" in prompt

    def test_files_modified_displayed(self) -> None:
        """files_modified list is displayed comma-separated."""
        prompt = build_reflect_prompt(
            phase="dev_story",
            mission="m",
            success=True,
            duration_ms=100,
            error=None,
            files_modified=["src/a.ts", "src/b.ts"],
            self_audit=None,
            index_content="INDEX",
            guide_content="Guide",
        )
        assert "src/a.ts" in prompt
        assert "src/b.ts" in prompt


class TestBuildGuidePrompt:
    """Tests for build_guide_prompt."""

    def test_guide_present(self) -> None:
        """When guide page exists, prompt contains guide content."""
        prompt = build_guide_prompt(
            phase_type="dev",
            index_content="INDEX content",
            guide_content="Quality checklist items",
            is_guide_present=True,
        )
        assert "Guide Page for Phase Type: dev" in prompt
        assert "Quality checklist items" in prompt

    def test_guide_absent(self) -> None:
        """When no guide page, prompt contains env/pattern/design pages."""
        prompt = build_guide_prompt(
            phase_type="story",
            index_content="INDEX",
            guide_content="env and pattern content",
            is_guide_present=False,
        )
        assert "All Environment, Pattern, and Design Pages" in prompt

    def test_empty_index(self) -> None:
        """Empty INDEX shows fallback text."""
        prompt = build_guide_prompt(
            phase_type="dev",
            index_content=None,
            guide_content=None,
            is_guide_present=False,
        )
        assert "Empty INDEX" in prompt

    def test_no_guide_no_pages(self) -> None:
        """When guide absent and no env/pattern/design pages, shows fallback."""
        prompt = build_guide_prompt(
            phase_type="dev",
            index_content="INDEX",
            guide_content=None,
            is_guide_present=False,
        )
        assert "No pages available" in prompt
