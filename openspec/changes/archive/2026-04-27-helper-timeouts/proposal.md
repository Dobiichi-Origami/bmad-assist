## Why

Helper/Haiku 模型在 validation、QA、testarch、compiler、deep verify 等模块中做辅助 LLM 调用（摘要、指标提取、资格判定、技术栈检测等），但这些调用的超时值分散硬编码在各文件中（30s/60s/120s），无法通过 YAML 配置覆盖，也无法按场景差异化调整。

## What Changes

- 在 `TimeoutsConfig` 中新增 `helper: HelperTimeoutsConfig` 嵌套子对象，包含 6 个场景的超时字段：`qa_summary`、`testarch_eligibility`、`strategic_context`、`stack_detector`、`benchmarking_extraction`、`synthesis_extraction`
- 新增 `get_helper_timeout(config, scenario)` loader 函数，含 legacy fallback（未设置 timeouts 时保持原有硬编码值）
- 更新 6 个调用点，将硬编码超时替换为 `get_helper_timeout()` 调用
- 修正 benchmarking extraction 错误继承主 validate_story 超时的问题

## Capabilities

### New Capabilities
- `helper-timeouts`: 为 helper/辅助 LLM 调用提供按场景可配置的超时机制，嵌套在 TimeoutsConfig 中，支持 YAML 覆盖和 legacy fallback

### Modified Capabilities
<!-- 无现有 spec 需要修改 -->

## Impact

- **配置**: `TimeoutsConfig` 新增 `helper` 子字段，YAML 结构新增 `timeouts.helper` 段，向后兼容（默认值保持原有行为）
- **代码**: 6 个文件的硬编码超时值替换为配置读取
  - `qa/summary.py` — 60s → configurable
  - `testarch/eligibility.py` — 60s → configurable
  - `compiler/strategic_context.py` — 120s → configurable
  - `deep_verify/stack_detector.py` — 30s → configurable
  - `validation/orchestrator.py` — 修正超时来源
  - `validate_story_synthesis.py` / `code_review_synthesis.py` — 动态计算引入 ceiling
- **Loader**: `core/config/loaders.py` 新增 `get_helper_timeout()` 函数
- **测试**: 扩展 `tests/core/test_config_timeouts.py`
