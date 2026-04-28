## Context

Digital Twin's retry mechanism currently follows a single path: when `reflect()` returns `decision="retry"`, the runner performs a `git stash` to discard all phase output, then re-executes the entire phase from scratch with an appended correction compass. This approach is safe (clean slate) but expensive — each retry consumes the full LLM token cost of re-running the phase, plus the time and risk of regenerating work that was mostly correct.

In practice, many retry-worthy drifts are minor: a missed acceptance criterion, an incomplete test case, or a partially-implemented feature. For these cases, discarding everything and starting over is disproportionate. The existing output only needs targeted correction, not wholesale replacement.

The phase execution duration (`duration_ms`) is already available at the point where the retry decision is made. It comes from `execute_phase()` in `dispatch.py`, which uses `time.perf_counter()` to measure wall-clock elapsed time (including LLM waiting, I/O, etc.). This provides a reliable signal for choosing the appropriate retry strategy: long-running phases are expensive to redo, short phases are cheap to redo safely.

The runner's retry loop (lines 1355-1436 in `runner.py`) handles this as a while loop: stash → format correction compass → re-execute phase → reflect on retry result. The correction compass is derived from `twin_result.drift_assessment.correction` and appended to the original compass.

## Goals / Non-Goals

**Goals:**
- Add a `quick_correct` retry mode that preserves existing phase output and injects a correction compass for in-place fixes
- Add an `auto` retry mode that dynamically selects between `stash_retry` and `quick_correct` based on phase execution duration
- Keep `stash_retry` as the default mode so existing behavior is preserved
- Allow `max_quick_corrections` to cap quick correction cycles before escalating to halt or continue
- Make all settings configurable via YAML (`providers.twin` section)
- Keep Twin as a single LLM call — no tool-use loops or multi-turn conversations

**Non-Goals:**
- Changing the reflect prompt's drift detection logic — it already produces corrections; we just use them differently
- Adding a "partial stash" mechanism that only reverts specific files — too complex, full stash is sufficient when needed
- Auto-selecting retry mode based on drift severity — the LLM should not decide retry mode; that's a configuration concern
- Using cumulative epic/project duration as the auto threshold signal — the per-phase duration is the right granularity

## Decisions

### D1: Three retry modes — `stash_retry`, `quick_correct`, and `auto`

**Decision**: Add `retry_mode` field to `TwinProviderConfig` with values `"stash_retry"` (default), `"quick_correct"`, and `"auto"`.

**Rationale**: Three modes cover all use cases: explicit stash, explicit quick-correct, and automatic time-based selection. The `auto` mode is the most practical default for operators who want the system to adapt without manual tuning per phase.

**Alternatives considered**:
- *Two modes only (no auto)*: Forces operators to pick one mode globally. Rejected because phase durations vary dramatically (some phases take 30s, others 5+ minutes), and a single mode doesn't fit all.
- *Per-phase retry mode config*: Allow different modes per phase type. Rejected because it's over-configurable — `auto` with a threshold achieves the same result more simply.

### D2: `auto` mode uses `duration_ms` vs `retry_mode_threshold_seconds`

**Decision**: When `retry_mode="auto"`, the runner compares the phase's `duration_ms` (from `execute_phase()` result) against `retry_mode_threshold_seconds` (default 120). If `duration_ms / 1000 >= threshold`, use `quick_correct`; otherwise use `stash_retry`.

**Rationale**: Long-running phases are expensive to redo (high token cost, high time cost) → quick_correct saves the most value. Short phases are cheap to redo safely → stash_retry provides the cleanest result. The threshold is simple, configurable, and based on a metric that's already available.

**The `duration_ms` source**: `dispatch.py:execute_phase()` calculates this via `time.perf_counter()` difference — wall-clock elapsed time including LLM waiting, file I/O, and network latency. It's a real-world measure of how long the phase took, and it's already in `result.outputs["duration_ms"]` at the point where the retry decision is made.

**Alternatives considered**:
- *Token count as threshold*: Use LLM token usage instead of time. Rejected because token count is provider-specific and not always available; wall-clock time is universal and more intuitive.
- *Cumulative epic duration*: Use total time invested in the epic. Rejected because it conflates multiple phase executions — the relevant cost is the single phase that would be retried.
- *Number of files modified*: Use git diff size. Rejected because file count doesn't correlate well with retry cost (one large file can be more expensive than five small ones).

### D3: `quick_correct` re-invokes `execute_phase` without git stash

**Decision**: In `quick_correct` mode, when `decision="retry"`, the runner appends the correction compass (same merging logic as stash_retry) and calls `execute_phase(state, compass=full_compass)` **without** calling `stash_working_changes()`. The phase sees its existing output and can make targeted corrections.

**Rationale**: The execution model already receives the compass as context. By appending the correction compass and not stashing, the model naturally sees "here's what you did, and here's what needs fixing" — it can make surgical corrections without losing good work. This leverages the existing compass injection mechanism rather than inventing a new one.

**Alternatives considered**:
- *New "correct" phase type*: Create a dedicated correction phase. Rejected because it requires a new phase definition, new prompt template, and new wiring — all for something the existing phase can do with the right compass.
- *File-level patching*: Parse the correction into patches and apply directly. Rejected because Twin doesn't produce structured patches, and bypassing the LLM loses the model's understanding of the codebase.

### D4: `max_quick_corrections` caps quick corrections; no auto-escalation to stash_retry

**Decision**: Add `max_quick_corrections` (default 1) to `TwinProviderConfig`. When quick corrections are exhausted, the system follows `retry_exhausted_action` (halt or continue). It does NOT automatically fall back to `stash_retry`.

**Rationale**: Automatic fallback creates a confusing two-stage retry loop where total retry count becomes hard to predict. If quick corrections aren't working, the operator should decide whether to halt and investigate or switch modes manually.

**Alternatives considered**:
- *Auto-escalate to stash_retry*: After exhausting quick corrections, switch to stash_retry. Rejected because it creates unpredictable retry budgets and token costs.
- *Shared retry budget*: Use `max_retries` for both modes. Rejected because quick corrections are much cheaper, so they deserve their own budget.

### D5: Correction compass prefix differentiates mode

**Decision**: In `quick_correct` mode, the correction compass uses `[QUICK-CORRECT n/N]` prefix instead of `[RETRY retry=N]`. This signals to the execution model that it should correct in-place rather than start over.

**Rationale**: The execution model may behave differently when it knows it's doing an in-place correction vs. a full retry. The prefix tells it "your previous output is still here — fix it" vs. "you're starting fresh."

## Risks / Trade-offs

- **[Execution model confusion]** In `quick_correct` mode, the execution model might misinterpret the correction compass and still try to redo everything from scratch → *Mitigation*: The `[QUICK-CORRECT]` prefix explicitly tells the model to fix, not redo. Can be tuned if models struggle.
- **[Accumulated errors]** Multiple quick corrections without stash could layer corrections on top of partially-correct output → *Mitigation*: `max_quick_corrections` defaults to 1, limiting accumulation. Git history (auto-commit after each phase) provides a rollback point.
- **[Auto threshold calibration]** The default 120s threshold may not be optimal for all projects → *Mitigation*: It's configurable. Operators can tune based on observed phase durations. Logging the auto-selection decision makes calibration easy.
- **[No git stash = no clean rollback in quick_correct]** If quick correction makes things worse, there's no automatic undo → *Mitigation*: The runner commits after each phase (existing behavior). Git history provides rollback.
