"""Tests for wiki.py functions.

Covers: read_page, write_page, list_pages, page_exists, parse_frontmatter,
update_frontmatter, extract_links, rebuild_index, validate_page_name,
apply_section_patches, append_evidence_row, extract_evidence_table,
init_wiki, load_guide_page, fix_content_block_scalars, prepare_llm_output,
derive_confidence.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from bmad_assist.twin.wiki import (
    append_evidence_row,
    apply_section_patches,
    derive_confidence,
    extract_evidence_table,
    extract_links,
    fix_content_block_scalars,
    init_wiki,
    list_pages,
    load_guide_page,
    page_exists,
    parse_frontmatter,
    prepare_llm_output,
    read_page,
    rebuild_index,
    update_frontmatter,
    validate_page_name,
    write_page,
)


# ---------------------------------------------------------------------------
# Basic I/O
# ---------------------------------------------------------------------------


class TestReadWritePage:
    """Tests for read_page and write_page."""

    def test_write_and_read_page(self, wiki_dir: Path) -> None:
        """Write then read returns the same content."""
        content = "---\ncategory: env\n---\n\n# Test\n\nHello"
        write_page(wiki_dir, "env-test", content)
        assert read_page(wiki_dir, "env-test") == content

    def test_read_nonexistent_page(self, wiki_dir: Path) -> None:
        """Reading a nonexistent page returns None."""
        assert read_page(wiki_dir, "env-nope") is None

    def test_write_overwrites_existing(self, wiki_dir: Path) -> None:
        """Writing to an existing page overwrites it."""
        write_page(wiki_dir, "env-test", "old")
        write_page(wiki_dir, "env-test", "new")
        assert read_page(wiki_dir, "env-test") == "new"


class TestListPages:
    """Tests for list_pages."""

    def test_empty_dir(self, wiki_dir: Path) -> None:
        """Empty wiki returns empty list."""
        assert list_pages(wiki_dir) == []

    def test_lists_page_stems(self, wiki_dir: Path) -> None:
        """Returns sorted page stems (no .md, no INDEX)."""
        write_page(wiki_dir, "env-alpha", "a")
        write_page(wiki_dir, "pattern-beta", "b")
        # INDEX is excluded
        (wiki_dir / "INDEX.md").write_text("# INDEX\n")
        result = list_pages(wiki_dir)
        assert result == ["env-alpha", "pattern-beta"]

    def test_nonexistent_dir(self, tmp_path: Path) -> None:
        """Nonexistent directory returns empty list."""
        assert list_pages(tmp_path / "nope") == []


class TestPageExists:
    """Tests for page_exists."""

    def test_existing_page(self, wiki_dir: Path) -> None:
        """Returns True for existing page."""
        write_page(wiki_dir, "env-test", "content")
        assert page_exists(wiki_dir, "env-test") is True

    def test_nonexistent_page(self, wiki_dir: Path) -> None:
        """Returns False for nonexistent page."""
        assert page_exists(wiki_dir, "env-nope") is False


# ---------------------------------------------------------------------------
# Frontmatter
# ---------------------------------------------------------------------------


class TestParseFrontmatter:
    """Tests for parse_frontmatter edge cases."""

    def test_valid_frontmatter(self) -> None:
        """Parses valid YAML frontmatter."""
        content = "---\ncategory: env\nsentiment: positive\n---\n\nBody"
        fm = parse_frontmatter(content)
        assert fm == {"category": "env", "sentiment": "positive"}

    def test_no_frontmatter(self) -> None:
        """Content without --- returns empty dict."""
        assert parse_frontmatter("Just some text") == {}

    def test_unclosed_frontmatter(self) -> None:
        """Content with opening --- but no closing --- returns empty dict."""
        assert parse_frontmatter("---\ncategory: env\n") == {}

    def test_malformed_yaml(self) -> None:
        """Malformed YAML in frontmatter returns empty dict."""
        content = "---\n: invalid yaml {{\n---\n\nBody"
        assert parse_frontmatter(content) == {}

    def test_non_dict_yaml(self) -> None:
        """YAML that parses to non-dict (e.g., a list) returns empty dict."""
        content = "---\n- item1\n- item2\n---\n\nBody"
        assert parse_frontmatter(content) == {}

    def test_empty_frontmatter(self) -> None:
        """Empty frontmatter block returns empty dict."""
        content = "---\n---\n\nBody"
        assert parse_frontmatter(content) == {}


class TestUpdateFrontmatter:
    """Tests for update_frontmatter edge cases."""

    def _make_content(self, **overrides: object) -> str:
        """Helper to build a page with frontmatter."""
        fm = {
            "category": "env",
            "sentiment": "positive",
            "confidence": "tentative",
            "occurrences": 0,
            "last_updated": "",
            "source_epics": [],
            "links_to": [],
        }
        fm.update(overrides)
        import yaml

        fm_str = yaml.dump(fm, default_flow_style=False, allow_unicode=True, sort_keys=False)
        return f"---\n{fm_str}---\n\n# Test\n\nBody"

    def test_increment_occurrences(self) -> None:
        """Occurrences increments from 0 to 1."""
        content = self._make_content(occurrences=0)
        result = update_frontmatter(content, "EPIC-001")
        fm = parse_frontmatter(result)
        assert fm["occurrences"] == 1

    def test_confidence_re_derive(self) -> None:
        """Confidence is re-derived after incrementing occurrences."""
        content = self._make_content(occurrences=0, sentiment="positive")
        result = update_frontmatter(content, "EPIC-001")
        fm = parse_frontmatter(result)
        # occurrences went 0->1 → tentative
        assert fm["confidence"] == "tentative"

    def test_confidence_promotes_on_second(self) -> None:
        """Second occurrence promotes positive to established."""
        content = self._make_content(occurrences=1, sentiment="positive")
        result = update_frontmatter(content, "EPIC-002")
        fm = parse_frontmatter(result)
        assert fm["confidence"] == "established"

    def test_source_epics_append(self) -> None:
        """epic_id is appended to source_epics."""
        content = self._make_content(source_epics=["EPIC-001"])
        result = update_frontmatter(content, "EPIC-002")
        fm = parse_frontmatter(result)
        assert "EPIC-002" in fm["source_epics"]

    def test_source_epics_dedup(self) -> None:
        """Duplicate epic_id is not appended again."""
        content = self._make_content(source_epics=["EPIC-001"])
        result = update_frontmatter(content, "EPIC-001")
        fm = parse_frontmatter(result)
        assert fm["source_epics"].count("EPIC-001") == 1

    def test_no_frontmatter(self) -> None:
        """Content without frontmatter is returned unchanged."""
        content = "No frontmatter here"
        assert update_frontmatter(content, "EPIC-001") == content

    def test_negative_confidence_cap(self) -> None:
        """Negative sentiment caps at 'established' even with 3+ occurrences."""
        content = self._make_content(occurrences=2, sentiment="negative")
        result = update_frontmatter(content, "EPIC-003")
        fm = parse_frontmatter(result)
        # occurrences went 2->3, but negative caps at established
        assert fm["confidence"] == "established"


# ---------------------------------------------------------------------------
# Links and INDEX
# ---------------------------------------------------------------------------


class TestExtractLinks:
    """Tests for extract_links."""

    def test_extracts_wiki_links(self) -> None:
        """Extracts [[page-name]] links from content."""
        content = "See [[env-react]] and [[pattern-flaky]] for details."
        assert extract_links(content) == ["env-react", "pattern-flaky"]

    def test_no_links(self) -> None:
        """Returns empty list when no links present."""
        assert extract_links("No links here") == []

    def test_duplicate_links(self) -> None:
        """Duplicate links are returned as-is."""
        content = "[[env-react]] and again [[env-react]]"
        assert extract_links(content) == ["env-react", "env-react"]


class TestRebuildIndex:
    """Tests for rebuild_index."""

    def test_basic_index(self, wiki_dir: Path) -> None:
        """Rebuilds INDEX with category grouping and sentiment abbreviations."""
        write_page(wiki_dir, "env-alpha", "---\ncategory: env\nsentiment: positive\nconfidence: tentative\noccurrences: 1\nlast_updated: EPIC-001\nsource_epics: [EPIC-001]\nlinks_to: []\n---\n\n# Alpha\n\n## What\nDesc")
        rebuild_index(wiki_dir)
        index = read_page(wiki_dir, "INDEX")
        assert index is not None
        assert "env" in index
        assert "Alpha" in index
        assert "[tentative]" in index
        assert "+" in index  # positive abbreviation

    def test_backlinks(self, wiki_dir: Path) -> None:
        """Backlinks are computed from links_to."""
        write_page(wiki_dir, "env-alpha", "---\ncategory: env\nsentiment: positive\nconfidence: tentative\noccurrences: 1\nlast_updated: EPIC-001\nsource_epics: [EPIC-001]\nlinks_to: []\n---\n\n# Alpha")
        write_page(wiki_dir, "pattern-beta", "---\ncategory: pattern\nsentiment: negative\nconfidence: tentative\noccurrences: 1\nlast_updated: EPIC-001\nsource_epics: [EPIC-001]\nlinks_to: [[env-alpha]]\n---\n\n# Beta")
        rebuild_index(wiki_dir)
        index = read_page(wiki_dir, "INDEX")
        assert index is not None
        # env-alpha should have a backlink from pattern-beta
        assert "← pattern-beta" in index

    def test_category_order(self, wiki_dir: Path) -> None:
        """Categories appear in order: env, pattern, design, guide."""
        write_page(wiki_dir, "guide-z", "---\ncategory: guide\nsentiment: neutral\nconfidence: tentative\noccurrences: 0\nlast_updated: \"\"\nsource_epics: []\nlinks_to: []\n---\n\n# Z")
        write_page(wiki_dir, "env-a", "---\ncategory: env\nsentiment: positive\nconfidence: tentative\noccurrences: 1\nlast_updated: EPIC-001\nsource_epics: [EPIC-001]\nlinks_to: []\n---\n\n# A")
        rebuild_index(wiki_dir)
        index = read_page(wiki_dir, "INDEX")
        assert index is not None
        env_pos = index.index("## env")
        guide_pos = index.index("## guide")
        assert env_pos < guide_pos


# ---------------------------------------------------------------------------
# Page name validation
# ---------------------------------------------------------------------------


class TestValidatePageName:
    """Tests for validate_page_name."""

    def test_valid_names(self) -> None:
        """Valid page names pass validation."""
        for name in ["env-react-setup", "pattern-flaky-test", "design-api-arch", "guide-dev-story"]:
            assert validate_page_name(name) is True, f"{name} should be valid"

    def test_invalid_no_category_prefix(self) -> None:
        """Name without valid category prefix is rejected."""
        assert validate_page_name("random-name") is False

    def test_invalid_uppercase(self) -> None:
        """Uppercase characters are rejected."""
        assert validate_page_name("env-React") is False

    def test_invalid_underscore(self) -> None:
        """Underscores in concept part are rejected."""
        assert validate_page_name("env-react_setup") is False


# ---------------------------------------------------------------------------
# Section patches
# ---------------------------------------------------------------------------


class TestApplySectionPatches:
    """Tests for apply_section_patches."""

    def test_single_patch(self) -> None:
        """Replaces a single section body."""
        content = "# Title\n\n## What\nOld what\n\n## Why\nOld why"
        result = apply_section_patches(content, {"What": "New what"})
        assert "New what" in result
        assert "Old what" not in result
        assert "Old why" in result

    def test_multiple_patches(self) -> None:
        """Replaces multiple section bodies."""
        content = "## What\nOld\n\n## Why\nOld\n\n## How\nKeep"
        result = apply_section_patches(content, {"What": "New W", "Why": "New Y"})
        assert "New W" in result
        assert "New Y" in result
        assert "Keep" in result

    def test_missing_patch_key_unchanged(self) -> None:
        """Sections not in patches dict remain unchanged."""
        content = "## What\nOld\n\n## Why\nOld"
        result = apply_section_patches(content, {"What": "New"})
        assert "Old" in result  # Why section unchanged

    def test_empty_patches(self) -> None:
        """Empty patches dict returns content unchanged."""
        content = "## What\nOld"
        assert apply_section_patches(content, {}) == content


# ---------------------------------------------------------------------------
# Evidence row
# ---------------------------------------------------------------------------


class TestAppendEvidenceRow:
    """Tests for append_evidence_row."""

    def test_appends_row_matching_columns(self) -> None:
        """Appends a row matching the header column order."""
        content = (
            "# Title\n\n## Evidence\n\n"
            "| Context | Result | Epic |\n"
            "|---------|--------|------|\n"
            "| Setup | Works | EPIC-001 |\n"
        )
        result = append_evidence_row(content, {"context": "New ctx", "result": "New res", "epic": "EPIC-002"})
        assert "EPIC-002" in result
        # Row should appear after existing rows
        lines = result.split("\n")
        evidence_rows = [l for l in lines if l.strip().startswith("|") and "EPIC" in l]
        assert len(evidence_rows) == 2

    def test_case_insensitive_column_match(self) -> None:
        """Column matching is case-insensitive."""
        content = (
            "## Evidence\n\n"
            "| Context | Result | Epic |\n"
            "|---------|--------|------|\n"
        )
        result = append_evidence_row(content, {"CONTEXT": "ctx", "Result": "res", "EPIC": "EPIC-1"})
        assert "EPIC-1" in result

    def test_no_evidence_section(self) -> None:
        """Content without Evidence section returns unchanged."""
        content = "# Title\n\n## What\nDesc"
        assert append_evidence_row(content, {"context": "x"}) == content

    def test_empty_evidence_table(self) -> None:
        """Appends to empty evidence table (header + separator only)."""
        content = (
            "## Evidence\n\n"
            "| Context | Result | Epic |\n"
            "|---------|--------|------|\n"
        )
        result = append_evidence_row(content, {"context": "ctx", "result": "res", "epic": "EPIC-1"})
        assert "EPIC-1" in result


# ---------------------------------------------------------------------------
# Evidence table extraction
# ---------------------------------------------------------------------------


class TestExtractEvidenceTable:
    """Tests for extract_evidence_table."""

    def test_extracts_table(self) -> None:
        """Extracts the Evidence section content."""
        content = (
            "## Evidence\n\n"
            "| Context | Result | Epic |\n"
            "|---------|--------|------|\n"
            "| Setup | Works | EPIC-001 |\n"
            "\n## What\nOther"
        )
        result = extract_evidence_table(content)
        assert "EPIC-001" in result
        assert "What" not in result

    def test_no_evidence_section(self) -> None:
        """Returns empty string when no Evidence section."""
        assert extract_evidence_table("# Title\n\n## What\nDesc") == ""

    def test_stops_at_next_heading(self) -> None:
        """Stops extracting at the next ## heading."""
        content = (
            "## Evidence\n\n"
            "| A | B |\n"
            "\n## What\nOther"
        )
        result = extract_evidence_table(content)
        assert "Other" not in result


