"""Tests for Twin class, Pydantic models, apply_page_updates, extract_yaml_block."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pytest
from pydantic import ValidationError

from bmad_assist.core.exceptions import ProviderTimeoutError
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
from bmad_assist.twin.prompts import build_extract_self_audit_prompt
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


# ---------------------------------------------------------------------------
# Twin._extract_self_audit_llm
# ---------------------------------------------------------------------------


class TestTwinExtractSelfAudit:
    """Tests for Twin._extract_self_audit_llm."""

    def test_regex_succeeds_no_llm_call(
        self, twin_with_mock: Twin, sample_record: ExecutionRecord
    ) -> None:
        """When record.self_audit is not None, _extract_self_audit_llm is NOT called."""
        # sample_record has self_audit="- All ACs satisfied\n- Tests pass"
        twin_with_mock._provider.invoke.return_value = make_yaml_output(decision="continue", rationale="ok")
        result = twin_with_mock.reflect(sample_record)
        assert result.decision == "continue"
        # Only the main reflect call was made (no extraction call)
        # Successful parse on first attempt = 1 invoke call
        assert twin_with_mock._provider.invoke.call_count == 1

    def test_llm_fallback_when_regex_none(
        self, twin_config: TwinProviderConfig, wiki_dir: Path
    ) -> None:
        """When self_audit is None, LLM extraction is attempted."""
        provider = MagicMock()

        # First call: extraction returns found=true
        extract_output = "```yaml\nfound: true\ncontent: |\n  - All criteria met\n  - No regressions\n```"
        # Second call: main reflect
        reflect_output = make_yaml_output(decision="continue", rationale="ok")

        provider.invoke.side_effect = [extract_output, reflect_output]
        twin = Twin(config=twin_config, wiki_dir=wiki_dir, provider=provider)

        record = ExecutionRecord(
            phase="dev_story", mission="m",
            llm_output="## 审查\n- 完成", self_audit=None,
            success=True, duration_ms=100, error=None,
        )
        result = twin.reflect(record)
        assert result.decision == "continue"
        # Extraction call should have been made
        assert provider.invoke.call_count >= 1

    def test_llm_returns_found_false(
        self, twin_config: TwinProviderConfig, wiki_dir: Path
    ) -> None:
        """When LLM returns found:false, self_audit remains None."""
        provider = MagicMock()

        # Extraction returns found:false
        extract_output = "```yaml\nfound: false\ncontent: \"\"\n```"
        # Main reflect call
        reflect_output = make_yaml_output(decision="continue", rationale="ok")

        provider.invoke.side_effect = [extract_output, reflect_output]
        twin = Twin(config=twin_config, wiki_dir=wiki_dir, provider=provider)

        record = ExecutionRecord(
            phase="dev_story", mission="m",
            llm_output="No audit section here", self_audit=None,
            success=True, duration_ms=100, error=None,
        )
        result = twin.reflect(record)
        assert result.decision == "continue"

    def test_provider_failure_graceful(
        self, twin_config: TwinProviderConfig, wiki_dir: Path
    ) -> None:
        """Provider exception during extraction returns None gracefully."""
        provider = MagicMock()

        # Extraction raises exception
        # Main reflect call succeeds
        reflect_output = make_yaml_output(decision="continue", rationale="ok")

        provider.invoke.side_effect = [RuntimeError("API down"), reflect_output, reflect_output]
        twin = Twin(config=twin_config, wiki_dir=wiki_dir, provider=provider)

        record = ExecutionRecord(
            phase="dev_story", mission="m",
            llm_output="Some output", self_audit=None,
            success=True, duration_ms=100, error=None,
        )
        result = twin.reflect(record)
        assert result.decision == "continue"

    def test_audit_extract_model_usage(
        self, wiki_dir: Path
    ) -> None:
        """When audit_extract_model is set, extraction uses that model."""
        config = TwinProviderConfig(enabled=True, audit_extract_model="haiku")
        provider = MagicMock()

        extract_output = "```yaml\nfound: true\ncontent: |\n  Extracted audit\n```"
        reflect_output = make_yaml_output(decision="continue", rationale="ok")

        provider.invoke.side_effect = [extract_output, reflect_output]
        twin = Twin(config=config, wiki_dir=wiki_dir, provider=provider)

        record = ExecutionRecord(
            phase="dev_story", mission="m",
            llm_output="## 审查\n- 完成", self_audit=None,
            success=True, duration_ms=100, error=None,
        )
        twin.reflect(record)

        # First call (extraction) should use "haiku"
        first_call_kwargs = provider.invoke.call_args_list[0]
        assert first_call_kwargs[1].get("model") == "haiku" or (
            len(first_call_kwargs[0]) > 1 and first_call_kwargs[0][1] == "haiku"
        )

    def test_none_fallback_to_main_model(
        self, twin_config: TwinProviderConfig, wiki_dir: Path
    ) -> None:
        """When audit_extract_model is None, extraction uses main model."""
        provider = MagicMock()

        extract_output = "```yaml\nfound: true\ncontent: |\n  Extracted\n```"
        reflect_output = make_yaml_output(decision="continue", rationale="ok")

        provider.invoke.side_effect = [extract_output, reflect_output]
        twin = Twin(config=twin_config, wiki_dir=wiki_dir, provider=provider)

        record = ExecutionRecord(
            phase="dev_story", mission="m",
            llm_output="## 审查\n- Done", self_audit=None,
            success=True, duration_ms=100, error=None,
        )
        twin.reflect(record)

        # First call should use main model ("opus" from default config)
        first_call_kwargs = provider.invoke.call_args_list[0]
        model_used = first_call_kwargs[1].get("model") or (
            first_call_kwargs[0][1] if len(first_call_kwargs[0]) > 1 else None
        )
        assert model_used == "opus"

    def test_empty_llm_output_returns_none(
        self, twin_config: TwinProviderConfig, wiki_dir: Path
    ) -> None:
        """Empty llm_output returns None without LLM call."""
        provider = MagicMock()
        reflect_output = make_yaml_output(decision="continue", rationale="ok")
        provider.invoke.return_value = reflect_output

        twin = Twin(config=twin_config, wiki_dir=wiki_dir, provider=provider)

        record = ExecutionRecord(
            phase="dev_story", mission="m",
            llm_output="", self_audit=None,
            success=True, duration_ms=100, error=None,
        )
        result = twin.reflect(record)
        assert result.decision == "continue"

    def test_record_not_modified_by_extraction(
        self, twin_config: TwinProviderConfig, wiki_dir: Path
    ) -> None:
        """LLM extraction result doesn't modify the record dataclass."""
        provider = MagicMock()

        extract_output = "```yaml\nfound: true\ncontent: |\n  - Extracted audit\n```"
        reflect_output = make_yaml_output(decision="continue", rationale="ok")

        provider.invoke.side_effect = [extract_output, reflect_output]
        twin = Twin(config=twin_config, wiki_dir=wiki_dir, provider=provider)

        record = ExecutionRecord(
            phase="dev_story", mission="m",
            llm_output="## 审查\n- Done", self_audit=None,
            success=True, duration_ms=100, error=None,
        )
        twin.reflect(record)
        # record.self_audit should still be None (not modified)
        assert record.self_audit is None


