## 1. 测试框架基础设施

- [x] 1.1 创建 `tests/e2e/mock_loop/` 目录结构和 `__init__.py`
- [x] 1.2 实现 `ScriptedPhaseExecutor` 类：接受 `{(epic, story, phase): PhaseResult}` 映射，记录调用历史，未匹配时返回默认成功结果
- [x] 1.3 实现 `create_mock_project(tmp_path, epics)` fixture 工厂：生成最小化 BMAD 项目目录（bmad-assist.yaml、epics.md、.bmad-assist/），返回包含 `project_path`、`epic_list`、`epic_stories_loader` 的对象
- [x] 1.4 实现 `create_e2e_config()` 工厂：返回 mock provider 的最小 Config，支持 `qa_enabled` 和 `tea_enabled` 选项
- [x] 1.5 实现 `run_mock_loop()` 测试 harness：封装 `run_loop()` 调用，自动设置 `skip_signal_handlers=True`、`ipc_enabled=False`、`plain=True`，patch `execute_phase` 为 ScriptedPhaseExecutor，返回 `MockLoopResult(exit_reason, final_state, invocations)`
- [x] 1.6 实现断言 helpers：`assert_stories_completed(state, expected)`、`assert_epics_completed(state, expected)`、`assert_phase_order(executor, expected_phases)`
- [x] 1.7 编写 `tests/e2e/mock_loop/conftest.py`，注册所有 fixtures 并确保与根 conftest 的 autouse fixtures 兼容

## 2. Happy Path E2E 测试

- [x] 2.1 `test_single_story.py`: 单 epic 单 story 完整 phase 流程，验证 phase 执行顺序、state 完成状态、返回 COMPLETED
- [x] 2.2 `test_single_story.py`: 验证 state.yaml 在流程完成后被正确持久化
- [x] 2.3 `test_multi_story.py`: 单 epic 双 story 顺序执行，验证 story 转换、两个 story 都在 completed_stories 中
- [x] 2.4 `test_multi_story.py`: 单 epic 三 story，验证完整 phase 序列对每个 story 正确执行
- [x] 2.5 `test_multi_story.py`: 已完成的 story 在恢复时被跳过
- [x] 2.6 `test_multi_epic.py`: 双 epic 顺序执行，验证 epic 转换和两个 epic 都在 completed_epics 中
- [x] 2.7 `test_multi_epic.py`: 已完成的 epic 被跳过
- [x] 2.8 `test_multi_epic.py`: 所有 story 已完成的 epic 被跳过
- [x] 2.9 验证 RETROSPECTIVE 在每个 epic 的最后一个 story 之后只执行一次

## 3. 错误处理与恢复 E2E 测试

- [x] 3.1 `test_phase_failure.py`: DEV_STORY 失败触发 guardian halt，验证返回 GUARDIAN_HALT 和 state 位置
- [x] 3.2 `test_phase_failure.py`: CREATE_STORY 失败触发 guardian halt
- [x] 3.3 `test_phase_failure.py`: 失败信息记录到 state.anomalies
- [x] 3.4 `test_phase_failure.py`: 第一个 story 失败后后续 story 不执行，已完成工作被保留
- [x] 3.5 `test_crash_recovery.py`: 从 mid-story phase（DEV_STORY）恢复，不重新执行之前的 phase
- [x] 3.6 `test_crash_recovery.py`: 从 story 边界恢复（completed_stories 包含前一个 story）
- [x] 3.7 `test_crash_recovery.py`: 从 epic 边界恢复（completed_epics 包含前一个 epic）
- [x] 3.8 `test_crash_recovery.py`: 无 state.yaml 时从头开始
- [x] 3.9 `test_signal_handling.py`: SIGINT 信号通过 `request_shutdown()` 模拟，验证优雅退出和 state 保存
- [x] 3.10 `test_signal_handling.py`: SIGTERM 信号优雅退出
- [x] 3.11 `test_signal_handling.py`: 信号退出前 state.yaml 被正确保存
- [x] 3.12 `test_signal_handling.py`: CancellationContext 触发取消，返回 CANCELLED

## 4. 子系统集成 E2E 测试

- [x] 4.1 `test_qa_flow.py`: QA 启用时执行完整 QA_PLAN_GENERATE → QA_PLAN_EXECUTE → QA_REMEDIATE 链路
- [x] 4.2 `test_qa_flow.py`: QA 未启用时不执行 QA phase
- [x] 4.3 `test_cli_flags.py`: --epic flag 限制执行到指定 epic
- [x] 4.4 `test_cli_flags.py`: --story flag 从指定 story 开始执行
- [x] 4.5 `test_cli_flags.py`: --stop-after-epic flag 在指定 epic 完成后停止
- [x] 4.6 `test_sprint_sync.py`: story 完成后 sprint-status.yaml 被更新
- [x] 4.7 `test_sprint_sync.py`: 运行中 sprint-status 反映当前位置
- [x] 4.8 `test_notifications.py`: story/epic 完成和 guardian halt 时 mock notification dispatcher 被调用
- [x] 4.9 `test_auto_commit.py`: git-commit 启用时 committer 在正确 phase 后被调用
- [x] 4.10 `test_auto_commit.py`: git-commit 未启用时 committer 不被调用
- [x] 4.11 `test_auto_commit.py`: phase 失败时 committer 不被调用
- [x] 4.12 `test_tea_phases.py`: TEA 启用时 ATDD 和 TEA 相关 phase 被执行
- [x] 4.13 `test_tea_phases.py`: TEA 未启用时 TEA phase 不执行

## 5. 验证与收尾

- [x] 5.1 运行全套 mock E2E 测试确保通过：`pytest tests/e2e/mock_loop/ -v`
- [x] 5.2 确认所有测试在 60s 内完成（无真实 LLM 调用）
- [x] 5.3 验证 mock E2E 测试不与现有测试冲突：`pytest tests/ -v --ignore=tests/fixtures`
