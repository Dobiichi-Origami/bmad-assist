## ADDED Requirements

### Requirement: build_execution_record is called with real PhaseResult outputs
`_execute_phase_with_twin` SHALL call `build_execution_record` with values extracted from the real `PhaseResult.outputs` dict when Twin reflect is enabled.

#### Scenario: Record receives response and duration_ms from PhaseResult
- **WHEN** `_execute_phase_with_twin` executes with Twin enabled, and the handler returns `PhaseResult.ok(outputs={"response": "actual output", "duration_ms": 150})`
- **THEN** `build_execution_record` SHALL be called with `llm_output="actual output"` and `duration_ms=150`

#### Scenario: Record receives empty defaults when outputs lack keys
- **WHEN** `_execute_phase_with_twin` executes with Twin enabled, and the handler returns `PhaseResult.ok()` with no `"response"` key
- **THEN** `build_execution_record` SHALL be called with `llm_output=""` and `duration_ms=0`

#### Scenario: Non-int duration_ms is coerced to 0
- **WHEN** the handler returns `PhaseResult.ok(outputs={"duration_ms": "slow"})`
- **THEN** `build_execution_record` SHALL be called with `duration_ms=0`

### Requirement: reflect block exception handling preserves original result
When the reflect block in `_execute_phase_with_twin` raises an exception (from `build_execution_record` or `Twin.reflect()`), the original phase result SHALL be returned.

#### Scenario: build_execution_record raises TypeError
- **WHEN** `build_execution_record` raises `TypeError` during reflect
- **THEN** `_execute_phase_with_twin` SHALL log a warning and return the original successful `PhaseResult`

#### Scenario: Twin.reflect raises RuntimeError
- **WHEN** `Twin.reflect()` raises `RuntimeError("LLM call failed")`
- **THEN** `_execute_phase_with_twin` SHALL log a warning and return the original successful `PhaseResult`

### Requirement: apply_page_updates writes real files to wiki directory
When `Twin.reflect()` returns `page_updates`, `_execute_phase_with_twin` SHALL call `apply_page_updates` which performs real file I/O on the wiki directory.

#### Scenario: Page create writes new file
- **WHEN** `TwinResult.page_updates` contains `PageUpdate(page_name="patterns", action="create", content="# Patterns\n...")`
- **THEN** a file `patterns.md` SHALL be created in the wiki directory with the specified content

#### Scenario: Page update modifies existing file
- **WHEN** `TwinResult.page_updates` contains `PageUpdate(page_name="patterns", action="update", content="updated content")`
- **THEN** the existing `patterns.md` file SHALL be updated with the new content

### Requirement: Compass injection works end-to-end through bound method handler
The full chain from `execute_phase(state, compass=X)` through `get_handler()` returning a bound method to `handler.execute(state)` reading `self._compass` SHALL work correctly.

#### Scenario: Real handler instance receives compass via bound method
- **WHEN** `init_handlers(config, project_path)` registers a FakeHandler instance, `get_handler(phase)` returns `instance.execute`, and `execute_phase(state, compass="real-compass")` is called
- **THEN** the FakeHandler's `compass_seen` SHALL be `"real-compass"`

#### Scenario: Compass injection with Twin guide through full _execute_phase_with_twin path
- **WHEN** `_execute_phase_with_twin` is called with Twin enabled, and the FakeTwin guide returns `"twin-compass"`
- **THEN** the FakeHandler's `compass_seen` SHALL be `"twin-compass"`, verifying the compass flows from Twin guide → execute_phase → bound method handler

### Requirement: Twin guide returns None does not prevent reflect
When `Twin.guide()` returns `None` but `_twin_instance` is set, `_execute_phase_with_twin` SHALL still call reflect on the successful result.

#### Scenario: Guide returns None, reflect still called
- **WHEN** FakeTwin guide returns `None` and phase execution succeeds
- **THEN** `_execute_phase_with_twin` SHALL call `FakeTwin.reflect()` with the execution record
