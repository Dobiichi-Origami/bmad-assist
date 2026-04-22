## ADDED Requirements

### Requirement: TwinProviderConfig

The system SHALL define a `TwinProviderConfig` data class with the following fields:
- `provider`: string, default `"claude"`
- `model`: string, default `"opus"`
- `enabled`: boolean, default `True`
- `max_retries`: integer, default `2`
- `retry_exhausted_action`: literal `"halt"` or `"continue"`, default `"halt"`

`TwinProviderConfig` MUST NOT include a `reflect_budget_tokens` field. This was removed in v6.

`TwinProviderConfig` MUST NOT include any INDEX truncation configuration. This was removed in v6.

The system SHALL add a `twin` section to the existing providers configuration in `providers.py`, parsed from YAML under `providers.twin` alongside the existing `providers.master` section.

#### Scenario: Default TwinProviderConfig values

WHEN no twin section exists in the providers YAML configuration
THEN the system SHALL construct a TwinProviderConfig with all default values: provider="claude", model="opus", enabled=True, max_retries=2, retry_exhausted_action="halt"

#### Scenario: TwinProviderConfig parsed from YAML

WHEN the providers YAML contains a twin section with custom values
THEN the system SHALL parse those values into a TwinProviderConfig instance, making them available to the runner loop

#### Scenario: TwinProviderConfig rejects reflect_budget_tokens

WHEN a TwinProviderConfig is constructed with a reflect_budget_tokens field
THEN the system SHALL reject it as an invalid field, because reflect_budget_tokens was removed in v6

---

### Requirement: Twin Guide Before Phase Execution

Before each phase execution in the runner main loop, the system SHALL call `twin.guide()` to produce a compass string. The compass string provides experience-derived guidance for the upcoming phase.

If `TwinProviderConfig.enabled` is `False`, the system SHALL skip the guide call entirely and set `compass=None`.

The compass string SHALL be passed to `execute_phase()` via a `compass` parameter so that the compiled prompt can include it.

#### Scenario: Guide produces compass for phase

WHEN the runner is about to execute a phase and twin is enabled
THEN the system SHALL call twin.guide(phase, epic_id, story_id) and pass the returned compass string to execute_phase()

#### Scenario: Guide fails gracefully

WHEN twin.guide() raises an exception or returns an error
THEN the system SHALL set compass=None and proceed with phase execution normally. The phase MUST execute without a compass; guide is auxiliary, not critical.

#### Scenario: Twin disabled skips guide

WHEN TwinProviderConfig.enabled is False
THEN the system SHALL NOT call twin.guide() and SHALL set compass=None before phase execution

---

### Requirement: Twin Reflect After Phase Execution

After each phase execution in the runner main loop, when twin is enabled, the system SHALL:
1. Call `build_execution_record()` to assemble the ExecutionRecord from the current state, phase result, and project path
2. Call `twin.reflect()` with the ExecutionRecord
3. Call `apply_page_updates()` with `twin_result.page_updates` and the wiki directory, if page_updates is non-empty
4. Handle the decision from `twin_result.decision` (CONTINUE, RETRY, or HALT)

If `TwinProviderConfig.enabled` is `False`, the system SHALL skip reflect entirely and default to CONTINUE.

#### Scenario: Reflect returns CONTINUE

WHEN twin.reflect() returns decision="continue"
THEN the system SHALL apply any page_updates and proceed to the next phase in the loop

#### Scenario: Reflect returns HALT

WHEN twin.reflect() returns decision="halt"
THEN the system SHALL apply any page_updates and exit the loop with LoopExitReason.GUARDIAN_HALT

#### Scenario: Twin disabled skips reflect

WHEN TwinProviderConfig.enabled is False
THEN the system SHALL NOT call twin.reflect() or apply_page_updates(), and SHALL treat the phase result as CONTINUE

---

### Requirement: RETRY Logic with Git Stash

When `twin_result.decision` is `"retry"` and `state.retry_count < twin_config.max_retries`, the system SHALL:
1. Execute `git stash` to restore the working directory to the state before phase execution began
2. Format a correction compass from `twin_result.drift_assessment.correction`
3. Increment `state.retry_count`
4. Re-execute the phase with the correction compass

The correction compass SHALL be appended after the original compass, not replace it. The original compass context MUST be preserved, with the correction directive added as supplementary guidance.

The correction compass SHALL include a `retry="N"` marker indicating the retry attempt number.

