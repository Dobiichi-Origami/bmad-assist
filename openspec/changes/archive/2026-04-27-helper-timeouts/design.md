## Context

bmad-assist 使用 helper provider（默认 Haiku 模型）执行辅助 LLM 任务。当前 6 个调用点的超时值硬编码在代码中：

| 调用点 | 文件 | 硬编码超时 |
|---|---|---|
| QA summary | `qa/summary.py:155` | 60s |
| Testarch eligibility | `testarch/eligibility.py:332` | 60s |
| Strategic context | `compiler/strategic_context.py:303` | 120s |
| Stack detector | `deep_verify/stack_detector.py:135` | 30s |
| Benchmarking extraction | `validation/benchmarking_integration.py:450` | 继承主 validate_story 超时（语义错误） |
| Synthesis extraction | `validate_story_synthesis.py:244` / `code_review_synthesis.py:467` | 动态计算，floor=30s 硬编码 |

现有 `TimeoutsConfig` 已提供 per-phase 超时机制（`get_phase_timeout`），但没有覆盖 helper 子任务。Twin 子系统有自己的独立超时配置（`TwinProviderConfig.timeout`），证明子系统级超时配置是已有模式。

## Goals / Non-Goals

**Goals:**
- 在 `TimeoutsConfig` 中添加 `helper` 嵌套子对象，按场景配置超时
- 提供 `get_helper_timeout(config, scenario)` loader，含 legacy fallback
- 替换 6 个调用点的硬编码超时
- 修正 benchmarking extraction 错误继承主 phase 超时的问题
- 向后兼容：不设置 `timeouts.helper` 时行为与原来一致

**Non-Goals:**
- 不修改 Deep Verify 的 `LLMConfig.default_timeout_seconds`（已有独立配置路径）
- 不修改 Twin 的超时配置（已有 `TwinProviderConfig.timeout`）
- 不给 `HelperProviderConfig` 添加 timeout 字段（超时是跨切面关注点，不属于 provider）
- 不添加 per-scenario retry 配置（helper 调用通常不重试）

## Decisions

### D1: 嵌套在 TimeoutsConfig 中而非 HelperProviderConfig

**选择**: `TimeoutsConfig.helper: HelperTimeoutsConfig`

**备选**:
- A) `HelperProviderConfig.timeouts: HelperTimeoutsConfig` — 超时是跨切面关注点，不应跟 provider 耦合
- B) `TimeoutsConfig` 中平铺 `helper_*` 前缀字段 — 字段过多，YAML 不清晰

**理由**: 超时配置统一在 `TimeoutsConfig` 管理，用户知道去哪里找。嵌套子对象保持 phase 超时和 helper 超时的语义隔离。`get_timeout("validate_story")` 不会意外返回 helper 超时。

### D2: 所有场景字段默认 None，继承 helper.default

**选择**: 场景字段 `int | None = None`，`get_timeout()` fallback 到 `HelperTimeoutsConfig.default=60`

**备选**: 每个场景设置与原硬编码一致的默认值（strategic_context=120, stack_detector=30）

**理由**: 与 `TimeoutsConfig` 现有模式一致（phase 字段全为 None，fallback 到 default）。`helper.default=60` 是合理的中位数。不设置 `timeouts.helper` 段时，`get_helper_timeout()` 走 legacy fallback 保持原值。

### D3: Legacy fallback 保持原有硬编码值

**选择**: 当 `config.timeouts is None` 时，`get_helper_timeout()` 返回与原硬编码一致的值

**理由**: 确保不设置 `timeouts` 段的用户无行为变化。只有显式设置 `timeouts.helper` 时才使用新默认值 60s。

### D4: Synthesis extraction 使用 helper timeout 作为 ceiling

**选择**: `per_call_timeout = max(min(budget_per_call, helper_ext_timeout), 30)`

**理由**: 当前 `per_call_timeout` 由 `max_compression_timeout / expected_calls` 动态计算。当调用少时，per_call 可能很大。`synthesis_extraction` 超时作为 ceiling 限制单次调用最长等待，30s floor 保证基本可用性。

## Risks / Trade-offs

- **[Behavior change] benchmarking extraction 超时来源变更** → 从主 validate_story 超时改为 helper benchmarking_extraction 超时。用户若设置了高 validate_story 超时并依赖它覆盖 extraction，行为会变化。Mitigation: legacy fallback 为 120s，合理且安全。
- **[Default 60s vs 原 120s] strategic_context** → 若用户设置了 `timeouts` 段但没设 `timeouts.helper.strategic_context`，strategic_context 从 120s 降为 60s。Mitigation: 在 release notes 中说明；用户需显式设置 `timeouts.helper.strategic_context: 120`。
