## MODIFIED Requirements

### Requirement: TwinProviderConfig

The system SHALL define a `TwinProviderConfig` data class with the following fields:
- `provider`: string, default `"claude"`
- `model`: string, default `"opus"`
- `enabled`: boolean, default `False`
- `max_retries`: integer, default `2`
- `retry_exhausted_action`: literal `"halt"` or `"continue"`, default `"halt"`

`TwinProviderConfig` MUST NOT include a `reflect_budget_tokens` field. This was removed in v6.

`TwinProviderConfig` MUST NOT include any INDEX truncation configuration. This was removed in v6.

The system SHALL add a `twin` section to the existing providers configuration in `providers.py`, parsed from YAML under `providers.twin` alongside the existing `providers.master` section.

#### Scenario: Default TwinProviderConfig values

WHEN no twin section exists in the providers YAML configuration
THEN the system SHALL construct a TwinProviderConfig with all default values: provider="claude", model="opus", enabled=False, max_retries=2, retry_exhausted_action="halt"

#### Scenario: TwinProviderConfig parsed from YAML

WHEN the providers YAML contains a twin section with custom values
THEN the system SHALL parse those values into a TwinProviderConfig instance, making them available to the runner loop

#### Scenario: TwinProviderConfig rejects reflect_budget_tokens

WHEN a TwinProviderConfig is constructed with a reflect_budget_tokens field
THEN the system SHALL reject it as an invalid field, because reflect_budget_tokens was removed in v6

---

### Requirement: Twin Guide Before Phase Execution

Before each phase execution in the runner main loop, the system SHALL call `twin.guide()` to produce a compass string. The compass string provides experience-derived guidance for the upcoming phase.

If `TwinProviderConfig.enabled` is `False`, the system SHALL skip the guide call entirely and set `compass=None`.

The compass string SHALL be passed to `execute_phase()` via a `compass` parameter so that the compiled prompt can include it.

The runner SHALL access `config.providers.twin` directly without `hasattr` guards, because the Pydantic model always provides a default instance.

#### Scenario: Guide produces compass for phase

WHEN the runner is about to execute a phase and twin is enabled
THEN the system SHALL call twin.guide(phase, epic_id, story_id) and pass the returned compass string to execute_phase()

#### Scenario: Guide fails gracefully

WHEN twin.guide() raises an exception or returns an error
THEN the system SHALL log a warning with the exception type and message, set compass=None, and proceed with phase execution without a compass

#### Scenario: Twin disabled skips guide

WHEN TwinProviderConfig.enabled is False
THEN the system SHALL NOT call twin.guide(), set compass=None, and log "Twin disabled"
