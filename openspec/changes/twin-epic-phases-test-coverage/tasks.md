## 1. Create mock_twin.py module

- [x] 1.1 Create `tests/core/loop/mock_twin.py` with `FakeTwin` class: `__init__` accepting `guide_return`, `reflect_sequence`, `page_updates`, `reflect_exception`, `max_retries`, `retry_exhausted_action`; `guide(phase_type)` returning configured value; `reflect(record, is_retry, epic_id)` iterating sequence, capturing `last_record`, incrementing `reflect_call_count`, raising configured exception; `config` and `wiki_dir` properties
- [x] 1.2 Add `FakeHandler` class: `__init__` accepting `response`, `duration_ms`; `execute(state)` method reading `self._compass`, recording to `compass_seen`, returning `PhaseResult.ok(outputs={"response": ..., "duration_ms": ...})`
- [x] 1.3 Add `FakeWikiDir.create(tmp_path)` helper: creates wiki directory with `INDEX.md` and returns `Path`
- [x] 1.4 Add `install_fake_handler(phase, handler)` helper: patches `dispatch._handler_instances` and `_handlers_initialized` to inject a FakeHandler for a specific phase

## 2. build_execution_record production path tests

- [x] 2.1 Test `_execute_phase_with_twin` calls `build_execution_record` with real `response` and `duration_ms` from PhaseResult.outputs — verify via `FakeTwin.last_record`
- [x] 2.2 Test `build_execution_record` called with empty defaults when PhaseResult.outputs lacks `"response"` key — verify `llm_output=""` and `duration_ms=0` in `last_record`
- [x] 2.3 Test non-int `duration_ms` in outputs is coerced to 0 in `build_execution_record` call

## 3. Reflect block exception handling tests

- [x] 3.1 Test `build_execution_record` raises `TypeError` inside reflect block → original successful `PhaseResult` returned, warning logged
- [x] 3.2 Test `Twin.reflect()` raises `RuntimeError` → original successful `PhaseResult` returned, warning logged

## 4. apply_page_updates real I/O tests

- [x] 4.1 Test `PageUpdate(action="create")` writes new file in wiki directory via `FakeWikiDir`
- [x] 4.2 Test `PageUpdate(action="update")` modifies existing file in wiki directory

## 5. Bound method compass end-to-end tests

- [x] 5.1 Test `execute_phase(state, compass=X)` with `install_fake_handler` → FakeHandler.compass_seen == X, verifying `_compass` injection through bound method
- [x] 5.2 Test `_execute_phase_with_twin` with FakeTwin guide + FakeHandler → compass flows from Twin guide to FakeHandler.compass_seen

## 6. Twin guide returns None edge case

- [x] 6.1 Test FakeTwin guide returns None, phase succeeds → FakeTwin.reflect is still called with execution record

## 7. Run all tests and verify

- [x] 7.1 Run `tests/core/loop/test_twin_production_paths.py` and verify all pass
- [x] 7.2 Run full `tests/core/loop/` suite and verify no regressions
