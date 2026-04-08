## ADDED Requirements

### Requirement: QA flow complete chain
The system SHALL execute the full QA phase chain (QA_PLAN_GENERATE → QA_PLAN_EXECUTE → QA_REMEDIATE) when QA is enabled.

#### Scenario: QA phases execute after story phases
- **WHEN** QA is enabled and all story phases succeed
- **THEN** QA_PLAN_GENERATE, QA_PLAN_EXECUTE, and QA_REMEDIATE phases execute in order after the story's main phases and before RETROSPECTIVE

#### Scenario: QA phases skipped when disabled
- **WHEN** QA is not enabled (default)
- **THEN** no QA_PLAN_GENERATE, QA_PLAN_EXECUTE, or QA_REMEDIATE phases are executed

### Requirement: CLI flag --epic filtering
The system SHALL respect the --epic flag to limit execution to specific epics.

#### Scenario: Run single epic from multi-epic project
- **WHEN** run_mock_loop is executed with epic_list=[1, 2, 3] but --epic=2 is specified
- **THEN** only epic 2's stories are executed, epics 1 and 3 are skipped

#### Scenario: --story flag starts from specific story
- **WHEN** --story="1.2" is specified for epic 1 with stories ["1.1", "1.2", "1.3"]
- **THEN** execution starts from story 1.2, story 1.1 is skipped

### Requirement: CLI flag --stop-after-epic
The system SHALL stop execution after completing the specified epic.

#### Scenario: Stop after epic 1
- **WHEN** epic_list=[1, 2, 3] and --stop-after-epic=1 is specified
- **THEN** the loop completes all stories in epic 1 then exits with COMPLETED, epics 2 and 3 are not started

### Requirement: Sprint status synchronization
The system SHALL update sprint-status.yaml correctly during loop execution.

#### Scenario: Story completion updates sprint status
- **WHEN** a story completes successfully
- **THEN** sprint-status.yaml is updated to reflect the story as "done"

#### Scenario: Sprint status reflects current position
- **WHEN** the loop is running story 1.2 in DEV_STORY phase
- **THEN** sprint-status.yaml shows story 1.2 as "in-progress"

### Requirement: Notification dispatch at lifecycle events
The system SHALL trigger notifications at correct lifecycle events when notifications are configured.

#### Scenario: Story completion triggers notification
- **WHEN** a story completes and notification dispatcher is mocked
- **THEN** the dispatcher receives a story_completed event with the correct story ID

#### Scenario: Epic completion triggers notification
- **WHEN** an epic completes
- **THEN** the dispatcher receives an epic_completed event

#### Scenario: Guardian halt triggers notification
- **WHEN** guardian decides to halt
- **THEN** the dispatcher receives a guardian_halt event with anomaly details

### Requirement: Git auto-commit at phase boundaries
The system SHALL trigger git auto-commit after configurable phases when git-commit is enabled.

#### Scenario: Commit after DEV_STORY phase
- **WHEN** git-commit is enabled and DEV_STORY phase completes successfully
- **THEN** the git committer is invoked with a dynamic commit message

#### Scenario: No commit when git-commit is disabled
- **WHEN** git-commit is disabled (default)
- **THEN** the git committer is never invoked

#### Scenario: No commit on phase failure
- **WHEN** git-commit is enabled but a phase fails
- **THEN** the git committer is not invoked for the failed phase

### Requirement: IPC event emission during loop execution
The system SHALL emit correct IPC/dashboard events during loop execution when IPC is enabled.

#### Scenario: Phase start and completion events
- **WHEN** IPC event emission is mocked and a phase executes
- **THEN** phase_started and phase_completed events are emitted with correct phase and story info

#### Scenario: Story transition events
- **WHEN** a story transitions to the next story
- **THEN** a story_changed event is emitted with the new story ID

### Requirement: TEA phases integration
The system SHALL execute TEA (Test Engineering Architect) phases when TEA is enabled in config.

#### Scenario: TEA phases included in story sequence
- **WHEN** TEA is enabled in config
- **THEN** ATDD phase executes as part of the story sequence and TEA framework/CI phases execute during epic setup

#### Scenario: TEA phases skipped when disabled
- **WHEN** TEA is not enabled in config (default)
- **THEN** no TEA-related phases (ATDD, TEA_FRAMEWORK, TEA_CI, etc.) are executed
