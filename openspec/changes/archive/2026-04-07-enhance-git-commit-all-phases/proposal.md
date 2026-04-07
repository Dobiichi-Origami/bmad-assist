## Why

Currently, only 4 out of 17 phases trigger git auto-commits (CREATE_STORY, DEV_STORY, CODE_REVIEW_SYNTHESIS, RETROSPECTIVE). This means validation reports, test reviews, QA results, and other phase outputs are silently lost between commits. Additionally, the commit messages are hardcoded per phase (e.g., "implement story") rather than reflecting what actually changed. Finally, `_bmad-output/` is explicitly excluded from commits, making it impossible to track generated artifacts in version control.

Teams need full phase-level commit traceability to understand what each phase produced, debug pipeline issues, and maintain a complete audit trail of the development workflow.

## What Changes

- **All phases now trigger commits**: Remove the `COMMIT_PHASES` whitelist; every phase that produces file changes will auto-commit after successful execution
- **Dynamic commit messages based on changed files**: Instead of hardcoded descriptions like "implement story", analyze the actual `git diff --stat` output to generate descriptive commit messages summarizing what files were added/modified/deleted and in which directories
- **Include `_bmad-output/` in commits**: Remove `_bmad-output/` from the `exclude_prefixes` list so that generated reports (validation, code review, QA, etc.) are committed alongside code changes
- **Retain exclusions for ephemeral directories**: Keep `.bmad-assist/prompts/`, `.bmad-assist/cache/`, and `.bmad-assist/debug/` excluded since these are transient build artifacts

## Capabilities

### New Capabilities
- `dynamic-commit-message`: Generate commit messages dynamically based on the actual files changed in each phase, using git diff analysis to produce meaningful descriptions
- `commit-all-phases`: Extend auto-commit to all workflow phases, not just the current hardcoded subset

### Modified Capabilities

(no existing specs to modify)

## Impact

- **`src/bmad_assist/git/committer.py`**: Core changes — remove `COMMIT_PHASES` whitelist, update `exclude_prefixes`, rewrite `generate_commit_message` / `_generate_conventional_message` to analyze changed files dynamically
- **`src/bmad_assist/git/committer.py:should_commit_phase()`**: Simplify or remove — all phases should commit
- **`tests/`**: Update existing committer tests, add new tests for dynamic message generation and `_bmad-output/` inclusion
- **Backward compatibility**: The `BMAD_GIT_COMMIT=1` env var gate remains — no change in activation. Users who enable git commits will see more frequent, more descriptive commits
