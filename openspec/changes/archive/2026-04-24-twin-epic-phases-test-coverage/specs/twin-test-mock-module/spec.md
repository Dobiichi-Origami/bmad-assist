## ADDED Requirements

### Requirement: FakeTwin simulates Twin guide/reflect/retry behavior
A `FakeTwin` class SHALL simulate the Twin interface (guide, reflect, config, wiki_dir) without LLM calls, configurable via constructor parameters.

#### Scenario: FakeTwin guide returns configured compass
- **WHEN** `FakeTwin(guide_return="navigate-south")` is constructed and `guide("atdd")` is called
- **THEN** it SHALL return `"navigate-south"`

#### Scenario: FakeTwin guide returns None when configured
- **WHEN** `FakeTwin(guide_return=None)` is constructed and `guide("atdd")` is called
- **THEN** it SHALL return `None`

#### Scenario: FakeTwin reflect iterates through configured sequence
- **WHEN** `FakeTwin(reflect_sequence=[TwinResult(decision="retry", ...), TwinResult(decision="continue", ...)])` is constructed
- **THEN** the first `reflect()` call SHALL return the retry result, and the second SHALL return the continue result

#### Scenario: FakeTwin reflect captures ExecutionRecord
- **WHEN** `FakeTwin.reflect(record, is_retry=False, epic_id=1)` is called with a real `ExecutionRecord`
- **THEN** `FakeTwin.last_record` SHALL store the record for assertion, and `reflect_call_count` SHALL increment

#### Scenario: FakeTwin reflect raises configured exception
- **WHEN** `FakeTwin(reflect_exception=RuntimeError("LLM failed"))` is constructed
- **THEN** `reflect()` SHALL raise `RuntimeError("LLM failed")`

#### Scenario: FakeTwin page_updates are included in reflect results
- **WHEN** `FakeTwin(page_updates=[PageUpdate(...)])` is constructed
- **THEN** each `TwinResult` from `reflect()` SHALL include the configured `page_updates`

#### Scenario: FakeTwin config exposes max_retries and retry_exhausted_action
- **WHEN** `FakeTwin(max_retries=3, retry_exhausted_action="continue")` is constructed
- **THEN** `FakeTwin.config.max_retries` SHALL be `3` and `FakeTwin.config.retry_exhausted_action` SHALL be `"continue"`

### Requirement: FakeHandler simulates BaseHandler with bound method execute
A `FakeHandler` class SHALL simulate a real handler's structure: an instance with an `execute()` method that reads `self._compass` and returns a `PhaseResult` with configurable outputs.

#### Scenario: FakeHandler execute reads _compass injected by dispatch
- **WHEN** `FakeHandler.execute(state)` is called after `_compass` is set on the instance
- **THEN** it SHALL record the compass value in `FakeHandler.compass_seen` and return `PhaseResult.ok(outputs={"response": ..., "duration_ms": ...})`

#### Scenario: FakeHandler returns configurable response and duration
- **WHEN** `FakeHandler(response="test output", duration_ms=250)` is constructed
- **THEN** `execute(state)` SHALL return `PhaseResult.ok(outputs={"response": "test output", "duration_ms": 250})`

### Requirement: FakeWikiDir provides real filesystem for wiki I/O tests
A `FakeWikiDir` helper SHALL create a minimal wiki directory structure (with INDEX page) on the real filesystem using tmp_path, suitable for `apply_page_updates` testing.

#### Scenario: FakeWikiDir creates wiki directory with INDEX
- **WHEN** `FakeWikiDir.create(tmp_path)` is called
- **THEN** it SHALL return a `Path` pointing to a directory containing a valid `INDEX.md` file
