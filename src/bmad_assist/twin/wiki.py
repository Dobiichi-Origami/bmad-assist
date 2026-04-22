"""Wiki infrastructure for the Digital Twin.

Provides file I/O, frontmatter parsing, link extraction, INDEX generation,
page validation, section patches, evidence operations, Strategy D loading,
YAML tolerance, smart truncation, and confidence derivation.
"""

import logging
import re
from pathlib import Path

import yaml

from bmad_assist.core.io import atomic_write

logger = logging.getLogger(__name__)

__all__ = [
    "read_page",
    "write_page",
    "list_pages",
    "page_exists",
    "parse_frontmatter",
    "update_frontmatter",
    "extract_links",
    "rebuild_index",
    "validate_page_name",
    "apply_section_patches",
    "append_evidence_row",
    "extract_evidence_table",
    "init_wiki",
    "load_guide_page",
    "fix_content_block_scalars",
    "prepare_llm_output",
    "derive_confidence",
]


# ---------------------------------------------------------------------------
# Task 1.2: Basic file I/O
# ---------------------------------------------------------------------------


def read_page(wiki_dir: Path, name: str) -> str | None:
    """Read wiki page content by name (without .md extension).

    Returns None if the page does not exist.
    """
    path = wiki_dir / f"{name}.md"
    if not path.exists():
        return None
    return path.read_text(encoding="utf-8")


def write_page(wiki_dir: Path, name: str, content: str) -> None:
    """Atomically write content to a wiki page."""
    path = wiki_dir / f"{name}.md"
    atomic_write(path, content)


def list_pages(wiki_dir: Path) -> list[str]:
    """Return sorted list of wiki page names (stems), excluding INDEX."""
    if not wiki_dir.exists():
        return []
    pages = []
    for p in wiki_dir.glob("*.md"):
        stem = p.stem
        if stem != "INDEX":
            pages.append(stem)
    return sorted(pages)


def page_exists(wiki_dir: Path, name: str) -> bool:
    """Return True if a wiki page with the given name exists."""
    return (wiki_dir / f"{name}.md").exists()


# ---------------------------------------------------------------------------
# Task 1.3: Frontmatter parsing and updating
# ---------------------------------------------------------------------------


def parse_frontmatter(content: str) -> dict:
    """Parse YAML frontmatter delimited by --- markers.

    Returns empty dict if no valid frontmatter is found.
    """
    if not content.startswith("---"):
        return {}
    end = content.find("---", 3)
    if end == -1:
        return {}
    yaml_str = content[3:end].strip()
    try:
        result = yaml.safe_load(yaml_str)
        return result if isinstance(result, dict) else {}
    except yaml.YAMLError:
        return {}


def update_frontmatter(content: str, epic_id: str) -> str:
    """Update frontmatter: increment occurrences, re-derive confidence,
    update last_updated, and append epic_id to source_epics if not present.
    """
    fm = parse_frontmatter(content)
    if not fm:
        # No frontmatter — nothing to update
        return content

    # Increment occurrences
    occurrences = fm.get("occurrences", 0) + 1

    # Re-derive confidence
    sentiment = fm.get("sentiment", "neutral")
    confidence = derive_confidence(occurrences, sentiment)

    # Update source_epics
    source_epics = list(fm.get("source_epics", []))
    if epic_id not in source_epics:
        source_epics.append(epic_id)

    # Rebuild frontmatter dict
    fm["occurrences"] = occurrences
    fm["confidence"] = confidence
    fm["last_updated"] = epic_id
    fm["source_epics"] = source_epics

    # Replace the frontmatter block in content
    if not content.startswith("---"):
        return content
    end = content.find("---", 3)
    if end == -1:
        return content

    # Everything after the closing ---
    body = content[end + 3 :]
    if body.startswith("\n"):
        body = body[1:]

    new_fm = yaml.dump(fm, default_flow_style=False, allow_unicode=True, sort_keys=False)
    return f"---\n{new_fm}---\n{body}"


# ---------------------------------------------------------------------------
# Task 1.4: Link extraction
# ---------------------------------------------------------------------------

_WIKI_LINK_RE = re.compile(r"\[\[([^\]]+)\]\]")


def extract_links(content: str) -> list[str]:
    """Extract all [[page-name]] style wiki links from content."""
    return _WIKI_LINK_RE.findall(content)


# ---------------------------------------------------------------------------
# Task 1.5: INDEX rebuild
# ---------------------------------------------------------------------------