# ---------------------------------------------------------------------------
# init_wiki
# ---------------------------------------------------------------------------


class TestInitWiki:
    """Tests for init_wiki."""

    def test_creates_directory(self, tmp_path: Path) -> None:
        """Creates the wiki directory under the expected path."""
        wiki_dir = init_wiki(tmp_path)
        assert wiki_dir.exists()
        assert wiki_dir.name == "experiences"

    def test_creates_seed_pages(self, tmp_path: Path) -> None:
        """Creates guide-dev-story and guide-qa-remediate seed pages."""
        wiki_dir = init_wiki(tmp_path)
        assert page_exists(wiki_dir, "guide-dev-story")
        assert page_exists(wiki_dir, "guide-qa-remediate")

    def test_creates_index(self, tmp_path: Path) -> None:
        """Creates INDEX.md after seeding pages."""
        wiki_dir = init_wiki(tmp_path)
        assert page_exists(wiki_dir, "INDEX")

    def test_idempotent(self, tmp_path: Path) -> None:
        """Calling init_wiki twice does not overwrite existing pages."""
        wiki_dir = init_wiki(tmp_path)
        first_content = read_page(wiki_dir, "guide-dev-story")
        # Second call should not overwrite
        init_wiki(tmp_path)
        second_content = read_page(wiki_dir, "guide-dev-story")
        assert first_content == second_content