When `twin_result.decision` is `"retry"` and `state.retry_count >= twin_config.max_retries`, the system SHALL log an error with the drift evidence, correction, and rationale, and exit the loop with `LoopExitReason.GUARDIAN_HALT`.

#### Scenario: RETRY within max_retries

WHEN twin.reflect() returns decision="retry" and retry_count is 0 (less than max_retries=2)
THEN the system SHALL git stash, format a correction compass, increment retry_count to 1, and re-execute the phase with the correction compass appended after the original compass

#### Scenario: RETRY exhausts max_retries

WHEN twin.reflect() returns decision="retry" and retry_count equals max_retries
THEN the system SHALL NOT re-execute the phase, SHALL log the drift evidence, correction, and rationale, and SHALL exit with GUARDIAN_HALT

#### Scenario: Correction compass appended not replaced

WHEN a RETRY occurs and the original compass was "Watch out for X"
THEN the system SHALL re-execute the phase with the compass set to "Watch out for X" followed by the correction compass content, preserving the original watch-outs and appending the correction directive

#### Scenario: Git stash before RETRY

WHEN a RETRY is triggered
THEN the system SHALL execute git stash BEFORE re-executing the phase, ensuring the working directory is restored to its state before the failed phase execution began

---

### Requirement: Reflect Failure Degradation

The system SHALL handle twin.reflect() failures with differentiated degradation based on whether the phase is a first execution or a retry:

- If guide() fails: set `compass=None` and proceed normally. Guide is auxiliary.
- If reflect() fails on a first execution (is_retry=False): default to `decision="continue"`. Do not block the main loop.
- If reflect() fails on a RETRY execution (is_retry=True): the action depends on `retry_exhausted_action`:
  - `"halt"` -> return `decision="halt"` (HALT the loop)
  - `"continue"` -> return `decision="continue"` (proceed to next phase)
- If YAML parsing from the reflect LLM output fails: retry the LLM call once. If it still fails, apply the is_retry + retry_exhausted_action logic above.

#### Scenario: Reflect fails on first execution

WHEN twin.reflect() raises an exception during a first-time (non-retry) phase execution
THEN the system SHALL default to decision="continue" and proceed to the next phase without blocking

#### Scenario: Reflect fails during RETRY with retry_exhausted_action=halt

WHEN twin.reflect() raises an exception during a RETRY execution and retry_exhausted_action is "halt"
THEN the system SHALL default to decision="halt" and exit the loop with GUARDIAN_HALT

#### Scenario: Reflect fails during RETRY with retry_exhausted_action=continue

WHEN twin.reflect() raises an exception during a RETRY execution and retry_exhausted_action is "continue"
THEN the system SHALL default to decision="continue" and proceed to the next phase

#### Scenario: YAML parse failure triggers single retry

WHEN the YAML output from twin.reflect() fails to parse
THEN the system SHALL retry the LLM call exactly once. If the retry also fails, the system SHALL apply the is_retry + retry_exhausted_action degradation logic

#### Scenario: Guide failure does not block execution

WHEN twin.guide() raises an exception
THEN the system SHALL set compass=None and proceed with phase execution normally

---

### Requirement: Source Epics Tracking in Frontmatter

The system SHALL track `source_epics` in the YAML frontmatter of wiki pages. `source_epics` is a list of epic IDs that contributed evidence to the page.

When `apply_page_updates()` processes a page update, the system SHALL append the current epic ID to the page's `source_epics` list if the epic ID is not already present.

`source_epics` tracking enables self-reinforcing error detection: if all evidence for a pattern comes from similar phase types or code regions (visible via source_epics), the pattern may not be a genuine cross-context finding.

#### Scenario: Source epics appended on page update

WHEN apply_page_updates() processes an update for page "pattern-async-session" and the current epic is "epic-15" and the page's source_epics is ["epic-12"]
THEN the system SHALL update source_epics to ["epic-12", "epic-15"]

#### Scenario: Source epics deduplicated

WHEN apply_page_updates() processes an update and the current epic ID already exists in the page's source_epics list
THEN the system SHALL NOT add a duplicate entry to source_epics

#### Scenario: Challenge mode triggered by source_epics count

WHEN len(source_epics) is divisible by 5 and the page sentiment is "negative"
THEN the reflect prompt SHALL include challenge mode instructions that question whether the negative pattern is a genuine project issue or an execution model blind spot
