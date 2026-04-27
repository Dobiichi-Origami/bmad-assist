## ADDED Requirements

### Requirement: HelperTimeoutsConfig model
系统 SHALL 提供 `HelperTimeoutsConfig` Pydantic 模型，嵌套在 `TimeoutsConfig.helper` 字段中，包含以下可配置场景超时：
- `default`: 所有 helper 场景的默认超时（默认 60s，ge=10）
- `qa_summary`: QA 摘要生成超时
- `testarch_eligibility`: Testarch 资格判定超时
- `strategic_context`: 战略上下文压缩超时
- `stack_detector`: 技术栈检测超时
- `benchmarking_extraction`: 验证指标提取超时
- `synthesis_extraction`: Synthesis 预提取单次调用 ceiling 超时

所有场景字段 SHALL 为 `int | None = None`，`get_timeout(scenario)` 方法 SHALL 返回场景值（若设置）或 `default` 值。Hyphen 场景名 SHALL 被规范化为 underscore。

#### Scenario: Scene-specific timeout overrides default
- **WHEN** `HelperTimeoutsConfig(default=60, strategic_context=180)` 配置
- **THEN** `get_timeout("strategic_context")` 返回 180，`get_timeout("qa_summary")` 返回 60

#### Scenario: All scenarios fall back to default
- **WHEN** `HelperTimeoutsConfig(default=90)` 配置且无场景覆盖
- **THEN** 所有 `get_timeout()` 调用返回 90

#### Scenario: Hyphen normalization
- **WHEN** 调用 `get_timeout("stack-detector")`
- **THEN** 返回 `stack_detector` 字段值或 default

### Requirement: get_helper_timeout loader function
系统 SHALL 提供 `get_helper_timeout(config, scenario)` 函数，位于 `core/config/loaders.py`。

当 `config.timeouts is not None` 时，SHALL 委托给 `config.timeouts.helper.get_timeout(scenario)`。

当 `config.timeouts is None` 时，SHALL 返回 legacy 硬编码默认值：
- `qa_summary`: 60
- `testarch_eligibility`: 60
- `strategic_context`: 120
- `stack_detector`: 30
- `benchmarking_extraction`: 120
- `synthesis_extraction`: 60
- 其他场景: 60

#### Scenario: Config with timeouts section
- **WHEN** `config.timeouts` 已设置且 `config.timeouts.helper.strategic_context = 180`
- **THEN** `get_helper_timeout(config, "strategic_context")` 返回 180

#### Scenario: Config without timeouts section (legacy)
- **WHEN** `config.timeouts is None`
- **THEN** `get_helper_timeout(config, "strategic_context")` 返回 120（legacy 默认）

#### Scenario: Unknown scenario with legacy fallback
- **WHEN** `config.timeouts is None` 且传入未知 scenario 名
- **THEN** 返回 60（通用 legacy 默认）

### Requirement: Call sites use get_helper_timeout
以下 6 个调用点 SHALL 将硬编码超时替换为 `get_helper_timeout()` 调用：

1. `qa/summary.py` — `timeout=60` → `timeout=get_helper_timeout(config, "qa_summary")`
2. `testarch/eligibility.py` — `timeout=60` → `timeout=get_helper_timeout(config, "testarch_eligibility")`
3. `compiler/strategic_context.py` — `timeout=120` → `timeout=get_helper_timeout(config, "strategic_context")`
4. `deep_verify/stack_detector.py` — `timeout=30` → `timeout=get_helper_timeout(config, "stack_detector")`
5. `validation/orchestrator.py` — benchmarking extraction 超时来源改为 `get_helper_timeout(config, "benchmarking_extraction")`
6. `validate_story_synthesis.py` / `code_review_synthesis.py` — synthesis extraction per_call_timeout 使用 `get_helper_timeout(config, "synthesis_extraction")` 作为 ceiling

#### Scenario: QA summary uses configured timeout
- **WHEN** `config.timeouts.helper.qa_summary = 90` 且调用 QA summary
- **THEN** provider.invoke 使用 `timeout=90`

#### Scenario: Benchmarking extraction uses helper timeout instead of phase timeout
- **WHEN** `config.timeouts.validate_story = 3600` 且 `config.timeouts.helper.benchmarking_extraction = 120`
- **THEN** benchmarking extraction 调用使用 `timeout=120`（不是 3600）

### Requirement: Synthesis extraction timeout ceiling
`validate_story_synthesis.py` 和 `code_review_synthesis.py` 的 `per_call_timeout` 计算 SHALL 使用 `synthesis_extraction` helper 超时作为单次调用的 ceiling：

```python
helper_ext_timeout = get_helper_timeout(config, "synthesis_extraction")
budget_per_call = synthesis_config.max_compression_timeout // max(expected_calls, 1)
per_call_timeout = max(min(budget_per_call, helper_ext_timeout), 30)
```

#### Scenario: Budget per call within ceiling
- **WHEN** `budget_per_call = 50` 且 `helper_ext_timeout = 90`
- **THEN** `per_call_timeout = 50`（未超 ceiling）

#### Scenario: Budget per call exceeds ceiling
- **WHEN** `budget_per_call = 150` 且 `helper_ext_timeout = 90`
- **THEN** `per_call_timeout = 90`（ceiling 限制）

#### Scenario: Budget per call below floor
- **WHEN** `budget_per_call = 15` 且 `helper_ext_timeout = 90`
- **THEN** `per_call_timeout = 30`（floor 保护）
