## ADDED Requirements

### Requirement: TEST_REVIEW maps to in-progress status
The `PHASE_TO_STATUS` mapping in `sprint/sync.py` SHALL map `Phase.TEST_REVIEW` to `"in-progress"` (not `"review"`), because test_review now runs before code_review in the story phase sequence.

#### Scenario: Sprint-status after test_review completes
- **WHEN** the `test_review` phase completes and sprint sync is triggered
- **THEN** the story's status in `sprint-status.yaml` SHALL be `"in-progress"`

#### Scenario: Sprint-status transitions through full TEA story lifecycle
- **WHEN** a story progresses through the TEA loop phases: `dev_story → test_review → code_review → code_review_synthesis`
- **THEN** the sprint-status transitions SHALL be: `in-progress → in-progress → review → review`

#### Scenario: code_review executes after test_review
- **WHEN** `test_review` completes successfully with sprint-status set to `"in-progress"`
- **THEN** `code_review` SHALL execute normally without being skipped
