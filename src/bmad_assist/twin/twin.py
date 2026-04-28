"""Digital Twin core: reflect, guide, and page update execution.

Twin is NOT an agent with tools — each operation is a single LLM call
→ parse YAML → code executes file I/O.
"""

from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import Any, Literal

import yaml
from pydantic import BaseModel, Field, model_validator

from bmad_assist.core.exceptions import ProviderTimeoutError
from bmad_assist.core.retry import invoke_with_timeout_retry
from bmad_assist.twin.config import TwinProviderConfig
from bmad_assist.twin.execution_record import ExecutionRecord
from bmad_assist.twin.prompts import build_extract_self_audit_prompt, build_guide_prompt, build_reflect_prompt
from bmad_assist.twin.wiki import (
    append_evidence_row,
    apply_section_patches,
    derive_confidence,
    extract_evidence_table,
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

logger = logging.getLogger(__name__)

__all__ = [
    "Twin",
    "TwinResult",
    "DriftAssessment",
    "PageUpdate",
    "apply_page_updates",
    "extract_yaml_block",
]


# ---------------------------------------------------------------------------
# Pydantic Models (Task 4.2)
# ---------------------------------------------------------------------------


class DriftAssessment(BaseModel):
    """Assessment of whether execution drifted from mission."""

    drifted: bool
    evidence: str
    correction: str | None = None

    @model_validator(mode="after")
    def _correction_required_when_drifted(self) -> "DriftAssessment":
        if self.drifted and not self.correction:
            raise ValueError("correction is required when drifted=True")
        return self


class PageUpdate(BaseModel):
    """A wiki page update from the Twin.

    Supports exactly three actions: create, update, evolve.
    No archive action exists.
    """

    page_name: str
    action: Literal["create", "update", "evolve"]
    content: str = ""
    append_evidence: dict[str, Any] | None = None
    section_patches: dict[str, str] | None = None
    reason: str = ""


class TwinResult(BaseModel):
    """Result of a Twin reflect() call."""

    decision: Literal["continue", "retry", "halt"]
    rationale: str
    drift_assessment: DriftAssessment | None = None
    page_updates: list[PageUpdate] | None = None


# ---------------------------------------------------------------------------
# YAML extraction (Task 4.13)
# ---------------------------------------------------------------------------

_YAML_BLOCK_RE = re.compile(r"```yaml\s*\n(.*?)```", re.DOTALL)


def extract_yaml_block(raw_output: str) -> str | None:
    """Extract the YAML code block from raw LLM output.

    Returns the YAML content between ```yaml ... ```, or None if not found.
    """
    match = _YAML_BLOCK_RE.search(raw_output)
    if match:
        return match.group(1).strip()
    # Fallback: try to find YAML-like content starting with "decision:"
    lines = raw_output.split("\n")
    yaml_start = None
    for i, line in enumerate(lines):
        if line.strip().startswith("decision:"):
            yaml_start = i
            break
    if yaml_start is not None:
        return "\n".join(lines[yaml_start:])
    return None


# ---------------------------------------------------------------------------
# Twin class (Task 4.1, 4.9, 4.10, 5.2, 5.3, 5.4, 5.5)
# ---------------------------------------------------------------------------


class Twin:
    """Digital Twin: post-execution review and pre-execution compass generation.

    Twin is NOT an agent with tools — each operation is a single LLM call
    → parse YAML → code executes file I/O.
    """

    def __init__(
        self,
        config: TwinProviderConfig,
        wiki_dir: Path,
        provider: Any = None,
    ) -> None:
        self.config = config
        self.wiki_dir = wiki_dir
        self._provider = provider

    # ------------------------------------------------------------------
    # Reflect (Task 4.9, 4.10)
    # ------------------------------------------------------------------

    def reflect(
        self,
        record: ExecutionRecord,
        is_retry: bool = False,
        epic_id: str | None = None,
    ) -> TwinResult:
        """Review phase execution output and decide next action.

        Single LLM call → parse YAML → return TwinResult.
        On parse failure: retry once, then degrade based on is_retry.

        Args:
            record: ExecutionRecord with full phase outcome.
            is_retry: Whether this is evaluating a RETRY attempt.
            epic_id: Current epic ID for frontmatter tracking.

        Returns:
            TwinResult with decision, rationale, and optional page updates.
        """
        if not self.config.enabled:
            return TwinResult(decision="continue", rationale="Twin disabled")

        # Load wiki context (Strategy D)
        index_content, guide_content = load_guide_page(self.wiki_dir, record.phase)

        # Resolve self_audit: if regex failed, try LLM extraction
        self_audit = record.self_audit
        if self_audit is None and record.llm_output:
            self_audit = self._extract_self_audit_llm(record.llm_output)

        # Prepare LLM output with smart truncation
        prepared_output = prepare_llm_output(record.llm_output)

        # Build reflect prompt
        prompt = build_reflect_prompt(
            phase=record.phase,
            mission=record.mission,
            success=record.success,
            duration_ms=record.duration_ms,
            error=record.error,
            files_modified=record.files_modified,
            self_audit=self_audit,
            index_content=index_content,
            guide_content=guide_content,
            is_retry=is_retry,
            epic_id=epic_id,
            wiki_dir=self.wiki_dir,
        )

        # Inject truncated output into prompt
        # (The prompt template doesn't include the full output directly;
        #  it's assembled here by appending the execution details)
        full_prompt = prompt + f"\n\n# Full Execution Output (prepared)\n{prepared_output}\n"

        # Call LLM with retry on parse failure
        return self._reflect_with_retry(full_prompt, is_retry, epic_id)

    def _extract_self_audit_llm(self, llm_output: str) -> str | None:
        """Use LLM to semantically extract a self-audit section from raw output.

        Called when regex-based format_self_audit() returns None.
        Returns extracted content, or None on any failure.

        Args:
            llm_output: The raw LLM output to scan.

        Returns:
            Extracted self-audit content, or None.
        """
        if not llm_output:
            return None

        try:
            # Apply smart truncation for very large outputs
            truncated = prepare_llm_output(llm_output)

            prompt = build_extract_self_audit_prompt(truncated)
            model = self.config.audit_extract_model or self.config.model
            raw = invoke_with_timeout_retry(
                self._provider.invoke,
                timeout_retries=self.config.timeout_retries,
                phase_name="twin_audit_extract",
                prompt=prompt,
                model=model,
                timeout=self.config.timeout,
            )
            if hasattr(raw, "stdout"):
                raw = raw.stdout
            raw = str(raw)

            # Parse YAML from extraction output
            yaml_str = extract_yaml_block(raw)
            if yaml_str is None:
                logger.warning("Self-audit extraction: no YAML block found")
                return None

            yaml_str = fix_content_block_scalars(yaml_str)
            data = yaml.safe_load(yaml_str)
            if not isinstance(data, dict):
                logger.warning("Self-audit extraction: YAML is not a dict")
                return None

            found = data.get("found", False)
            content = data.get("content", "")

            if not found or not content:
                return None

            return str(content).strip()

        except Exception as e:
            logger.warning("Self-audit extraction failed: %s", e)
            return None

    def _reflect_with_retry(
        self,
        prompt: str,
        is_retry: bool,
        epic_id: str | None,
    ) -> TwinResult:
        """Execute reflect LLM call with one retry on parse failure."""
        for attempt in range(2):
            try:
                raw_output = self._invoke_llm(prompt)
                result = self._parse_reflect_output(raw_output)
                return result
            except Exception as e:
                logger.warning(
                    "Twin reflect parse failure (attempt %d/2): %s",
                    attempt + 1,
                    e,
                )
                if attempt == 0:
                    # Retry once
                    continue

        # Both attempts failed — degrade based on is_retry
        return self._degrade_on_parse_failure(is_retry)

    def _invoke_llm(self, prompt: str) -> str:
        """Invoke the LLM provider and return raw output.

        Routes through invoke_with_timeout_retry for ProviderTimeoutError
        handling before falling through to degradation.

        Raises on any provider failure (including ProviderTimeoutError
        after all timeout retries exhausted).
        """
        if self._provider is None:
            raise RuntimeError("No LLM provider configured for Twin")

        result = invoke_with_timeout_retry(
            self._provider.invoke,
            timeout_retries=self.config.timeout_retries,
            phase_name="twin_reflect",
            prompt=prompt,
            model=self.config.model,
            timeout=self.config.timeout,
        )
        if hasattr(result, "stdout"):
            return result.stdout
        return str(result)

    def _parse_reflect_output(self, raw_output: str) -> TwinResult:
        """Parse raw LLM output into TwinResult.

        Extracts YAML block, applies fix_content_block_scalars,
        and validates with TwinResult model.
        """
        yaml_str = extract_yaml_block(raw_output)
        if yaml_str is None:
            raise ValueError("No YAML code block found in Twin output")

        # Fix content block scalars
        yaml_str = fix_content_block_scalars(yaml_str)

        # Parse YAML
        try:
            data = yaml.safe_load(yaml_str)
        except yaml.YAMLError as e:
            raise ValueError(f"YAML parse error: {e}") from e

        if not isinstance(data, dict):
            raise ValueError(f"Expected dict, got {type(data).__name__}")

        # Validate with TwinResult
        try:
            result = TwinResult.model_validate(data)
        except Exception as e:
            raise ValueError(f"TwinResult validation error: {e}") from e

        # Check watch-outs limit (warning only)
        if result.page_updates:
            for update in result.page_updates:
                if update.section_patches and len(update.section_patches) > 5:
                    logger.warning(
                        "PageUpdate for %s has %d section patches (max 5 recommended)",
                        update.page_name,
                        len(update.section_patches),
                    )

        # Limit page updates to max 2
        if result.page_updates and len(result.page_updates) > 2:
            logger.warning(
                "Twin returned %d page updates, limiting to 2",
                len(result.page_updates),
            )
            result = result.model_copy(update={"page_updates": result.page_updates[:2]})

        return result

    def _degrade_on_parse_failure(self, is_retry: bool) -> TwinResult:
        """Degrade gracefully on parse failure.

        - is_retry=False → CONTINUE (don't block the main loop)
        - is_retry=True + retry_exhausted_action=halt → HALT
        - is_retry=True + retry_exhausted_action=continue → CONTINUE
        """
        if is_retry:
            action = self.config.retry_exhausted_action
            if action == "halt":
                return TwinResult(
                    decision="halt",
                    rationale="Twin parse error during RETRY, halting to prevent uncontrolled execution",
                )
            else:
                return TwinResult(
                    decision="continue",
                    rationale="Twin parse error during RETRY, continuing per retry_exhausted_action=continue",
                )
        else:
            return TwinResult(
                decision="continue",
                rationale="Twin parse error, defaulting to continue",
            )

    # ------------------------------------------------------------------
    # Guide (Task 5.2, 5.3, 5.4, 5.5)
    # ------------------------------------------------------------------

    def guide(self, phase_type: str) -> str | None:
        """Generate a compass string for the given phase type.

        Loads INDEX + guide page (Strategy D), calls LLM, returns compass.
        When guide page doesn't exist, reasons from all env/pattern/design pages.
        Guide does NOT produce wiki updates — only returns a compass string.
        On any failure, returns None (non-critical).

        Args:
            phase_type: The phase type being guided (e.g., "story", "qa_plan_execute").

        Returns:
            Compass string, or None on failure.
        """
        if not self.config.enabled:
            return None

        try:
            return self._guide_impl(phase_type)
        except Exception as e:
            logger.warning("Twin guide failed for phase_type=%s: %s", phase_type, e)
            return None

    def _guide_impl(self, phase_type: str) -> str | None:
        """Internal guide implementation."""
        # Load INDEX + guide page (Strategy D)
        index_content, guide_content = load_guide_page(self.wiki_dir, phase_type)
        is_guide_present = guide_content is not None

        # Fallback: when guide page doesn't exist, reason from env/pattern/design pages
        if not is_guide_present:
            guide_content = self._collect_env_pattern_design_pages()

        # Build guide prompt
        prompt = build_guide_prompt(
            phase_type=phase_type,
            index_content=index_content,
            guide_content=guide_content,
            is_guide_present=is_guide_present,
        )

        # Call LLM
        raw_output = self._invoke_llm(prompt)

        # The output is a plain string compass (no YAML)
        compass = raw_output.strip()
        if not compass:
            return None

        return compass

    def _collect_env_pattern_design_pages(self) -> str:
        """Collect all environment, pattern, and design page contents for fallback guide."""
        pages = list_pages(self.wiki_dir)
        sections = []
        for name in pages:
            if name.startswith(("env-", "pattern-", "design-")):
                content = read_page(self.wiki_dir, name)
                if content:
                    sections.append(f"### {name}\n{content}\n")
        return "\n".join(sections) if sections else "(No environment/pattern/design pages found)"


# ---------------------------------------------------------------------------
# apply_page_updates (Task 4.11, 4.12)
# ---------------------------------------------------------------------------


def apply_page_updates(
    updates: list[PageUpdate],
    wiki_dir: Path,
    epic_id: str,
) -> None:
    """Execute Twin page updates as file I/O against the wiki directory.

    For CREATE: write new file if it doesn't exist.
    For UPDATE: append evidence and/or section patches, update frontmatter.
    For EVOLVE: replace content with {{EVIDENCE_TABLE}} preservation.
    After all updates, calls rebuild_index().

    Args:
        updates: List of PageUpdate objects from TwinResult.
        wiki_dir: Path to the wiki directory.
        epic_id: Current epic ID for frontmatter tracking.
    """
    for update in updates:
        try:
            _apply_single_update(update, wiki_dir, epic_id)
        except Exception as e:
            logger.error("Failed to apply page update for %s: %s", update.page_name, e)

    rebuild_index(wiki_dir)


def _apply_single_update(
    update: PageUpdate,
    wiki_dir: Path,
    epic_id: str,
) -> None:
    """Apply a single page update."""
    name = update.page_name

    # Validate page name
    if not validate_page_name(name):
        logger.warning("Invalid page name '%s' — skipping update", name)
        return

    # Substring deduplication warning for CREATE (Task 4.12)
    if update.action == "create":
        _check_substring_dedup(name, wiki_dir)

    if update.action == "create":
        _apply_create(name, update.content, wiki_dir, epic_id)
    elif update.action == "update":
        _apply_update(name, update, wiki_dir, epic_id)
    elif update.action == "evolve":
        _apply_evolve(name, update.content, wiki_dir, epic_id)


def _apply_create(name: str, content: str, wiki_dir: Path, epic_id: str) -> None:
    """CREATE: write new page if it doesn't exist."""
    if page_exists(wiki_dir, name):
        logger.warning(
            "Page '%s' already exists — Twin should have used UPDATE/EVOLVE. Skipping CREATE.",
            name,
        )
        return

    # Ensure frontmatter includes source_epics
    fm = parse_frontmatter(content)
    if fm and "source_epics" not in fm:
        # Add source_epics to frontmatter
        content = _add_source_epics_to_content(content, epic_id)
    elif fm and "source_epics" in fm:
        if epic_id not in fm["source_epics"]:
            content = _add_source_epics_to_content(content, epic_id)

    write_page(wiki_dir, name, content)
    logger.info("Created wiki page: %s", name)


def _apply_update(name: str, update: PageUpdate, wiki_dir: Path, epic_id: str) -> None:
    """UPDATE: append evidence, apply section patches, update frontmatter."""
    if not page_exists(wiki_dir, name):
        # Page doesn't exist — treat as CREATE if content is provided
        if update.content:
            logger.warning(
                "Page '%s' does not exist for UPDATE — treating as CREATE",
                name,
            )
            _apply_create(name, update.content, wiki_dir, epic_id)
            return
        else:
            logger.warning("Page '%s' does not exist and no content provided — skipping", name)
            return

    content = read_page(wiki_dir, name)
    if content is None:
        return

    # Append evidence row if provided
    if update.append_evidence:
        update.append_evidence["epic"] = epic_id
        content = append_evidence_row(content, update.append_evidence)

    # Apply section patches if provided
    if update.section_patches:
        content = apply_section_patches(content, update.section_patches)

    # Update frontmatter (increment occurrences, re-derive confidence, track source_epics)
    content = update_frontmatter(content, epic_id)

    write_page(wiki_dir, name, content)
    logger.info("Updated wiki page: %s", name)


def _apply_evolve(name: str, new_content: str, wiki_dir: Path, epic_id: str) -> None:
    """EVOLVE: replace content with {{EVIDENCE_TABLE}} preservation."""
    if not page_exists(wiki_dir, name):
        logger.warning("Page '%s' does not exist for EVOLVE — skipping", name)
        return

    existing_content = read_page(wiki_dir, name)
    if existing_content is None:
        return

    # EVOLVE safety check: verify last_updated matches current epic
    fm = parse_frontmatter(existing_content)
    if fm:
        last_updated = fm.get("last_updated", "")
        if last_updated and last_updated != epic_id:
            logger.warning(
                "EVOLVE skipped for '%s': last_updated=%s != epic_id=%s "
                "(manual edits take priority)",
                name, last_updated, epic_id,
            )
            return

    # Preserve evidence table via {{EVIDENCE_TABLE}} placeholder
    # Also handle single-brace variant {EVIDENCE_TABLE} (LLM may output
    # either form depending on what it saw in the prompt)
    placeholder_found = False
    for variant in ("{{EVIDENCE_TABLE}}", "{EVIDENCE_TABLE}"):
        if variant in new_content:
            original_evidence = extract_evidence_table(existing_content)
            new_content = new_content.replace(variant, original_evidence)
            placeholder_found = True
            break

    if not placeholder_found:
        logger.warning(
            "EVOLVE %s: no EVIDENCE_TABLE placeholder found in content "
            "(evidence table may be lost or overwritten)", name,
        )

    # Update frontmatter in the new content
    # First, ensure the new content has frontmatter
    if new_content.startswith("---"):
        # Replace frontmatter with updated version
        new_content = _update_evolve_frontmatter(new_content, epic_id)
    else:
        # Copy frontmatter from existing and prepend
        fm_str = _extract_frontmatter_str(existing_content)
        if fm_str:
            new_content = fm_str + "\n" + new_content
            new_content = _update_evolve_frontmatter(new_content, epic_id)

    write_page(wiki_dir, name, new_content)
    logger.info("Evolved wiki page: %s", name)


def _update_evolve_frontmatter(content: str, epic_id: str) -> str:
    """Update frontmatter in evolved content (increment occurrences, etc.)."""
    return update_frontmatter(content, epic_id)


def _extract_frontmatter_str(content: str) -> str | None:
    """Extract the raw frontmatter string (including --- delimiters)."""
    if not content.startswith("---"):
        return None
    end = content.find("---", 3)
    if end == -1:
        return None
    return content[: end + 3]


def _add_source_epics_to_content(content: str, epic_id: str) -> str:
    """Add source_epics field to frontmatter in content."""
    fm = parse_frontmatter(content)
    if not fm:
        return content

    source_epics = list(fm.get("source_epics", []))
    if epic_id not in source_epics:
        source_epics.append(epic_id)
    fm["source_epics"] = source_epics

    # Rebuild frontmatter
    if not content.startswith("---"):
        return content
    end = content.find("---", 3)
    if end == -1:
        return content
    body = content[end + 3 :]
    if body.startswith("\n"):
        body = body[1:]

    new_fm = yaml.dump(fm, default_flow_style=False, allow_unicode=True, sort_keys=False)
    return f"---\n{new_fm}---\n{body}"


def _check_substring_dedup(name: str, wiki_dir: Path) -> None:
    """Check for substring overlap between new page name and existing pages.

    Only warns — does NOT auto-convert CREATE to UPDATE.
    """
    existing = list_pages(wiki_dir)
    name_parts = name.split("-", 1)
    if len(name_parts) < 2:
        return
    category = name_parts[0]
    concept = name_parts[1]

    for existing_name in existing:
        if not existing_name.startswith(f"{category}-"):
            continue
        existing_concept = existing_name.split("-", 1)[1] if "-" in existing_name else ""
        if concept in existing_concept or existing_concept in concept:
            if concept != existing_concept:  # Not exact match
                logger.warning(
                    "Substring overlap: new page '%s' vs existing '%s' — "
                    "possible duplication, but proceeding with CREATE",
                    name,
                    existing_name,
                )
