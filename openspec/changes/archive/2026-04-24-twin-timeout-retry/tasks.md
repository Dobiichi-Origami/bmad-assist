## 1. Configuration

- [x] 1.1 Add `timeout_retries: int | None = 2` field to `TwinProviderConfig` in `src/bmad_assist/twin/config.py`
- [x] 1.2 Add `timeout_retries` to the `bmad-assist.yaml.example` twin section with documentation comment
- [x] 1.3 Add config test: default `timeout_retries=2` in `tests/twin/test_config.py`
- [x] 1.4 Add config test: `timeout_retries=None` disables timeout retry in `tests/twin/test_config.py`
- [x] 1.5 Add config test: custom `timeout_retries=5` in `tests/twin/test_config.py`

## 2. Core Implementation

- [x] 2.1 Import `invoke_with_timeout_retry` in `src/bmad_assist/twin/twin.py`
- [x] 2.2 Refactor `_invoke_llm` to route through `invoke_with_timeout_retry` using `self.config.timeout_retries`, no `fallback_invoke_fn`
- [x] 2.3 Refactor `_extract_self_audit_llm` to route its `self._provider.invoke()` call through `invoke_with_timeout_retry` using `self.config.timeout_retries`, no `fallback_invoke_fn`

## 3. Tests

- [x] 3.1 Test: `_invoke_llm` retries on `ProviderTimeoutError` and succeeds on second attempt
- [x] 3.2 Test: `_invoke_llm` raises `ProviderTimeoutError` after all timeout retries exhausted
- [x] 3.3 Test: `_invoke_llm` with `timeout_retries=None` does not retry on timeout
- [x] 3.4 Test: `_extract_self_audit_llm` retries on `ProviderTimeoutError` and returns extracted content
- [x] 3.5 Test: `_extract_self_audit_llm` returns `None` after timeout retries exhausted
- [x] 3.6 Test: `_reflect_with_retry` applies degradation when `_invoke_llm` raises `ProviderTimeoutError` after retries exhausted
- [x] 3.7 Test: reflect end-to-end — timeout on first attempt, retry succeeds, returns valid TwinResult