# ---------------------------------------------------------------------------
# Chinese heading and non-standard heading level scenarios
# ---------------------------------------------------------------------------


class TestTwinExtractSelfAuditHeadings:
    """Tests for Chinese heading and non-standard heading level extraction."""

    def test_chinese_heading_audit(
        self, twin_config: TwinProviderConfig, wiki_dir: Path
    ) -> None:
        """LLM extraction finds Chinese heading '审查' section."""
        provider = MagicMock()

        extract_output = "```yaml\nfound: true\ncontent: |\n  - 所有验收标准已满足\n  - 无回归问题\n```"
        reflect_output = make_yaml_output(decision="continue", rationale="ok")

        provider.invoke.side_effect = [extract_output, reflect_output]
        twin = Twin(config=twin_config, wiki_dir=wiki_dir, provider=provider)

        record = ExecutionRecord(
            phase="dev_story", mission="m",
            llm_output="## 审查\n- 所有验收标准已满足\n- 无回归问题",
            self_audit=None, success=True, duration_ms=100, error=None,
        )
        result = twin.reflect(record)
        assert result.decision == "continue"

    def test_chinese_zishen_heading(
        self, twin_config: TwinProviderConfig, wiki_dir: Path
    ) -> None:
        """LLM extraction finds Chinese heading '自审' section."""
        provider = MagicMock()

        extract_output = "```yaml\nfound: true\ncontent: |\n  - 代码质量良好\n```"
        reflect_output = make_yaml_output(decision="continue", rationale="ok")

        provider.invoke.side_effect = [extract_output, reflect_output]
        twin = Twin(config=twin_config, wiki_dir=wiki_dir, provider=provider)

        record = ExecutionRecord(
            phase="dev_story", mission="m",
            llm_output="## 自审\n- 代码质量良好",
            self_audit=None, success=True, duration_ms=100, error=None,
        )
        result = twin.reflect(record)
        assert result.decision == "continue"

    def test_h3_quality_check_heading(
        self, twin_config: TwinProviderConfig, wiki_dir: Path
    ) -> None:
        """LLM extraction finds h3 '### Quality Check' section."""
        provider = MagicMock()

        extract_output = "```yaml\nfound: true\ncontent: |\n  - Code reviewed\n  - Tests passing\n```"
        reflect_output = make_yaml_output(decision="continue", rationale="ok")

        provider.invoke.side_effect = [extract_output, reflect_output]
        twin = Twin(config=twin_config, wiki_dir=wiki_dir, provider=provider)

        record = ExecutionRecord(
            phase="dev_story", mission="m",
            llm_output="### Quality Check\n- Code reviewed\n- Tests passing",
            self_audit=None, success=True, duration_ms=100, error=None,
        )
        result = twin.reflect(record)
        assert result.decision == "continue"


