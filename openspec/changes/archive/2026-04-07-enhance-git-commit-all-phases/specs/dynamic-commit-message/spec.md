## ADDED Requirements

### Requirement: Dynamic commit message from changed files
The system SHALL generate commit messages dynamically by analyzing the actual files changed during a phase, instead of using hardcoded per-phase descriptions.

#### Scenario: Commit message reflects actual file changes
- **WHEN** the DEV_STORY phase modifies 3 files in `src/app/` and 1 file in `src/lib/`
- **THEN** the commit message subject SHALL include a summary like "implement changes in src/app/, src/lib/"

#### Scenario: Commit message for documentation changes
- **WHEN** the CREATE_STORY phase creates a story file in `docs/sprint-artifacts/`
- **THEN** the commit message subject SHALL describe it as a documentation change

#### Scenario: Commit message for output artifacts
- **WHEN** a validation phase generates reports in `_bmad-output/`
- **THEN** the commit message subject SHALL mention the generated reports/artifacts

### Requirement: Conventional commit format preserved
The dynamic commit message SHALL follow the Conventional Commits format: `<type>(<scope>): <description>`.

#### Scenario: Format structure
- **WHEN** any phase triggers a commit
- **THEN** the message SHALL match the pattern `<type>(<scope>): <dynamic_description>`

#### Scenario: Scope uses story ID for story phases
- **WHEN** a story-level phase (e.g., DEV_STORY for story 1.2) triggers a commit
- **THEN** the scope SHALL be `story-1.2`

#### Scenario: Scope uses epic ID for epic phases
- **WHEN** the RETROSPECTIVE phase for epic 22 triggers a commit
- **THEN** the scope SHALL be `epic-22`

### Requirement: Subject line length limit
The commit message subject line (first line) SHALL NOT exceed 72 characters. If the dynamic summary would exceed this limit, it SHALL be truncated with an ellipsis.

#### Scenario: Long summary is truncated
- **WHEN** the dynamic summary would produce a subject line longer than 72 characters
- **THEN** the subject SHALL be truncated to 72 characters ending with "..."

#### Scenario: Short summary is not truncated
- **WHEN** the dynamic summary fits within 72 characters
- **THEN** the subject SHALL be used as-is without truncation

### Requirement: Commit body with file details
When more than 3 files are changed, the commit message SHALL include a body section listing the file changes grouped by directory.

#### Scenario: Many files include body details
- **WHEN** a phase modifies 8 files across 3 directories
- **THEN** the commit body SHALL list file counts per directory (e.g., "src/: 5 files, docs/: 2 files, tests/: 1 file")

#### Scenario: Few files omit body
- **WHEN** a phase modifies 2 files
- **THEN** the commit message SHALL only contain the subject line with no body

### Requirement: File categorization for summaries
The system SHALL categorize changed files by type to produce readable summaries:
- `.ts`, `.tsx`, `.js`, `.jsx`, `.py` → source code
- Files in `_bmad-output/` or `docs/` with `.md` extension → reports/documentation
- Files matching `test*` or `spec*` patterns → test files
- Other files → general/configuration

#### Scenario: Mixed file types produce combined summary
- **WHEN** a phase modifies 2 TypeScript files and 1 markdown report
- **THEN** the summary SHALL mention both categories (e.g., "update source code, add report")

#### Scenario: Single file type produces focused summary
- **WHEN** a phase only modifies files in `_bmad-output/`
- **THEN** the summary SHALL describe them as reports/artifacts only
