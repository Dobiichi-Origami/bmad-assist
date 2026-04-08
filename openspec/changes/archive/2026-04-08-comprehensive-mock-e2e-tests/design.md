## Context

bmad-assist 是一个 Python CLI 工具，通过编排多个 LLM CLI 工具自动化 AI 驱动的软件开发。核心执行路径为：

```
CLI (run command) → run_loop() → _run_loop_body()
  → 外层循环: iterate epics
    → 内层循环: iterate stories
      → execute_phase(state) → handler.execute(state)
        → render_prompt() + invoke_provider()
      → guardian_check_anomaly()
      → save_state()
    → handle_story_completion() → advance_to_next_story()
  → handle_epic_completion() → advance_to_next_epic()
```

当前有 ~368 个测试文件，~11,000 个测试函数，单元测试覆盖优秀。但**缺乏全流程 mock E2E 测试**——从未有测试验证过上述完整链路的正确性。现有测试基础设施包括：
- 15 个 conftest 文件，丰富的 mock 工厂（特别是 `tests/providers/conftest.py` 中的 provider mock）
- autouse fixtures 自动重置 config/state/paths/loop_config 单例
- `skip_signal_handlers=True`、`ipc_enabled=False`、`plain=True` 参数可简化测试环境

## Goals / Non-Goals

**Goals:**
- 建立一套全流程 mock E2E 测试框架，可在秒级完成运行
- 在 `execute_phase` 层面 mock，验证主循环的编排逻辑（phase 顺序、story/epic 转换、state 持久化）
- 覆盖 happy path、错误恢复、子系统集成三大类场景
- 所有 provider 调用均为 mock，无需网络或 LLM 访问
- 可重用的 fixture 和工具，方便后续扩展新场景

**Non-Goals:**
- 不测试真实 LLM 输出质量（那是 benchmarking 框架的职责）
- 不测试 compiler 的提示词生成正确性（已有 43 个编译器测试覆盖）
- 不测试 provider 的进程管理细节（已有 20 个 provider 测试覆盖）
- 不测试 dashboard UI（已有 Playwright E2E 测试覆盖）
- 不重构任何生产源码

## Decisions

### D1: Mock 层级选择 — 在 `execute_phase` 层面 mock

**选择:** Mock `bmad_assist.core.loop.dispatch.execute_phase` 返回可编排的 `PhaseResult`

**替代方案:**
- Mock `run_loop` 本身 → 太高层，无法测试循环内部逻辑
- Mock provider `Popen` → 太底层，引入过多无关复杂性（prompt 编译、输出解析等）
- Mock `handler.invoke_provider` → 中间层，但需要初始化 handlers 和 compiler

**理由:** `execute_phase` 是主循环与 handler 之间的唯一接口，mock 它可以完全控制每个 phase 的结果，同时保留主循环的全部编排逻辑（state 管理、guardian 检查、story/epic 转换）。

### D2: 测试目录结构

```
tests/e2e/mock_loop/
├── conftest.py              # 共享 fixtures: project scaffold, mock execute_phase, state helpers
├── fixtures/                # BMAD 项目 fixture 文件（epics.md, config 等）
├── test_single_story.py     # 单 story happy path
├── test_multi_story.py      # 多 story 流转
├── test_multi_epic.py       # 多 epic 流转
├── test_phase_failure.py    # phase 失败与 guardian halt
├── test_crash_recovery.py   # 崩溃恢复（从 state.yaml 恢复）
├── test_signal_handling.py  # SIGINT/SIGTERM 优雅关闭
├── test_qa_flow.py          # QA 完整流程
├── test_cli_flags.py        # CLI flag 端到端行为
├── test_sprint_sync.py      # sprint-status.yaml 同步
├── test_notifications.py    # 通知触发验证
└── test_auto_commit.py      # git auto-commit 验证
```

### D3: Fixture 策略 — 使用 `tmp_path` + 最小化 BMAD 项目

**选择:** 每个测试在 `tmp_path` 下创建一个最小化 BMAD 项目目录结构

**理由:**
- 避免依赖 `tests/fixtures/bmad-sample-project`（那是为 parser 测试设计的，结构可能变化）
- `tmp_path` 天然隔离，无副作用
- 最小化项目仅需：`bmad-assist.yaml`、`epics.md`（或 sharded epic 文件）、`.bmad-assist/` 目录

### D4: Phase 结果编排 — 使用 ScriptedPhaseExecutor

**选择:** 创建一个 `ScriptedPhaseExecutor` 类，接受一个 `{(epic, story, phase): PhaseResult}` 字典，在被调用时按 key 返回对应结果。

**理由:**
- 比简单的 `side_effect` 列表更可读、更易维护
- 支持基于当前 state 动态决定结果
- 便于在测试中直接看出每个 phase 的预期行为

### D5: 断言策略

**选择:** 基于最终 State 和调用记录进行断言

- 验证 `state.completed_stories` 和 `state.completed_epics` 包含正确的条目
- 验证 `execute_phase` 被调用的次数和顺序
- 验证 `run_loop` 返回正确的 `LoopExitReason`
- 验证 `state.yaml` 文件在关键时刻被正确持久化

## Risks / Trade-offs

- **[Mock 漂移]** execute_phase 的接口变化可能导致 mock 失效 → 缓解：测试中导入真实的 `PhaseResult` 类型，接口变化时编译期即可发现
- **[过度 mock 导致假阳性]** mock 太多可能让测试通过但实际集成失败 → 缓解：选择 execute_phase 这个自然边界点，保留主循环全部真实代码
- **[Fixture 维护成本]** BMAD 项目 fixture 需要随项目演进更新 → 缓解：使用 fixture 生成函数而非静态文件，只包含必要的最小结构
- **[信号处理测试脆弱]** 真实信号在 CI 环境中可能行为不一致 → 缓解：通过 `request_shutdown()` 函数模拟信号，不发送真实系统信号