# ---------------------------------------------------------------------------
# Direct unit tests for _extract_self_audit_llm
# ---------------------------------------------------------------------------


class TestExtractSelfAuditLlmUnit:
    """Direct unit tests for Twin._extract_self_audit_llm."""

    def test_successful_extraction_returns_content(
        self, twin_config: TwinProviderConfig, wiki_dir: Path
    ) -> None:
        """Direct call returns extracted content when LLM finds audit."""
        provider = MagicMock()
        provider.invoke.return_value = (
            "```yaml\nfound: true\ncontent: |\n  - ACs met\n  - No regressions\n```"
        )
        twin = Twin(config=twin_config, wiki_dir=wiki_dir, provider=provider)

        result = twin._extract_self_audit_llm("## 审查\n- ACs met\n- No regressions")
        assert result is not None
        assert "ACs met" in result
        assert "No regressions" in result

    def test_empty_llm_output_returns_none_without_call(
        self, twin_config: TwinProviderConfig, wiki_dir: Path
    ) -> None:
        """Empty string returns None immediately, no LLM call."""
        provider = MagicMock()
        twin = Twin(config=twin_config, wiki_dir=wiki_dir, provider=provider)

        result = twin._extract_self_audit_llm("")
        assert result is None
        provider.invoke.assert_not_called()

    def test_yaml_parse_failure_returns_none(
        self, twin_config: TwinProviderConfig, wiki_dir: Path
    ) -> None:
        """LLM returns non-YAML output → returns None."""
        provider = MagicMock()
        provider.invoke.return_value = "I couldn't find any audit section in this document."
        twin = Twin(config=twin_config, wiki_dir=wiki_dir, provider=provider)

        result = twin._extract_self_audit_llm("Some output text")
        assert result is None

    def test_invalid_yaml_block_returns_none(
        self, twin_config: TwinProviderConfig, wiki_dir: Path
    ) -> None:
        """LLM returns YAML block but content is invalid YAML → returns None."""
        provider = MagicMock()
        provider.invoke.return_value = "```yaml\nfound: true\ncontent: {invalid yaml [[\n```"
        twin = Twin(config=twin_config, wiki_dir=wiki_dir, provider=provider)

        result = twin._extract_self_audit_llm("Some output")
        assert result is None

    def test_found_true_empty_content_returns_none(
        self, twin_config: TwinProviderConfig, wiki_dir: Path
    ) -> None:
        """found: true but content is empty string → returns None."""
        provider = MagicMock()
        provider.invoke.return_value = "```yaml\nfound: true\ncontent: \"\"\n```"
        twin = Twin(config=twin_config, wiki_dir=wiki_dir, provider=provider)

        result = twin._extract_self_audit_llm("Some output")
        assert result is None

    def test_found_false_returns_none(
        self, twin_config: TwinProviderConfig, wiki_dir: Path
    ) -> None:
        """found: false → returns None."""
        provider = MagicMock()
        provider.invoke.return_value = "```yaml\nfound: false\ncontent: \"\"\n```"
        twin = Twin(config=twin_config, wiki_dir=wiki_dir, provider=provider)

        result = twin._extract_self_audit_llm("Some output without audit")
        assert result is None

    def test_non_dict_yaml_returns_none(
        self, twin_config: TwinProviderConfig, wiki_dir: Path
    ) -> None:
        """YAML parses to a list (not dict) → returns None."""
        provider = MagicMock()
        provider.invoke.return_value = "```yaml\n- item1\n- item2\n```"
        twin = Twin(config=twin_config, wiki_dir=wiki_dir, provider=provider)

        result = twin._extract_self_audit_llm("Some output")
        assert result is None

    def test_provider_exception_returns_none(
        self, twin_config: TwinProviderConfig, wiki_dir: Path
    ) -> None:
        """Provider raises exception → returns None, does not propagate."""
        provider = MagicMock()
        provider.invoke.side_effect = RuntimeError("API timeout")
        twin = Twin(config=twin_config, wiki_dir=wiki_dir, provider=provider)

        result = twin._extract_self_audit_llm("Some output")
        assert result is None

    def test_uses_audit_extract_model(
        self, wiki_dir: Path
    ) -> None:
        """When audit_extract_model is set, invoke is called with that model."""
        config = TwinProviderConfig(enabled=True, audit_extract_model="haiku")
        provider = MagicMock()
        provider.invoke.return_value = "```yaml\nfound: false\ncontent: \"\"\n```"
        twin = Twin(config=config, wiki_dir=wiki_dir, provider=provider)

        twin._extract_self_audit_llm("Some output")
        provider.invoke.assert_called_once()
        call_kwargs = provider.invoke.call_args
        assert call_kwargs[1]["model"] == "haiku"

    def test_none_model_falls_back_to_main(
        self, twin_config: TwinProviderConfig, wiki_dir: Path
    ) -> None:
        """When audit_extract_model is None, uses main model."""
        provider = MagicMock()
        provider.invoke.return_value = "```yaml\nfound: false\ncontent: \"\"\n```"
        twin = Twin(config=twin_config, wiki_dir=wiki_dir, provider=provider)

        twin._extract_self_audit_llm("Some output")
        provider.invoke.assert_called_once()
        call_kwargs = provider.invoke.call_args
        assert call_kwargs[1]["model"] == "opus"

    def test_content_is_stripped(
        self, twin_config: TwinProviderConfig, wiki_dir: Path
    ) -> None:
        """Returned content has leading/trailing whitespace stripped."""
        provider = MagicMock()
        provider.invoke.return_value = (
            "```yaml\nfound: true\ncontent: |\n  - Item 1\n  - Item 2\n  \n```"
        )
        twin = Twin(config=twin_config, wiki_dir=wiki_dir, provider=provider)

        result = twin._extract_self_audit_llm("Some output")
        assert result is not None
        assert result.strip() == result

    def test_invoke_prompt_contains_document(
        self, twin_config: TwinProviderConfig, wiki_dir: Path
    ) -> None:
        """The prompt passed to invoke contains the llm_output text."""
        provider = MagicMock()
        provider.invoke.return_value = "```yaml\nfound: false\ncontent: \"\"\n```"
        twin = Twin(config=twin_config, wiki_dir=wiki_dir, provider=provider)

        twin._extract_self_audit_llm("UNIQUE_MARKER_TEXT_12345")
        call_args = provider.invoke.call_args
        prompt = call_args[1].get("prompt") or (call_args[0][0] if call_args[0] else None)
        assert "UNIQUE_MARKER_TEXT_12345" in prompt