# ---------------------------------------------------------------------------
# load_guide_page
# ---------------------------------------------------------------------------


class TestLoadGuidePage:
    """Tests for load_guide_page."""

    def test_loads_existing_guide(self, initialized_wiki: Path) -> None:
        """Loads INDEX and guide page for a known phase type."""
        # dev_story → phase_type="dev", so loads guide-dev
        # qa_remediate → phase_type="qa", so loads guide-qa
        index, guide = load_guide_page(initialized_wiki, "qa_remediate")
        assert index is not None
        assert guide is not None
        assert "Quality Checklist" in guide

    def test_missing_guide_returns_none(self, initialized_wiki: Path) -> None:
        """Returns None for guide_content when guide page doesn't exist."""
        index, guide = load_guide_page(initialized_wiki, "nonexistent_phase")
        assert index is not None
        assert guide is None

    def test_phase_type_extraction(self, initialized_wiki: Path) -> None:
        """Phase type is derived by splitting on underscore (qa_remediate -> qa)."""
        # We have guide-qa in our initialized wiki
        index, guide = load_guide_page(initialized_wiki, "qa_remediate")
        assert guide is not None


# ---------------------------------------------------------------------------
# fix_content_block_scalars
# ---------------------------------------------------------------------------


class TestFixContentBlockScalars:
    """Tests for fix_content_block_scalars."""

    def test_fixes_double_quoted_multiline(self) -> None:
        """Converts double-quoted content with \\n to block scalar."""
        yaml_str = '    content: "line1\\nline2\\nline3"'
        result = fix_content_block_scalars(yaml_str)
        assert "content: |" in result
        assert "line1\n" in result
        # The escaped \n should be actual newlines in block scalar

    def test_block_scalar_unchanged(self) -> None:
        """Proper block scalar notation is left unchanged."""
        yaml_str = "    content: |\n      line1\n      line2"
        result = fix_content_block_scalars(yaml_str)
        assert result == yaml_str

    def test_single_quoted_not_fixed(self) -> None:
        """Single-quoted fields are NOT repaired (known limitation)."""
        yaml_str = "    content: 'line1\\nline2'"
        result = fix_content_block_scalars(yaml_str)
        # Single-quoted patterns don't match the double-quoted regex
        assert "content: |" not in result

    def test_fixes_section_patches(self) -> None:
        """Also fixes inline-quoted section_patches values."""
        yaml_str = '    section_patches: "patch1\\npatch2"'
        result = fix_content_block_scalars(yaml_str)
        assert "section_patches: |" in result


