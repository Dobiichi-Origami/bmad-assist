## 1. Config Model

- [x] 1.1 Add `timeout: int = Field(default=300)` to `TwinProviderConfig` in `src/bmad_assist/twin/config.py`
- [x] 1.2 Add unit test for default `timeout=300` in `tests/twin/test_config.py`
- [x] 1.3 Add unit test for custom `timeout` value in `tests/twin/test_config.py`

## 2. Twin LLM Calls

- [x] 2.1 Pass `timeout=self.config.timeout` in `Twin._invoke_llm()` to `invoke_with_timeout_retry`
- [x] 2.2 Pass `timeout=self.config.timeout` in `Twin._extract_self_audit_llm()` to `invoke_with_timeout_retry`
- [x] 2.3 Add test verifying `_invoke_llm` passes `timeout` to `invoke_with_timeout_retry`
- [x] 2.4 Add test verifying `_extract_self_audit_llm` passes `timeout` to `invoke_with_timeout_retry`

## 3. YAML Config

- [x] 3.1 Add `timeout` field example to `providers.twin` section in `bmad-assist.yaml.example`
- [x] 3.4 Run full test suite to verify no regressions