# ---------------------------------------------------------------------------
# Integration: extracted content flows into reflect prompt
# ---------------------------------------------------------------------------


class TestExtractSelfAuditIntegration:
    """Verify extracted content reaches build_reflect_prompt correctly."""

    def test_extracted_content_appears_in_reflect_prompt(
        self, twin_config: TwinProviderConfig, wiki_dir: Path
    ) -> None:
        """When LLM extracts audit, the content appears in the reflect prompt."""
        provider = MagicMock()
        captured_prompts = []

        def capture_invoke(prompt: str, **kwargs) -> str:
            captured_prompts.append(prompt)
            if len(captured_prompts) == 1:
                # First call = extraction
                return "```yaml\nfound: true\ncontent: |\n  - ALL_AC_MET\n  - NO_REGRESSION\n```"
            # Second call = reflect
            return make_yaml_output(decision="continue", rationale="ok")

        provider.invoke = capture_invoke
        twin = Twin(config=twin_config, wiki_dir=wiki_dir, provider=provider)

        record = ExecutionRecord(
            phase="dev_story", mission="m",
            llm_output="## 审查\n- ALL_AC_MET\n- NO_REGRESSION",
            self_audit=None, success=True, duration_ms=100, error=None,
        )
        twin.reflect(record)

        # The reflect prompt (second call) should contain extracted content
        reflect_prompt = captured_prompts[1]
        assert "ALL_AC_MET" in reflect_prompt

    def test_extraction_none_falls_back_to_no_audit_message(
        self, twin_config: TwinProviderConfig, wiki_dir: Path
    ) -> None:
        """When extraction also returns None, prompt uses '(No Self-Audit…)'."""
        provider = MagicMock()
        captured_prompts = []

        def capture_invoke(prompt: str, **kwargs) -> str:
            captured_prompts.append(prompt)
            if len(captured_prompts) == 1:
                # Extraction returns found:false
                return "```yaml\nfound: false\ncontent: \"\"\n```"
            return make_yaml_output(decision="continue", rationale="ok")

        provider.invoke = capture_invoke
        twin = Twin(config=twin_config, wiki_dir=wiki_dir, provider=provider)

        record = ExecutionRecord(
            phase="dev_story", mission="m",
            llm_output="No audit here at all",
            self_audit=None, success=True, duration_ms=100, error=None,
        )
        twin.reflect(record)

        reflect_prompt = captured_prompts[1]
        assert "No Self-Audit section found" in reflect_prompt