# ---------------------------------------------------------------------------
# prepare_llm_output (smart truncation)
# ---------------------------------------------------------------------------


class TestPrepareLlmOutput:
    """Tests for prepare_llm_output."""

    def test_below_threshold(self) -> None:
        """Short output is not truncated."""
        text = "short output"
        assert prepare_llm_output(text) == text

    def test_above_threshold_truncates(self) -> None:
        """Long output is truncated with head:tail ratio."""
        # Use a small max_tokens for testing
        text = "A" * 1000  # 1000 chars = ~250 tokens
        result = prepare_llm_output(text, max_tokens=50)
        assert "[TRUNCATED" in result
        # Head should be first 1/4 of char budget, tail last 3/4
        # char_budget = 50*4 = 200, head = 50 chars, tail = 150 chars
        assert len(result) < len(text)

    def test_exactly_at_threshold(self) -> None:
        """Text exactly at threshold is not truncated."""
        # max_tokens * 4 chars = exactly at boundary
        char_count = 120_000 * 4
        text = "A" * char_count
        # estimated_tokens = char_count / 4 = 120_000 <= max_tokens
        result = prepare_llm_output(text, max_tokens=120_000)
        assert result == text

    def test_head_tail_ratio(self) -> None:
        """Verifies head:tail = 1:3 ratio in truncated output."""
        text = "A" * 2000  # 500 tokens
        result = prepare_llm_output(text, max_tokens=100)  # budget = 400 chars
        # head = 400//4 = 100, tail = (400*3)//4 = 300
        # Marker has \n\n prefix and suffix, so head gets 2 extra chars
        marker = "... [TRUNCATED: showing first 1/4 and last 3/4] ..."
        assert marker in result
        parts = result.split(marker)
        assert len(parts) == 2
        # head includes the \n\n before marker
        assert len(parts[0]) == 102  # 100 head chars + 2 newlines
        # tail includes the \n\n after marker
        assert len(parts[1]) == 302  # 300 tail chars + 2 newlines


