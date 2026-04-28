"""Prompt templates for the Digital Twin reflect and guide capabilities.

Contains the reflect prompt (with phase-specific guidance, challenge mode,
forced checklist, watch-outs limit) and the guide prompt.
"""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)

__all__ = [
    "build_reflect_prompt",
    "build_guide_prompt",
    "build_extract_self_audit_prompt",
    "PHASE_REVIEW_GUIDANCE",
]

# ---------------------------------------------------------------------------
# Self-audit extraction prompt (LLM fallback when regex fails)
# ---------------------------------------------------------------------------

_EXTRACT_SELF_AUDIT_PROMPT_TEMPLATE = """\
You are a document analyzer. Your task is to find and extract a self-audit, review, or quality-check \
section from the following document.

Look for sections with headings like:
- "Self-Audit", "Execution Self-Audit", "Self Audit"
- "审查", "自审", "执行自审"
- "Quality Check", "Quality Review", "Verification"
- Any heading at any level (##, ###, etc.) that contains a self-assessment or audit of the work done

Return your result as YAML:

```yaml
found: true  # or false if no such section exists
content: |
  <verbatim content of the section, not a summary>
```

If no such section exists, return:
```yaml
found: false
content: ""
```

# Document to analyze

{document}
"""


def build_extract_self_audit_prompt(llm_output: str) -> str:
    """Build the extraction prompt for LLM-based self-audit detection.

    Args:
        llm_output: The raw LLM output to scan for a self-audit section.

    Returns:
        Assembled extraction prompt string.
    """
    return _EXTRACT_SELF_AUDIT_PROMPT_TEMPLATE.format(document=llm_output)


# ---------------------------------------------------------------------------
# Phase-specific review guidance (Task 4.4)
# ---------------------------------------------------------------------------

PHASE_REVIEW_GUIDANCE: dict[str, str] = {
    "dev_story": (
        "## Phase-Specific Review: dev_story\n"
        "Check these dev_story-specific issues:\n"
        "- Are ALL acceptance criteria satisfied? Cross-reference each AC with actual code changes.\n"
        "- Is 'not essential' used as a skip justification without specific technical reason?\n"
        "- Do all tests pass? Are there any test.fixme() calls remaining?\n"
        "- Is the File List section complete with ALL changed files?\n"
        "- Is the story status set to 'review'?\n"
        "- Were any tasks marked complete without passing tests?\n"
    ),
    "qa_remediate": (
        "## Phase-Specific Review: qa_remediate\n"
        "Check these qa_remediate-specific issues:\n"
        "- Is each issue FIXED/SKIPPED/ESCALATED with an explicit reason?\n"
        "- Is SKIPPED justified with a specific technical reason (not convenience)?\n"
        "- Are escalations reasonable (not just giving up)?\n"
        "- Were fixes verified by re-running relevant tests?\n"
        "- Was a regression check done (no new issues introduced)?\n"
        "- Was the safety cap respected?\n"
    ),
    "atdd": (
        "## Phase-Specific Review: atdd\n"
        "Check these ATDD-specific issues:\n"
        "- Are test cases in proper Given/When/Then format?\n"
        "- Do tests cover all acceptance criteria from the story?\n"
        "- Are edge cases and error scenarios covered?\n"
        "- Are test.fixme() stubs created for the dev phase?\n"
    ),
    "create_story": (
        "## Phase-Specific Review: create_story\n"
        "Check these create_story-specific issues:\n"
        "- Are acceptance criteria in BDD format (Given/When/Then)?\n"
        "- Is the architecture analysis complete?\n"
        "- Were all 5 disaster categories checked?\n"
        "- Is the story status set to 'ready-for-dev'?\n"
        "- Are Dev Notes comprehensive with specific technical guidance?\n"
    ),
    "code_review_synthesis": (
        "## Phase-Specific Review: code_review_synthesis\n"
        "Check these synthesis-specific issues:\n"
        "- Does the synthesis faithfully represent ALL reviewer findings?\n"
        "- Are contradictions between reviewers resolved or flagged?\n"
        "- Is the severity assignment consistent across findings?\n"
        "- Are action items specific and actionable (not vague)?\n"
    ),
    "retrospective": (
        "## Phase-Specific Review: retrospective\n"
        "Check these retrospective-specific issues:\n"
        "- Are findings specific and actionable (not generic platitudes)?\n"
        "- Do recommendations reference specific code or patterns?\n"
        "- Are both positive and negative patterns captured?\n"
        "- Is the report complete with all required sections?\n"
    ),
}

