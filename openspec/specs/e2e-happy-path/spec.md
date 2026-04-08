## ADDED Requirements

### Requirement: Single story complete flow
The system SHALL verify that a single epic with a single story executes all phases in the correct order from CREATE_STORY through RETROSPECTIVE.

#### Scenario: All phases succeed for one story
- **WHEN** run_mock_loop is executed with 1 epic containing 1 story and all phases return success
- **THEN** the loop returns COMPLETED, the story is in completed_stories, the epic is in completed_epics, and phases executed in order: CREATE_STORY → VALIDATE_STORY → VALIDATE_STORY_SYNTHESIS → DEV_STORY → TEST_REVIEW → CODE_REVIEW → CODE_REVIEW_SYNTHESIS → RETROSPECTIVE

#### Scenario: State is persisted after each phase
- **WHEN** a single story flow completes
- **THEN** the state.yaml file exists and reflects the final completed state

### Requirement: Multi-story flow within single epic
The system SHALL verify correct story-to-story transitions within a single epic.

#### Scenario: Two stories execute sequentially
- **WHEN** run_mock_loop is executed with 1 epic containing stories ["1.1", "1.2"] and all phases succeed
- **THEN** all phases execute for story 1.1, then all phases execute for story 1.2, then RETROSPECTIVE runs once, and both stories are in completed_stories

#### Scenario: Three stories with correct phase sequences
- **WHEN** run_mock_loop is executed with 1 epic containing stories ["1.1", "1.2", "1.3"]
- **THEN** each story goes through the full phase sequence, stories complete in order, and the epic is marked complete after the last story

#### Scenario: Completed stories are skipped on resume
- **WHEN** run_mock_loop is executed with initial state having story "1.1" already in completed_stories
- **THEN** the loop skips story 1.1 and begins execution from story 1.2

### Requirement: Multi-epic flow
The system SHALL verify correct epic-to-epic transitions.

#### Scenario: Two epics execute sequentially
- **WHEN** run_mock_loop is executed with epic_list=[1, 2], epic 1 has ["1.1"] and epic 2 has ["2.1"]
- **THEN** epic 1's story and retrospective complete first, then epic 2's story and retrospective complete, and both epics are in completed_epics

#### Scenario: Completed epics are skipped
- **WHEN** run_mock_loop is executed with initial state having epic 1 in completed_epics
- **THEN** the loop skips epic 1 entirely and begins with epic 2

#### Scenario: Epic with all stories completed is skipped
- **WHEN** run_mock_loop is executed where epic 1's stories are all in completed_stories
- **THEN** epic 1 is skipped and execution proceeds to epic 2

### Requirement: Phase sequence correctness
The system SHALL verify that the default phase sequence follows the configured loop order.

#### Scenario: Default loop config phase order
- **WHEN** a story is executed with default loop configuration
- **THEN** phases execute in the order defined by LoopConfig.story_sequence, which is: CREATE_STORY, VALIDATE_STORY, VALIDATE_STORY_SYNTHESIS, DEV_STORY, TEST_REVIEW, CODE_REVIEW, CODE_REVIEW_SYNTHESIS

#### Scenario: Retrospective runs once per epic after last story
- **WHEN** an epic with multiple stories completes
- **THEN** RETROSPECTIVE phase executes exactly once, after the last story's CODE_REVIEW_SYNTHESIS

### Requirement: Loop exit reason correctness
The system SHALL return the correct LoopExitReason for different completion scenarios.

#### Scenario: All epics complete successfully
- **WHEN** all epics and stories complete with success
- **THEN** run_loop returns LoopExitReason.COMPLETED

#### Scenario: Single epic completes
- **WHEN** a single epic run completes all stories
- **THEN** run_loop returns LoopExitReason.COMPLETED
