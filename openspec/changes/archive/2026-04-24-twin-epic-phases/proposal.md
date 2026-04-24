## Why

epic_setup 和 epic_teardown 阶段完全绕过 Twin guide/reflect 流程——它们调用 `execute_phase(state)` 时不传 compass，执行后也不走 reflect。Twin 作为 process guardian 应覆盖所有阶段，不限于 story 主循环阶段。当前缺失意味着 Twin 无法在 epic 级别的关键阶段（ATDD、retrospective 等）提供导航指导或漂移检测。

## What Changes

- 新增 `_execute_phase_with_twin()` 辅助函数，封装 Twin guide → execute → reflect → retry 完整流程，供 epic_phases.py 和未来主循环重构复用
- 将 `_resolve_twin_provider()` 从 runner.py 移至 dispatch.py，使其可被 epic_phases.py 等模块共享
- `_execute_epic_setup` 和 `_execute_epic_teardown` 新增 `config` 参数，每个子阶段改为调用 `_execute_phase_with_twin()`
- epic_setup: retry 耗尽 → halt（与现有 HALT 语义一致）
- epic_teardown: retry 耗尽 → continue；Twin halt 也继续执行（ADR-002 优先：teardown 失败也继续）
- runner.py 中两处调用点更新签名，传入 `config`
- 主循环的 Twin 代码本次不改（与 IPC/cancel/run_log 交错，风险高），标记 TODO

## Capabilities

### New Capabilities
- `twin-epic-phases`: Twin guide/reflect/retry 覆盖 epic_setup 和 epic_teardown 阶段，含 `_execute_phase_with_twin()` 辅助函数

### Modified Capabilities
- `twin-runner-integration`: `_resolve_twin_provider` 移至 dispatch.py，runner.py 改为 import

## Impact

- **API 变更**: `_execute_epic_setup` 和 `_execute_epic_teardown` 新增 `config` 参数（**BREAKING** — 内部函数签名变更）
- **代码**: epic_phases.py（主要改动）、dispatch.py（移动函数）、runner.py（调用点更新 + import 更新）
- **测试**: test_runner_epic_scope.py 需更新调用签名；新增 test_epic_phases_twin.py
- **依赖**: 无新外部依赖
