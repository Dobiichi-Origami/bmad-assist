## MODIFIED Requirements

### Requirement: ExecutionRecord data structure
The system SHALL define an `ExecutionRecord` dataclass with fields: `phase: str`, `mission: str`, `llm_output: str`, `self_audit: str | None`, `success: bool`, `duration_ms: int`, `error: str | None`, `phase_outputs: dict[str, Any]`, and `files_modified: list[str]`. The `files_diff` field SHALL NOT exist.

#### Scenario: ExecutionRecord construction without files_diff
- **WHEN** an ExecutionRecord is constructed with phase, mission, llm_output, self_audit, success, duration_ms, error, phase_outputs, and files_modified
- **THEN** the record SHALL NOT have a `files_diff` attribute

#### Scenario: files_modified covers all change types
- **WHEN** `build_execution_record` is called with a `project_path` and `success=True`
- **AND** the project has tracked modified files, staged new files, and untracked new files
- **THEN** `files_modified` SHALL contain all three types of files

#### Scenario: files_modified omits untracked files in .gitignore
- **WHEN** `build_execution_record` is called with a `project_path`
- **AND** the project has untracked files that match .gitignore patterns
- **THEN** those files SHALL NOT appear in `files_modified`

### Requirement: File change capture via git status
The system SHALL use `git status --porcelain` to capture all changed files, covering tracked modifications, staged changes, and untracked new files. The XY status prefix SHALL be stripped; only the file path SHALL be stored.

#### Scenario: Only tracked modifications
- **WHEN** the project has modified tracked files and no staged or untracked files
- **THEN** `files_modified` SHALL contain only those modified file paths

#### Scenario: New untracked files
- **WHEN** the project has untracked new files not in .gitignore
- **THEN** `files_modified` SHALL contain those file paths

#### Scenario: Staged new files
- **WHEN** the project has newly created files that have been `git add`-ed
- **THEN** `files_modified` SHALL contain those file paths

#### Scenario: Mixed changes
- **WHEN** the project has tracked modifications, staged files, and untracked files simultaneously
- **THEN** `files_modified` SHALL contain all of them without duplicates

## REMOVED Requirements

### Requirement: Full git diff capture
**Reason**: Complete diff output is unnecessary for Twin reflect; file names suffice for cross-validation. Removes prompt bloat and truncation complexity.
**Migration**: Twin reflect no longer receives a `# Git Diff (prepared)` section in its prompt. The `files_modified` list now covers all change types as the sole source of file change information.
