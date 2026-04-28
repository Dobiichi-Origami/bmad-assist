## ADDED Requirements

### Requirement: Retry mode configuration
The system SHALL support a `retry_mode` field on `TwinProviderConfig` with values `"stash_retry"` (default), `"quick_correct"`, and `"auto"`. When `retry_mode="stash_retry"`, the runner SHALL follow the existing retry behavior: git stash + re-execute the phase from scratch. When `retry_mode="quick_correct"`, the runner SHALL re-invoke the phase with the correction compass appended but WITHOUT git stash, allowing the execution model to correct the existing output in-place. When `retry_mode="auto"`, the runner SHALL dynamically select between `stash_retry` and `quick_correct` based on the phase's `duration_ms` compared against `retry_mode_threshold_seconds`.

#### Scenario: Default retry mode is stash_retry
- **WHEN** a `TwinProviderConfig` is constructed without specifying `retry_mode`
- **THEN** the `retry_mode` field SHALL default to `"stash_retry"`, preserving current behavior

#### Scenario: Quick correct mode configured via YAML
- **WHEN** the providers YAML contains `providers.twin.retry_mode: quick_correct`
- **THEN** the system SHALL parse this into a `TwinProviderConfig` with `retry_mode="quick_correct"`

#### Scenario: Auto mode configured via YAML
- **WHEN** the providers YAML contains `providers.twin.retry_mode: auto`
- **THEN** the system SHALL parse this into a `TwinProviderConfig` with `retry_mode="auto"`

#### Scenario: Invalid retry mode value rejected
- **WHEN** a `TwinProviderConfig` is constructed with `retry_mode="unknown"`
- **THEN** the system SHALL reject it as an invalid value, because only `"stash_retry"`, `"quick_correct"`, and `"auto"` are permitted

### Requirement: Auto mode time-based selection
When `retry_mode="auto"` and Twin decides `retry`, the runner SHALL compare the phase's `duration_ms` (from `execute_phase()` result, measured via `time.perf_counter()` wall-clock elapsed time) against `retry_mode_threshold_seconds`. If `duration_ms / 1000 >= retry_mode_threshold_seconds`, the runner SHALL use `quick_correct` mode for this retry. Otherwise, the runner SHALL use `stash_retry` mode. The selection SHALL be logged at INFO level with the phase name, duration, threshold, and selected mode.

#### Scenario: Auto mode selects quick_correct for long-running phase
- **WHEN** `retry_mode="auto"` and `retry_mode_threshold_seconds=120` and the phase `duration_ms` is 180000 (3 minutes)
- **THEN** the runner SHALL use `quick_correct` mode because 180s >= 120s, and SHALL NOT call `stash_working_changes()`

#### Scenario: Auto mode selects stash_retry for short-running phase
- **WHEN** `retry_mode="auto"` and `retry_mode_threshold_seconds=120` and the phase `duration_ms` is 45000 (45 seconds)
- **THEN** the runner SHALL use `stash_retry` mode because 45s < 120s, and SHALL call `stash_working_changes()` before re-execution

#### Scenario: Auto mode logs selection decision
- **WHEN** `retry_mode="auto"` and Twin decides retry
- **THEN** the runner SHALL log at INFO level a message containing the phase name, duration in seconds, threshold in seconds, and the selected mode (e.g., "auto-selected quick_correct for phase dev_story (duration=180s >= threshold=120s)")

### Requirement: Retry mode threshold configuration
The system SHALL support a `retry_mode_threshold_seconds` field on `TwinProviderConfig` with type integer, default `120`. This field is only used when `retry_mode="auto"`. It defines the minimum phase execution duration (in seconds) above which `quick_correct` is selected and below which `stash_retry` is selected.

#### Scenario: Default threshold is 120 seconds
- **WHEN** a `TwinProviderConfig` is constructed without specifying `retry_mode_threshold_seconds`
- **THEN** the `retry_mode_threshold_seconds` field SHALL default to `120`

#### Scenario: Custom threshold configured via YAML
- **WHEN** the providers YAML contains `providers.twin.retry_mode_threshold_seconds: 300`
- **THEN** the system SHALL parse this into a `TwinProviderConfig` with `retry_mode_threshold_seconds=300`

#### Scenario: Threshold ignored in non-auto modes
- **WHEN** `retry_mode="stash_retry"` or `retry_mode="quick_correct"` and `retry_mode_threshold_seconds` is configured
- **THEN** the threshold SHALL have no effect on retry behavior — the explicit mode is used directly