# ---------------------------------------------------------------------------
# Timeout retry behavior
# ---------------------------------------------------------------------------


class TestInvokeLlmTimeoutRetry:
    """Tests for _invoke_llm timeout retry via invoke_with_timeout_retry."""

    def test_retries_on_timeout_and_succeeds(
        self, wiki_dir: Path
    ) -> None:
        """_invoke_llm retries on ProviderTimeoutError and succeeds on second attempt."""
        provider = MagicMock()
        provider.invoke.side_effect = [
            ProviderTimeoutError("timeout"),
            "LLM output text",
        ]
        config = TwinProviderConfig(enabled=True, timeout_retries=2)
        twin = Twin(config=config, wiki_dir=wiki_dir, provider=provider)

        result = twin._invoke_llm("test prompt")
        assert result == "LLM output text"
        assert provider.invoke.call_count == 2

    def test_raises_after_retries_exhausted(
        self, wiki_dir: Path
    ) -> None:
        """_invoke_llm raises ProviderTimeoutError after all timeout retries exhausted."""
        provider = MagicMock()
        provider.invoke.side_effect = ProviderTimeoutError("timeout")
        config = TwinProviderConfig(enabled=True, timeout_retries=2)
        twin = Twin(config=config, wiki_dir=wiki_dir, provider=provider)

        with pytest.raises(ProviderTimeoutError, match="timeout"):
            twin._invoke_llm("test prompt")
        # 1 initial + 2 retries = 3 attempts
        assert provider.invoke.call_count == 3

    def test_no_retry_when_timeout_retries_none(
        self, wiki_dir: Path
    ) -> None:
        """_invoke_llm with timeout_retries=None does not retry on timeout."""
        provider = MagicMock()
        provider.invoke.side_effect = ProviderTimeoutError("timeout")
        config = TwinProviderConfig(enabled=True, timeout_retries=None)
        twin = Twin(config=config, wiki_dir=wiki_dir, provider=provider)

        with pytest.raises(ProviderTimeoutError, match="timeout"):
            twin._invoke_llm("test prompt")
        # Only 1 attempt, no retry
        assert provider.invoke.call_count == 1


