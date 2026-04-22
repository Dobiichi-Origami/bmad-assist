"""Shared fixtures for Digital Twin tests."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from bmad_assist.twin.config import TwinProviderConfig
from bmad_assist.twin.execution_record import ExecutionRecord
from bmad_assist.twin.wiki import init_wiki, write_page
from bmad_assist.twin.twin import Twin


# ---------------------------------------------------------------------------
# Wiki directory fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def wiki_dir(tmp_path: Path) -> Path:
    """Fresh wiki directory (no pages)."""
    d = tmp_path / "wiki"
    d.mkdir()
    return d


@pytest.fixture
def initialized_wiki(wiki_dir: Path) -> Path:
    """Wiki directory initialized with seed guide pages + INDEX."""
    # Manually run init_wiki logic pointing at wiki_dir directly
    from bmad_assist.twin.wiki import rebuild_index

    _seed_pages(wiki_dir)
    rebuild_index(wiki_dir)
    return wiki_dir


def _seed_pages(wiki_dir: Path) -> None:
    """Write sample pages to wiki_dir for testing."""
    write_page(wiki_dir, "guide-dev-story", _GUIDE_DEV_STORY)
    write_page(wiki_dir, "guide-qa", _GUIDE_QA)
    write_page(wiki_dir, "env-react-setup", _ENV_REACT)
    write_page(wiki_dir, "pattern-flaky-test", _PATTERN_FLAKY)


# ---------------------------------------------------------------------------
# Sample page content
# ---------------------------------------------------------------------------

_SAMPLE_POSITIVE_FM = """\
category: env
sentiment: positive
confidence: tentative
occurrences: 0
last_updated: ""
source_epics: []
links_to: []
"""

_SAMPLE_NEGATIVE_FM = """\
category: pattern
sentiment: negative
confidence: tentative
occurrences: 0
last_updated: ""
source_epics: []
links_to: []
"""

_GUIDE_DEV_STORY = f"""\
---
category: guide
sentiment: neutral
confidence: tentative
occurrences: 0
last_updated: ""
source_epics: []
links_to: []
---

# guide-dev-story

## Watch-outs

*(No watch-outs yet)*

## Recommended Patterns

*(No patterns recommended yet)*

## Quality Checklist

- [ ] AC fully covered
- [ ] All tests pass
- [ ] No test.fixme()
"""

_GUIDE_QA = f"""\
---
category: guide
sentiment: neutral
confidence: tentative
occurrences: 0
last_updated: ""
source_epics: []
links_to: []
---

# guide-qa

## Watch-outs

*(No watch-outs yet)*

## Quality Checklist

- [ ] Each issue resolved
"""

_ENV_REACT = f"""\
---
{_SAMPLE_POSITIVE_FM.strip()}
---

# React Project Setup

## What

This project uses React 18 with TypeScript and Vite for the build system.

## Evidence

| Context | Result | Epic |
|---------|--------|------|
| Initial project setup | React 18 + Vite configured | EPIC-001 |

## When This Applies

New stories that involve UI component development.

## Links

[[guide-dev-story]]
"""

_PATTERN_FLAKY = f"""\
---
{_SAMPLE_NEGATIVE_FM.strip()}
---

# Flaky Test Detection

## What

Intermittent test failures due to race conditions in async test setup.

## Evidence

| Context | Root Cause | Real Impact | Epic |
|---------|------------|-------------|------|
| CI pipeline failures | Async teardown order | 3 false negatives | EPIC-002 |

## Why This Fails

Race conditions in shared test fixtures when tests run in parallel.

## Links