### Requirement: Max quick corrections configuration
The system SHALL support a `max_quick_corrections` field on `TwinProviderConfig` with type integer, default `1`. This field controls the maximum number of quick correction cycles before the retry is considered exhausted. This field is independent of `max_retries` (which controls stash_retry cycles). When `max_quick_corrections` is exhausted, the system SHALL follow the `retry_exhausted_action` (halt or continue) — it SHALL NOT automatically escalate to stash_retry.

#### Scenario: Default max quick corrections is 1
- **WHEN** a `TwinProviderConfig` is constructed without specifying `max_quick_corrections`
- **THEN** the `max_quick_corrections` field SHALL default to `1`

#### Scenario: Max quick corrections configured via YAML
- **WHEN** the providers YAML contains `providers.twin.max_quick_corrections: 3`
- **THEN** the system SHALL parse this into a `TwinProviderConfig` with `max_quick_corrections=3`

#### Scenario: Quick corrections exhausted with halt action
- **WHEN** `retry_mode` resolves to `quick_correct` and the number of quick correction cycles reaches `max_quick_corrections` without a `continue` decision, and `retry_exhausted_action="halt"`
- **THEN** the runner SHALL return `LoopExitReason.GUARDIAN_HALT`

#### Scenario: Quick corrections exhausted with continue action
- **WHEN** `retry_mode` resolves to `quick_correct` and the number of quick correction cycles reaches `max_quick_corrections` without a `continue` decision, and `retry_exhausted_action="continue"`
- **THEN** the runner SHALL proceed to the next phase

### Requirement: Quick correct compass prefix
The system SHALL use different compass prefixes based on the resolved retry mode. In `stash_retry` mode, the correction compass SHALL use `[RETRY retry=N]` prefix (existing behavior). In `quick_correct` mode, the correction compass SHALL use `[QUICK-CORRECT n/N]` prefix where `n` is the current correction attempt and `N` is `max_quick_corrections`. This signals to the execution model that it should correct in-place rather than start over.

#### Scenario: Stash retry compass format
- **WHEN** the resolved retry mode is `stash_retry` and Twin decides retry on attempt 2
- **THEN** the correction compass SHALL be formatted as `[RETRY retry=2] <correction text>`

#### Scenario: Quick correct compass format
- **WHEN** the resolved retry mode is `quick_correct` and Twin decides retry on the first correction attempt with `max_quick_corrections=1`
- **THEN** the correction compass SHALL be formatted as `[QUICK-CORRECT 1/1] <correction text>`

### Requirement: Quick correct re-execution without git stash
When the resolved retry mode is `quick_correct` and Twin decides `retry`, the runner SHALL re-invoke `execute_phase(state, compass=full_compass)` without calling `stash_working_changes()`. The phase SHALL see its existing output in the working directory and can make targeted corrections. The correction compass is appended to the original compass (same merging logic as stash_retry).

#### Scenario: Quick correct preserves working directory
- **WHEN** the resolved retry mode is `quick_correct` and Twin decides retry after a phase execution
- **THEN** the runner SHALL NOT call `stash_working_changes()` and the working directory SHALL retain all output from the previous phase execution

#### Scenario: Quick correct appends correction compass
- **WHEN** the resolved retry mode is `quick_correct` and Twin decides retry with correction text "Implement missing rate limit headers"
- **THEN** the runner SHALL append `[QUICK-CORRECT n/N] Implement missing rate limit headers` to the original compass and pass the full compass to `execute_phase`

#### Scenario: Quick correct reflect on correction result
- **WHEN** the resolved retry mode is `quick_correct` and the phase is re-invoked with the correction compass
- **THEN** the runner SHALL call `_twin_instance.reflect(retry_record, is_retry=True, epic_id=epic_id)` on the correction result, following the same reflect-and-decide logic as stash_retry

### Requirement: Quick correct failure degradation
When a quick correction cycle fails (phase execution fails or reflect returns `retry` again after exhausting `max_quick_corrections`), the system SHALL follow the same degradation logic as stash_retry based on `retry_exhausted_action`. Parse failures during quick correction reflect SHALL also follow the existing `is_retry=True` degradation rules.

#### Scenario: Quick correction phase execution failure
- **WHEN** the resolved retry mode is `quick_correct` and `execute_phase()` returns `success=False` during a quick correction cycle
- **THEN** the runner SHALL break out of the correction loop and follow `retry_exhausted_action` (halt or continue)

#### Scenario: Quick correction reflect parse failure
- **WHEN** the resolved retry mode is `quick_correct` and the reflect call during a quick correction cycle fails to parse YAML
- **THEN** the system SHALL apply the same degradation logic as stash_retry: if `is_retry=True` and `retry_exhausted_action="halt"`, default to `decision="halt"`; otherwise default to `decision="continue"`
