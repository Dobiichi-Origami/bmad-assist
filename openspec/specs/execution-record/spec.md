## MODIFIED Requirements

### Requirement: TwinProviderConfig for reflect configuration
The system SHALL define a `TwinProviderConfig` Pydantic model with fields `provider: str`, `model: str`, `enabled: bool = True`, `max_retries: int = 2`, `retry_exhausted_action: Literal["halt", "continue"] = "halt"`, and `audit_extract_model: str | None = None`. The `Twin` class SHALL be initialized with this config and use the specified provider/model for LLM calls, independent of the execution model. The `audit_extract_model` field specifies the model to use for LLM-based self-audit extraction; when None, the Twin's main `model` SHALL be used.

#### Scenario: Default configuration
- **WHEN** a TwinProviderConfig is constructed with no arguments
- **THEN** `enabled` SHALL be `True`, `max_retries` SHALL be `2`, `retry_exhausted_action` SHALL be `"halt"`, and `audit_extract_model` SHALL be `None`

#### Scenario: Custom configuration with audit extraction model
- **WHEN** a TwinProviderConfig is constructed with `provider="claude"`, `model="opus"`, `audit_extract_model="haiku"`, `max_retries=3`, and `retry_exhausted_action="continue"`
- **THEN** all fields SHALL store the provided values

#### Scenario: audit_extract_model None falls back to main model
- **WHEN** a TwinProviderConfig is constructed with `model="opus"` and `audit_extract_model=None`
- **THEN** self-audit extraction SHALL use "opus" as the model
