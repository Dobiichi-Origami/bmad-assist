## Context

After commit b8c9407, the TEA story phase order changed from:

```
dev_story → code_review → code_review_synthesis → test_review
```

to:

```
dev_story → test_review → code_review → code_review_synthesis
```

The `PHASE_TO_STATUS` mapping in `src/bmad_assist/sprint/sync.py` (line 145) still maps `Phase.TEST_REVIEW → "review"`. After each phase, the runner calls `_invoke_sprint_sync()` which uses this mapping to update `sprint-status.yaml`. With the new ordering, `test_review` sets the story to `"review"` before `code_review` has started, causing `code_review` to be effectively skipped.

The mapping was correct in the old ordering because `test_review` ran after `code_review_synthesis` — the story was already in review at that point. But with the new ordering, `test_review` is part of the development pipeline (validating test quality after implementation, before code review), and should not transition the story out of `"in-progress"`.

## Goals / Non-Goals

**Goals:**
- Fix `PHASE_TO_STATUS[Phase.TEST_REVIEW]` to map to `"in-progress"` instead of `"review"`
- Ensure the story lifecycle follows: `in-progress` (during dev + test_review) → `review` (during code_review + code_review_synthesis) → `done` (at retrospective)
- Update tests that assert the old mapping
- Update comments/docstrings to reflect the new ordering rationale

**Non-Goals:**
- Changing any other phase-to-status mappings
- Modifying the phase ordering itself
- Changing the test_review handler logic
- Modifying the sprint sync mechanism

## Decisions

### Decision 1: Map TEST_REVIEW to "in-progress"

**Choice**: Change `Phase.TEST_REVIEW: "review"` to `Phase.TEST_REVIEW: "in-progress"` in `PHASE_TO_STATUS`.

**Rationale**: After reordering, `test_review` runs as part of the development pipeline (between `dev_story` and `code_review`). The story should remain "in-progress" until the actual code review phase begins. This aligns with the semantic meaning: "review" means code review is happening, not test review.

**Alternatives considered**:
- *Add skip-logic bypass in code_review handler*: More invasive, treats symptom not cause, would need maintenance.
- *Remove TEST_REVIEW from PHASE_TO_STATUS entirely*: Would leave sprint-status stale during test_review. Worse: sync would not update the story status at all during this phase.

## Risks / Trade-offs

- **[Low risk] Sprint-status shows "in-progress" longer** → Acceptable: the story IS still in progress during test review. Users see "review" once actual code review starts, which is semantically correct.
- **[No risk] Regression in old ordering** → The old ordering (test_review after code_review_synthesis) is no longer the default or recommended configuration. The LoopConfig validators explicitly warn against it.