# Sentiment abbreviation mapping
_SENTIMENT_ABBR = {
    "positive": "+",
    "negative": "-",
    "neutral": "~",
    "caution": "!",
}


def rebuild_index(wiki_dir: Path) -> None:
    """Rebuild INDEX.md from all wiki pages.

    Groups pages by category, displays confidence, sentiment abbreviation,
    last_updated epic, and occurrence counts. Computes backlinks from links_to.
    """
    pages = list_pages(wiki_dir)

    # Collect metadata and compute backlinks
    page_data: dict[str, dict] = {}
    backlinks: dict[str, list[str]] = {}

    for name in pages:
        content = read_page(wiki_dir, name)
        if content is None:
            continue
        fm = parse_frontmatter(content)
        # Extract title from first ## heading or use name
        title = name
        for line in content.split("\n"):
            if line.startswith("# "):
                title = line[2:].strip()
                break

        links = extract_links(content)
        category = fm.get("category", name.split("-")[0] if "-" in name else "unknown")

        page_data[name] = {
            "title": title,
            "category": category,
            "confidence": fm.get("confidence", "tentative"),
            "sentiment": fm.get("sentiment", "neutral"),
            "last_updated": fm.get("last_updated", ""),
            "occurrences": fm.get("occurrences", 0),
            "links_to": links,
        }

        # Track backlinks
        for linked in links:
            backlinks.setdefault(linked, []).append(name)

    # Group by category
    categories: dict[str, list[str]] = {}
    for name, data in page_data.items():
        cat = data["category"]
        categories.setdefault(cat, []).append(name)

    # Build INDEX content
    lines = ["# Experience Wiki INDEX\n"]
    lines.append(f"Total pages: {len(page_data)}\n")

    # Category order
    cat_order = ["env", "pattern", "design", "guide"]
    for cat in cat_order:
        if cat not in categories:
            continue
        lines.append(f"\n## {cat}\n")
        for name in sorted(categories[cat]):
            d = page_data[name]
            sent_abbr = _SENTIMENT_ABBR.get(d["sentiment"], "~")
            bl = backlinks.get(name, [])
            bl_str = f" ← {', '.join(bl)}" if bl else ""
            lines.append(
                f"- **{name}**: {d['title']} "
                f"[{d['confidence']}] {sent_abbr} "
                f"(epic: {d['last_updated']}, seen: {d['occurrences']}x){bl_str}"
            )

    # Remaining categories not in cat_order
    for cat in sorted(categories):
        if cat in cat_order:
            continue
        lines.append(f"\n## {cat}\n")
        for name in sorted(categories[cat]):
            d = page_data[name]
            sent_abbr = _SENTIMENT_ABBR.get(d["sentiment"], "~")
            bl = backlinks.get(name, [])
            bl_str = f" ← {', '.join(bl)}" if bl else ""
            lines.append(
                f"- **{name}**: {d['title']} "
                f"[{d['confidence']}] {sent_abbr} "
                f"(epic: {d['last_updated']}, seen: {d['occurrences']}x){bl_str}"
            )

    atomic_write(wiki_dir / "INDEX.md", "\n".join(lines) + "\n")


# ---------------------------------------------------------------------------
# Task 1.6: Page name validation
# ---------------------------------------------------------------------------

_PAGE_NAME_RE = re.compile(r"^(env|pattern|design|guide)-[a-z0-9-]+$")


def validate_page_name(name: str) -> bool:
    """Validate page name matches (env|pattern|design|guide)-[a-z0-9-]+."""
    return bool(_PAGE_NAME_RE.match(name))


# ---------------------------------------------------------------------------
# Task 1.7: Section-level replacement
# ---------------------------------------------------------------------------

_SECTION_HEADING_RE = re.compile(r"^(## .+)$", re.MULTILINE)


def apply_section_patches(content: str, patches: dict[str, str]) -> str:
    """Replace section bodies identified by ## Title headings.

    For each patch key, locates the section by its heading and replaces
    the body up to the next ## heading or end of content.
    """
    if not patches:
        return content

    # Split content into sections
    sections = _SECTION_HEADING_RE.split(content)

    # sections alternates: [pre_content, heading1, body1, heading2, body2, ...]
    result_parts = [sections[0]]  # Content before first ## heading

    i = 1
    while i < len(sections):
        heading = sections[i]
        body = sections[i + 1] if i + 1 < len(sections) else ""

        # Extract heading title (strip "## " prefix)
        heading_title = heading[3:].strip()

        if heading_title in patches:
            # Replace body with patched content
            result_parts.append(heading)
            result_parts.append(f"\n{patches[heading_title]}\n")
        else:
            result_parts.append(heading)
            result_parts.append(body)

        i += 2

    return "".join(result_parts)


