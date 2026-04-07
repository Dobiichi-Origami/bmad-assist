## 1. Remove phase whitelist and expand commit type mapping

- [x] 1.1 Remove `COMMIT_PHASES` frozenset and `should_commit_phase()` function from `src/bmad_assist/git/committer.py`
- [x] 1.2 Update `auto_commit_phase()` to remove the `should_commit_phase()` gate — all phases proceed to the modified-files check
- [x] 1.3 Expand `PHASE_COMMIT_TYPES` dict to map all 17 Phase values (VALIDATE_STORY→test, ATDD→test, CODE_REVIEW→test, QA phases→ci, etc.), with `chore` as default fallback

## 2. Include _bmad-output in commits

- [x] 2.1 Remove `"_bmad-output/"` from the `exclude_prefixes` tuple in `get_modified_files()`
- [x] 2.2 Verify that `.bmad-assist/prompts/`, `.bmad-assist/cache/`, `.bmad-assist/debug/` remain excluded

## 3. Implement dynamic commit message generation

- [x] 3.1 Create a `_categorize_files(modified_files: list[str])` function that groups files by type: source code, reports/docs, test files, configuration
- [x] 3.2 Create a `_summarize_changes(modified_files: list[str])` function that produces a human-readable summary from categorized files (e.g., "update source code in src/app/, add validation report")
- [x] 3.3 Rewrite `_generate_conventional_message()` to use `_summarize_changes()` for the description instead of hardcoded strings
- [x] 3.4 Add subject line truncation to 72 characters with ellipsis when exceeded
- [x] 3.5 Update commit body generation: when >3 files changed, list file counts grouped by top-level directory

## 4. Update exports and public API

- [x] 4.1 Remove `should_commit_phase` from `src/bmad_assist/git/__init__.py` exports if it was exported
- [x] 4.2 Verify `auto_commit_phase` function signature is unchanged (no breaking changes to runner.py call site)

## 5. Tests

- [x] 5.1 Update existing tests for `should_commit_phase` — remove or replace with tests verifying all phases are accepted
- [x] 5.2 Add tests for `_categorize_files()` with mixed file types (source, docs, tests, config)
- [x] 5.3 Add tests for `_summarize_changes()` covering: single category, multiple categories, empty list
- [x] 5.4 Add tests for dynamic message generation: verify conventional commit format, scope correctness, truncation behavior
- [x] 5.5 Add test verifying `_bmad-output/` files are no longer excluded from `get_modified_files()`
- [x] 5.6 Add test verifying commit body includes directory grouping when >3 files changed
