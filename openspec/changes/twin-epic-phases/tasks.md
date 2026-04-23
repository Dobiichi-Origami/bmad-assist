## 1. Move resolve_twin_provider to dispatch.py

- [x] 1.1 Add `resolve_twin_provider(config)` to `src/bmad_assist/core/loop/dispatch.py` (copy logic from runner.py `_resolve_twin_provider`, remove underscore prefix)
- [x] 1.2 Update `runner.py` to import `resolve_twin_provider` from dispatch, remove the local `_resolve_twin_provider` definition
- [x] 1.3 Update all references in runner.py from `_resolve_twin_provider` to `resolve_twin_provider`
- [ ] 1.4 Verify existing Twin tests still pass (`tests/core/loop/test_twin_runner_integration.py`)

## 2. Implement _execute_phase_with_twin helper

- [x] 2.1 Add `_execute_phase_with_twin(state, config, project_path, retry_exhausted_action)` to `src/bmad_assist/core/loop/epic_phases.py` with Twin guide → execute → reflect → retry cycle (no git stash for setup/teardown)
- [x] 2.2 Import `resolve_twin_provider` from dispatch in epic_phases.py
- [x] 2.3 Handle Twin disabled path (compass=None, no reflect)
- [x] 2.4 Handle Twin guide exception (compass=None, no _twin_instance, continue execution)
- [x] 2.5 Handle Twin reflect continue/halt/retry decisions
- [x] 2.6 Handle retry loop with correction compass appended to original
- [x] 2.7 Handle reflect exception (log warning, continue with original result)
- [x] 2.8 Handle apply_page_updates when twin_result.page_updates is not None

## 3. Integrate Twin into _execute_epic_setup

- [x] 3.1 Add `config: Config` parameter to `_execute_epic_setup`
- [x] 3.2 Replace `execute_phase(state)` call with `_execute_phase_with_twin(state, config, project_path, retry_exhausted_action="halt")`
- [x] 3.3 Handle Twin halt: when `_execute_phase_with_twin` result indicates halt (reflect decision="halt"), return `(state, False)` immediately
- [x] 3.4 Update runner.py call site (~L957) to pass `config`

## 4. Integrate Twin into _execute_epic_teardown

- [x] 4.1 Add `config: Config` parameter to `_execute_epic_teardown`
- [x] 4.2 Replace `execute_phase(state)` call with `_execute_phase_with_twin(state, config, project_path, retry_exhausted_action="continue")`
- [x] 4.3 Handle Twin halt: log warning, continue to next teardown phase (ADR-002 priority)
- [x] 4.4 Update runner.py call site (~L1654) to pass `config`

## 5. Update existing tests

- [x] 5.1 Update `test_runner_epic_scope.py` — add `config` argument to all `_execute_epic_setup` and `_execute_epic_teardown` call sites
- [x] 5.2 Update `test_twin_runner_integration.py` — adjust `resolve_twin_provider` import path if needed
- [x] 5.3 Verify all existing loop and e2e tests pass

## 6. Add new integration tests

- [x] 6.1 Create `tests/core/loop/test_epic_phases_twin.py` with `TestEpicSetupTwin` (4 tests: guide+compass, reflect halt→False, retry→continue, twin disabled)
- [x] 6.2 Add `TestEpicTeardownTwin` (4 tests: guide+compass, reflect halt→continues, retry→continue, twin disabled)
- [x] 6.3 Run all new tests and verify they pass
