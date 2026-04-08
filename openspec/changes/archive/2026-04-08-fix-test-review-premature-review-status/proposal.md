## Why

Commit b8c9407 repositioned `test_review` from after `code_review_synthesis` to after `dev_story` (before `code_review`). However, the `PHASE_TO_STATUS` mapping in `sprint/sync.py` still maps `Phase.TEST_REVIEW → "review"`, causing the story's sprint-status to be set to `"review"` prematurely — before `code_review` has started. This premature status change causes `code_review` to be effectively skipped.

## What Changes

- Change `PHASE_TO_STATUS[Phase.TEST_REVIEW]` from `"review"` to `"in-progress"` in `src/bmad_assist/sprint/sync.py`, reflecting that test_review now runs during the development phase (before code review begins).
- Update the docstring/comments in the `PHASE_TO_STATUS` mapping to accurately describe the new phase ordering rationale.
- Update any tests that assert `TEST_REVIEW → "review"` to expect `"in-progress"`.

## Capabilities

### New Capabilities

_(none)_

### Modified Capabilities

_(none — this is a bug fix to an internal mapping; no spec-level behavior changes)_

## Impact

- **Code**: `src/bmad_assist/sprint/sync.py` (PHASE_TO_STATUS mapping + comments)
- **Tests**: Any test asserting `TEST_REVIEW` maps to `"review"` status
- **Behavior**: Stories in the TEA loop will remain `"in-progress"` during `test_review`, transitioning to `"review"` only when `code_review` begins. This restores the correct lifecycle: `in-progress → review → done`.
