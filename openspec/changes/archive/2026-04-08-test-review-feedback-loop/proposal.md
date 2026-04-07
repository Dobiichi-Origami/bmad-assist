## Why

The `test-review` workflow currently sits after `code_review_synthesis` in the story phase list, but the runner hard-codes story completion at `CODE_REVIEW_SYNTHESIS` success (runner.py:1350), making test_review unreachable in normal execution. Even if it did run, its outputs (quality_score, review report) are not consumed by any downstream decision logic — they are purely informational artifacts with no feedback loop. This means test quality issues discovered by TEA are never acted upon automatically, and the review report has no mechanism to trigger rework.

## What Changes

- **Reposition test_review phase**: Move from after `code_review_synthesis` to after `dev_story` (before `code_review`) in both `TEA_FULL_LOOP_CONFIG` and the yaml example, so it runs in the normal execution path and its findings can feed into code review.
- **Condensed summary output**: `TestReviewHandler` produces an additional condensed summary file (`test-review-summary-{story}.md`) containing only quality score + critical issues, alongside the full report.
- **TEA context wiring for code_review**: Add `test-review` to the `code_review` workflow's TEA context config so the condensed summary is injected into code review prompts. Update `TestReviewResolver` to prefer the summary file when loaded for code_review (full report for other consumers).
- **quality_score written to state**: `TestReviewHandler` writes `quality_score` to `state` after extraction, making it available for downstream phases.
- **Configurable quality thresholds**: Add `test_review_quality_threshold` (soft gate, default 70) and `test_review_block_threshold` (hard gate, default 50) to testarch config. `code_review_synthesis` uses these to inject quality signals into the synthesis prompt or force REJECT.
- **Phase ordering validator update**: Update `validate_phase_ordering()` to warn when `test_review` is placed after `code_review_synthesis` (instead of the current warning when it's before).
- **Documentation updates**: Update all docs referencing phase order, loop configuration, or TEA config to reflect new test_review position and quality threshold fields. Includes README flow diagram, configuration guide, TEA config guide, sprint management mappings, and experiment loop templates.

## Capabilities

### New Capabilities

- `test-review-condensed-summary`: TestReviewHandler produces a short summary artifact (score + critical issues only) in addition to the full report, for efficient context injection into downstream prompts.
- `test-review-quality-gate`: Configurable quality thresholds (soft/hard) that feed into code_review_synthesis decision-making. quality_score is persisted to state and consumed by synthesis to influence rework decisions.

### Modified Capabilities

_(no existing specs are affected)_

## Impact

- **Config model**: `TestarchConfig` gains two new fields (`test_review_quality_threshold`, `test_review_block_threshold`).
- **State model**: `State` gains `test_review_quality_score: int | None` field.
- **Loop config**: `TEA_FULL_LOOP_CONFIG` story phase order changes; `validate_phase_ordering()` logic inverted for test_review.
- **TEA context config**: Default `code_review` workflow config adds `test-review` include.
- **Compiler**: `code_review_synthesis` compiler reads `state.test_review_quality_score` and threshold config to inject quality gate signals.
- **Handler**: `TestReviewHandler` extended to save condensed summary and write score to state.
- **Resolver**: `TestReviewResolver` gains condensed mode for code_review context.
- **Yaml example**: `bmad-assist.yaml.example` updated with new threshold fields and reordered story phases.
- **Documentation**: `README.md` (flow diagram, phase table), `docs/configuration.md` (loop example, rework diagram), `docs/tea-configuration.md` (threshold fields), `docs/sprint-management.md` (phase-to-status mapping, loop example), `docs/ab-testing.md` (supported phases), `experiments/loops/standard.yaml` (experiment loop template).
- **No breaking changes**: All new config fields have defaults; existing configs continue to work.
