## ADDED Requirements

### Requirement: TestReviewHandler produces condensed summary file
The `TestReviewHandler` SHALL produce a condensed summary file in addition to the full review report after each successful test-review execution. The summary file SHALL be named `test-review-summary-{story_id}-{timestamp}.md` and saved in the same directory as the full report (`{output_folder}/test-reviews/`).

#### Scenario: Successful test review produces both files
- **WHEN** `TestReviewHandler.execute()` completes successfully with a quality score
- **THEN** two files are saved: the full report (`test-review-{story_id}-{timestamp}.md`) and a condensed summary (`test-review-summary-{story_id}-{timestamp}.md`) in the `test-reviews/` directory

#### Scenario: Summary content structure
- **WHEN** the condensed summary is generated from a test-review output containing quality score 68, grade C, and 2 critical issues at `auth-login.spec.ts:45` and `auth-login.spec.ts:23`
- **THEN** the summary SHALL contain: a header with score and grade, a numbered list of critical issues with file:line locations and one-line descriptions, and a one-line recommendation (Approve/Request Changes/Block). Total length SHALL NOT exceed 30 lines.

#### Scenario: Summary extraction fallback
- **WHEN** the LLM output does not contain recognizable section headers for extraction
- **THEN** the handler SHALL fall back to including the first 30 lines of the full output as the summary content

### Requirement: TestReviewResolver supports condensed mode
The `TestReviewResolver` SHALL accept a `condensed` parameter. When `condensed=True`, the resolver SHALL prefer `test-review-summary-*.md` files over full report files. When no summary file exists, it SHALL fall back to the full report with standard token truncation.

#### Scenario: Condensed mode loads summary file
- **WHEN** `TestReviewResolver.resolve()` is called with `condensed=True` and a summary file `test-review-summary-{story}.md` exists
- **THEN** the resolver SHALL return the summary file content

#### Scenario: Condensed mode falls back to full report
- **WHEN** `TestReviewResolver.resolve()` is called with `condensed=True` but no summary file exists
- **THEN** the resolver SHALL load the full report file with token truncation applied

#### Scenario: Non-condensed mode loads full report
- **WHEN** `TestReviewResolver.resolve()` is called with `condensed=False` (default)
- **THEN** the resolver SHALL load the full report file as it does today

### Requirement: code_review TEA context includes test-review summary
The default TEA context configuration SHALL include `test-review` in the `code_review` workflow's include list with `condensed: true`. This ensures the condensed summary is injected into code review prompts.

#### Scenario: code_review prompt includes test quality findings
- **WHEN** the `code_review` workflow is compiled and a test-review summary artifact exists for the current story
- **THEN** the compiled prompt SHALL contain the condensed test quality findings as context

#### Scenario: code_review prompt works without test-review artifact
- **WHEN** the `code_review` workflow is compiled but no test-review artifact exists (e.g., test_review was skipped)
- **THEN** the compiled prompt SHALL proceed without test quality context (no error)
