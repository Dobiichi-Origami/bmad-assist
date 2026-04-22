# Execution Record Spec

Capability: execution-record
System: Digital Twin (bmad-assist)

---

## ADDED Requirements

### Requirement: ExecutionRecord dataclass

The system SHALL define an `ExecutionRecord` dataclass that captures the full outcome of a single phase execution for consumption by the Digital Twin reflect step.

The dataclass MUST contain the following fields:

| Field | Type | Description |
|---|---|---|
| `phase` | `str` | The atomic phase name that was executed |
| `mission` | `str` | The mission/prompt that was sent to the LLM |
| `llm_output` | `str` | The raw LLM response text (NOT truncated by default) |
| `self_audit` | `Optional[str]` | Parsed Self-Audit section from llm_output, or None |
| `success` | `bool` | Whether the phase completed without error |
| `duration_ms` | `int` | Wall-clock execution time in milliseconds |
| `error` | `Optional[str]` | Error message if the phase failed, otherwise None |
| `phase_outputs` | `Dict[str, Any]` | Structured outputs produced by the phase (e.g., test results, review findings) |
| `files_modified` | `List[str]` | List of file paths changed during this phase (from `git diff --name-only`) |
| `files_diff` | `str` | Full git diff output (not `--stat`) for Twin cross-validation |

The `ExecutionRecord` MUST NOT include an `experiences: str` field. Wiki and experience loading is handled separately by `build_reflect_prompt` and is not part of the execution record.

#### Scenario: Successful phase execution produces a complete record

WHEN a phase executes successfully for 3500ms, modifies `src/main.py` and `src/test_main.py`, and the LLM output contains a Self-Audit section
THEN `ExecutionRecord` is constructed with `success=True`, `duration_ms=3500`, `self_audit` containing the parsed Self-Audit text, `files_modified=["src/main.py", "src/test_main.py"]`, `files_diff` containing the full git diff, and `error=None`

#### Scenario: Failed phase execution produces a record with error

WHEN a phase raises an exception after 1200ms with message "API rate limit exceeded"
THEN `ExecutionRecord` is constructed with `success=False`, `duration_ms=1200`, `error="API rate limit exceeded"`, `llm_output=""`, `self_audit=None`, `files_modified=[]`, and `files_diff=""`

#### Scenario: ExecutionRecord has no experiences field

WHEN an ExecutionRecord is constructed for any phase
THEN the record MUST NOT contain an `experiences` field, and any code that attempts to access `record.experiences` SHALL raise an `AttributeError`

---

### Requirement: build_execution_record()

The system SHALL provide a `build_execution_record()` function that constructs an `ExecutionRecord` from the phase execution state, the LLM result, and the current git diff.

`build_execution_record()` MUST accept the following inputs:
- The phase name and mission string
- The raw LLM output string
- The execution result (success/failure, error, duration, phase_outputs)
- The git diff output (full diff and name-only list)

`build_execution_record()` SHALL call `format_self_audit()` to populate the `self_audit` field.

`build_execution_record()` SHALL populate `files_modified` from `git diff --name-only` output and `files_diff` from the full `git diff` output (not `--stat`).

`build_execution_record()` MUST NOT truncate `llm_output` by default. Truncation is handled separately by `prepare_llm_output` only when the output exceeds 120K tokens, using a head(1/4) + tail(3/4) strategy by position.

#### Scenario: Building a record from a successful execution

WHEN `build_execution_record()` is called with phase="code_review_synthesis", mission="Review the following code...", llm_output containing a Self-Audit section, success=True, duration_ms=4200, error=None, phase_outputs={"findings": 3}, files_modified=["src/api.py"], and files_diff containing the full git diff
THEN it SHALL return an `ExecutionRecord` with all fields populated, `self_audit` set to the parsed Self-Audit text, and `llm_output` equal to the unmodified raw LLM output

#### Scenario: Building a record with no Self-Audit in LLM output

WHEN `build_execution_record()` is called with llm_output that does not contain a Self-Audit section
THEN it SHALL return an `ExecutionRecord` with `self_audit=None`

#### Scenario: llm_output is not truncated by build_execution_record

WHEN `build_execution_record()` is called with an llm_output string of 150K tokens
THEN the `llm_output` field in the returned `ExecutionRecord` SHALL contain the full 150K-token string without any truncation; truncation is the responsibility of `prepare_llm_output` at a later stage