class TestExtractSelfAuditTimeoutRetry:
    """Tests for _extract_self_audit_llm timeout retry behavior."""

    def test_retries_on_timeout_and_returns_content(
        self, wiki_dir: Path
    ) -> None:
        """_extract_self_audit_llm retries on ProviderTimeoutError and returns content."""
        provider = MagicMock()
        provider.invoke.side_effect = [
            ProviderTimeoutError("timeout"),
            "```yaml\nfound: true\ncontent: |\n  - Extracted audit\n```",
        ]
        config = TwinProviderConfig(enabled=True, timeout_retries=2)
        twin = Twin(config=config, wiki_dir=wiki_dir, provider=provider)

        result = twin._extract_self_audit_llm("Some output")
        assert result is not None
        assert "Extracted audit" in result
        assert provider.invoke.call_count == 2

    def test_returns_none_after_retries_exhausted(
        self, wiki_dir: Path
    ) -> None:
        """_extract_self_audit_llm returns None after timeout retries exhausted."""
        provider = MagicMock()
        provider.invoke.side_effect = ProviderTimeoutError("timeout")
        config = TwinProviderConfig(enabled=True, timeout_retries=2)
        twin = Twin(config=config, wiki_dir=wiki_dir, provider=provider)

        result = twin._extract_self_audit_llm("Some output")
        assert result is None


