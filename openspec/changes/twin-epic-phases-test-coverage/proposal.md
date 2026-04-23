## Why

twin-epic-phases 的实现测试全部 mock 了 `execute_phase` 和 Twin 实例，导致 `_execute_phase_with_twin` 中的 `build_execution_record`、reflect 异常处理、`apply_page_updates` 等真实代码路径从未被执行。bound method `_compass` 注入和 retry correction 不更新两个生产 bug 正是这种过度 mock 的后果。需要创建专门的 mock 模块，在不过度 mock 的情况下覆盖这些生产路径。

## What Changes

- 新增 `tests/core/loop/mock_twin.py` 模块，提供 `FakeTwin`、`FakeWikiDir`、`FakeHandler` 等 mock 组件，模拟 Twin 的 guide/reflect/retry 行为而不 mock `execute_phase` 本身
- 新增 `tests/core/loop/test_twin_production_paths.py`，使用 mock 模块覆盖 `build_execution_record` 真实调用、reflect 异常吞没、`apply_page_updates` 真实 I/O、bound method compass 注入端到端等生产路径
- 增强 `test_epic_phases_twin.py` 已有测试的断言强度（区分原始 result vs retry result）

## Capabilities

### New Capabilities
- `twin-test-mock-module`: 提供 FakeTwin、FakeWikiDir、FakeHandler 等可复用的 mock 组件，模拟 Twin guide/reflect/retry/page_updates 行为
- `twin-production-path-tests`: 覆盖 build_execution_record 真实调用、reflect 异常吞没、apply_page_updates 真实 I/O、bound method compass 端到端注入等从未被测试过的生产路径

### Modified Capabilities

## Impact

- **代码**: 新增 `tests/core/loop/mock_twin.py` 和 `tests/core/loop/test_twin_production_paths.py`，不修改生产代码
- **测试**: 纯增量，不影响已有测试
- **依赖**: 无新外部依赖