_GENERIC_REVIEW_GUIDANCE = (
    "## Generic Review Guidance\n"
    "Apply three-layer cross-validation:\n"
    "1. **Self-audit vs mission**: Does the claimed completion match what was requested?\n"
    "2. **Self-audit vs git diff**: Do actual file changes match the claimed completion?\n"
    "3. **Self-audit vs wiki patterns**: Does this execution repeat any known failure patterns?\n"
    "Then decide: CONTINUE (satisfactory), RETRY (drift detected, correctable), or HALT (unrecoverable).\n"
)

# ---------------------------------------------------------------------------
# Initialization guidance for empty wiki (Task 4.5)
# ---------------------------------------------------------------------------

_INITIALIZATION_GUIDANCE = (
    "## Wiki Initialization\n"
    "The experience wiki is sparse (fewer than 3 pages). Prioritize establishing the initial\n"
    "knowledge base by creating pages that capture:\n"
    "- **Environment knowledge** (env-*): Project-specific tools, frameworks, configurations\n"
    "- **Observed patterns** (pattern-*): Recurring successful or problematic approaches\n"
    "- **Design preferences** (design-*): Architectural decisions and conventions\n"
    "- **Phase guidance** (guide-*): Lessons learned for specific phase types\n\n"
    "IMPORTANT: Create only pages with PROJECT-SPECIFIC information. Generic platitudes like\n"
    "'always test your code' are NOT valid experiences. Each page's What section MUST contain\n"
    "specific technical details (library/framework/method names).\n"
)

# ---------------------------------------------------------------------------
# Challenge mode for negative patterns (Task 4.6)
# ---------------------------------------------------------------------------

_CHALLENGE_MODE = (
    "## Challenge Mode\n"
    "A negative pattern page has reached a 5-epic boundary. You MUST critically evaluate it:\n"
    "1. Is this a real project issue or an execution model limitation?\n"
    "2. Would a different approach avoid this pattern?\n"
    "3. Has any positive evidence contradicted this pattern?\n\n"
    "Only after defending the pattern with evidence from genuinely independent contexts\n"
    "may you promote a negative pattern from 'established' to 'definitive'.\n"
    "If the pattern cannot be defended, update it with the challenge results.\n"
)

# ---------------------------------------------------------------------------
# Forced checklist before decision (Task 4.7)
# ---------------------------------------------------------------------------

_FORCED_CHECKLIST = (
    "## Before deciding, you MUST complete this checklist:\n"
    "1. Did the execution address all items in the mission?\n"
    "2. Does the self-audit match the objective facts (git diff, phase_outputs)?\n"
    "3. Are there any contradictions between claimed completion and actual file changes?\n"
    "4. Does this execution repeat any known failure patterns from the wiki?\n"
    "5. Is the self-audit status justified by the evidence?\n\n"
    "Only after answering ALL five items should you set your decision.\n"
)

# ---------------------------------------------------------------------------
# Watch-outs ≤5 limit (Task 4.8)
# ---------------------------------------------------------------------------

_WATCHOUTS_LIMIT = (
    "IMPORTANT: You MUST NOT output more than 5 watch-out items. Focus on the most critical.\n"
)


# ---------------------------------------------------------------------------
# Reflect prompt template (Task 4.3)
# ---------------------------------------------------------------------------