# ---------------------------------------------------------------------------
# Task 1.8: Evidence row appending
# ---------------------------------------------------------------------------


def append_evidence_row(content: str, evidence: dict) -> str:
    """Append a new data row to the markdown table in the Evidence section."""
    lines = content.split("\n")
    result = []
    in_evidence = False
    last_table_row_idx = -1

    for idx, line in enumerate(lines):
        result.append(line)
        if line.strip().startswith("## Evidence"):
            in_evidence = True
            continue
        if in_evidence:
            if line.strip().startswith("## "):
                # Next section — insert evidence row before this
                in_evidence = False
                if last_table_row_idx >= 0:
                    # Build row from evidence dict
                    row = _build_evidence_row(content, evidence)
                    result.insert(len(result) - 1, row)
                continue
            # Track the last row of the markdown table
            stripped = line.strip()
            if stripped.startswith("|") and not stripped.startswith("|---") and not stripped.startswith("| ---"):
                # Skip header separator row
                if not all(c in "|- " for c in stripped):
                    last_table_row_idx = idx

    # If still in evidence section at end of content
    if in_evidence and last_table_row_idx >= 0:
        row = _build_evidence_row(content, evidence)
        result.append(row)

    return "\n".join(result)


def _build_evidence_row(content: str, evidence: dict) -> str:
    """Build a markdown table row from evidence dict matching column order."""
    # Find the header row to determine column order
    lines = content.split("\n")
    header_cols = []
    for line in lines:
        stripped = line.strip()
        if stripped.startswith("|") and not stripped.startswith("|---"):
            # Check it's not the separator
            if not all(c in "|- " for c in stripped):
                header_cols = [c.strip() for c in stripped.split("|") if c.strip()]
                break

    if not header_cols:
        # Fallback: just join values
        values = [str(v) for v in evidence.values()]
        return "| " + " | ".join(values) + " |"

    # Map evidence keys to column positions
    row_values = []
    for col in header_cols:
        # Case-insensitive match
        val = ""
        for k, v in evidence.items():
            if k.lower() == col.lower():
                val = str(v)
                break
        row_values.append(val)

    return "| " + " | ".join(row_values) + " |"


# ---------------------------------------------------------------------------
# Task 1.9: Evidence table extraction
# ---------------------------------------------------------------------------


def extract_evidence_table(content: str) -> str:
    """Extract the Evidence section content (table without heading).

    Returns empty string if no Evidence section exists.
    """
    lines = content.split("\n")
    result = []
    in_evidence = False

    for line in lines:
        if line.strip().startswith("## Evidence"):
            in_evidence = True
            continue
        if in_evidence:
            if line.strip().startswith("## "):
                break
            result.append(line)

    return "\n".join(result).strip()


# ---------------------------------------------------------------------------
# Task 1.10: Wiki initialization
# ---------------------------------------------------------------------------


def init_wiki(project_root: Path) -> Path:
    """Create wiki directory and seed guide pages.

    Creates the wiki directory under _bmad-output/implementation-artifacts/experiences/,
    writes seed guide page templates for guide-dev-story and guide-qa-remediate,
    and calls rebuild_index to generate the initial INDEX.

    Returns the wiki directory path.
    """
    wiki_dir = project_root / "_bmad-output" / "implementation-artifacts" / "experiences"
    wiki_dir.mkdir(parents=True, exist_ok=True)

    # Seed guide pages
    _seed_guide_page(wiki_dir, "guide-dev-story", [
        "Acceptance criteria fully covered (all AC items implemented)",
        'No "not essential" used as skip justification without specific technical reason',
        "All tests pass (no test.fixme(), no skipped assertions)",
    ])

    _seed_guide_page(wiki_dir, "guide-qa-remediate", [
        "Each issue FIXED/SKIPPED/ESCALATED with explicit reason",
        "Escalation is justified (not just convenience)",
        "Fix verified by re-running relevant tests",
        "Regression check done (no new issues introduced)",
        "Safety cap respected (max issues per iteration)",
    ])

    rebuild_index(wiki_dir)
    return wiki_dir


