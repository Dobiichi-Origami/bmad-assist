## ADDED Requirements

### Requirement: All phases trigger auto-commit
The system SHALL attempt a git auto-commit after every successful phase execution, regardless of phase type. The `COMMIT_PHASES` whitelist SHALL be removed.

#### Scenario: Validation phase produces a commit
- **WHEN** the VALIDATE_STORY phase completes successfully and produces file changes
- **THEN** the system SHALL create a git commit containing those changes

#### Scenario: Phase with no file changes skips commit
- **WHEN** any phase completes successfully but produces no file changes
- **THEN** the system SHALL skip the commit and log a debug message

#### Scenario: New phases auto-commit without code changes
- **WHEN** a new Phase enum value is added to the codebase in the future
- **THEN** it SHALL automatically participate in auto-commit without requiring any update to commit configuration

### Requirement: Expanded commit type mapping
The system SHALL map every Phase to a conventional commit type. The mapping SHALL be:

- CREATE_STORY → `docs`
- DEV_STORY → `feat`
- CODE_REVIEW_SYNTHESIS → `refactor`
- RETROSPECTIVE → `chore`
- VALIDATE_STORY, VALIDATE_STORY_SYNTHESIS → `test`
- ATDD, TEST_REVIEW, TRACE → `test`
- TEA_FRAMEWORK, TEA_CI, TEA_TEST_DESIGN, TEA_AUTOMATE, TEA_NFR_ASSESS → `test`
- CODE_REVIEW → `test`
- QA_PLAN_GENERATE, QA_PLAN_EXECUTE, QA_REMEDIATE → `ci`

For any Phase not explicitly mapped, the system SHALL default to `chore`.

#### Scenario: Validation phase uses test commit type
- **WHEN** VALIDATE_STORY phase triggers a commit
- **THEN** the commit type SHALL be `test`

#### Scenario: QA phase uses ci commit type
- **WHEN** QA_PLAN_EXECUTE phase triggers a commit
- **THEN** the commit type SHALL be `ci`

#### Scenario: Unknown phase defaults to chore
- **WHEN** a phase not in the mapping triggers a commit
- **THEN** the commit type SHALL be `chore`

### Requirement: Include _bmad-output in commits
The system SHALL remove `_bmad-output/` from the `exclude_prefixes` list so that generated artifacts (validation reports, code reviews, QA results) are tracked in version control.

#### Scenario: Validation report is committed
- **WHEN** a validation phase generates a report in `_bmad-output/`
- **THEN** that report file SHALL be included in the git commit

#### Scenario: Ephemeral directories remain excluded
- **WHEN** files are modified in `.bmad-assist/prompts/`, `.bmad-assist/cache/`, or `.bmad-assist/debug/`
- **THEN** those files SHALL NOT be included in the git commit

### Requirement: Safety guards preserved
All existing safety mechanisms SHALL remain active: story file deletion protection SHALL abort the commit if story files are detected as deleted; pre-commit ESLint/TypeScript auto-fix SHALL still run before committing.

#### Scenario: Story file deletion still aborts commit
- **WHEN** a phase produces changes that include a deleted story file
- **THEN** the system SHALL abort the commit and log a CRITICAL error

#### Scenario: Pre-commit fix still runs
- **WHEN** a phase triggers a commit with staged changes
- **THEN** the system SHALL run `_run_precommit_fix()` before creating the commit
