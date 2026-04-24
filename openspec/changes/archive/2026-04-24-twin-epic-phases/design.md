## Context

runner.py 的主循环中 Twin guide/reflect 流程覆盖 story 阶段（lines 1056-1462），但 `_execute_epic_setup` 和 `_execute_epic_teardown`（epic_phases.py）直接调用 `execute_phase(state)` 无 compass 且无 reflect。这两个函数在 runner.py 的 `_run_loop_body` 中被调用，`config` 作为局部变量可用但未传递给它们。

主循环的 Twin 代码与 IPC 事件、cancel 检查、run_log 记录等逻辑紧密交错，重构风险高。

## Goals / Non-Goals

**Goals:**
- epic_setup 每个子阶段走 Twin guide → compass → execute → reflect 完整流程
- epic_teardown 每个子阶段走 Twin guide → compass → execute → reflect 完整流程
- 提取共享辅助函数避免 ~130 行 Twin 逻辑重复
- `_resolve_twin_provider` 移至共享位置
- 保持 ADR-002 语义：teardown 阶段 Twin halt 不中断流程

**Non-Goals:**
- 不重构主循环的 Twin 代码（IPC/cancel/run_log 交错，风险高）
- 不改变 epic_setup/teardown 的失败策略（setup→HALT, teardown→CONTINUE）
- 不处理 epic_phases 中的 git stash（setup/teardown 阶段 retry 时不做 git stash——setup 阶段通常不写文件，teardown 阶段的文件变更是终态）

## Decisions

### D1: 新增 `_execute_phase_with_twin()` 辅助函数

**选择**: 在 epic_phases.py 中新增辅助函数，封装 guide → execute → reflect → retry 完整循环

**备选方案**:
- A) 复制 Twin 逻辑到 epic_phases.py → 重复代码，维护负担
- B) 抽取到独立模块（如 twin_helpers.py）→ 过度设计，目前只有两个消费者
- C) 直接在 epic_phases.py 中内联 → 两个函数各 ~80 行重复

**理由**: 选项 A/C 产生重复；选项 B 过度抽象。在 epic_phases.py 中提取辅助函数是最小化方案——epic_setup 和 epic_teardown 共享同一逻辑，仅 `retry_exhausted_action` 不同。

**函数签名**:
```python
def _execute_phase_with_twin(
    state: State,
    config: Config,
    project_path: Path,
    retry_exhausted_action: Literal["halt", "continue"] = "halt",
) -> PhaseResult:
```

返回 `PhaseResult`，调用方根据 `result.success` 和自身语义决定后续行为。

**不包含 git stash**: 与主循环不同，setup/teardown 的 retry 不做 git stash。原因：
- setup 阶段（如 ATDD）通常不修改工作目录
- teardown 阶段（如 retrospective）的文件变更是终态，stash 后重跑无意义

### D2: `_resolve_twin_provider` 移至 dispatch.py

**选择**: 从 runner.py 移到 dispatch.py

**理由**: 该函数解析 Twin LLM provider，逻辑上属于 dispatch 层。dispatch.py 已有 `execute_phase` 和 `reset_handlers`，增加 `resolve_twin_provider` 自然。runner.py 改为 `from bmad_assist.core.loop.dispatch import resolve_twin_provider`（去掉下划线前缀，成为模块级公开函数）。

**备选方案**:
- 留在 runner.py，epic_phases 从 runner 导入 → 创建 runner ↔ epic_phases 循环依赖风险
- 新建 twin_helpers.py → 过度抽象

### D3: teardown Twin halt → 继续执行

**选择**: Twin reflect 返回 halt 时，epic_teardown 记录警告但不中断

**理由**: ADR-002 明确规定 teardown 失败继续下一个阶段。Twin halt 是严重信号，但 teardown 是收尾流程，中断可能遗漏关键清理（如 retrospective）。记录日志即可，调用方可根据需要做后续处理。

### D4: 函数签名变更 — 新增 `config` 参数

**选择**: `_execute_epic_setup` 和 `_execute_epic_teardown` 新增 `config: Config` 参数

**理由**: Twin 需要 `config.providers.twin` 来判断是否启用、获取 provider/model 配置。当前函数仅通过 `get_loop_config()` 获取 loop 配置，无法访问 Twin 配置。传参比 `get_config()` 单例更清晰、更可测试。

## Risks / Trade-offs

- **[签名变更]** `_execute_epic_setup/teardown` 新增 `config` 参数 → 内部函数，仅 runner.py 调用，影响可控
- **[行为变更]** Twin halt 在 setup 中现在会触发 HALT（之前无 Twin→永远不 halt）→ 符合 guardian 语义，是有意改进
- **[主循环不一致]** 主循环 Twin 代码未重构 → 后续应统一使用 `_execute_phase_with_twin`，但本次标记 TODO 不做
- **[git stash 缺失]** setup/teardown retry 不做 git stash → 对 setup 无影响；对 teardown，若阶段写文件则 retry 会叠加变更，但 teardown 阶段通常只读/写 wiki，风险低