_REFLECT_PROMPT_TEMPLATE = """\
You are the Digital Twin — an independent reviewer that evaluates phase execution output.
Your job is to detect drift, validate completion claims, and update the experience wiki.

# Context

## Current Phase
- Phase: {phase}
- Mission summary: {mission_summary}

## Execution Outcome
- Success: {success}
- Duration: {duration_ms}ms
- Error: {error}
- Files modified: {files_modified}
- Self-Audit section from output:
{self_audit_section}

## Wiki INDEX
{index_content}

## Guide Page for This Phase Type
{guide_content}

{initialization_guidance}

{challenge_mode}

{phase_review_guidance}

{forced_checklist}

{watchouts_limit}

# Quality Constraints on Wiki Content
1. The What section MUST contain specific technical details (library/framework/method names), NOT universal principles.
2. Evidence Context column MUST contain enough detail to recreate the scenario.
3. Pages containing no project-specific information (e.g., "always test your code") are NOT valid experiences.
4. Each PageUpdate's reason field MUST cite specific evidence from the current execution.

# Output Format

Produce your review as a YAML code block:

```yaml
decision: continue  # one of: continue, retry, halt
rationale: |
  <one-paragraph explanation of your decision>
drift_assessment:
  drifted: false
  evidence: |
    <what you observed, referencing specific facts from the execution>
  correction: |
    <if drifted=true, specific correction directive for the RETRY attempt>
page_updates:
  - page_name: <name matching (env|pattern|design|guide)-[a-z0-9-]+>
    action: create  # one of: create, update, evolve
    content: |
      <full page content for create/evolve; for evolve use {{{{EVIDENCE_TABLE}}}} placeholder>
    append_evidence:
      context: <what was happening>
      result: <what was observed>
      epic: <epic id>
    section_patches:
      <Section Title>: |
        <new section body>
    reason: <why this update, citing specific evidence>
```

Rules:
- At most 2 page_updates entries per reflect call.
- page_name MUST match (env|pattern|design|guide)-[a-z0-9-]+.
- action MUST be one of: create, update, evolve (no archive).
- For evolve, use {{{{EVIDENCE_TABLE}}}} placeholder where evidence table should appear.
- Confidence is NOT set by you — it is code-derived from occurrences and sentiment.
- Sentiment values: positive, negative, neutral, caution.
"""


def build_reflect_prompt(
    phase: str,
    mission: str,
    success: bool,
    duration_ms: int,
    error: str | None,
    files_modified: list[str],
    self_audit: str | None,
    index_content: str | None,
    guide_content: str | None,
    is_retry: bool = False,
    epic_id: str | None = None,
    wiki_dir: "Path | None" = None,
) -> str:
    """Build the reflect prompt from execution record and wiki context.

    Args:
        phase: Phase name that was executed.
        mission: The mission/prompt sent to the LLM.
        success: Whether the phase succeeded.
        duration_ms: Execution duration.
        error: Error message if failed.
        files_modified: List of modified file paths.
        self_audit: Parsed self-audit section from LLM output.
        index_content: INDEX.md content (Strategy D).
        guide_content: Guide page content for the phase type.
        is_retry: Whether this is a RETRY evaluation.
        epic_id: Current epic ID (for challenge mode check).
        wiki_dir: Wiki directory path (for challenge mode check).

    Returns:
        Assembled reflect prompt string.
    """
    # Mission summary (first 200 chars)
    mission_summary = mission[:200] + "..." if len(mission) > 200 else mission

    # Self-audit section
    self_audit_section = self_audit if self_audit else "(No Self-Audit section found in output)"

    # Index content
    index_str = index_content if index_content else "(Empty INDEX — wiki not initialized)"

    # Guide content
    guide_str = guide_content if guide_content else "(No guide page for this phase type)"

    # Initialization guidance (Task 4.5)
    init_guidance = ""
    if index_content is None or _count_index_pages(index_content) < 3:
        init_guidance = _INITIALIZATION_GUIDANCE

    # Challenge mode (Task 4.6)
    challenge = ""
    if wiki_dir is not None and epic_id is not None:
        challenge = _check_challenge_mode(wiki_dir, epic_id)

    # Phase-specific review guidance (Task 4.4)
    phase_type = phase.split("_")[0] if "_" in phase else phase
    review_guidance = PHASE_REVIEW_GUIDANCE.get(phase, _GENERIC_REVIEW_GUIDANCE)

    return _REFLECT_PROMPT_TEMPLATE.format(
        phase=phase,
        mission_summary=mission_summary,
        success=success,
        duration_ms=duration_ms,
        error=error or "None",
        files_modified=", ".join(files_modified) if files_modified else "None",
        self_audit_section=self_audit_section,
        index_content=index_str,
        guide_content=guide_str,
        initialization_guidance=init_guidance,
        challenge_mode=challenge,
        phase_review_guidance=review_guidance,
        forced_checklist=_FORCED_CHECKLIST,
        watchouts_limit=_WATCHOUTS_LIMIT,
    )