class TestInvokeLlmPassesTimeout:
    """Tests verifying _invoke_llm passes config.timeout to invoke_with_timeout_retry."""

    def test_default_timeout_passed(self, wiki_dir: Path) -> None:
        """_invoke_llm passes default timeout=300 to provider.invoke."""
        provider = MagicMock()
        provider.invoke.return_value = "LLM output"
        config = TwinProviderConfig(enabled=True)
        twin = Twin(config=config, wiki_dir=wiki_dir, provider=provider)

        twin._invoke_llm("test prompt")
        provider.invoke.assert_called_once()
        call_kwargs = provider.invoke.call_args.kwargs
        assert call_kwargs.get("timeout") == 300

    def test_custom_timeout_passed(self, wiki_dir: Path) -> None:
        """_invoke_llm passes custom timeout=600 to provider.invoke."""
        provider = MagicMock()
        provider.invoke.return_value = "LLM output"
        config = TwinProviderConfig(enabled=True, timeout=600)
        twin = Twin(config=config, wiki_dir=wiki_dir, provider=provider)

        twin._invoke_llm("test prompt")
        provider.invoke.assert_called_once()
        call_kwargs = provider.invoke.call_args.kwargs
        assert call_kwargs.get("timeout") == 600


class TestExtractSelfAuditLlmPassesTimeout:
    """Tests verifying _extract_self_audit_llm passes config.timeout to invoke_with_timeout_retry."""

    def test_default_timeout_passed(self, wiki_dir: Path) -> None:
        """_extract_self_audit_llm passes default timeout=300 to provider.invoke."""
        provider = MagicMock()
        provider.invoke.return_value = "```yaml\nfound: true\ncontent: |\n  - Audit text\n```"
        config = TwinProviderConfig(enabled=True)
        twin = Twin(config=config, wiki_dir=wiki_dir, provider=provider)

        twin._extract_self_audit_llm("Some output")
        provider.invoke.assert_called_once()
        call_kwargs = provider.invoke.call_args.kwargs
        assert call_kwargs.get("timeout") == 300

    def test_custom_timeout_passed(self, wiki_dir: Path) -> None:
        """_extract_self_audit_llm passes custom timeout=600 to provider.invoke."""
        provider = MagicMock()
        provider.invoke.return_value = "```yaml\nfound: true\ncontent: |\n  - Audit text\n```"
        config = TwinProviderConfig(enabled=True, timeout=600)
        twin = Twin(config=config, wiki_dir=wiki_dir, provider=provider)

        twin._extract_self_audit_llm("Some output")
        provider.invoke.assert_called_once()
        call_kwargs = provider.invoke.call_args.kwargs
        assert call_kwargs.get("timeout") == 600


class TestReflectWithRetryTimeoutDegradation:
    """Tests for _reflect_with_retry degradation when timeout retries exhausted."""

    def test_degradation_on_timeout_exhausted(
        self, wiki_dir: Path
    ) -> None:
        """_reflect_with_retry applies degradation when _invoke_llm raises ProviderTimeoutError."""
        provider = MagicMock()
        provider.invoke.side_effect = ProviderTimeoutError("timeout")
        # halt on exhaust + is_retry=True → decision should be halt
        config = TwinProviderConfig(
            enabled=True, timeout_retries=2,
            retry_exhausted_action="halt",
        )
        twin = Twin(config=config, wiki_dir=wiki_dir, provider=provider)

        result = twin._reflect_with_retry("prompt", is_retry=True, epic_id=None)
        assert result.decision == "halt"


class TestReflectE2eTimeoutRetry:
    """End-to-end test: reflect with timeout on first attempt, retry succeeds."""

    def test_timeout_then_success_returns_valid_result(
        self, wiki_dir: Path
    ) -> None:
        """reflect() end-to-end: timeout on first attempt, retry succeeds."""
        provider = MagicMock()
        provider.invoke.side_effect = [
            ProviderTimeoutError("timeout"),
            make_yaml_output(decision="continue", rationale="Recovered after timeout"),
        ]
        config = TwinProviderConfig(enabled=True, timeout_retries=2)
        twin = Twin(config=config, wiki_dir=wiki_dir, provider=provider)

        record = ExecutionRecord(
            phase="dev_story", mission="m",
            llm_output="output", self_audit="- Audit OK",
            success=True, duration_ms=100, error=None,
        )
        result = twin.reflect(record)
        assert result.decision == "continue"
        assert "Recovered after timeout" in result.rationale
