## Context

twin-epic-phases 实现了 `_execute_phase_with_twin()` 辅助函数，封装 Twin guide → execute → reflect → retry 完整循环。当前测试全部通过 mock `execute_phase` 和 `Twin` 类绕过了以下生产代码路径：

1. **`build_execution_record` 真实调用**：从未用真实 `PhaseResult.outputs` 构造 `ExecutionRecord`，`mission`/`llm_output`/`duration_ms` 的提取和 `isinstance` 守卫从未执行
2. **reflect 异常吞没**：`except Exception` 在 reflect 块中捕获 `build_execution_record` 故障，返回原始 `result`，调用方无法感知 Twin 反思被跳过
3. **`apply_page_updates` 真实 I/O**：wiki 文件的 create/update/evolve 操作从未在测试中执行
4. **bound method compass 端到端注入**：从 `init_handlers` → `get_handler` 返回 bound method → `execute_phase` 设 `_compass` → handler 读取 `self._compass` 的完整链路从未走通
5. **Twin guide 返回 None/空字符串**时的 `_twin_instance` 状态差异未被测试

关键约束：不能引入真实 LLM 调用或网络依赖。需要在 mock 的精细度和生产路径覆盖之间找到平衡。

## Goals / Non-Goals

**Goals:**
- 创建可复用的 `mock_twin.py` 模块，提供 FakeTwin、FakeWikiDir、FakeHandler 组件
- 覆盖 `build_execution_record` 真实调用路径（含 outputs 提取、git diff 捕获）
- 覆盖 reflect 块异常处理路径（build_execution_record 失败、reflect 自身异常）
- 覆盖 `apply_page_updates` 真实文件 I/O
- 覆盖 bound method compass 端到端注入（init_handlers → get_handler → execute_phase → handler）
- 测试不依赖真实 LLM 或网络

**Non-Goals:**
- 不测试 Twin 的 LLM 调用和 YAML 解析（属于 Twin 模块自身测试）
- 不测试 `init_wiki` 真实目录创建（属于 wiki 模块自身测试）
- 不修改任何生产代码
- 不替代已有 E2E 测试（补充而非替代）

## Decisions

### D1: FakeTwin 替代 MagicMock

**选择**: 创建 `FakeTwin` 类，模拟 Twin 的 guide/reflect/retry 行为但不调用 LLM

**备选方案**:
- A) 继续用 MagicMock 配置 return_value/side_effect → 无法模拟状态变化（如 retry 计数、correction 更新），测试代码冗长
- B) 用真实 Twin + mock LLM provider → 过度复杂，引入 provider 初始化依赖
- C) FakeTwin 类 → 精确控制行为，可模拟 retry/halt/continue/page_updates，测试代码简洁

**理由**: 选项 C 最适合。FakeTwin 是一个简单的 Python 类，通过构造参数控制行为（`guide_return`、`reflect_sequence`、`page_updates` 等），比 MagicMock 更易读、更可维护。Twin 的 `reflect()` 方法可接受 `ExecutionRecord` 并验证其字段，确保 `build_execution_record` 真实调用路径被覆盖。

**FakeTwin 接口**:
```python
class FakeTwin:
    def __init__(self, *, guide_return="compass", reflect_sequence=None,
                 page_updates=None, reflect_exception=None):
        self.guide_return = guide_return
        self.reflect_sequence = reflect_sequence or [TwinResult(decision="continue", rationale="ok")]
        self.page_updates = page_updates
        self.reflect_exception = reflect_exception
        self.reflect_call_count = 0
        self.last_record = None  # Captures the ExecutionRecord

    def guide(self, phase_type): ...
    def reflect(self, record, is_retry=False, epic_id=None): ...
```

### D2: FakeHandler 替代 MagicMock 执行 handler

**选择**: 创建 `FakeHandler` 类，具有 `execute()` 方法（bound method），可读取 `self._compass` 并返回可控的 `PhaseResult`

**理由**: 这正是生产路径中 handler 的形态——`init_handlers` 注册 handler 实例，`get_handler` 返回 `instance.execute`（bound method）。FakeHandler 模拟这一结构，确保 `_compass` 注入在 bound method 上正常工作。返回的 `PhaseResult` 包含 `response` 和 `duration_ms`，使 `build_execution_record` 获得真实数据。

**FakeHandler 接口**:
```python
class FakeHandler:
    def __init__(self, *, response="handler output", duration_ms=100):
        self._compass = None
        self._response = response
        self._duration_ms = duration_ms
        self.compass_seen = None

    def execute(self, state):
        self.compass_seen = self._compass
        return PhaseResult.ok(outputs={"response": self._response, "duration_ms": self._duration_ms})
```

### D3: FakeWikiDir 使用 tmp_path 真实文件系统

**选择**: `apply_page_updates` 测试使用真实 `tmp_path` 目录作为 wiki_dir

**理由**: `apply_page_updates` 的核心是文件 I/O（create/update/evolve wiki pages + rebuild_index）。Mock 文件操作等于不测试。使用 `tmp_path` 可以验证真实文件创建、frontmatter 处理、index 重建等行为，且不影响测试速度。

### D4: 测试文件组织

**选择**: 两个文件：`mock_twin.py`（mock 组件）和 `test_twin_production_paths.py`（测试）

**理由**: mock 组件独立成模块可被未来其他测试复用（如主循环 Twin 重构后的测试）。测试文件按覆盖路径分组（record、reflect exception、page updates、compass e2e），与已有 `test_epic_phases_twin.py` 互补。

## Risks / Trade-offs

- **[FakeTwin 与真实 Twin 行为不一致]** → FakeTwin 只模拟接口契约，不模拟内部状态。定期对照真实 Twin 接口审查 FakeTwin → 如果 Twin 接口变更，FakeTwin 需同步更新
- **[git diff 测试不稳定]** → `build_execution_record` 的 git diff 捕获在非 git 目录或无 git 环境下可能行为不同 → 测试用 `tmp_path` 创建临时 git repo（`git init` + `git add`），确保环境可控
- **[apply_page_updates 测试耦合 wiki 格式]** → 测试依赖 wiki 页面的 frontmatter 和 markdown 格式 → 只验证核心行为（文件创建/更新、index 重建），不验证格式细节
