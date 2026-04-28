## MODIFIED Requirements

### Requirement: Twin failure degradation on YAML parse failure
When `Twin.reflect()` fails to parse the LLM's YAML output (even after one automatic retry), the degradation behavior SHALL depend on the `is_retry` parameter. If `is_retry=False` (this is a first-run reflect, not after a RETRY), the system SHALL default to `decision="continue"` and log the parse failure. If `is_retry=True` (this reflect is evaluating a RETRY attempt) and `retry_exhausted_action="halt"`, the system SHALL default to `decision="halt"` to prevent uncontrolled execution. If `is_retry=True` and `retry_exhausted_action="continue"`, the system SHALL default to `decision="continue"`.

This degradation logic applies regardless of the resolved retry mode — both `stash_retry` and `quick_correct` modes use `is_retry=True` when reflecting on a retry/correction result, so the same degradation rules govern both paths.

Note: `_reflect_with_retry` catches `Exception` broadly, which covers both YAML parse failures and `ProviderTimeoutError` that has exhausted all timeout retries (via `invoke_with_timeout_retry`). In both cases, the same degradation logic applies. The timeout retry mechanism in `_invoke_llm` provides earlier recovery for transient timeouts before they reach this degradation path.

#### Scenario: Parse failure on first-run reflect
- **WHEN** the LLM returns malformed YAML on a reflect call where `is_retry=False` and the automatic retry also fails
- **THEN** the method SHALL return a TwinResult with `decision="continue"` and `rationale="Twin parse error, defaulting to continue"`

#### Scenario: Parse failure on retry reflect with halt action
- **WHEN** the LLM returns malformed YAML on a reflect call where `is_retry=True` and `retry_exhausted_action="halt"`
- **THEN** the method SHALL return a TwinResult with `decision="halt"` and `rationale="Twin parse error during RETRY, halting to prevent uncontrolled execution"`

#### Scenario: Parse failure on retry reflect with continue action
- **WHEN** the LLM returns malformed YAML on a reflect call where `is_retry=True` and `retry_exhausted_action="continue"`
- **THEN** the method SHALL return a TwinResult with `decision="continue"` and a rationale indicating the parse error

#### Scenario: Automatic retry on first parse failure
- **WHEN** the LLM returns malformed YAML on the first attempt of a reflect call
- **THEN** the method SHALL retry the LLM call exactly once before applying degradation logic

#### Scenario: ProviderTimeoutError after timeout retries exhausted reaches degradation
- **WHEN** `invoke_with_timeout_retry` in `_invoke_llm` exhausts all `timeout_retries` attempts and raises `ProviderTimeoutError`
- **THEN** `_reflect_with_retry` SHALL catch the `ProviderTimeoutError` as a generic `Exception` and apply the same degradation logic as parse failure

#### Scenario: Parse failure during quick correct reflect
- **WHEN** the LLM returns malformed YAML on a reflect call during a `quick_correct` cycle where `is_retry=True` and `retry_exhausted_action="halt"`
- **THEN** the method SHALL return a TwinResult with `decision="halt"`, applying the same degradation logic as stash_retry