def _seed_guide_page(wiki_dir: Path, name: str, quality_items: list[str]) -> None:
    """Create a seed guide page if it does not already exist."""
    if page_exists(wiki_dir, name):
        return

    quality_list = "\n".join(f"- [ ] {item}" for item in quality_items)
    content = f"""---
category: guide
sentiment: neutral
confidence: tentative
occurrences: 0
last_updated: ""
source_epics: []
links_to: []
---

# {name}

## Watch-outs

*(No watch-outs yet — will be populated by Twin as experience accumulates)*

## Recommended Patterns

*(No patterns recommended yet)*

## Quality Checklist

{quality_list}
"""
    write_page(wiki_dir, name, content)


# ---------------------------------------------------------------------------
# Task 1.11: Strategy D loading
# ---------------------------------------------------------------------------


def load_guide_page(wiki_dir: Path, phase: str) -> tuple[str | None, str | None]:
    """Load INDEX + guide page for the given phase (Strategy D).

    Phase type is derived from the phase name by taking the portion
    before the first underscore (e.g., qa_remediate -> qa).

    Returns (INDEX content, guide page content) tuple.
    Guide page content is None if it doesn't exist.
    """
    index_content = read_page(wiki_dir, "INDEX")

    # Derive phase type from phase name
    phase_type = phase.split("_")[0] if "_" in phase else phase
    guide_name = f"guide-{phase_type}"

    guide_content = read_page(wiki_dir, guide_name)
    return index_content, guide_content


# ---------------------------------------------------------------------------
# Task 1.12: YAML block scalar recovery
# ---------------------------------------------------------------------------


def fix_content_block_scalars(yaml_str: str) -> str:
    """Repair common formatting errors in Twin YAML output.

    Converts inline-quoted multi-line content fields to proper
    block scalar (|) notation so that yaml.safe_load can parse them.
    """
    # Pattern: content: "..." or content: '...' with embedded newlines
    # Replace with content: | block scalar
    result = yaml_str

    # Fix double-quoted multi-line content fields
    result = _fix_inline_quoted_field(result, "content")
    # Fix section_patches values that use inline quoting
    result = _fix_inline_quoted_field(result, "section_patches")

    return result


def _fix_inline_quoted_field(yaml_str: str, field_name: str) -> str:
    """Fix a specific field that should use block scalar but uses inline quotes."""
    # Match field_name: "..." or field_name: '...'
    # Only fix if the value contains \n (escaped newline in quotes)
    import re as _re

    # Match field: "text with \n" or field: 'text with \n'
    pattern = _re.compile(
        rf'^(\s*{field_name}:\s*)"((?:[^"\\]|\\.)*)"\s*$',
        _re.MULTILINE,
    )

    def _replace(match: _re.Match) -> str:
        indent = match.group(1)
        raw = match.group(2)
        # Unescape \n to actual newlines
        unescaped = raw.replace("\\n", "\n")
        # Indent each line for block scalar
        indent_str = "      "  # 6 spaces for nested content
        lines = unescaped.split("\n")
        indented = "\n".join(f"{indent_str}{line}" for line in lines)
        return f"{indent}|\n{indented}"

    return pattern.sub(_replace, yaml_str)


# ---------------------------------------------------------------------------
# Task 1.13: Smart truncation
# ---------------------------------------------------------------------------

_TRUNCATION_MARKER = "\n\n... [TRUNCATED: showing first 1/4 and last 3/4] ...\n\n"


def prepare_llm_output(llm_output: str, max_tokens: int = 120_000) -> str:
    """Smart truncation for long LLM output.

    Estimates tokens at ~4 chars/token. When estimated tokens exceed max_tokens,
    keeps first 1/4 of character budget (head) and last 3/4 (tail), joined
    by a truncation marker.
    """
    estimated_tokens = len(llm_output) / 4
    if estimated_tokens <= max_tokens:
        return llm_output

    # Character budget
    char_budget = max_tokens * 4
    head_chars = char_budget // 4
    tail_chars = (char_budget * 3) // 4

    head = llm_output[:head_chars]
    tail = llm_output[-tail_chars:]

    return head + _TRUNCATION_MARKER + tail


# ---------------------------------------------------------------------------
# Task 1.14: Confidence derivation
# ---------------------------------------------------------------------------


def derive_confidence(occurrences: int, sentiment: str) -> str:
    """Derive confidence level from occurrences and sentiment.

    - 1 occurrence → tentative
    - 2 occurrences → established
    - 3+ occurrences → definitive (positive) or established (negative cap)
    Negative patterns are capped at 'established' regardless of occurrences.
    Only challenge mode (every 5 epics) can promote negative to definitive.
    """
    if occurrences <= 1:
        return "tentative"
    if occurrences == 2:
        return "established"
    # occurrences >= 3
    if sentiment == "negative":
        return "established"
    return "definitive"
