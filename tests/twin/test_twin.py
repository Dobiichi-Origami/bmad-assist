"""Tests for Twin class, Pydantic models, apply_page_updates, extract_yaml_block."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pytest
from pydantic import ValidationError

from bmad_assist.twin.config import TwinProviderConfig
from bmad_assist.twin.execution_record import ExecutionRecord
from bmad_assist.twin.twin import (
    DriftAssessment,
    PageUpdate,
    Twin,
    TwinResult,
    apply_page_updates,
    extract_yaml_block,
)
from bmad_assist.twin.wiki import (
    parse_frontmatter,
    read_page,
    rebuild_index,
    write_page,
    page_exists,
)
from tests.twin.conftest import make_yaml_output, write_sample_page


# ---------------------------------------------------------------------------
# Pydantic Models
# ---------------------------------------------------------------------------


class TestDriftAssessmentModel:
    """Tests for DriftAssessment Pydantic model."""

    def test_drifted_without_correction_raises(self) -> None:
        """drifted=True without correction must fail validation."""
        with pytest.raises(ValidationError, match="correction is required"):
            DriftAssessment(drifted=True, evidence="some drift")

    def test_drifted_with_correction_valid(self) -> None:
        """drifted=True with correction is valid."""
        da = DriftAssessment(drifted=True, evidence="drift", correction="fix it")
        assert da.correction == "fix it"

    def test_not_drifted_without_correction_valid(self) -> None:
        """drifted=False without correction is valid."""
        da = DriftAssessment(drifted=False, evidence="no drift")
        assert da.correction is None

    def test_not_drifted_with_correction_valid(self) -> None:
        """drifted=False with correction is also valid (unusual but allowed)."""
        da = DriftAssessment(drifted=False, evidence="ok", correction="extra")
        assert da.correction == "extra"


class TestPageUpdateModel:
    """Tests for PageUpdate Pydantic model."""

    def test_create_action(self) -> None:
        """create action is valid."""
        pu = PageUpdate(page_name="env-test", action="create", content="content")
        assert pu.action == "create"

    def test_update_action(self) -> None:
        """update action is valid."""
        pu = PageUpdate(page_name="env-test", action="update", append_evidence={"context": "x"})
        assert pu.action == "update"

    def test_evolve_action(self) -> None:
        """evolve action is valid."""
        pu = PageUpdate(page_name="env-test", action="evolve", content="new content")
        assert pu.action == "evolve"

    def test_archive_action_invalid(self) -> None:
        """archive action is NOT valid."""
        with pytest.raises(ValidationError, match="action"):
            PageUpdate(page_name="env-test", action="archive")

    def test_defaults(self) -> None:
        """Default values for optional fields."""
        pu = PageUpdate(page_name="env-test", action="create")
        assert pu.content == ""
        assert pu.append_evidence is None
        assert pu.section_patches is None
        assert pu.reason == ""


class TestTwinResultModel:
    """Tests for TwinResult Pydantic model."""

    def test_continue_decision(self) -> None:
        """continue decision is valid."""
        result = TwinResult(decision="continue", rationale="ok")
        assert result.decision == "continue"

    def test_retry_decision(self) -> None:
        """retry decision is valid."""
        result = TwinResult(decision="retry", rationale="drift detected")
        assert result.decision == "retry"

    def test_halt_decision(self) -> None:
        """halt decision is valid."""
        result = TwinResult(decision="halt", rationale="fatal error")
        assert result.decision == "halt"

    def test_invalid_decision(self) -> None:
        """Invalid decision value raises validation error."""
        with pytest.raises(ValidationError, match="decision"):
            TwinResult(decision="skip", rationale="nope")


# ---------------------------------------------------------------------------
# extract_yaml_block
# ---------------------------------------------------------------------------


class TestExtractYamlBlock:
    """Tests for extract_yaml_block."""

    def test_code_block_extraction(self) -> None:
        """Extracts YAML from ```yaml ... ``` code block."""
        raw = 'Some text\n```yaml\ndecision: continue\nrationale: ok\n```\nMore text'
        result = extract_yaml_block(raw)
        assert result is not None
        assert "decision: continue" in result

    def test_no_code_block(self) -> None:
        """Returns None when no code block found and no decision: line."""
        assert extract_yaml_block("Just plain text") is None

    def test_fallback_decision_line(self) -> None:
        """Falls back to finding a 'decision:' line when no code fence."""
        raw = "No code fence here\ndecision: continue\nrationale: ok"
        result = extract_yaml_block(raw)
        assert result is not None
        assert "decision: continue" in result

    def test_multiple_blocks_uses_first(self) -> None:
        """When multiple YAML blocks exist, uses the first one."""
        raw = "```yaml\nfirst: 1\n```\n```yaml\nsecond: 2\n```"
        result = extract_yaml_block(raw)
        assert result is not None
        assert "first: 1" in result


# ---------------------------------------------------------------------------
# Twin.reflect
# ---------------------------------------------------------------------------


class TestTwinReflect:
    """Tests for Twin.reflect."""

    def test_disabled_returns_continue(
        self, disabled_twin_config: TwinProviderConfig, wiki_dir: Path
    ) -> None:
        """Disabled Twin returns continue without calling LLM."""
        twin = Twin(config=disabled_twin_config, wiki_dir=wiki_dir)
        record = ExecutionRecord(
            phase="dev_story", mission="m", llm_output="o",
            self_audit=None, success=True, duration_ms=100, error=None,
        )
        result = twin.reflect(record)
        assert result.decision == "continue"
        assert "disabled" in result.rationale.lower()

    def test_mock_llm_continue(self, twin_with_mock: Twin, sample_record: ExecutionRecord) -> None:
        """Mock LLM returning valid continue YAML."""
        twin_with_mock._provider.invoke.return_value = make_yaml_output(
            decision="continue", rationale="All checks pass"
        )
        result = twin_with_mock.reflect(sample_record)
        assert result.decision == "continue"
        assert "checks pass" in result.rationale.lower()

    def test_parse_failure_retries_then_degrades(
        self, twin_with_mock: Twin, sample_record: ExecutionRecord
    ) -> None:
        """On parse failure, retries once then degrades."""
        twin_with_mock._provider.invoke.return_value = "not valid yaml output"
        result = twin_with_mock.reflect(sample_record)
        # Should degrade to continue (is_retry=False)
        assert result.decision == "continue"
        assert "parse error" in result.rationale.lower()


class TestTwinDegradeOnParseFailure:
    """Tests for all 4 combinations of is_retry x retry_exhausted_action."""

    def test_not_retry_halt_config(self, halt_on_exhaust_config: TwinProviderConfig, wiki_dir: Path) -> None:
        """is_retry=False → always continue, regardless of config."""
        twin = Twin(config=halt_on_exhaust_config, wiki_dir=wiki_dir, provider=MagicMock())
        result = twin._degrade_on_parse_failure(is_retry=False)
        assert result.decision == "continue"

    def test_not_retry_continue_config(self, continue_on_exhaust_config: TwinProviderConfig, wiki_dir: Path) -> None:
        """is_retry=False → always continue."""
        twin = Twin(config=continue_on_exhaust_config, wiki_dir=wiki_dir, provider=MagicMock())
        result = twin._degrade_on_parse_failure(is_retry=False)
        assert result.decision == "continue"

    def test_is_retry_halt_config(self, halt_on_exhaust_config: TwinProviderConfig, wiki_dir: Path) -> None:
        """is_retry=True + halt → decision is halt."""
        twin = Twin(config=halt_on_exhaust_config, wiki_dir=wiki_dir, provider=MagicMock())
        result = twin._degrade_on_parse_failure(is_retry=True)
        assert result.decision == "halt"

    def test_is_retry_continue_config(self, continue_on_exhaust_config: TwinProviderConfig, wiki_dir: Path) -> None:
        """is_retry=True + continue → decision is continue."""
        twin = Twin(config=continue_on_exhaust_config, wiki_dir=wiki_dir, provider=MagicMock())
        result = twin._degrade_on_parse_failure(is_retry=True)
        assert result.decision == "continue"


class TestTwinParseReflectOutput:
    """Tests for Twin._parse_reflect_output."""

    def test_valid_yaml(self, twin_with_mock: Twin) -> None:
        """Valid YAML is parsed into TwinResult."""
        raw = make_yaml_output(decision="continue", rationale="OK")
        result = twin_with_mock._parse_reflect_output(raw)
        assert result.decision == "continue"

    def test_fix_content_block_scalars_applied(self, twin_with_mock: Twin) -> None:
        """fix_content_block_scalars is applied before YAML parsing."""
        # Double-quoted content with embedded \n
        raw = (
            "```yaml\n"
            "decision: continue\n"
            "rationale: ok\n"
            "drift_assessment:\n"
            "  drifted: false\n"
            "  evidence: no drift\n"
            "page_updates:\n"
            "  - page_name: env-test\n"
            '    content: "line1\\nline2"\n'
            "    action: create\n"
            "    reason: test\n"
            "```"
        )
        result = twin_with_mock._parse_reflect_output(raw)
        assert result.page_updates is not None
        assert "line1" in result.page_updates[0].content

    def test_invalid_yaml_raises(self, twin_with_mock: Twin) -> None:
        """Invalid YAML raises ValueError."""
        raw = "```yaml\n: invalid {{\n```"
        with pytest.raises(ValueError, match="YAML parse error"):
            twin_with_mock._parse_reflect_output(raw)

    def test_page_updates_truncated_at_2(self, twin_with_mock: Twin) -> None:
        """page_updates list is truncated to max 2 entries."""
        updates = [
            {"page_name": f"env-test-{i}", "action": "create", "reason": f"reason {i}"}
            for i in range(4)
        ]
        raw = make_yaml_output(decision="continue", rationale="ok", page_updates=updates)
        result = twin_with_mock._parse_reflect_output(raw)
        assert len(result.page_updates) == 2


# ---------------------------------------------------------------------------
# Twin.guide
# ---------------------------------------------------------------------------


class TestTwinGuide:
    """Tests for Twin.guide."""

    def test_disabled_returns_none(
        self, disabled_twin_config: TwinProviderConfig, wiki_dir: Path
    ) -> None:
        """Disabled Twin returns None."""
        twin = Twin(config=disabled_twin_config, wiki_dir=wiki_dir)
        assert twin.guide("dev") is None

    def test_compass_string_returned(
        self, twin_with_mock: Twin, initialized_wiki: Path
    ) -> None:
        """Returns compass string from LLM."""
        twin_with_mock.wiki_dir = initialized_wiki
        twin_with_mock._provider.invoke.return_value = "Focus on test coverage and error handling."
        result = twin_with_mock.guide("dev")
        assert result == "Focus on test coverage and error handling."

    def test_fallback_when_no_guide(
        self, twin_with_mock: Twin, initialized_wiki: Path
    ) -> None:
        """Falls back to env/pattern/design pages when guide page missing."""
        twin_with_mock.wiki_dir = initialized_wiki
        twin_with_mock._provider.invoke.return_value = "Compass from env pages"
        result = twin_with_mock.guide("nonexistent")
        assert result == "Compass from env pages"

    def test_llm_failure_returns_none(
        self, twin_config: TwinProviderConfig, wiki_dir: Path
    ) -> None:
        """LLM failure returns None (non-critical)."""
        provider = MagicMock()
        provider.invoke.side_effect = RuntimeError("LLM down")
        twin = Twin(config=twin_config, wiki_dir=wiki_dir, provider=provider)
        assert twin.guide("dev") is None

    def test_empty_output_returns_none(
        self, twin_with_mock: Twin, initialized_wiki: Path
    ) -> None:
        """Empty LLM output returns None."""
        twin_with_mock.wiki_dir = initialized_wiki
        twin_with_mock._provider.invoke.return_value = "   "
        assert twin_with_mock.guide("dev") is None


# ---------------------------------------------------------------------------
# apply_page_updates
# ---------------------------------------------------------------------------


class TestApplyPageUpdates:
    """Tests for apply_page_updates standalone function."""

    # -- CREATE --

    def test_create_writes_new_page(self, wiki_dir: Path) -> None:
        """CREATE writes a new page to disk."""
        content = "---\ncategory: env\nsentiment: positive\nconfidence: tentative\noccurrences: 0\nlast_updated: \"\"\nsource_epics: []\nlinks_to: []\n---\n\n# Test\n\n## What\nDesc"
        updates = [PageUpdate(page_name="env-test", action="create", content=content)]
        apply_page_updates(updates, wiki_dir, "EPIC-001")
        assert page_exists(wiki_dir, "env-test")

    def test_create_existing_skips(self, wiki_dir: Path) -> None:
        """CREATE on existing page skips (should use UPDATE/EVOLVE)."""
        write_page(wiki_dir, "env-test", "original")
        content = "---\ncategory: env\n---\n\n# New"
        updates = [PageUpdate(page_name="env-test", action="create", content=content)]
        apply_page_updates(updates, wiki_dir, "EPIC-001")
        # Original should be preserved
        assert read_page(wiki_dir, "env-test") == "original"

    def test_create_adds_source_epics(self, wiki_dir: Path) -> None:
        """CREATE ensures source_epics includes epic_id."""
        content = "---\ncategory: env\nsentiment: positive\nconfidence: tentative\noccurrences: 0\nlast_updated: \"\"\nsource_epics: []\nlinks_to: []\n---\n\n# Test"
        updates = [PageUpdate(page_name="env-test", action="create", content=content)]
        apply_page_updates(updates, wiki_dir, "EPIC-001")
        page = read_page(wiki_dir, "env-test")
        fm = parse_frontmatter(page)
        assert "EPIC-001" in fm.get("source_epics", [])

    def test_create_invalid_name_skips(self, wiki_dir: Path) -> None:
        """CREATE with invalid page_name skips the update."""
        content = "Some content"
        updates = [PageUpdate(page_name="invalid-name", action="create", content=content)]
        apply_page_updates(updates, wiki_dir, "EPIC-001")
        assert not page_exists(wiki_dir, "invalid-name")

    def test_create_substring_dedup_warns(self, wiki_dir: Path) -> None:
        """CREATE with substring overlap logs warning but proceeds."""
        write_page(wiki_dir, "env-react", "---\ncategory: env\n---\n\n# React")
        content = "---\ncategory: env\n---\n\n# React Hooks"
        updates = [PageUpdate(page_name="env-react-hooks", action="create", content=content)]
        # Should not raise, just log warning
        apply_page_updates(updates, wiki_dir, "EPIC-001")
        assert page_exists(wiki_dir, "env-react-hooks")

    # -- UPDATE --

    def test_update_appends_evidence(self, wiki_dir: Path) -> None:
        """UPDATE appends evidence row to Evidence section."""
        content = (
            "---\ncategory: env\nsentiment: positive\nconfidence: tentative\n"
            "occurrences: 1\nlast_updated: EPIC-001\nsource_epics: [EPIC-001]\nlinks_to: []\n"
            "---\n\n# Test\n\n## Evidence\n\n"
            "| Context | Result | Epic |\n|---------|--------|------|\n"
            "| Setup | Works | EPIC-001 |\n"
        )
        write_page(wiki_dir, "env-test", content)
        updates = [
            PageUpdate(
                page_name="env-test",
                action="update",
                append_evidence={"context": "New ctx", "result": "New res"},
            )
        ]
        apply_page_updates(updates, wiki_dir, "EPIC-002")
        page = read_page(wiki_dir, "env-test")
        assert "EPIC-002" in page

    def test_update_section_patches(self, wiki_dir: Path) -> None:
        """UPDATE applies section patches."""
        content = (
            "---\ncategory: env\nsentiment: positive\nconfidence: tentative\n"
            "occurrences: 1\nlast_updated: EPIC-001\nsource_epics: [EPIC-001]\nlinks_to: []\n"
            "---\n\n# Test\n\n## What\nOld what\n\n## Why\nOld why"
        )
        write_page(wiki_dir, "env-test", content)
        updates = [
            PageUpdate(
                page_name="env-test",
                action="update",
                section_patches={"What": "New what"},
            )
        ]
        apply_page_updates(updates, wiki_dir, "EPIC-002")
        page = read_page(wiki_dir, "env-test")
        assert "New what" in page

    def test_update_evidence_before_patches(self, wiki_dir: Path) -> None:
        """UPDATE appends evidence before applying patches (ordering)."""
        content = (
            "---\ncategory: env\nsentiment: positive\nconfidence: tentative\n"
            "occurrences: 1\nlast_updated: EPIC-001\nsource_epics: [EPIC-001]\nlinks_to: []\n"
            "---\n\n# Test\n\n## Evidence\n\n"
            "| Context | Result | Epic |\n|---------|--------|------|\n"
            "| Old | OldRes | EPIC-001 |\n\n## What\nDesc"
        )
        write_page(wiki_dir, "env-test", content)
        updates = [
            PageUpdate(
                page_name="env-test",
                action="update",
                append_evidence={"context": "New", "result": "Res"},
                section_patches={"What": "Updated desc"},
            )
        ]
        apply_page_updates(updates, wiki_dir, "EPIC-002")
        page = read_page(wiki_dir, "env-test")
        # Both evidence row and patched section should be present
        assert "Updated desc" in page
        assert "EPIC-002" in page

    def test_update_frontmatter_updated(self, wiki_dir: Path) -> None:
        """UPDATE increments occurrences and re-derives confidence."""
        content = (
            "---\ncategory: env\nsentiment: positive\nconfidence: tentative\n"
            "occurrences: 1\nlast_updated: EPIC-001\nsource_epics: [EPIC-001]\nlinks_to: []\n"
            "---\n\n# Test\n\n## What\nDesc"
        )
        write_page(wiki_dir, "env-test", content)
        updates = [PageUpdate(page_name="env-test", action="update")]
        apply_page_updates(updates, wiki_dir, "EPIC-002")
        page = read_page(wiki_dir, "env-test")
        fm = parse_frontmatter(page)
        assert fm["occurrences"] == 2
        assert fm["confidence"] == "established"

    def test_update_nonexistent_with_content_creates(self, wiki_dir: Path) -> None:
        """UPDATE on nonexistent page with content falls back to CREATE."""
        content = "---\ncategory: env\nsentiment: positive\nconfidence: tentative\noccurrences: 0\nlast_updated: \"\"\nsource_epics: []\nlinks_to: []\n---\n\n# New Page"
        updates = [
            PageUpdate(page_name="env-new", action="update", content=content)
        ]
        apply_page_updates(updates, wiki_dir, "EPIC-001")
        assert page_exists(wiki_dir, "env-new")

    # -- EVOLVE --

    def test_evolve_preserves_evidence(self, wiki_dir: Path) -> None:
        """EVOLVE replaces {{EVIDENCE_TABLE}} with original evidence table."""
        content = (
            "---\ncategory: env\nsentiment: positive\nconfidence: established\n"
            "occurrences: 2\nlast_updated: EPIC-002\nsource_epics: [EPIC-001, EPIC-002]\nlinks_to: []\n"
            "---\n\n# Test\n\n## Evidence\n\n"
            "| Context | Result | Epic |\n|---------|--------|------|\n"
            "| Setup | Works | EPIC-001 |\n\n## What\nOld what"
        )
        write_page(wiki_dir, "env-test", content)

        new_content = (
            "---\ncategory: env\nsentiment: positive\nconfidence: established\n"
            "occurrences: 2\nlast_updated: EPIC-002\nsource_epics: [EPIC-001, EPIC-002]\nlinks_to: []\n"
            "---\n\n# Test\n\n## Evidence\n\n{{EVIDENCE_TABLE}}\n\n## What\nEvolved what"
        )
        updates = [
            PageUpdate(page_name="env-test", action="evolve", content=new_content)
        ]
        apply_page_updates(updates, wiki_dir, "EPIC-002")
        page = read_page(wiki_dir, "env-test")
        # Original evidence should be preserved
        assert "EPIC-001" in page
        assert "Evolved what" in page

    def test_evolve_safety_check_mismatched_epic(self, wiki_dir: Path) -> None:
        """EVOLVE skips when last_updated != epic_id (manual edits take priority)."""
        content = (
            "---\ncategory: env\nsentiment: positive\nconfidence: established\n"
            "occurrences: 2\nlast_updated: EPIC-999\nsource_epics: [EPIC-999]\nlinks_to: []\n"
            "---\n\n# Test\n\n## What\nOriginal"
        )
        write_page(wiki_dir, "env-test", content)
        updates = [
            PageUpdate(page_name="env-test", action="evolve", content="---\ncategory: env\n---\n\n# Evolved")
        ]
        apply_page_updates(updates, wiki_dir, "EPIC-001")
        # Page should NOT be modified
        page = read_page(wiki_dir, "env-test")
        assert "Original" in page

    def test_evolve_no_frontmatter_copies_from_existing(self, wiki_dir: Path) -> None:
        """EVOLVE content without frontmatter copies from existing page."""
        content = (
            "---\ncategory: env\nsentiment: positive\nconfidence: tentative\n"
            "occurrences: 1\nlast_updated: EPIC-001\nsource_epics: [EPIC-001]\nlinks_to: []\n"
            "---\n\n# Test\n\n## What\nOld"
        )
        write_page(wiki_dir, "env-test", content)

        new_content = "# Test\n\n## What\nEvolved without frontmatter"
        updates = [
            PageUpdate(page_name="env-test", action="evolve", content=new_content)
        ]
        apply_page_updates(updates, wiki_dir, "EPIC-001")
        page = read_page(wiki_dir, "env-test")
        # Should have frontmatter from existing page
        fm = parse_frontmatter(page)
        assert "category" in fm

    def test_evolve_nonexistent_skips(self, wiki_dir: Path) -> None:
        """EVOLVE on nonexistent page skips."""
        updates = [
            PageUpdate(page_name="env-nope", action="evolve", content="new")
        ]
        apply_page_updates(updates, wiki_dir, "EPIC-001")
        assert not page_exists(wiki_dir, "env-nope")

    # -- General --

    def test_rebuild_index_called(self, wiki_dir: Path) -> None:
        """apply_page_updates calls rebuild_index after all updates."""
        content = "---\ncategory: env\nsentiment: positive\nconfidence: tentative\noccurrences: 0\nlast_updated: \"\"\nsource_epics: []\nlinks_to: []\n---\n\n# Test\n\n## What\nDesc"
        updates = [PageUpdate(page_name="env-test", action="create", content=content)]
        apply_page_updates(updates, wiki_dir, "EPIC-001")
        # INDEX should exist after apply_page_updates
        assert page_exists(wiki_dir, "INDEX")

    def test_continue_on_failure(self, wiki_dir: Path) -> None:
        """Individual update failure doesn't stop other updates."""
        content = "---\ncategory: env\nsentiment: positive\nconfidence: tentative\noccurrences: 0\nlast_updated: \"\"\nsource_epics: []\nlinks_to: []\n---\n\n# Good\n\n## What\nDesc"
        updates = [
            PageUpdate(page_name="invalid-name", action="create", content="bad"),
            PageUpdate(page_name="env-good", action="create", content=content),
        ]
        apply_page_updates(updates, wiki_dir, "EPIC-001")
        # The valid update should still succeed
        assert page_exists(wiki_dir, "env-good")

    def test_empty_list_noop(self, wiki_dir: Path) -> None:
        """Empty updates list is a no-op."""
        apply_page_updates([], wiki_dir, "EPIC-001")
        # No crash, just rebuilds INDEX (empty)
