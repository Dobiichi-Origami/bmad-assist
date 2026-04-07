## Context

The bmad-assist development loop orchestrates story phases via a declarative `loop.story` list in `bmad-assist.yaml`. The `get_next_phase()` function in `guardian.py` walks this list sequentially. Currently, `test_review` is listed last in the story phase sequence (after `code_review_synthesis`), but `runner.py:1350` hard-codes story completion at `CODE_REVIEW_SYNTHESIS` success, bypassing `get_next_phase()` and making `test_review` unreachable.

The TEA context system (`TEAContextService`) already supports injecting artifacts into workflow prompts via per-workflow `include` lists in `testarch.context.workflows`. Today, `code_review_synthesis` includes `test-review`, but `code_review` does not. The `TestReviewResolver` loads full report files (~390 lines) with token truncation.

State is managed via the `State` pydantic model, which persists across phases. `PhaseResult.outputs` is ephemeral per-phase and not accessible to subsequent phases.

## Goals / Non-Goals

**Goals:**

- Make `test_review` execute reliably in the normal story flow by repositioning it before the `CODE_REVIEW_SYNTHESIS` hard-coded completion block.
- Create a feedback loop where test quality findings influence code review and rework decisions.
- Provide configurable thresholds so teams can tune quality gate strictness.
- Keep the full review report for human consumption while providing a condensed version for LLM context injection.
- Update all user-facing documentation to reflect the new phase position, new config fields, and updated flow diagrams.

**Non-Goals:**

- Automatic code fix generation based on test-review findings (future work).
- Running test_review multiple times within a single story iteration.
- Changing the test-review workflow instructions, checklist, or template content.
- Modifying the scoring algorithm (P0/P1/P2/P3 weights, bonus points).

## Decisions

### 1. Phase position: after dev_story, before code_review

**Decision**: Place `test_review` between `dev_story` and `code_review`.

**Rationale**: At this point, test files are complete (both ATDD-generated and developer-written). Placing it here means findings flow naturally into code_review as context, and the code_review → synthesis → rework loop can address test issues. Placing it after code_review but before synthesis was considered but offers no advantage — code_review doesn't modify test files, so the review input is identical, but code_review loses the ability to reference test findings.

**Alternative rejected — after code_review, before synthesis**: Same test content reviewed, but code_review can't see findings. Synthesis could still use them, but the rework instruction would lack specificity since the code review itself didn't mention test issues.

### 2. Two-file output: full report + condensed summary

**Decision**: `TestReviewHandler` saves two files per review:
- `test-review-{story}-{timestamp}.md` — full report (existing format)
- `test-review-summary-{story}-{timestamp}.md` — condensed summary (~15 lines: score + critical issues)

**Rationale**: The full report is valuable for human consumption and archival, but injecting 390 lines into an LLM prompt wastes tokens and dilutes signal. A focused summary with just the score and critical violations (file:line + one-liner) gives the code_review LLM exactly what it needs.

**Alternative rejected — truncation only**: The existing `_truncate_content()` method cuts at a token limit but doesn't understand document structure. It might cut in the middle of a recommendation, losing the most actionable content.

### 3. Condensed mode in TestReviewResolver

**Decision**: Add a `condensed` parameter to `TestReviewResolver.resolve()`. When `condensed=True`, it looks for `test-review-summary-*.md` files first, falling back to the full report with truncation. The TEA context config for `code_review` sets `condensed: true`; `code_review_synthesis` keeps `condensed: false` (full report available if needed).

**Rationale**: Different consumers need different granularity. Code review needs a quick signal; synthesis may need the full picture for borderline cases.

### 4. quality_score persisted to State

**Decision**: Add `test_review_quality_score: int | None = None` to the `State` model. `TestReviewHandler.execute()` writes the extracted score to state after successful completion.

**Rationale**: `PhaseResult.outputs` is ephemeral — it's not accessible to phases that run later. State persists across the entire story lifecycle and is already the mechanism used by other cross-phase signals (e.g., `atdd_ran_for_story`).

