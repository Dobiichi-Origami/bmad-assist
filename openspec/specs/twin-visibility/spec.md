## ADDED Requirements

### Requirement: Twin status logging

The runner SHALL emit an info-level log message indicating Twin activation status when the main loop begins processing a phase.

When Twin is enabled, the runner SHALL log: `"Twin enabled (provider=%s, model=%s)"` with the configured provider and model.

When Twin is disabled, the runner SHALL log: `"Twin disabled"`.

#### Scenario: Twin enabled log message

- **WHEN** `providers.twin.enabled` is `True` and the runner enters the Twin integration block
- **THEN** the system SHALL log at info level a message containing "Twin enabled" along with the provider and model

#### Scenario: Twin disabled log message

- **WHEN** `providers.twin.enabled` is `False`
- **THEN** the system SHALL log at info level "Twin disabled"

---

### Requirement: Twin guide failure is visible

When the Twin guide call fails (raises an exception), the runner SHALL log a warning that includes the exception type and message.

The warning message SHALL follow the format: `"Twin guide failed, proceeding without compass: %s: %s"` with the exception type name and message.

#### Scenario: Twin guide failure logged as warning

- **WHEN** `twin_instance.guide()` raises an exception
- **THEN** the system SHALL log a warning containing the exception type name and exception message

---

### Requirement: Twin reflect failure is visible

When the Twin reflect call fails (raises an exception), the runner SHALL log a warning that includes the exception type and message.

The warning message SHALL follow the format: `"Twin reflect failed, proceeding: %s: %s"` with the exception type name and message.

#### Scenario: Twin reflect failure logged as warning

- **WHEN** `twin_instance.reflect()` raises an exception
- **THEN** the system SHALL log a warning containing the exception type name and exception message
