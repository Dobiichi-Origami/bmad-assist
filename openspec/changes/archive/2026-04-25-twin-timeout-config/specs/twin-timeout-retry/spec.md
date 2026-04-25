## MODIFIED Requirements

### Requirement: Twin LLM calls use invoke_with_timeout_retry
The `Twin._invoke_llm()` method SHALL route its provider invocation through `invoke_with_timeout_retry()` instead of calling `self._provider.invoke()` directly. This ensures that `ProviderTimeoutError` is retried according to `TwinProviderConfig.timeout_retries` before the error propagates to `_reflect_with_retry`.

The `Twin._extract_self_audit_llm()` method SHALL also route its provider invocation through `invoke_with_timeout_retry()` for the same reason.

Both methods SHALL pass `timeout=self.config.timeout` through `invoke_with_timeout_retry` as a keyword argument so that `provider.invoke()` uses the configured timeout duration instead of the provider's hardcoded default.

Neither method SHALL pass a `fallback_invoke_fn` parameter — Twin does not have a fallback provider chain.

#### Scenario: Reflect LLM call times out and retries successfully
- **WHEN** `Twin._invoke_llm()` calls the provider with `timeout` from `TwinProviderConfig.timeout` and receives a `ProviderTimeoutError` on the first attempt, but succeeds on the second attempt
- **THEN** the method SHALL return the successful LLM output without triggering degradation logic

#### Scenario: Reflect LLM call times out and all retries exhausted
- **WHEN** `Twin._invoke_llm()` calls the provider with `timeout` from `TwinProviderConfig.timeout` and receives `ProviderTimeoutError` on all attempts (1 initial + `timeout_retries` retries)
- **THEN** `invoke_with_timeout_retry` SHALL raise `ProviderTimeoutError`, which SHALL be caught by `_reflect_with_retry`'s generic `except Exception` block and trigger degradation logic

#### Scenario: Self-audit extraction LLM call times out and retries
- **WHEN** `Twin._extract_self_audit_llm()` calls the provider with `timeout` from `TwinProviderConfig.timeout` and receives a `ProviderTimeoutError` on the first attempt, but succeeds on the second attempt
- **THEN** the method SHALL return the extracted self-audit content normally

#### Scenario: Self-audit extraction LLM call times out with all retries exhausted
- **WHEN** `Twin._extract_self_audit_llm()` calls the provider with `timeout` from `TwinProviderConfig.timeout` and receives `ProviderTimeoutError` on all attempts
- **THEN** the `ProviderTimeoutError` SHALL be caught by the existing `except Exception` block in `_extract_self_audit_llm`, which SHALL log a warning and return `None`

#### Scenario: Timeout retries disabled
- **WHEN** `TwinProviderConfig.timeout_retries` is `None`
- **THEN** `invoke_with_timeout_retry` SHALL invoke the provider once with `timeout` from `TwinProviderConfig.timeout` and let any `ProviderTimeoutError` propagate immediately without retry

#### Scenario: No fallback provider configured
- **WHEN** `Twin._invoke_llm()` routes through `invoke_with_timeout_retry`
- **THEN** no `fallback_invoke_fn` parameter SHALL be passed, because Twin does not have a fallback provider chain

#### Scenario: Configured timeout is used instead of provider default
- **WHEN** `TwinProviderConfig.timeout` is set to a value different from the provider's hardcoded default
- **THEN** `provider.invoke()` SHALL receive the configured `timeout` value, not the provider's default
