## Context

The bmad-assist project uses a phased development workflow (17 phases total) managed by `runner.py`. Each phase produces file changes — code, documentation, validation reports, test artifacts, etc. The git auto-commit system (`src/bmad_assist/git/committer.py`) currently:

- Only commits after 4 of 17 phases (CREATE_STORY, DEV_STORY, CODE_REVIEW_SYNTHESIS, RETROSPECTIVE)
- Uses hardcoded commit messages per phase type (e.g., "implement story" for DEV_STORY)
- Excludes `_bmad-output/` from commits, losing generated artifacts like validation reports and QA results
- Is gated behind `BMAD_GIT_COMMIT=1` environment variable (unchanged by this design)

Key files:
- `src/bmad_assist/git/committer.py` — commit logic, phase filtering, message generation
- `src/bmad_assist/core/loop/runner.py` — calls `auto_commit_phase()` after each phase
- `src/bmad_assist/core/state.py` — defines `Phase` enum (17 values)

## Goals / Non-Goals

**Goals:**
- Every phase that produces file changes SHALL trigger an auto-commit
- Commit messages SHALL be generated dynamically based on actual changed files
- `_bmad-output/` contents SHALL be included in commits
- Conventional commit format (`<type>(<scope>): <description>`) SHALL be preserved
- Existing safety guards (story file deletion protection, pre-commit fixes) SHALL remain

**Non-Goals:**
- Changing the `BMAD_GIT_COMMIT=1` activation mechanism
- Modifying branch management (`git/branch.py`)
- Adding git push automation
- Changing the pre-commit fix flow (ESLint/TypeScript auto-fix)
- Supporting interactive or manual commit message editing

## Decisions

### D1: Remove COMMIT_PHASES whitelist — commit on every phase

**Decision**: Remove the `COMMIT_PHASES` frozenset and `should_commit_phase()` gate. Instead, `auto_commit_phase()` will attempt to commit after every phase, but gracefully skip if there are no changed files.

**Rationale**: The original whitelist existed because validation phases were considered "outputs, not code changes." But commit history should reflect all work done, including validation and QA. Phases with no file changes naturally produce no commit (the `get_modified_files()` empty check handles this).

**Alternative considered**: Adding all phases to the whitelist — rejected because maintaining a whitelist creates ongoing maintenance burden as new phases are added.

### D2: Dynamic commit message from git diff analysis

**Decision**: Replace the hardcoded `_generate_conventional_message()` with a function that:
1. Groups changed files by directory and extension
2. Detects the type of change (new files, modifications, deletions)
3. Produces a human-readable summary of what was done

**Message format**:
```
<type>(<scope>): <phase_name> — <dynamic_summary>

Files: <count> changed
- <dir/>: +N added, ~M modified, -D deleted
```

**Commit type mapping**: Expand `PHASE_COMMIT_TYPES` to cover all phases. New mappings:
- Validation/review phases → `test`
- ATDD/TEA phases → `test`
- QA phases → `ci`
- Other → `chore`

**Scope**: Keep story-based scope (`story-X.Y`) for story-level phases, epic-based (`epic-X`) for epic-level phases.

**Alternative considered**: Using LLM to generate commit messages — rejected because it adds latency, cost, and non-determinism. A rule-based approach from file paths is fast, free, and reproducible.

### D3: Include `_bmad-output/` by removing it from exclude list

**Decision**: Remove `"_bmad-output/"` from the `exclude_prefixes` tuple. Keep the other three exclusions (`.bmad-assist/prompts/`, `.bmad-assist/cache/`, `.bmad-assist/debug/`) as these are truly ephemeral.

**Rationale**: `_bmad-output/` contains validation reports, code reviews, QA results — these are valuable artifacts that should be tracked. The other excluded directories contain transient prompt/cache files that would just add noise.

### D4: Summarize changes by directory grouping

**Decision**: Group modified files by their top-level directory (e.g., `src/`, `docs/`, `tests/`, `_bmad-output/`) and generate a summary like:
- "add validation report, modify 3 source files"
- "implement 5 components in src/app/, add test plan"

**Approach**: Categorize files by extension and path patterns:
- `.md` in `_bmad-output/` or `docs/` → "report/documentation"
- `.ts`/`.tsx`/`.js`/`.jsx`/`.py` → "source code"
- `test*` or `spec*` → "test files"
- Config files → "configuration"

## Risks / Trade-offs

- **[More frequent commits]** → Every phase now commits, which could produce many small commits for a single story. Mitigation: phases with no file changes are still skipped; the commit history accurately reflects what each phase did.
- **[Larger commits with `_bmad-output/`]** → Including output artifacts increases commit sizes. Mitigation: these are typically markdown files, which are small and diff well. Users can `.gitignore` `_bmad-output/` if they don't want it.
- **[Dynamic messages may be less readable than curated ones]** → Automatically generated summaries may lack the polish of handcrafted messages. Mitigation: Use clear categorization rules and keep summaries concise (< 72 chars for subject line).
- **[Backward compatibility]** → Users accustomed to specific commit patterns may be surprised. Mitigation: behavior is already gated behind opt-in `BMAD_GIT_COMMIT=1`; the format remains Conventional Commits.
