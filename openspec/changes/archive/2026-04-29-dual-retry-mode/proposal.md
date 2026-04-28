## Why

Digital Twin's current retry mechanism always performs a full `git stash` + re-execute cycle when drift is detected. This is expensive: a retry discards all phase output, re-runs the entire phase from scratch, and consumes significant LLM tokens and time. In many cases, the drift is minor (e.g., a missed acceptance criterion, a partial implementation) and the existing output only needs targeted correction — not wholesale replacement. Without a lighter-weight correction path, teams either accept the cost of full retries or disable Twin entirely.

## What Changes

- Introduce a **retry_mode** setting on `TwinProviderConfig` with three values: `stash_retry` (current behavior), `quick_correct` (always correct in-place), and `auto` (time-based dynamic selection)
- In `quick_correct` mode: when Twin decides `retry`, instead of git stash + re-execute, the correction compass is appended and the phase is re-invoked **without git stash** — the phase sees its existing output and can make targeted fixes
- In `auto` mode: the runner uses the phase's `duration_ms` (from `execute_phase()` via `time.perf_counter()`) compared against a configurable threshold `retry_mode_threshold_seconds` to dynamically select the retry mode — long-running phases get `quick_correct` (retry cost is high), short phases get `stash_retry` (clean redo is cheap and safer)
- Add a `retry_mode_threshold_seconds` config field (default 120) used only when `retry_mode="auto"`
- Add a `max_quick_corrections` config field (default 1) to cap quick correction cycles before escalating to halt or continue
- The runner's retry loop branches on the resolved retry mode: `stash_retry` uses the existing stash + re-execute path; `quick_correct` re-invokes the phase with correction compass but without discarding work
- In `quick_correct` mode, the correction compass uses `[QUICK-CORRECT n/N]` prefix instead of `[RETRY retry=N]`, signaling the execution model to correct in-place rather than start over

## Capabilities

### New Capabilities
- `twin-retry-mode`: Defines the retry mode system — `stash_retry`, `quick_correct`, and `auto` — including the `retry_mode`, `max_quick_corrections`, and `retry_mode_threshold_seconds` config fields, the runner branching logic, and the auto mode's time-based selection rule

### Modified Capabilities
- `twin-runner-integration`: The `TwinProviderConfig` data class gains `retry_mode`, `max_quick_corrections`, and `retry_mode_threshold_seconds` fields; the runner's retry loop gains mode-branching logic with auto selection
- `twin-reflect`: The reflect prompt's `is_retry=True` degradation logic applies uniformly across both `stash_retry` and `quick_correct` paths; no prompt changes needed — Twin already produces `drift_assessment.correction` for both modes

## Impact

- **Code**: `runner.py` retry loop (lines ~1355-1436), `config.py` `TwinProviderConfig`, `providers.py` YAML parsing
- **Config**: `providers.twin` YAML section gains `retry_mode`, `max_quick_corrections`, and `retry_mode_threshold_seconds` fields; defaults preserve current behavior (`retry_mode: stash_retry`)
- **Backward compatibility**: Fully backward-compatible — `stash_retry` is the default, existing configs work unchanged
- **Tests**: Existing retry tests continue passing (stash_retry path unchanged); new tests needed for quick_correct and auto paths
