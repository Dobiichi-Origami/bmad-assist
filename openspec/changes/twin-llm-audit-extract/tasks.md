## 1. Configuration

- [x] 1.1 Add `audit_extract_model: str | None = None` field to `TwinProviderConfig` in `src/bmad_assist/twin/config.py`
- [x] 1.2 Add `audit_extract_model` example to `bmad-assist.yaml.example` twin section

## 2. Extraction Prompt

- [x] 2.1 Add `_EXTRACT_SELF_AUDIT_PROMPT_TEMPLATE` constant to `src/bmad_assist/twin/prompts.py` — prompt listing Chinese/English heading variants, requesting YAML output with `found` + `content`
- [x] 2.2 Add `build_extract_self_audit_prompt(llm_output: str) -> str` function to `prompts.py` and export in `__all__`

## 3. Core LLM Extraction Method

- [x] 3.1 Add `_extract_self_audit_llm(self, llm_output: str) -> str | None` method to `Twin` class in `src/bmad_assist/twin/twin.py` — builds prompt, calls provider with `audit_extract_model or config.model`, parses YAML, returns content or None
- [x] 3.2 Apply `prepare_llm_output()` truncation in `_extract_self_audit_llm()` before building the extraction prompt

## 4. Reflect Integration

- [x] 4.1 Modify `Twin.reflect()` to resolve `self_audit` local variable: if `record.self_audit is None` and `record.llm_output` is non-empty, call `_extract_self_audit_llm()`
- [x] 4.2 Pass the resolved `self_audit` local variable (not `record.self_audit`) to `build_reflect_prompt()`

## 5. Tests

- [x] 5.1 Add `TestTwinExtractSelfAudit` test class to `tests/twin/test_twin.py` — regex succeeds no LLM call, LLM fallback on None, LLM returns found:false, provider failure graceful, audit_extract_model usage, None fallback to main model
- [x] 5.2 Add Chinese heading and non-standard heading level test scenarios to `tests/twin/test_twin.py`
- [x] 5.3 Add prompt tests to `tests/twin/test_prompts.py` — prompt contains document, requests YAML, lists heading variants
- [x] 5.4 Add `TwinProviderConfig` tests for `audit_extract_model` default None and custom value
- [x] 5.5 Run `pytest tests/twin/` and verify all tests pass (existing + new)
