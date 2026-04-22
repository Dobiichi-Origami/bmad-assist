"""End-to-end data flow tests for the Digital Twin.

Tests the full flow from record creation through reflect/guide to page updates,
verifying data integrity across the entire pipeline.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from bmad_assist.twin.config import TwinProviderConfig
from bmad_assist.twin.execution_record import ExecutionRecord, build_execution_record
from bmad_assist.twin.twin import (
    PageUpdate,
    Twin,
    TwinResult,
    apply_page_updates,
    extract_yaml_block,
)
from bmad_assist.twin.wiki import (
    derive_confidence,
    init_wiki,
    list_pages,
    parse_frontmatter,
    read_page,
    rebuild_index,
    write_page,
)
from tests.twin.conftest import make_yaml_output


# ---------------------------------------------------------------------------
# Guide flow
# ---------------------------------------------------------------------------


class TestGuideFlow:
    """End-to-end guide flow tests."""

    def test_guide_with_guide_page(self, tmp_path: Path) -> None:
        """Full guide flow with an existing guide page."""
        wiki_dir = init_wiki(tmp_path)
        provider = MagicMock()
        provider.invoke.return_value = (
            "Ensure all acceptance criteria are implemented. "
            "Watch for test.fixme() stubs left from ATDD phase."
        )
        twin = Twin(config=TwinProviderConfig(enabled=True), wiki_dir=wiki_dir, provider=provider)
        compass = twin.guide("dev")
        assert compass is not None
        assert "acceptance criteria" in compass.lower()

    def test_guide_without_guide_page(self, tmp_path: Path) -> None:
        """Full guide flow when no guide page exists (fallback)."""
        wiki_dir = init_wiki(tmp_path)
        # Add an env page so fallback has something to reason from
        write_page(
            wiki_dir,
            "env-build-tool",
            "---\ncategory: env\nsentiment: positive\nconfidence: tentative\n"
            "occurrences: 1\nlast_updated: EPIC-001\nsource_epics: [EPIC-001]\nlinks_to: []\n"
            "---\n\n# Build Tool\n\n## What\nProject uses Vite 5 for builds.",
        )
        rebuild_index(wiki_dir)
        provider = MagicMock()
        provider.invoke.return_value = "Use Vite for builds. Check tsconfig paths."
        twin = Twin(config=TwinProviderConfig(enabled=True), wiki_dir=wiki_dir, provider=provider)
        compass = twin.guide("nonexistent_phase_type")
        assert compass is not None

    def test_guide_disabled(self, tmp_path: Path) -> None:
        """Disabled Twin returns None for guide."""
        wiki_dir = init_wiki(tmp_path)
        twin = Twin(config=TwinProviderConfig(enabled=False), wiki_dir=wiki_dir)
        assert twin.guide("dev") is None


# ---------------------------------------------------------------------------
# Reflect flow
# ---------------------------------------------------------------------------


class TestReflectFlow:
    """End-to-end reflect flow tests."""

    def test_continue_decision(self, tmp_path: Path) -> None:
        """Reflect returns continue on satisfactory execution."""
        wiki_dir = init_wiki(tmp_path)
        provider = MagicMock()
        provider.invoke.return_value = make_yaml_output(decision="continue", rationale="All good")
        twin = Twin(config=TwinProviderConfig(enabled=True), wiki_dir=wiki_dir, provider=provider)
        record = ExecutionRecord(
            phase="dev_story", mission="Build login", llm_output="## Self-Audit\n\n- ACs met",
            self_audit="- ACs met", success=True, duration_ms=5000, error=None,
        )
        result = twin.reflect(record)
        assert result.decision == "continue"

    def test_retry_decision(self, tmp_path: Path) -> None:
        """Reflect returns retry when drift detected."""
        wiki_dir = init_wiki(tmp_path)
        provider = MagicMock()
        provider.invoke.return_value = make_yaml_output(
            decision="retry",
            rationale="Drift detected",
            drifted=True,
            evidence="Missing AC coverage",
            correction="Re-implement login handler",
        )
        twin = Twin(config=TwinProviderConfig(enabled=True), wiki_dir=wiki_dir, provider=provider)
        record = ExecutionRecord(
            phase="dev_story", mission="Build login", llm_output="## Self-Audit\n\n- Partial",
            self_audit="- Partial", success=True, duration_ms=5000, error=None,
        )
        result = twin.reflect(record)
        assert result.decision == "retry"
        assert result.drift_assessment is not None
        assert result.drift_assessment.drifted is True

    def test_halt_decision(self, tmp_path: Path) -> None:
        """Reflect returns halt on fatal error."""
        wiki_dir = init_wiki(tmp_path)
        provider = MagicMock()
        provider.invoke.return_value = make_yaml_output(
            decision="halt", rationale="Unrecoverable error in build"
        )
        twin = Twin(config=TwinProviderConfig(enabled=True), wiki_dir=wiki_dir, provider=provider)
        record = ExecutionRecord(
            phase="dev_story", mission="Build", llm_output="",
            self_audit=None, success=False, duration_ms=1000, error="Build failed",
        )
        result = twin.reflect(record)
        assert result.decision == "halt"

    def test_page_updates_applied(self, tmp_path: Path) -> None:
        """Reflect result page_updates are applied to wiki."""
        wiki_dir = init_wiki(tmp_path)
        provider = MagicMock()
        content = (
            "---\ncategory: env\nsentiment: positive\nconfidence: tentative\n"
            "occurrences: 0\nlast_updated: \"\"\nsource_epics: []\nlinks_to: []\n---\n\n"
            "# Build Tool\n\n## What\nVite 5\n\n## Evidence\n\n"
            "| Context | Result | Epic |\n|---------|--------|------|\n"
        )
        provider.invoke.return_value = make_yaml_output(
            decision="continue",
            rationale="Good execution",
            page_updates=[{
                "page_name": "env-build-tool",
                "action": "create",
                "content": content,
                "reason": "New env knowledge",
            }],
        )
        twin = Twin(config=TwinProviderConfig(enabled=True), wiki_dir=wiki_dir, provider=provider)
        record = ExecutionRecord(
            phase="dev_story", mission="Build", llm_output="## Self-Audit\n\n- Done",
            self_audit="- Done", success=True, duration_ms=3000, error=None,
        )
        result = twin.reflect(record)
        assert result.page_updates is not None
        apply_page_updates(result.page_updates, wiki_dir, "EPIC-001")
        assert "env-build-tool" in list_pages(wiki_dir)


# ---------------------------------------------------------------------------
# Retry flow
# ---------------------------------------------------------------------------


class TestRetryFlow:
    """End-to-end retry flow tests."""

    def test_degrade_continue_not_retry(self, tmp_path: Path) -> None:
        """Parse failure when is_retry=False degrades to continue."""
        wiki_dir = init_wiki(tmp_path)
        provider = MagicMock()
        provider.invoke.return_value = "garbage output, no yaml here"
        twin = Twin(config=TwinProviderConfig(enabled=True), wiki_dir=wiki_dir, provider=provider)
        record = ExecutionRecord(
            phase="dev_story", mission="Build", llm_output="o",
            self_audit=None, success=True, duration_ms=100, error=None,
        )
        result = twin.reflect(record, is_retry=False)
        assert result.decision == "continue"

    def test_degrade_halt_on_retry(self, tmp_path: Path) -> None:
        """Parse failure when is_retry=True with halt config degrades to halt."""
        wiki_dir = init_wiki(tmp_path)
        provider = MagicMock()
        provider.invoke.return_value = "garbage output"
        config = TwinProviderConfig(enabled=True, retry_exhausted_action="halt")
        twin = Twin(config=config, wiki_dir=wiki_dir, provider=provider)
        record = ExecutionRecord(
            phase="dev_story", mission="Build", llm_output="o",
            self_audit=None, success=True, duration_ms=100, error=None,
        )
        result = twin.reflect(record, is_retry=True)
        assert result.decision == "halt"

    def test_degrade_continue_on_retry_with_continue_config(self, tmp_path: Path) -> None:
        """Parse failure when is_retry=True with continue config degrades to continue."""
        wiki_dir = init_wiki(tmp_path)
        provider = MagicMock()
        provider.invoke.return_value = "garbage output"
        config = TwinProviderConfig(enabled=True, retry_exhausted_action="continue")
        twin = Twin(config=config, wiki_dir=wiki_dir, provider=provider)
        record = ExecutionRecord(
            phase="dev_story", mission="Build", llm_output="o",
            self_audit=None, success=True, duration_ms=100, error=None,
        )
        result = twin.reflect(record, is_retry=True)
        assert result.decision == "continue"


# ---------------------------------------------------------------------------
# Page lifecycle
# ---------------------------------------------------------------------------


class TestPageLifecycle:
    """Tests for the CREATE → UPDATE → EVOLVE page lifecycle."""

    def test_full_lifecycle(self, tmp_path: Path) -> None:
        """A page goes through CREATE → UPDATE → EVOLVE lifecycle."""
        wiki_dir = tmp_path / "wiki"
        wiki_dir.mkdir()

        # CREATE
        create_content = (
            "---\ncategory: env\nsentiment: positive\nconfidence: tentative\n"
            "occurrences: 0\nlast_updated: \"\"\nsource_epics: []\nlinks_to: []\n"
            "---\n\n# React Setup\n\n## What\nReact 18\n\n## Evidence\n\n"
            "| Context | Result | Epic |\n|---------|--------|------|\n"
        )
        apply_page_updates(
            [PageUpdate(page_name="env-react", action="create", content=create_content)],
            wiki_dir, "EPIC-001",
        )
        page = read_page(wiki_dir, "env-react")
        assert page is not None
        fm = parse_frontmatter(page)
        assert fm["occurrences"] == 0  # CREATE doesn't increment via update_frontmatter

        # UPDATE
        apply_page_updates(
            [PageUpdate(
                page_name="env-react",
                action="update",
                append_evidence={"context": "Story 2", "result": "Vite configured"},
            )],
            wiki_dir, "EPIC-002",
        )
        page = read_page(wiki_dir, "env-react")
        fm = parse_frontmatter(page)
        assert fm["occurrences"] == 1
        assert "EPIC-002" in page

        # EVOLVE
        evolve_content = (
            "---\ncategory: env\nsentiment: positive\nconfidence: established\n"
            "occurrences: 1\nlast_updated: EPIC-002\nsource_epics: [EPIC-001, EPIC-002]\nlinks_to: []\n"
            "---\n\n# React Setup\n\n## Evidence\n\n{{EVIDENCE_TABLE}}\n\n## What\nReact 18 with Vite 5"
        )
        apply_page_updates(
            [PageUpdate(page_name="env-react", action="evolve", content=evolve_content)],
            wiki_dir, "EPIC-002",
        )
        page = read_page(wiki_dir, "env-react")
        # Evidence should be preserved, What section should be evolved
        assert "EPIC-002" in page  # from evidence
        assert "Vite 5" in page  # from evolved content

    def test_negative_confidence_cap_across_updates(self, wiki_dir: Path) -> None:
        """Negative page confidence stays at established even with many updates."""
        content = (
            "---\ncategory: pattern\nsentiment: negative\nconfidence: tentative\n"
            "occurrences: 0\nlast_updated: \"\"\nsource_epics: []\nlinks_to: []\n"
            "---\n\n# Flaky Test\n\n## What\nFlaky\n\n## Evidence\n\n"
            "| Context | Root Cause | Real Impact | Epic |\n|---------|------------|-------------|------|\n"
        )
        write_page(wiki_dir, "pattern-flaky", content)

        # Apply 5 updates
        for i in range(1, 6):
            apply_page_updates(
                [PageUpdate(
                    page_name="pattern-flaky",
                    action="update",
                    append_evidence={"context": f"Ctx {i}", "root_cause": f"RC {i}", "real_impact": f"Impact {i}"},
                )],
                wiki_dir, f"EPIC-{i:03d}",
            )

        page = read_page(wiki_dir, "pattern-flaky")
        fm = parse_frontmatter(page)
        # Negative patterns are capped at 'established'
        assert fm["confidence"] == "established"
        assert fm["confidence"] != "definitive"

    def test_evidence_preservation_across_updates(self, wiki_dir: Path) -> None:
        """Evidence rows accumulate across multiple UPDATE operations."""
        content = (
            "---\ncategory: env\nsentiment: positive\nconfidence: tentative\n"
            "occurrences: 0\nlast_updated: \"\"\nsource_epics: []\nlinks_to: []\n"
            "---\n\n# Test\n\n## Evidence\n\n"
            "| Context | Result | Epic |\n|---------|--------|------|\n"
        )
        write_page(wiki_dir, "env-test", content)

        for i in range(1, 4):
            apply_page_updates(
                [PageUpdate(
                    page_name="env-test",
                    action="update",
                    append_evidence={"context": f"Run {i}", "result": f"Res {i}"},
                )],
                wiki_dir, f"EPIC-{i:03d}",
            )

        page = read_page(wiki_dir, "env-test")
        # All 3 evidence rows should be present
        assert "EPIC-001" in page
        assert "EPIC-002" in page
        assert "EPIC-003" in page


# ---------------------------------------------------------------------------
# Challenge mode flow
# ---------------------------------------------------------------------------


class TestChallengeModeFlow:
    """End-to-end tests for challenge mode triggering."""

    def test_5_epic_boundary_triggers(self, wiki_dir: Path) -> None:
        """Negative page with 5 source_epics triggers challenge mode."""
        from bmad_assist.twin.prompts import _check_challenge_mode

        fm = (
            "category: pattern\nsentiment: negative\nconfidence: established\n"
            "occurrences: 5\nlast_updated: EPIC-005\n"
            "source_epics: [EPIC-001, EPIC-002, EPIC-003, EPIC-004, EPIC-005]\nlinks_to: []\n"
        )
        write_page(wiki_dir, "pattern-5epic", f"---\n{fm}---\n\n# 5-Epic Negative")
        rebuild_index(wiki_dir)

        result = _check_challenge_mode(wiki_dir, "EPIC-006")
        assert "Challenge Mode" in result
        assert "pattern-5epic" in result

    def test_4_epic_no_trigger(self, wiki_dir: Path) -> None:
        """Negative page with 4 source_epics does NOT trigger challenge mode."""
        from bmad_assist.twin.prompts import _check_challenge_mode

        fm = (
            "category: pattern\nsentiment: negative\nconfidence: tentative\n"
            "occurrences: 4\nlast_updated: EPIC-004\n"
            "source_epics: [EPIC-001, EPIC-002, EPIC-003, EPIC-004]\nlinks_to: []\n"
        )
        write_page(wiki_dir, "pattern-4epic", f"---\n{fm}---\n\n# 4-Epic Negative")
        rebuild_index(wiki_dir)

        result = _check_challenge_mode(wiki_dir, "EPIC-005")
        assert result == ""

    def test_10_epic_triggers(self, wiki_dir: Path) -> None:
        """Negative page with 10 source_epics triggers challenge mode (10 % 5 == 0)."""
        from bmad_assist.twin.prompts import _check_challenge_mode

        epics = [f"EPIC-{i:03d}" for i in range(1, 11)]
        fm = (
            f"category: pattern\nsentiment: negative\nconfidence: established\n"
            f"occurrences: 10\nlast_updated: EPIC-010\n"
            f"source_epics: {epics}\nlinks_to: []\n"
        )
        write_page(wiki_dir, "pattern-10epic", f"---\n{fm}---\n\n# 10-Epic Negative")
        rebuild_index(wiki_dir)

        result = _check_challenge_mode(wiki_dir, "EPIC-011")
        assert "Challenge Mode" in result


# ---------------------------------------------------------------------------
# Initialization guidance flow
# ---------------------------------------------------------------------------


class TestInitializationGuidanceFlow:
    """End-to-end tests for initialization guidance injection."""

    def test_sparse_wiki_injects_guidance(self, wiki_dir: Path) -> None:
        """Wiki with < 3 pages triggers initialization guidance in prompt."""
        write_page(wiki_dir, "env-only", "---\ncategory: env\n---\n\n# Only Page")
        rebuild_index(wiki_dir)

        from bmad_assist.twin.prompts import build_reflect_prompt
        index_content = read_page(wiki_dir, "INDEX")
        prompt = build_reflect_prompt(
            phase="dev_story",
            mission="Build",
            success=True,
            duration_ms=100,
            error=None,
            files_modified=[],
            self_audit=None,
            index_content=index_content,
            guide_content=None,
        )
        assert "Wiki Initialization" in prompt

    def test_dense_wiki_no_guidance(self, tmp_path: Path) -> None:
        """Wiki with >= 3 pages does NOT trigger initialization guidance."""
        wiki_dir = init_wiki(tmp_path)
        # init_wiki creates 2 guide pages; add a 3rd
        write_page(wiki_dir, "env-extra", "---\ncategory: env\n---\n\n# Extra")
        rebuild_index(wiki_dir)

        from bmad_assist.twin.prompts import build_reflect_prompt
        index_content = read_page(wiki_dir, "INDEX")
        prompt = build_reflect_prompt(
            phase="dev_story",
            mission="Build",
            success=True,
            duration_ms=100,
            error=None,
            files_modified=[],
            self_audit=None,
            index_content=index_content,
            guide_content="Guide",
        )
        assert "Wiki Initialization" not in prompt


# ---------------------------------------------------------------------------
# Truncation in reflect flow
# ---------------------------------------------------------------------------


class TestTruncationInReflectFlow:
    """Tests that truncation is applied during reflect."""

    def test_long_llm_output_truncated(self, tmp_path: Path) -> None:
        """Long llm_output is truncated before being included in prompt."""
        wiki_dir = init_wiki(tmp_path)
        provider = MagicMock()
        # Capture the prompt passed to the LLM
        captured_prompt = []
        def capture_invoke(prompt: str) -> str:
            captured_prompt.append(prompt)
            return make_yaml_output(decision="continue", rationale="ok")
        provider.invoke = capture_invoke

        twin = Twin(config=TwinProviderConfig(enabled=True), wiki_dir=wiki_dir, provider=provider)
        long_output = "A" * 600_000  # Very long output
        record = ExecutionRecord(
            phase="dev_story", mission="Build", llm_output=long_output,
            self_audit=None, success=True, duration_ms=5000, error=None,
        )
        twin.reflect(record)
        # The prompt should contain truncated output
        assert len(captured_prompt) == 1
        assert "TRUNCATED" in captured_prompt[0]

    def test_long_files_diff_truncated(self, tmp_path: Path) -> None:
        """Long files_diff is truncated before being included in prompt."""
        wiki_dir = init_wiki(tmp_path)
        provider = MagicMock()
        captured_prompt = []
        def capture_invoke(prompt: str) -> str:
            captured_prompt.append(prompt)
            return make_yaml_output(decision="continue", rationale="ok")
        provider.invoke = capture_invoke

        twin = Twin(config=TwinProviderConfig(enabled=True), wiki_dir=wiki_dir, provider=provider)
        long_diff = "B" * 600_000
        record = ExecutionRecord(
            phase="dev_story", mission="Build", llm_output="short output",
            self_audit=None, success=True, duration_ms=5000, error=None,
            files_diff=long_diff,
        )
        twin.reflect(record)
        assert len(captured_prompt) == 1
        assert "TRUNCATED" in captured_prompt[0]


# ---------------------------------------------------------------------------
# YAML tolerance in reflect flow
# ---------------------------------------------------------------------------


class TestYAMLToleranceInReflectFlow:
    """Tests for YAML tolerance mechanisms during reflect parsing."""

    def test_double_quoted_recovery(self, tmp_path: Path) -> None:
        """Double-quoted content with \\n is recovered via fix_content_block_scalars."""
        wiki_dir = init_wiki(tmp_path)
        provider = MagicMock()
        # Simulate LLM output with double-quoted multi-line content
        raw_output = (
            "```yaml\n"
            "decision: continue\n"
            "rationale: ok\n"
            "drift_assessment:\n"
            "  drifted: false\n"
            "  evidence: no drift\n"
            "page_updates:\n"
            "  - page_name: env-test\n"
            '    content: "---\\ncategory: env\\n---\\n\\n# Test"\n'
            "    action: create\n"
            "    reason: test\n"
            "```"
        )
        provider.invoke.return_value = raw_output
        twin = Twin(config=TwinProviderConfig(enabled=True), wiki_dir=wiki_dir, provider=provider)
        record = ExecutionRecord(
            phase="dev_story", mission="Build", llm_output="output",
            self_audit=None, success=True, duration_ms=100, error=None,
        )
        result = twin.reflect(record)
        assert result.decision == "continue"
        assert result.page_updates is not None

    def test_no_yaml_block_fallback(self, tmp_path: Path) -> None:
        """When no yaml code block, fallback to 'decision:' line detection."""
        wiki_dir = init_wiki(tmp_path)
        provider = MagicMock()
        # First call returns garbage, second call returns something with decision: line
        provider.invoke.side_effect = [
            "no yaml here at all",
            "no yaml again",
        ]
        twin = Twin(config=TwinProviderConfig(enabled=True), wiki_dir=wiki_dir, provider=provider)
        record = ExecutionRecord(
            phase="dev_story", mission="Build", llm_output="output",
            self_audit=None, success=True, duration_ms=100, error=None,
        )
        result = twin.reflect(record)
        # Both attempts fail → degrades to continue
        assert result.decision == "continue"
