## MODIFIED Requirements

### Requirement: TwinProviderConfig
The system SHALL define a `TwinProviderConfig` data class with the following fields:
- `provider`: string, default `"claude"`
- `model`: string, default `"opus"`
- `enabled`: boolean, default `False`
- `max_retries`: integer, default `2`
- `retry_exhausted_action`: literal `"halt"` or `"continue"`, default `"halt"`
- `timeout_retries`: integer or None, default `2` — maximum timeout retry attempts for Twin LLM calls. `None` disables timeout retry (first `ProviderTimeoutError` propagates immediately). This is separate from `max_retries` which controls the RETRY decision loop.

`TwinProviderConfig` MUST NOT include a `reflect_budget_tokens` field. This was removed in v6.

`TwinProviderConfig` MUST NOT include any INDEX truncation configuration. This was removed in v6.

The system SHALL add a `twin` section to the existing providers configuration in `providers.py`, parsed from YAML under `providers.twin` alongside the existing `providers.master` section.

#### Scenario: Default TwinProviderConfig values
WHEN no twin section exists in the providers YAML configuration
THEN the system SHALL construct a TwinProviderConfig with all default values: provider="claude", model="opus", enabled=False, max_retries=2, retry_exhausted_action="halt", timeout_retries=2

#### Scenario: TwinProviderConfig parsed from YAML
WHEN the providers YAML contains a twin section with custom values
THEN the system SHALL parse those values into a TwinProviderConfig instance, making them available to the runner loop

#### Scenario: TwinProviderConfig rejects reflect_budget_tokens
WHEN a TwinProviderConfig is constructed with a reflect_budget_tokens field
THEN the system SHALL reject it as an invalid field, because reflect_budget_tokens was removed in v6

#### Scenario: TwinProviderConfig with timeout_retries=None
WHEN a TwinProviderConfig is constructed with `timeout_retries=None`
THEN the system SHALL store `None`, which means Twin LLM calls will not retry on ProviderTimeoutError

#### Scenario: TwinProviderConfig with custom timeout_retries
WHEN a TwinProviderConfig is constructed with `timeout_retries=5`
THEN the system SHALL store `5`, allowing up to 5 timeout retry attempts for Twin LLM calls