---

### Requirement: format_self_audit()

The system SHALL provide a `format_self_audit()` function that extracts and parses the Self-Audit section from the raw LLM output.

`format_self_audit()` MUST scan the LLM output for a Self-Audit section demarcated by a recognized heading pattern (e.g., "## Self-Audit" or equivalent markdown heading).

`format_self_audit()` SHALL return the full text of the Self-Audit section (from the heading to the next同等 or higher-level heading, or to the end of the output) as a string.

If no Self-Audit section is found in the LLM output, `format_self_audit()` MUST return `None`.

#### Scenario: LLM output contains a Self-Audit section

WHEN `format_self_audit()` is called with llm_output that includes "## Self-Audit\n- All acceptance criteria met\n- No regressions detected"
THEN it SHALL return "- All acceptance criteria met\n- No regressions detected"

#### Scenario: LLM output has no Self-Audit section

WHEN `format_self_audit()` is called with llm_output that contains "## Summary\nThe code changes are complete." but no Self-Audit heading
THEN it SHALL return `None`

#### Scenario: Self-Audit section extends to end of output

WHEN `format_self_audit()` is called with llm_output ending with "## Self-Audit\n- Item 1\n- Item 2" and no subsequent heading
THEN it SHALL return "- Item 1\n- Item 2"

---

### Requirement: qa_remediate handler collects all_llm_outputs

The `qa_remediate` phase handler SHALL collect LLM outputs from all preceding phases in the current epic into an `all_llm_outputs` list and make it available to the remediation prompt.

The `all_llm_outputs` list MUST include the raw `llm_output` from every `ExecutionRecord` of phases executed within the same epic prior to `qa_remediate`.

The `all_llm_outputs` list SHALL be ordered by phase execution sequence (earliest first).

#### Scenario: qa_remediate with multiple preceding phases

WHEN `qa_remediate` executes after `validate_story` (llm_output="story validated") and `code_review_synthesis` (llm_output="3 findings") have completed in the same epic
THEN `all_llm_outputs` SHALL be `["story validated", "3 findings"]` in that order

#### Scenario: qa_remediate as first phase in epic

WHEN `qa_remediate` executes and no prior phases have been recorded in the current epic
THEN `all_llm_outputs` SHALL be an empty list `[]`

---

### Requirement: PhaseResult.ok() includes "response" field

`PhaseResult.ok()` SHALL accept and propagate a `response` keyword argument that carries the primary LLM response content.

The `response` field in the returned `PhaseResult` MUST be set to the value of the `response` argument passed to `ok()`.

This `response` field is used by downstream consumers (including `build_execution_record`) to access the structured LLM output separately from metadata.

#### Scenario: PhaseResult.ok() with response argument

WHEN `PhaseResult.ok(response="All tests pass", duration_ms=2000)` is called
THEN the returned `PhaseResult` SHALL have `response="All tests pass"` and `duration_ms=2000`

#### Scenario: PhaseResult.ok() without response argument

WHEN `PhaseResult.ok(duration_ms=1500)` is called without a `response` argument
THEN the returned `PhaseResult` SHALL have `response=None` or an empty default value

---

### Requirement: files_diff uses full git diff

The `files_diff` field in `ExecutionRecord` MUST contain the output of `git diff` (full diff), not `git diff --stat`.

This full diff is required so that the Digital Twin can cross-validate file changes during reflect, examining the actual content of additions and deletions rather than just summary statistics.

The system SHALL capture `files_diff` after the phase execution completes and before any subsequent phase begins, to ensure the diff accurately reflects only the changes made during that phase.

#### Scenario: files_diff contains full diff content

WHEN a phase modifies `src/api.py` by adding 5 lines and removing 2 lines
THEN `ExecutionRecord.files_diff` SHALL contain the full unified diff including line-by-line additions (prefixed with `+`) and deletions (prefixed with `-`), not just "src/api.py | 7 +-"

#### Scenario: files_diff is scoped to the phase

WHEN phase A modifies `src/a.py` and then phase B modifies `src/b.py`
THEN the `files_diff` for phase B SHALL NOT include changes to `src/a.py`; only changes introduced by phase B