def _count_index_pages(index_content: str) -> int:
    """Count pages listed in the INDEX."""
    if not index_content:
        return 0
    # Count lines starting with "- **" which represent page entries
    return sum(1 for line in index_content.split("\n") if line.strip().startswith("- **"))


def _check_challenge_mode(wiki_dir: "Path", epic_id: str) -> str:
    """Check if any negative pattern page needs challenge mode.

    Challenge mode triggers when len(source_epics) % 5 == 0 and
    sentiment is negative.
    """
    from bmad_assist.twin.wiki import list_pages, parse_frontmatter, read_page

    challenge_pages = []
    for name in list_pages(wiki_dir):
        content = read_page(wiki_dir, name)
        if content is None:
            continue
        fm = parse_frontmatter(content)
        if fm.get("sentiment") == "negative":
            source_epics = fm.get("source_epics", [])
            if len(source_epics) > 0 and len(source_epics) % 5 == 0:
                challenge_pages.append(name)

    if challenge_pages:
        return _CHALLENGE_MODE + f"\nPages requiring challenge: {', '.join(challenge_pages)}\n"
    return ""


# ---------------------------------------------------------------------------
# Guide prompt template (Task 5.1)
# ---------------------------------------------------------------------------

_GUIDE_PROMPT_TEMPLATE = """\
You are the Digital Twin Guide. Your job is to produce a concise compass that orients
the upcoming phase execution toward the most relevant wiki knowledge.

# Context

## Upcoming Phase
- Phase type: {phase_type}

## Wiki INDEX
{index_content}

{guide_or_reason_section}

# Instructions

{guide_instructions}

Produce ONLY the compass string — a focused advisory paragraph (3-5 sentences) that:
1. Identifies the most relevant wiki knowledge for this phase type
2. Highlights specific watch-outs or patterns that apply
3. Suggests approaches based on established project experience

Do NOT produce any YAML, frontmatter, or page update directives.
Do NOT produce wiki page updates — only a plain text compass string.
"""


def build_guide_prompt(
    phase_type: str,
    index_content: str | None,
    guide_content: str | None,
    is_guide_present: bool,
) -> str:
    """Build the guide prompt for compass generation.

    Args:
        phase_type: The phase type being guided.
        index_content: INDEX.md content.
        guide_content: Guide page content or collected env/pattern/design pages.
        is_guide_present: Whether a dedicated guide page was loaded.

    Returns:
        Assembled guide prompt string.
    """
    index_str = index_content if index_content else "(Empty INDEX — no wiki pages yet)"

    if is_guide_present:
        guide_or_reason = f"## Guide Page for Phase Type: {phase_type}\n{guide_content}"
        instructions = (
            "Derive the compass primarily from the guide page content above, "
            "supplemented by the INDEX. Focus on the most actionable guidance "
            "for the upcoming phase."
        )
    else:
        guide_or_reason = f"## All Environment, Pattern, and Design Pages\n{guide_content or '(No pages available)'}"
        instructions = (
            "No dedicated guide page exists for this phase type. "
            "Reason across ALL provided environment, pattern, and design pages "
            "to synthesize the most relevant compass for this phase type. "
            "Identify cross-cutting concerns and patterns that apply."
        )

    return _GUIDE_PROMPT_TEMPLATE.format(
        phase_type=phase_type,
        index_content=index_str,
        guide_or_reason_section=guide_or_reason,
        guide_instructions=instructions,
    )
