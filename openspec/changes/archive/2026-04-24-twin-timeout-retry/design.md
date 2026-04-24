## Context

The project has a well-established `invoke_with_timeout_retry` wrapper (`src/bmad_assist/core/retry.py`) that handles `ProviderTimeoutError` with configurable retry counts and fallback providers. All main-loop phase execution paths (handlers/base.py, code_review_synthesis.py, validate_story_synthesis.py) already use this wrapper.

However, the Digital Twin's LLM calls bypass this mechanism entirely. `Twin._invoke_llm` (twin.py:291) and `Twin._extract_self_audit_llm` (twin.py:228) call `self._provider.invoke()` directly. When a provider timeout occurs, the `ProviderTimeoutError` is caught by `_reflect_with_retry`'s generic `except Exception` block and treated identically to a YAML parse failure — triggering degradation logic (continue/halt) instead of a retry of the timed-out LLM call.

This means transient provider timeouts (which are common with remote LLM APIs) cause unnecessary Twin failures, even though the infrastructure to handle them already exists.

## Goals / Non-Goals

**Goals:**
- Route Twin's LLM calls through `invoke_with_timeout_retry` so that `ProviderTimeoutError` is retried before falling through to degradation
- Make Twin's timeout retry count configurable via `TwinProviderConfig.timeout_retries`
- Cover both `_invoke_llm` (reflect) and `_extract_self_audit_llm` (self-audit extraction) paths

**Non-Goals:**
- No fallback provider for Twin (Twin uses a single configured provider; fallback complexity is not warranted)
- No changes to the main-loop handler timeout retry logic
- No changes to `_reflect_with_retry`'s parse-failure retry count (remains 1 internal retry for parse errors)
- No infinite retry (`timeout_retries=0`) support for Twin — only finite retry counts or None

## Decisions

### Decision 1: Add `timeout_retries` to `TwinProviderConfig`

**Choice**: Add a dedicated `timeout_retries: int | None = 2` field to `TwinProviderConfig`.

**Rationale**: Twin's timeout retry needs are separate from the main provider's retry configuration. The main handlers get their `timeout_retries` from `get_phase_retries()`, which is phase-specific. Twin doesn't have per-phase retry semantics — it has a single retry count for all its LLM calls.

**Alternatives considered**:
- Reuse `max_retries` for timeout retries: Bad idea — `max_retries` controls the RETRY decision loop (how many times to re-execute a phase when Twin says "retry"), not LLM call timeout retry. Conflating these would be confusing.
- Read from main provider config: Would couple Twin config to main provider config unnecessarily.

### Decision 2: Use `invoke_with_timeout_retry` wrapper in `_invoke_llm`

**Choice**: Refactor `_invoke_llm` to call `invoke_with_timeout_retry(self._provider.invoke, ...)` instead of `self._provider.invoke()` directly.

**Rationale**: Reuses the existing battle-tested retry logic. The wrapper handles `ProviderTimeoutError` specifically, logs retry attempts, and respects the retry count. No need to duplicate this in Twin.

**Implementation detail**: `_invoke_llm` currently returns a string. After wrapping with `invoke_with_timeout_retry`, the result may be a string or an object with `.stdout`. The existing `hasattr(result, "stdout")` check in `_invoke_llm` handles both cases, so no change needed there.

### Decision 3: No fallback provider for Twin

**Choice**: Do not pass `fallback_invoke_fn` to `invoke_with_timeout_retry` for Twin calls.

**Rationale**: The main handlers use subprocess providers as fallback for SDK providers. Twin doesn't have an equivalent fallback chain. Adding one would introduce complexity (separate fallback provider config) for a scenario where the user can already configure the Twin's provider/model independently.

### Decision 4: `timeout_retries=None` means no retry (same as `invoke_with_timeout_retry` convention)

**Choice**: `timeout_retries=None` disables timeout retry; the first `ProviderTimeoutError` propagates immediately.

**Rationale**: Matches the existing convention in `invoke_with_timeout_retry` where `None` = no retry. This gives users an escape hatch to disable Twin timeout retries if desired.

## Risks / Trade-offs

- **[Double retry confusion]** Users might confuse `max_retries` (RETRY decision loop) with `timeout_retries` (LLM call timeout). → Mitigation: clear naming, documentation, and YAML comments distinguishing the two.
- **[Increased Twin latency]** Retrying timed-out calls adds latency. → Mitigation: default of 2 is conservative; users can set `timeout_retries: null` to disable.
- **[Timeout error still possible after retries]** If all timeout retries are exhausted, `ProviderTimeoutError` propagates into `_reflect_with_retry`, which catches it as a generic `Exception` and applies degradation. This is acceptable — the timeout retries give the provider a chance to recover, and if it can't, the existing degradation logic handles it gracefully.
