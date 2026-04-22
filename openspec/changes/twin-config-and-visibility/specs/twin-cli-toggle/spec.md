## ADDED Requirements

### Requirement: CLI --twin flag

The CLI SHALL accept a `--twin` flag that enables the Digital Twin feature for the current run.

When `--twin` is passed, the system SHALL set the environment variable `BMAD_TWIN_ENABLED=1` before configuration is loaded.

#### Scenario: --twin flag enables Twin

- **WHEN** the user runs `bmad-assist run --twin`
- **THEN** the system SHALL set `BMAD_TWIN_ENABLED=1` in the process environment

#### Scenario: --twin flag not passed

- **WHEN** the user runs `bmad-assist run` without `--twin`
- **THEN** the system SHALL NOT set `BMAD_TWIN_ENABLED` in the process environment

---

### Requirement: BMAD_TWIN_ENABLED environment variable

The system SHALL support a `BMAD_TWIN_ENABLED` environment variable to control Twin activation.

When `BMAD_TWIN_ENABLED` is set to `"1"`, the system SHALL override `providers.twin.enabled` to `True` regardless of the YAML configuration value.

When `BMAD_TWIN_ENABLED` is not set, the system SHALL use the value from the YAML configuration (which defaults to `False`).

The override priority SHALL be: `BMAD_TWIN_ENABLED` > YAML config > default (`False`).

#### Scenario: BMAD_TWIN_ENABLED=1 overrides YAML enabled=false

- **WHEN** `BMAD_TWIN_ENABLED=1` is set in the environment and the YAML config has `providers.twin.enabled: false`
- **THEN** the system SHALL set `providers.twin.enabled` to `True`

#### Scenario: BMAD_TWIN_ENABLED not set, YAML has enabled=true

- **WHEN** `BMAD_TWIN_ENABLED` is not set and the YAML config has `providers.twin.enabled: true`
- **THEN** the system SHALL keep `providers.twin.enabled` as `True`

#### Scenario: BMAD_TWIN_ENABLED not set, no twin section in YAML

- **WHEN** `BMAD_TWIN_ENABLED` is not set and the YAML config has no `providers.twin` section
- **THEN** the system SHALL use the default value `enabled=False`
