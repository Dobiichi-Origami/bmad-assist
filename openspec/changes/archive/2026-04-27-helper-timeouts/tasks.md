## 1. Config Model

- [x] 1.1 Add `HelperTimeoutsConfig` model to `src/bmad_assist/core/config/models/features.py` (before `TimeoutsConfig`) with fields: `default=60`, `qa_summary=None`, `testarch_eligibility=None`, `strategic_context=None`, `stack_detector=None`, `benchmarking_extraction=None`, `synthesis_extraction=None` (all `ge=10`), and `get_timeout(scenario)` method
- [x] 1.2 Add `helper: HelperTimeoutsConfig = Field(default_factory=HelperTimeoutsConfig)` to `TimeoutsConfig` class in the same file
- [x] 1.3 Export `HelperTimeoutsConfig` from `src/bmad_assist/core/config/models/__init__.py`

## 2. Loader Function

- [x] 2.1 Add `get_helper_timeout(config, scenario)` to `src/bmad_assist/core/config/loaders.py` with legacy fallback dict (`qa_summary=60`, `testarch_eligibility=60`, `strategic_context=120`, `stack_detector=30`, `benchmarking_extraction=120`, `synthesis_extraction=60`, default=60)
- [x] 2.2 Export `get_helper_timeout` from `src/bmad_assist/core/config/__init__.py`

## 3. Call Site Updates — Simple Replacements

- [x] 3.1 Replace `timeout=60` with `get_helper_timeout(config, "qa_summary")` in `src/bmad_assist/qa/summary.py:155`
- [x] 3.2 Replace `timeout=60` with `get_helper_timeout(config, "testarch_eligibility")` in `src/bmad_assist/testarch/eligibility.py:332`
- [x] 3.3 Replace `timeout=120` with `get_helper_timeout(config, "strategic_context")` in `src/bmad_assist/compiler/strategic_context.py:303`
- [x] 3.4 Replace `timeout=30` with `get_helper_timeout(config, "stack_detector")` in `src/bmad_assist/deep_verify/stack_detector.py:135`

## 4. Call Site Updates — Complex Changes

- [x] 4.1 Fix benchmarking extraction timeout in `src/bmad_assist/validation/orchestrator.py`: replace `timeout=timeout` (from `get_phase_timeout`) with `get_helper_timeout(config, "benchmarking_extraction")` at line ~881
- [x] 4.2 Update `validate_story_synthesis.py:244-256`: change `per_call_timeout` calculation to use `get_helper_timeout(config, "synthesis_extraction")` as ceiling: `max(min(budget_per_call, helper_ext_timeout), 30)`
- [x] 4.3 Update `code_review_synthesis.py:467-479`: same ceiling pattern as 4.2

## 5. Tests

- [x] 5.1 Add `TestHelperTimeoutsConfig` to `tests/core/test_config_timeouts.py`: default values, get_timeout with scenario override, get_timeout fallback to default, hyphen normalization
- [x] 5.2 Add `TestGetHelperTimeout` to same test file: with timeouts config, without timeouts config (legacy fallback), unknown scenario fallback