### 5. Two-tier threshold design (soft + hard gate)

**Decision**: Add two config fields to `TestarchConfig`:
- `test_review_quality_threshold: int = 70` — When score < threshold, inject a directive into synthesis prompt: "Test quality score is {score}/100 (below {threshold}). Consider requiring test quality improvements in rework."
- `test_review_block_threshold: int = 50` — When score < threshold, synthesis receives a hard directive: "Test quality score is {score}/100 (CRITICAL). Rework MUST include fixing critical test issues."

Neither threshold mechanically forces a REJECT. Both operate by injecting signals into the synthesis prompt, letting the LLM weigh them against other factors.

**Rationale**: A purely mechanical gate (score < X → auto-REJECT) is too rigid — a score of 69 on a threshold of 70 shouldn't auto-block if code quality is excellent. The soft/hard distinction gives teams a way to express "be aware" vs "strongly consider" without removing LLM judgment.

**Alternative rejected — single threshold**: Doesn't distinguish between "could improve" and "critical problems". A single threshold at 70 treats a 65 score the same as a 30 score.

**Alternative rejected — mechanical gate**: Would bypass LLM judgment entirely. Works for CI pipelines but not for an LLM-driven synthesis phase where context matters.

### 6. Phase ordering validator update

**Decision**: Invert the warning in `validate_phase_ordering()` to warn when `test_review` appears **after** `code_review_synthesis` instead of before. Add a new check that `test_review` should appear after `dev_story`.

**Rationale**: The validator's purpose is to catch common misconfigurations. With the new position, placing test_review after synthesis (where it's unreachable) is the misconfiguration to warn about.

### 7. Documentation update strategy

**Decision**: Update all docs that reference phase ordering or TEA configuration in a single pass. Specifically:

- `README.md`: Update ASCII flow diagram to show `Dev Story → Test Review → Code Review`, add test_review row to the Multi-LLM phase table.
- `docs/configuration.md`: Update loop config YAML example, update Code Review Rework Loop diagram to include test_review node, add quality threshold config documentation.
- `docs/tea-configuration.md`: Add documentation for `test_review_quality_threshold` and `test_review_block_threshold` fields. Review whether the config key `test_review_on_code_complete` should be renamed (decision: keep the existing name for backwards compatibility, add a clarifying comment that it controls whether test_review runs, regardless of its position).
- `docs/sprint-management.md`: Update phase-to-status mapping — test_review moves from the "review" group to the "in-progress" group since it now executes before code_review. Update loop example to include test_review.
- `docs/ab-testing.md`: Add test-review to the supported phases table.
- `experiments/loops/standard.yaml`: Add test_review in the correct position for full TEA experiment loops.
- `bmad-assist.yaml.example`: Already covered in implementation tasks (phase order + threshold fields + context config).

**Rationale**: Documentation must be consistent with code behavior. Shipping the phase reposition without updating docs creates a gap where users see one story order in docs and a different one in `TEA_FULL_LOOP_CONFIG`. Doing it in one pass ensures consistency.

## Risks / Trade-offs

- **[Added latency]** test_review adds LLM invocation time between dev_story and code_review. → Mitigation: This is an opt-in phase (controlled by `test_review_on_code_complete` mode). Teams that don't want the latency can set mode to `off`.

- **[Summary quality]** The condensed summary is generated by extracting sections from the full LLM output, which may have inconsistent formatting. → Mitigation: Use regex-based extraction targeting well-known section headers (Executive Summary, Critical Issues) from the template. Fall back to first N lines if extraction fails.

- **[Threshold tuning]** Default thresholds (70/50) may not suit all projects. → Mitigation: Both are configurable per-project in yaml. Defaults are deliberately moderate.

- **[State model growth]** Adding a field to State increases the persisted state size. → Mitigation: Single `int | None` field. Negligible impact.
