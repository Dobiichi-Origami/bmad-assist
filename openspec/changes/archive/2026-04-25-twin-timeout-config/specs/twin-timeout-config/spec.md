## ADDED Requirements

### Requirement: TwinProviderConfig timeout field
`TwinProviderConfig` SHALL include a `timeout` field of type `int` with a default value of `300` (seconds). This field controls the timeout duration for all Twin LLM provider invocations (reflect and audit_extract).

#### Scenario: Default timeout value
- **WHEN** a `TwinProviderConfig` is created without specifying `timeout`
- **THEN** the `timeout` field SHALL be `300`

#### Scenario: Custom timeout value
- **WHEN** a `TwinProviderConfig` is created with `timeout=600`
- **THEN** the `timeout` field SHALL be `600`

#### Scenario: Timeout is immutable
- **WHEN** a `TwinProviderConfig` instance has been created
- **THEN** the `timeout` field SHALL NOT be mutable (frozen model)

### Requirement: Twin LLM calls pass timeout to provider
`Twin._invoke_llm()` and `Twin._extract_self_audit_llm()` SHALL pass `self.config.timeout` as the `timeout` keyword argument through `invoke_with_timeout_retry` to `provider.invoke()`.

#### Scenario: Reflect call uses configured timeout
- **WHEN** `Twin._invoke_llm()` is called and `TwinProviderConfig.timeout` is `600`
- **THEN** `provider.invoke()` SHALL receive `timeout=600`

#### Scenario: Audit extract call uses configured timeout
- **WHEN** `Twin._extract_self_audit_llm()` is called and `TwinProviderConfig.timeout` is `600`
- **THEN** `provider.invoke()` SHALL receive `timeout=600`

#### Scenario: Default timeout passes through
- **WHEN** `TwinProviderConfig.timeout` is not explicitly set (default `300`)
- **THEN** `provider.invoke()` SHALL receive `timeout=300`

### Requirement: YAML configuration for twin timeout
The `providers.twin` section in `bmad-assist.yaml` SHALL accept an optional `timeout` key (integer, seconds). When omitted, the default `300` applies.

#### Scenario: YAML with explicit timeout
- **WHEN** the YAML contains `providers.twin.timeout: 600`
- **THEN** the resulting `TwinProviderConfig.timeout` SHALL be `600`

#### Scenario: YAML without timeout key
- **WHEN** the YAML `providers.twin` section does not include a `timeout` key
- **THEN** the resulting `TwinProviderConfig.timeout` SHALL be `300`
