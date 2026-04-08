## Why

bmad-assist 拥有约 368 个测试文件和 ~11,000 个测试函数，单元测试覆盖率很高，但缺乏一套完整的 **全流程 mock E2E 测试**，无法验证从 CLI 入口到各 phase handler 再到 provider 调用的端到端集成路径。当前约 30% 的源模块（~119 个）没有对应测试，关键的主循环（epic 迭代 → story 迭代 → phase 执行 → provider 调用 → state 持久化）从未作为一个完整流程被测试过。需要一套全 mock 的 E2E 测试来捕获跨模块集成问题、状态转换错误和异常恢复路径。

## What Changes

- 新增一套全流程 mock E2E 测试框架，mock 所有 LLM provider 调用，测试完整的 run loop 流程
- 覆盖以下关键场景：
  - **Happy path**: 单 epic/单 story 完整流程（create → validate → synthesis → dev → test_review → code_review → synthesis → retrospective）
  - **多 epic/多 story**: 跨 epic 和 story 的转换逻辑
  - **Phase 失败与重试**: provider 超时、transient error、exit code 错误处理
  - **崩溃恢复**: 模拟中途崩溃后从 state.yaml 恢复
  - **Guardian 异常检测**: 触发 guardian halt 的场景
  - **信号处理**: SIGINT/SIGTERM 优雅关闭
  - **QA 流程**: QA plan generate → execute → remediate 完整链路
  - **CLI 入口**: `--epic`/`--story`/`--stop-after-epic` 等 flag 的端到端行为
  - **Sprint 同步**: 运行过程中 sprint-status.yaml 的正确更新
  - **IPC 事件**: 主循环运行期间 IPC 事件的正确发射
  - **通知**: Discord/Telegram webhook 在正确时机被调用
  - **Auto-commit**: git committer 在正确 phase 被触发

## Capabilities

### New Capabilities
- `mock-e2e-framework`: Mock E2E 测试基础框架，包含 provider mock 工厂、BMAD 项目 fixture 生成器、state 断言工具
- `e2e-happy-path`: 正常流程 E2E 测试，覆盖单/多 epic+story 的完整 phase 链路
- `e2e-error-recovery`: 错误处理与恢复 E2E 测试，覆盖 provider 失败、崩溃恢复、guardian halt、信号处理
- `e2e-subsystem-integration`: 子系统集成 E2E 测试，覆盖 QA 流程、sprint 同步、IPC 事件、通知、auto-commit、CLI flags

### Modified Capabilities

（无需修改现有 spec，本次变更仅新增测试代码）

## Impact

- **新增文件**: `tests/e2e/mock_loop/` 目录下约 15-20 个测试文件 + conftest + fixtures
- **依赖**: 仅使用现有 pytest 生态（pytest, pytest-asyncio, unittest.mock），无需新增外部依赖
- **CI**: 需在 CI 中新增 `pytest tests/e2e/mock_loop/ -m "not slow"` 步骤，或将其纳入现有测试命令
- **性能**: 所有 provider 调用均为 mock，单次 E2E 测试预计 < 5s，全套 < 60s
- **影响范围**: 仅新增测试代码，不修改任何生产源码
