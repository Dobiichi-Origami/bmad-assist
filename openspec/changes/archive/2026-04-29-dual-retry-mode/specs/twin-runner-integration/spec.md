## MODIFIED Requirements

### Requirement: TwinProviderConfig
The system SHALL define a `TwinProviderConfig` data class with the following fields:
- `provider`: string, default `"claude"`
- `model`: string, default `"opus"`
- `enabled`: boolean, default `False`
- `max_retries`: integer, default `2` — maximum stash_retry cycles when `retry_mode="stash_retry"` or auto resolves to `stash_retry`
- `retry_exhausted_action`: literal `"halt"` or `"continue"`, default `"halt"` — applies to both stash_retry and quick_correct exhaustion
- `timeout_retries`: integer or None, default `2` — maximum timeout retry attempts for Twin LLM calls. `None` disables timeout retry (first `ProviderTimeoutError` propagates immediately). This is separate from `max_retries` which controls the RETRY decision loop.
- `retry_mode`: literal `"stash_retry"`, `"quick_correct"`, or `"auto"`, default `"stash_retry"` — determines how the runner handles a `retry` decision from Twin. `stash_retry` performs git stash + full phase re-execution. `quick_correct` re-invokes the phase with a correction compass without git stash. `auto` dynamically selects based on `duration_ms` vs `retry_mode_threshold_seconds`.
- `max_quick_corrections`: integer, default `1` — maximum quick correction cycles when the resolved retry mode is `quick_correct`. Independent of `max_retries`. When exhausted, follows `retry_exhausted_action`.
- `retry_mode_threshold_seconds`: integer, default `120` — minimum phase execution duration (in seconds) above which `auto` mode selects `quick_correct` and below which it selects `stash_retry`. Only used when `retry_mode="auto"`.

`TwinProviderConfig` MUST NOT include a `reflect_budget_tokens` field. This was removed in v6.

`TwinProviderConfig` MUST NOT include any INDEX truncation configuration. This was removed in v6.

The system SHALL add a `twin` section to the existing providers configuration in `providers.py`, parsed from YAML under `providers.twin` alongside the existing `providers.master` section.

#### Scenario: Default TwinProviderConfig values
WHEN no twin section exists in the providers YAML configuration
THEN the system SHALL construct a TwinProviderConfig with all default values: provider="claude", model="opus", enabled=False, max_retries=2, retry_exhausted_action="halt", timeout_retries=2, retry_mode="stash_retry", max_quick_corrections=1, retry_mode_threshold_seconds=120

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

#### Scenario: TwinProviderConfig with quick_correct mode
WHEN a TwinProviderConfig is constructed with `retry_mode="quick_correct"` and `max_quick_corrections=2`
THEN the system SHALL store these values, enabling the quick correct retry path with a maximum of 2 correction cycles

#### Scenario: TwinProviderConfig with auto mode
WHEN a TwinProviderConfig is constructed with `retry_mode="auto"` and `retry_mode_threshold_seconds=300`
THEN the system SHALL store these values, enabling time-based dynamic retry mode selection with a 300-second threshold

#### Scenario: TwinProviderConfig rejects invalid retry_mode
WHEN a TwinProviderConfig is constructed with `retry_mode="unknown"`
THEN the system SHALL reject it as an invalid value, because only `"stash_retry"`, `"quick_correct"`, and `"auto"` are permitted
