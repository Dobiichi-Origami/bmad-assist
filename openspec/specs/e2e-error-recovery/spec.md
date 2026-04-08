## ADDED Requirements

### Requirement: Phase failure triggers guardian halt
The system SHALL halt the loop when a phase returns a failure result and guardian decides to halt.

#### Scenario: DEV_STORY phase fails
- **WHEN** DEV_STORY phase returns PhaseResult.fail() for story 1.1
- **THEN** guardian_check_anomaly returns HALT, run_loop returns LoopExitReason.GUARDIAN_HALT, and state reflects the failed phase position

#### Scenario: CREATE_STORY phase fails
- **WHEN** CREATE_STORY phase returns PhaseResult.fail() for story 1.1
- **THEN** the loop halts with GUARDIAN_HALT and state.current_phase is CREATE_STORY

#### Scenario: Anomaly is recorded in state
- **WHEN** a phase failure triggers guardian halt
- **THEN** state.anomalies contains an entry with the failure details

### Requirement: Crash recovery from persisted state
The system SHALL resume correctly from a persisted state.yaml after a simulated crash.

#### Scenario: Resume from mid-story phase
- **WHEN** state.yaml contains epic=1, story="1.1", phase=DEV_STORY (indicating crash after VALIDATE_STORY_SYNTHESIS completed) and run_mock_loop is started
- **THEN** the loop resumes from DEV_STORY for story 1.1, does not re-run CREATE_STORY or VALIDATE_STORY phases

#### Scenario: Resume from story boundary
- **WHEN** state.yaml contains completed_stories=["1.1"] and current_story="1.2", current_phase=CREATE_STORY
- **THEN** the loop begins story 1.2 from CREATE_STORY, story 1.1 is not re-executed

#### Scenario: Resume from epic boundary
- **WHEN** state.yaml contains completed_epics=[1] and current_epic=2
- **THEN** the loop begins epic 2, epic 1 is not re-executed

#### Scenario: Fresh start with no state file
- **WHEN** no state.yaml exists in the project directory
- **THEN** the loop starts from the first epic's first story's first phase

### Requirement: Signal-based graceful shutdown
The system SHALL shut down gracefully when a shutdown signal is received.

#### Scenario: Shutdown requested during phase execution
- **WHEN** `request_shutdown(signal.SIGINT)` is called while a phase is executing (simulated via executor callback)
- **THEN** the loop completes the current phase, does not start the next phase, saves state, and returns LoopExitReason.INTERRUPTED_SIGINT

#### Scenario: SIGTERM shutdown
- **WHEN** `request_shutdown(signal.SIGTERM)` is called during execution
- **THEN** the loop returns LoopExitReason.INTERRUPTED_SIGTERM

#### Scenario: State is saved before exit on signal
- **WHEN** a shutdown signal is received and the loop exits
- **THEN** state.yaml reflects the position at the time of shutdown, allowing correct resume

### Requirement: Cancellation context support
The system SHALL respect CancellationContext for programmatic loop cancellation.

#### Scenario: Cancel via CancellationContext
- **WHEN** run_loop is called with a CancellationContext and cancel is triggered during phase execution
- **THEN** the loop exits with LoopExitReason.CANCELLED after the current phase completes

### Requirement: Multiple consecutive failures
The system SHALL handle multiple phase failures correctly.

#### Scenario: First story fails, loop halts
- **WHEN** story 1.1's DEV_STORY fails and guardian halts
- **THEN** stories 1.2 and 1.3 are never started, state shows position at story 1.1 DEV_STORY

#### Scenario: Guardian halt preserves completed work
- **WHEN** story 1.1 completes successfully but story 1.2's CODE_REVIEW fails
- **THEN** state.completed_stories contains "1.1" but not "1.2"
