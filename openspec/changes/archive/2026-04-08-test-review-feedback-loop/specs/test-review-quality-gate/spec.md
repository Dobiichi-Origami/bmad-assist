## ADDED Requirements

### Requirement: test_review phase repositioned after dev_story
The `test_review` phase SHALL be positioned after `dev_story` and before `code_review` in both `TEA_FULL_LOOP_CONFIG` and the `bmad-assist.yaml.example` story phase list. The `validate_phase_ordering()` validator SHALL warn when `test_review` appears after `code_review_synthesis` and SHALL warn when `test_review` appears before `dev_story`.

#### Scenario: TEA_FULL_LOOP_CONFIG story order
- **WHEN** the `TEA_FULL_LOOP_CONFIG` is loaded
- **THEN** `loop.story` SHALL contain `test_review` at a position after `dev_story` and before `code_review`

#### Scenario: Phase ordering validation warns on post-synthesis position
- **WHEN** a user configures `loop.story` with `test_review` after `code_review_synthesis`
- **THEN** `validate_phase_ordering()` SHALL log a warning indicating test_review should run before code_review_synthesis

#### Scenario: Phase ordering validation warns on pre-dev_story position
- **WHEN** a user configures `loop.story` with `test_review` before `dev_story`
- **THEN** `validate_phase_ordering()` SHALL log a warning indicating test_review should run after dev_story

### Requirement: quality_score persisted to State
The `State` model SHALL include a `test_review_quality_score` field of type `int | None` with default `None`. The `TestReviewHandler` SHALL write the extracted quality score to `state.test_review_quality_score` after successful test-review execution.

#### Scenario: Score written to state on successful review
- **WHEN** `TestReviewHandler.execute()` completes successfully and extracts quality_score=78
- **THEN** `state.test_review_quality_score` SHALL be set to 78

#### Scenario: Score remains None when review is skipped
- **WHEN** `TestReviewHandler.execute()` is skipped (mode=off or auto condition not met)
- **THEN** `state.test_review_quality_score` SHALL remain None

#### Scenario: Score remains None when extraction fails
- **WHEN** `TestReviewHandler.execute()` completes but quality score extraction returns None
- **THEN** `state.test_review_quality_score` SHALL remain None

### Requirement: Configurable quality thresholds
The `TestarchConfig` model SHALL include `test_review_quality_threshold` (int, default 70) and `test_review_block_threshold` (int, default 50) configuration fields. Both fields SHALL be validated to ensure `block_threshold <= quality_threshold` and both are in range 0-100.

#### Scenario: Default threshold values
- **WHEN** `TestarchConfig` is loaded without explicit threshold configuration
- **THEN** `test_review_quality_threshold` SHALL be 70 and `test_review_block_threshold` SHALL be 50

#### Scenario: Custom threshold values from yaml
- **WHEN** `bmad-assist.yaml` contains `test_review_quality_threshold: 80` and `test_review_block_threshold: 60`
- **THEN** `TestarchConfig` SHALL load with those values

#### Scenario: Invalid threshold relationship rejected
- **WHEN** `bmad-assist.yaml` contains `test_review_quality_threshold: 50` and `test_review_block_threshold: 70`
- **THEN** config validation SHALL raise an error indicating block_threshold must be <= quality_threshold

### Requirement: Synthesis prompt receives quality gate signals
The `code_review_synthesis` compiler SHALL inject quality gate directives into the synthesis prompt based on `state.test_review_quality_score` and configured thresholds.

#### Scenario: Score below quality_threshold injects soft signal
- **WHEN** `state.test_review_quality_score` is 65 and `test_review_quality_threshold` is 70
- **THEN** the synthesis prompt SHALL include a directive indicating test quality is below threshold and suggesting rework should consider test improvements

#### Scenario: Score below block_threshold injects hard signal
- **WHEN** `state.test_review_quality_score` is 42 and `test_review_block_threshold` is 50
- **THEN** the synthesis prompt SHALL include a strong directive indicating critical test quality issues that MUST be addressed in rework

#### Scenario: Score above quality_threshold injects no signal
- **WHEN** `state.test_review_quality_score` is 85 and `test_review_quality_threshold` is 70
- **THEN** the synthesis prompt SHALL NOT include any test quality gate directives

#### Scenario: Score is None (review skipped) injects no signal
- **WHEN** `state.test_review_quality_score` is None
- **THEN** the synthesis prompt SHALL NOT include any test quality gate directives
