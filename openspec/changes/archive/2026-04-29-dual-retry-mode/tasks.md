## 1. Config & Data Model

- [x] 1.1 Add `retry_mode: Literal["stash_retry", "quick_correct", "auto"]` field to `TwinProviderConfig` in `config.py` with default `"stash_retry"`
- [x] 1.2 Add `max_quick_corrections: int` field to `TwinProviderConfig` with default `1`
- [x] 1.3 Add `retry_mode_threshold_seconds: int` field to `TwinProviderConfig` with default `120`
- [x] 1.4 Update YAML config parsing in `providers.py` to read `retry_mode`, `max_quick_corrections`, and `retry_mode_threshold_seconds` from `providers.twin` section
- [x] 1.5 Validate that `retry_mode` only accepts `"stash_retry"`, `"quick_correct"`, or `"auto"` (enforced by Literal type)

## 2. Auto Mode Resolution Logic

- [x] 2.1 Implement `_resolve_retry_mode(config, duration_ms)` helper that returns `"stash_retry"` or `"quick_correct"` based on `retry_mode` and `duration_ms`: if `retry_mode="auto"`, compare `duration_ms / 1000` against `retry_mode_threshold_seconds`; otherwise return the explicit `retry_mode` value
- [x] 2.2 Log the auto mode selection decision at INFO level (phase name, duration, threshold, selected mode)

## 3. Runner Retry Loop

- [x] 3.1 Refactor the retry loop in `runner.py` (lines ~1355-1436) to extract a helper function for the stash_retry path
- [x] 3.2 Add quick_correct branch: when resolved mode is `quick_correct`, skip `stash_working_changes()` and format correction compass with `[QUICK-CORRECT n/N]` prefix
- [x] 3.3 Implement quick correct loop: use `max_quick_corrections` as the loop limit instead of `max_retries`
- [x] 3.4 On quick correct exhaustion, follow `retry_exhausted_action` (halt or continue) — do NOT auto-escalate to stash_retry
- [x] 3.5 Handle quick correct phase execution failure: break out of correction loop, follow `retry_exhausted_action`
- [x] 3.6 Integrate `_resolve_retry_mode()` call at the point where Twin decides `retry`, using the `duration_ms` from the current execution result
- [x] 3.7 Log quick correct attempts with distinct messages (e.g., `"Twin QUICK-CORRECT %d/%d for phase %s"`)

## 4. Reflect Prompt

- [x] 4.1 No changes to the reflect prompt template — Twin already produces `drift_assessment.correction` for both modes
- [x] 4.2 Verify that `is_retry=True` is passed correctly during quick correction reflect calls (same as stash_retry)

## 5. Tests

- [x] 5.1 Add unit tests for `TwinProviderConfig` with `retry_mode`, `max_quick_corrections`, and `retry_mode_threshold_seconds` defaults and custom values
- [x] 5.2 Add unit test for invalid `retry_mode` value rejection
- [x] 5.3 Add unit tests for `_resolve_retry_mode()`: auto mode with duration above/below threshold, explicit stash_retry, explicit quick_correct
- [x] 5.4 Add integration test: `quick_correct` mode re-invokes phase without git stash
- [x] 5.5 Add integration test: `quick_correct` mode uses `[QUICK-CORRECT n/N]` compass prefix
- [x] 5.6 Add integration test: `quick_correct` exhaustion follows `retry_exhausted_action`
- [x] 5.7 Add integration test: `auto` mode selects `quick_correct` for long-running phase (duration >= threshold)
- [x] 5.8 Add integration test: `auto` mode selects `stash_retry` for short-running phase (duration < threshold)
- [x] 5.9 Add integration test: `stash_retry` mode behavior unchanged when `retry_mode="stash_retry"` (regression guard)
- [x] 5.10 Add integration test: `quick_correct` phase execution failure degradation
- [x] 5.11 Add integration test: parse failure during quick correction reflect follows `is_retry=True` degradation rules
- [x] 5.12 Add integration test: `retry_mode_threshold_seconds` has no effect when `retry_mode` is not `"auto"`
