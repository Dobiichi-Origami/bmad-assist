## ADDED Requirements

### Requirement: Configuration reference documents idle_timeout field
The `docs/configuration.md` Timeouts section SHALL include the `idle_timeout` field in its YAML example block and provide a description explaining its purpose, default value (None/disabled), minimum value (30 seconds), and recommended range.

#### Scenario: User reads Timeouts section
- **WHEN** a user reads the Timeouts section of `docs/configuration.md`
- **THEN** they SHALL see `idle_timeout` listed in the YAML example with a comment, and a paragraph below explaining stall detection behavior

#### Scenario: Documentation states correct constraints
- **WHEN** the user reads the `idle_timeout` description
- **THEN** it SHALL state that the default is `None` (disabled), minimum is 30 seconds, and recommended range is 120-300 seconds

### Requirement: Example configuration includes idle_timeout
The `bmad-assist.yaml.example` file SHALL include `idle_timeout` in the timeouts block as a commented-out entry with a descriptive comment.

#### Scenario: User copies example config
- **WHEN** a user copies `bmad-assist.yaml.example` as their configuration starting point
- **THEN** they SHALL see `# idle_timeout: 180` (commented out) in the timeouts section, indicating the option exists

### Requirement: Troubleshooting covers provider stall scenario
The `docs/troubleshooting.md` SHALL include a section for diagnosing and resolving provider stall/hang issues, referencing the `idle_timeout` configuration.

#### Scenario: User experiences provider hang
- **WHEN** a user's provider process hangs with no output
- **THEN** the troubleshooting guide SHALL describe the symptom, explain `idle_timeout` as the solution, and show a YAML configuration example

### Requirement: Provider docs mention stall detection
The `docs/providers.md` SHALL mention that all providers support idle timeout stall detection, with a cross-reference to the configuration docs.

#### Scenario: User reads provider documentation
- **WHEN** a user reads `docs/providers.md`
- **THEN** they SHALL find a mention that stall detection is available for all providers, with a link to the Timeouts configuration section
