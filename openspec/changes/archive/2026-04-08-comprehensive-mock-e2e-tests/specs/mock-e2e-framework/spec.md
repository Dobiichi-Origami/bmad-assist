## ADDED Requirements

### Requirement: ScriptedPhaseExecutor mock class
The system SHALL provide a `ScriptedPhaseExecutor` class that accepts a mapping of `(epic_id, story_id, phase) -> PhaseResult` and returns the corresponding result when called with a `State` object. If no mapping exists for the current state, it SHALL return `PhaseResult.ok()` by default.

#### Scenario: Returns scripted success result
- **WHEN** ScriptedPhaseExecutor is configured with `{(1, "1.1", Phase.DEV_STORY): PhaseResult.ok(outputs={"stdout": "done"})}` and execute_phase is called with state at epic=1, story="1.1", phase=DEV_STORY
- **THEN** it returns the configured PhaseResult with outputs containing "done"

#### Scenario: Returns scripted failure result
- **WHEN** ScriptedPhaseExecutor is configured with `{(1, "1.1", Phase.CODE_REVIEW): PhaseResult.fail(error="review failed")}` and execute_phase is called
- **THEN** it returns the configured failure PhaseResult

#### Scenario: Returns default success for unmapped phases
- **WHEN** execute_phase is called for a phase not in the mapping
- **THEN** it returns `PhaseResult.ok()` with empty outputs

#### Scenario: Records all invocations
- **WHEN** multiple phases are executed through the ScriptedPhaseExecutor
- **THEN** the executor records each invocation as `(epic_id, story_id, phase)` tuples accessible via `.invocations` property

### Requirement: Minimal BMAD project fixture generator
The system SHALL provide a `create_mock_project(tmp_path, epics_config)` fixture function that creates a minimal valid BMAD project directory structure for E2E testing.

#### Scenario: Single epic single story project
- **WHEN** `create_mock_project(tmp_path, epics=[{"id": 1, "stories": ["1.1"]}])` is called
- **THEN** it creates a valid project with `bmad-assist.yaml`, `bmad-docs/epics.md` containing epic 1 with story 1.1, and `.bmad-assist/` directory

#### Scenario: Multi epic multi story project
- **WHEN** `create_mock_project(tmp_path, epics=[{"id": 1, "stories": ["1.1", "1.2"]}, {"id": 2, "stories": ["2.1"]}])` is called
- **THEN** it creates epics.md with both epics and all stories, and the epic_stories_loader returns correct story lists per epic

#### Scenario: Returns callable epic_stories_loader
- **WHEN** a mock project is created
- **THEN** the returned object includes an `epic_stories_loader` callable and an `epic_list` that can be passed directly to `run_loop()`

### Requirement: State assertion helpers
The system SHALL provide assertion helper functions for verifying State objects in E2E tests.

#### Scenario: Assert completed stories
- **WHEN** `assert_stories_completed(state, ["1.1", "1.2"])` is called
- **THEN** it verifies that `state.completed_stories` contains exactly those story IDs

#### Scenario: Assert completed epics
- **WHEN** `assert_epics_completed(state, [1, 2])` is called
- **THEN** it verifies that `state.completed_epics` contains exactly those epic IDs

#### Scenario: Assert phase execution order
- **WHEN** `assert_phase_order(executor, expected_phases)` is called with an expected phase list
- **THEN** it verifies the ScriptedPhaseExecutor's invocations match the expected order

### Requirement: Mock config factory
The system SHALL provide a `create_e2e_config()` factory that returns a minimal valid `Config` object suitable for E2E testing with all provider calls mocked.

#### Scenario: Config with mock provider
- **WHEN** `create_e2e_config()` is called
- **THEN** it returns a Config with `providers.master` set to `claude/mock` and all timeouts set to minimal values

#### Scenario: Config with QA enabled
- **WHEN** `create_e2e_config(qa_enabled=True)` is called
- **THEN** it returns a Config with QA phases enabled in the loop config

### Requirement: Run loop test harness
The system SHALL provide a `run_mock_loop()` helper that wraps `run_loop()` with appropriate defaults for E2E testing (`skip_signal_handlers=True`, `ipc_enabled=False`, `plain=True`).

#### Scenario: Runs loop with mocked phases
- **WHEN** `run_mock_loop(project, executor)` is called with a mock project and scripted executor
- **THEN** it executes `run_loop()` with signal handlers disabled, IPC disabled, plain rendering, and the executor's mock patched over `execute_phase`

#### Scenario: Returns loop result and final state
- **WHEN** `run_mock_loop()` completes
- **THEN** it returns a `MockLoopResult` containing the `LoopExitReason`, the final `State`, and the executor's invocation log
