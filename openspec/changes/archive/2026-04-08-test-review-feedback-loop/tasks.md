## 1. Config & State Model Changes

- [x] 1.1 Add `test_review_quality_threshold: int = 70` and `test_review_block_threshold: int = 50` fields to `TestarchConfig` in `src/bmad_assist/testarch/config.py` with validator ensuring `block_threshold <= quality_threshold` and range 0-100
- [x] 1.2 Add `test_review_quality_score: int | None = None` field to `State` model in `src/bmad_assist/core/state.py`
- [x] 1.3 Update `bmad-assist.yaml.example` testarch section with new threshold fields and comments

## 2. Phase Repositioning

- [x] 2.1 Move `test_review` from after `code_review_synthesis` to after `dev_story` (before `code_review`) in `TEA_FULL_LOOP_CONFIG` in `src/bmad_assist/core/config/models/loop.py`
- [x] 2.2 Update `validate_phase_ordering()` in `loop.py`: warn when `test_review` is after `code_review_synthesis` (instead of before); add new check warning when `test_review` is before `dev_story`
- [x] 2.3 Update `bmad-assist.yaml.example` loop.story list to match new phase order
- [x] 2.4 Update docstrings in `LoopConfig` and `TestReviewHandler` to reflect new position

## 3. Condensed Summary Output

- [x] 3.1 Add `_generate_condensed_summary()` method to `TestReviewHandler` in `src/bmad_assist/testarch/handlers/test_review.py` that extracts quality score, critical issues, and recommendation from LLM output (regex-based with fallback to first 30 lines)
- [x] 3.2 Update `_invoke_test_review_workflow()` to save the condensed summary file alongside the full report (filename: `test-review-summary-{story_id}-{timestamp}.md`)
- [x] 3.3 Update `execute()` to write `state.test_review_quality_score` from extracted score

## 4. TestReviewResolver Condensed Mode

- [x] 4.1 Add `condensed: bool = False` parameter to `TestReviewResolver.resolve()` in `src/bmad_assist/testarch/context/resolvers/test_review.py`
- [x] 4.2 When `condensed=True`, prioritize `test-review-summary-*.md` file patterns before falling back to full report patterns
- [x] 4.3 Update `get_artifact_patterns()` in `src/bmad_assist/testarch/paths.py` to support summary file patterns

## 5. TEA Context Wiring

- [x] 5.1 Add `test-review` with `condensed: true` to the `code_review` workflow config in default TEA context configuration (`src/bmad_assist/testarch/context/config.py`)
- [x] 5.2 Update `TEAContextWorkflowConfig` model to support `condensed` parameter per artifact type (if not already supported)
- [x] 5.3 Wire `condensed` parameter through `TEAContextService.collect()` → `TestReviewResolver.resolve()`

## 6. Synthesis Quality Gate Injection

- [x] 6.1 Update `code_review_synthesis` compiler (`src/bmad_assist/compiler/workflows/code_review_synthesis.py`) to read `state.test_review_quality_score` and threshold config
- [x] 6.2 Inject soft signal directive into synthesis prompt when score < `quality_threshold`
- [x] 6.3 Inject hard signal directive into synthesis prompt when score < `block_threshold`
- [x] 6.4 No injection when score is None or above threshold

## 7. Documentation Updates

- [x] 7.1 Update `README.md`: add test_review to ASCII flow diagram (`Dev Story → Test Review → Code Review`); add test_review row to Multi-LLM phase table (~line 188)
- [x] 7.2 Update `docs/configuration.md`: update loop config YAML example (~line 293) to include test_review after dev_story; update Code Review Rework Loop diagram (~line 314) to show test_review node; add quality threshold config field documentation
- [x] 7.3 Update `docs/tea-configuration.md`: document `test_review_quality_threshold` and `test_review_block_threshold` fields; add clarifying comment to `test_review_on_code_complete` explaining it controls run/skip regardless of phase position
- [x] 7.4 Update `docs/sprint-management.md`: move test_review from "review" to "in-progress" group in Phase-to-Status mapping table (~line 218); add test_review to loop example (~line 370)
- [x] 7.5 Update `docs/ab-testing.md`: add test-review to Supported Phases table (~line 100)
- [x] 7.6 Update `experiments/loops/standard.yaml`: add test_review in correct position (after dev_story, before code_review)

## 8. Tests

- [x] 8.1 Unit tests for `TestarchConfig` threshold validation (valid, invalid relationship, defaults)
- [x] 8.2 Unit tests for `_generate_condensed_summary()` (normal extraction, fallback, edge cases)
- [x] 8.3 Unit tests for `TestReviewResolver` condensed mode (summary found, fallback to full, non-condensed)
- [x] 8.4 Unit tests for `validate_phase_ordering()` updated warnings
- [x] 8.5 Unit tests for synthesis quality gate injection (soft signal, hard signal, no signal, None score)
- [x] 8.6 Integration test: test_review handler writes quality_score to state
- [x] 8.7 Update existing test_review handler tests for new phase position and summary output
