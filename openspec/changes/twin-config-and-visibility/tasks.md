## 1. Config Defaults

- [x] 1.1 Change `TwinProviderConfig.enabled` default from `True` to `False` in `src/bmad_assist/twin/config.py`
- [x] 1.2 Update `test_config.py` default assertions to expect `enabled=False`

## 2. CLI Toggle

- [x] 2.1 Add `--twin` flag to CLI in `src/bmad_assist/cli.py`, setting `BMAD_TWIN_ENABLED=1` when passed
- [x] 2.2 Add `BMAD_TWIN_ENABLED` environment variable override in `src/bmad_assist/core/config/loaders.py` — when set to `"1"`, override `providers.twin.enabled` to `True`

## 3. Runner Visibility

- [x] 3.1 Replace `hasattr(config.providers, 'twin')` guard with direct `config.providers.twin` access in `src/bmad_assist/core/loop/runner.py` (guide and reflect integration points)
- [x] 3.2 Add `logger.info("Twin enabled (provider=%s, model=%s)", ...)` when Twin is enabled, and `logger.info("Twin disabled")` when disabled
- [x] 3.3 Improve guide failure logging: change `logger.warning("Twin guide failed, proceeding without compass: %s", e)` to include exception type name: `logger.warning("Twin guide failed, proceeding without compass: %s: %s", type(e).__name__, e)`
- [x] 3.4 Improve reflect failure logging similarly: include exception type name in the warning message

## 4. Existing Spec & Test Updates

- [x] 4.1 Update `openspec/changes/digital-twin/specs/twin-runner-integration/spec.md` — change `enabled` default from `True` to `False` in the TwinProviderConfig requirement
- [x] 4.2 Update `tests/twin/test_e2e_mock.py` — all `TwinProviderConfig()` usages that expect enabled behavior must explicitly set `enabled=True`
- [x] 4.3 Update `tests/twin/test_integration.py` — same as 4.2, ensure TwinProviderConfig fixtures explicitly enable Twin

## 5. New Tests

- [x] 5.1 Test: `TwinProviderConfig()` defaults to `enabled=False` (update existing test in `test_config.py`)
- [x] 5.2 Test: `BMAD_TWIN_ENABLED=1` overrides `enabled=False` in config loading
- [x] 5.3 Test: `--twin` CLI flag sets `BMAD_TWIN_ENABLED=1`
- [x] 5.4 Test: Runner logs "Twin enabled" / "Twin disabled" at info level
- [x] 5.5 Test: Runner logs exception type name on Twin guide/reflect failure
- [x] 5.6 Run full twin test suite (`tests/twin/`) and verify 199 tests still pass