[[env-react-setup]]
"""


@pytest.fixture
def sample_page_content() -> str:
    """Full wiki page with frontmatter, sections, evidence table (positive)."""
    return _ENV_REACT


@pytest.fixture
def sample_negative_page_content() -> str:
    """Full wiki page with frontmatter, sections, evidence table (negative)."""
    return _PATTERN_FLAKY


# ---------------------------------------------------------------------------
# Config fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def twin_config() -> TwinProviderConfig:
    """Default TwinProviderConfig (enabled, halt on exhaust)."""
    return TwinProviderConfig()


@pytest.fixture
def disabled_twin_config() -> TwinProviderConfig:
    """TwinProviderConfig with enabled=False."""
    return TwinProviderConfig(enabled=False)


@pytest.fixture
def halt_on_exhaust_config() -> TwinProviderConfig:
    """TwinProviderConfig with retry_exhausted_action='halt'."""
    return TwinProviderConfig(retry_exhausted_action="halt")


@pytest.fixture
def continue_on_exhaust_config() -> TwinProviderConfig:
    """TwinProviderConfig with retry_exhausted_action='continue'."""
    return TwinProviderConfig(retry_exhausted_action="continue")


# ---------------------------------------------------------------------------
# ExecutionRecord fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def sample_record() -> ExecutionRecord:
    """ExecutionRecord with Self-Audit in llm_output."""
    return ExecutionRecord(
        phase="dev_story",
        mission="Implement the login feature",
        llm_output="# Dev Story Output\n\n## Self-Audit\n\n- All ACs satisfied\n- Tests pass\n\n## File List\n\n- src/login.ts",
        self_audit="- All ACs satisfied\n- Tests pass",
        success=True,
        duration_ms=5000,
        error=None,
    )


@pytest.fixture
def failed_record() -> ExecutionRecord:
    """ExecutionRecord with success=False."""
    return ExecutionRecord(
        phase="dev_story",
        mission="Implement the login feature",
        llm_output="",
        self_audit=None,
        success=False,
        duration_ms=1000,
        error="Compilation failed",
    )


# ---------------------------------------------------------------------------
# Mock provider
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_provider() -> MagicMock:
    """MagicMock with .invoke() method."""
    provider = MagicMock()
    provider.invoke = MagicMock(return_value="compass string")
    return provider


@pytest.fixture
def twin_with_mock(
    twin_config: TwinProviderConfig,
    wiki_dir: Path,
    mock_provider: MagicMock,
) -> Twin:
    """Twin instance with mock LLM provider."""
    return Twin(config=twin_config, wiki_dir=wiki_dir, provider=mock_provider)


# ---------------------------------------------------------------------------
# Helper: build YAML output for mock LLM returns
# ---------------------------------------------------------------------------


def make_yaml_output(
    decision: str = "continue",
    rationale: str = "All good",
    drifted: bool = False,
    evidence: str = "No drift detected",
    correction: str | None = None,
    page_updates: list[dict] | None = None,
) -> str:
    """Build a ```yaml block for mock LLM returns."""
    yaml_lines = [
        "```yaml",
        f"decision: {decision}",
        f"rationale: |",
        f"  {rationale}",
        "drift_assessment:",
        f"  drifted: {'true' if drifted else 'false'}",
        f"  evidence: |",
        f"    {evidence}",
    ]
    if correction is not None:
        yaml_lines.append(f"  correction: |")
        yaml_lines.append(f"    {correction}")
    if page_updates:
        yaml_lines.append("page_updates:")
        for pu in page_updates:
            yaml_lines.append(f"  - page_name: {pu['page_name']}")
            yaml_lines.append(f"    action: {pu['action']}")
            if "content" in pu:
                yaml_lines.append("    content: |")
                for line in pu["content"].split("\n"):
                    yaml_lines.append(f"      {line}")
            if "append_evidence" in pu:
                yaml_lines.append("    append_evidence:")
                for k, v in pu["append_evidence"].items():
                    yaml_lines.append(f"      {k}: {v}")
            if "section_patches" in pu:
                yaml_lines.append("    section_patches:")
                for k, v in pu["section_patches"].items():
                    yaml_lines.append(f"      {k}: |")
                    for line in v.split("\n"):
                        yaml_lines.append(f"        {line}")
            if "reason" in pu:
                yaml_lines.append(f"    reason: {pu['reason']}")
    yaml_lines.append("```")
    return "\n".join(yaml_lines)


def write_sample_page(wiki_dir: Path, name: str, content: str) -> None:
    """Write a page via wiki.write_page."""
    write_page(wiki_dir, name, content)
