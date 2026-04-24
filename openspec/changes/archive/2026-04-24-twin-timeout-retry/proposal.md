## Why

Twin's LLM calls (`_invoke_llm` and `_extract_self_audit_llm`) directly call `self._provider.invoke()` without the `invoke_with_timeout_retry` wrapper. When the provider times out, the error propagates as a generic exception into `_reflect_with_retry`, which treats it as a parse failure and degrades (continue/halt) instead of retrying the timed-out call. This causes unnecessary Twin failures on transient provider timeouts that would otherwise recover with a simple retry.

## What Changes

- Wrap Twin's `_invoke_llm` call with `invoke_with_timeout_retry`, using the Twin's own provider and model configuration
- Wrap Twin's `_extract_self_audit_llm` call with `invoke_with_timeout_retry` for the self-audit extraction LLM call
- Add `timeout_retries` field to `TwinProviderConfig` (defaults to 2) to control timeout retry behavior independently from the main provider config
- Update `bmad-assist.yaml.example` to document the new field

## Capabilities

### New Capabilities
- `twin-timeout-retry`: Timeout retry protection for Twin LLM calls (reflect and self-audit extraction), using `invoke_with_timeout_retry` with Twin-specific `timeout_retries` configuration

### Modified Capabilities
- `twin-reflect`: `_invoke_llm` and `_extract_self_audit_llm` now route through `invoke_with_timeout_retry` instead of bare `provider.invoke()`; `ProviderTimeoutError` is retried before falling through to parse-failure degradation
- `twin-runner-integration`: `TwinProviderConfig` gains `timeout_retries: int` field (default 2)

## Impact

- `src/bmad_assist/twin/twin.py` — `_invoke_llm` and `_extract_self_audit_llm` method changes
- `src/bmad_assist/twin/config.py` — `TwinProviderConfig` new field
- `bmad-assist.yaml.example` — new `timeout_retries` field documentation
- `tests/twin/test_twin.py` — new tests for timeout retry behavior
- `tests/twin/test_config.py` — new tests for `timeout_retries` config field
