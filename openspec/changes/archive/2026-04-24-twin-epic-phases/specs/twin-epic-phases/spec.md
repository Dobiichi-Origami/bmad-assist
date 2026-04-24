## ADDED Requirements

### Requirement: Twin guide provides compass for epic setup phases
When Twin is enabled, `_execute_epic_setup` SHALL call `Twin.guide()` for each setup phase and pass the returned compass to `execute_phase(state, compass=compass)`.

#### Scenario: Twin enabled during epic setup
- **WHEN** `config.providers.twin.enabled` is `True` and epic setup phases are configured
- **THEN** each setup phase SHALL receive compass from `Twin.guide(phase_type)` via `execute_phase(state, compass=compass)`

#### Scenario: Twin disabled during epic setup
- **WHEN** `config.providers.twin.enabled` is `False`
- **THEN** each setup phase SHALL be executed with `compass=None`

#### Scenario: Twin guide fails during epic setup
- **WHEN** `Twin.guide()` raises an exception
- **THEN** the setup phase SHALL execute with `compass=None` and execution SHALL continue

### Requirement: Twin reflect runs after successful epic setup phase execution
When Twin is enabled and a setup phase succeeds, `_execute_epic_setup` SHALL call `Twin.reflect()` and handle its decision.

#### Scenario: Reflect returns continue during setup
- **WHEN** Twin reflect returns `decision="continue"` after a successful setup phase
- **THEN** the setup loop SHALL proceed to the next setup phase

#### Scenario: Reflect returns halt during setup
- **WHEN** Twin reflect returns `decision="halt"` after a successful setup phase
- **THEN** `_execute_epic_setup` SHALL return `(state, False)`, causing the loop to exit with `GUARDIAN_HALT`

#### Scenario: Reflect returns retry during setup
- **WHEN** Twin reflect returns `decision="retry"` after a successful setup phase
- **THEN** the phase SHALL be re-executed with correction compass appended to the original compass

#### Scenario: Retry exhausted during setup
- **WHEN** Twin retry count reaches `max_retries` during epic setup
- **THEN** `_execute_epic_setup` SHALL return `(state, False)`, causing the loop to exit with `GUARDIAN_HALT`

### Requirement: Twin guide provides compass for epic teardown phases
When Twin is enabled, `_execute_epic_teardown` SHALL call `Twin.guide()` for each teardown phase and pass the returned compass to `execute_phase(state, compass=compass)`.

#### Scenario: Twin enabled during epic teardown
- **WHEN** `config.providers.twin.enabled` is `True` and epic teardown phases are configured
- **THEN** each teardown phase SHALL receive compass from `Twin.guide(phase_type)` via `execute_phase(state, compass=compass)`

#### Scenario: Twin disabled during epic teardown
- **WHEN** `config.providers.twin.enabled` is `False`
- **THEN** each teardown phase SHALL be executed with `compass=None`

### Requirement: Twin reflect runs after successful epic teardown phase execution
When Twin is enabled and a teardown phase succeeds, `_execute_epic_teardown` SHALL call `Twin.reflect()` and handle its decision. Per ADR-002, teardown phases continue on failure.

#### Scenario: Reflect returns continue during teardown
- **WHEN** Twin reflect returns `decision="continue"` after a successful teardown phase
- **THEN** the teardown loop SHALL proceed to the next teardown phase

#### Scenario: Reflect returns halt during teardown
- **WHEN** Twin reflect returns `decision="halt"` after a successful teardown phase
- **THEN** `_execute_epic_teardown` SHALL log a warning and continue to the next teardown phase (ADR-002 takes priority)

#### Scenario: Reflect returns retry during teardown
- **WHEN** Twin reflect returns `decision="retry"` after a successful teardown phase
- **THEN** the phase SHALL be re-executed with correction compass appended to the original compass

#### Scenario: Retry exhausted during teardown
- **WHEN** Twin retry count reaches `max_retries` during epic teardown
- **THEN** `_execute_epic_teardown` SHALL log a warning and continue to the next teardown phase

#### Scenario: Reflect exception during teardown
- **WHEN** `Twin.reflect()` raises an exception during epic teardown
- **THEN** the exception SHALL be caught, a warning logged, and execution SHALL continue to the next teardown phase

### Requirement: Shared Twin orchestration helper function
A shared helper function `_execute_phase_with_twin()` SHALL encapsulate the Twin guide → execute → reflect → retry cycle for reuse by epic_phases.py.

#### Scenario: Helper executes phase with Twin guide and reflect
- **WHEN** `_execute_phase_with_twin(state, config, project_path)` is called with Twin enabled
- **THEN** it SHALL call `Twin.guide()`, execute the phase with compass, and call `Twin.reflect()` on success

#### Scenario: Helper respects retry_exhausted_action parameter
- **WHEN** `_execute_phase_with_twin()` is called with `retry_exhausted_action="halt"` and retries are exhausted
- **THEN** it SHALL return the failed PhaseResult
- **WHEN** called with `retry_exhausted_action="continue"` and retries are exhausted
- **THEN** it SHALL return the last retry PhaseResult (which may be successful)

### Requirement: Twin provider resolution shared across modules
`resolve_twin_provider()` SHALL be available in `dispatch.py` for use by both runner.py and epic_phases.py.

#### Scenario: Runner imports resolve_twin_provider from dispatch
- **WHEN** runner.py needs to resolve a Twin provider
- **THEN** it SHALL import `resolve_twin_provider` from `bmad_assist.core.loop.dispatch`

### Requirement: Epic phase functions accept config parameter
`_execute_epic_setup` and `_execute_epic_teardown` SHALL accept a `config` parameter to access Twin configuration.

#### Scenario: Setup function receives config
- **WHEN** `_execute_epic_setup(state, state_path, project_path, config)` is called
- **THEN** it SHALL use `config.providers.twin` to determine Twin enablement and configuration

#### Scenario: Teardown function receives config
- **WHEN** `_execute_epic_teardown(state, state_path, project_path, config)` is called
- **THEN** it SHALL use `config.providers.twin` to determine Twin enablement and configuration

## MODIFIED Requirements

### Requirement: Twin runner integration uses shared provider resolution
The Twin runner integration module SHALL import `resolve_twin_provider` from `dispatch.py` instead of defining it locally.

#### Scenario: Provider resolution via dispatch module
- **WHEN** runner.py calls `resolve_twin_provider(config)`
- **THEN** it SHALL use the function imported from `bmad_assist.core.loop.dispatch` instead of a locally defined private function