# ---------------------------------------------------------------------------
# derive_confidence
# ---------------------------------------------------------------------------


class TestDeriveConfidence:
    """Tests for derive_confidence.

    All 8 combinations: 0/1/2/3+ occurrences x positive/negative/neutral/caution.
    """

    def test_0_occurrences_positive(self) -> None:
        """0 occurrences → tentative regardless of sentiment."""
        assert derive_confidence(0, "positive") == "tentative"

    def test_0_occurrences_negative(self) -> None:
        """0 occurrences with negative sentiment → tentative."""
        assert derive_confidence(0, "negative") == "tentative"

    def test_1_occurrence_positive(self) -> None:
        """1 occurrence → tentative."""
        assert derive_confidence(1, "positive") == "tentative"

    def test_2_occurrences_positive(self) -> None:
        """2 occurrences → established."""
        assert derive_confidence(2, "positive") == "established"

    def test_3_occurrences_positive(self) -> None:
        """3+ occurrences positive → definitive."""
        assert derive_confidence(3, "positive") == "definitive"

    def test_3_occurrences_negative(self) -> None:
        """3+ occurrences negative → established (negative cap)."""
        assert derive_confidence(3, "negative") == "established"

    def test_5_occurrences_negative(self) -> None:
        """5 occurrences negative still capped at established."""
        assert derive_confidence(5, "negative") == "established"

    def test_3_occurrences_neutral(self) -> None:
        """3 occurrences neutral → definitive (not negative)."""
        assert derive_confidence(3, "neutral") == "definitive"

    def test_3_occurrences_caution(self) -> None:
        """3 occurrences caution → definitive (only negative is capped)."""
        assert derive_confidence(3, "caution") == "definitive"
