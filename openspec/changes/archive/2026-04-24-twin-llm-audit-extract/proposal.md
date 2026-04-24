## Why

`format_self_audit()` 使用正则从 LLM 输出中提取自审段落，但 LLM 输出格式不受模板约束——中文标题（"审查"、"自审"）、非标准标题级别（`###`）、语义等价但命名不同（"Quality Check"、"Verification"）——正则全部丢失，导致 Twin reflect prompt 中的 `self_audit_section` 退化为 "(No Self-Audit section found in output)"，Twin 失去关键的跨校验输入。需要在正则匹配失败时引入 LLM 做语义抽取，补齐丢失的审计信息。

## What Changes

- 在 `Twin.reflect()` 中增加 LLM 兜底抽取：当 `record.self_audit is None` 时，调用 LLM 从原始输出中语义识别并提取自审段落
- 新增 `TwinProviderConfig.audit_extract_model` 配置字段，允许使用轻量模型做抽取（默认 None 回退主模型）
- 新增抽取 prompt 模板 `build_extract_self_audit_prompt()`，支持中英文多语言标题变体
- 正则 `format_self_audit()` 保持不变，仍作为零成本快速路径

## Capabilities

### New Capabilities
- `twin-audit-llm-extract`: LLM 语义抽取自审段落——当正则匹配失败时，使用 LLM 从原始输出中识别并提取自审/审查/质量检查等语义等价段落

### Modified Capabilities
- `twin-reflect`: `Twin.reflect()` 在构建 prompt 前增加 LLM 兜底抽取步骤，当 `record.self_audit is None` 时调用 `_extract_self_audit_llm()` 覆盖 `self_audit` 值
- `execution-record`: `TwinProviderConfig` 新增 `audit_extract_model` 字段

## Impact

- **代码**：`src/bmad_assist/twin/twin.py`（新增方法 + 修改 reflect 流程）、`src/bmad_assist/twin/prompts.py`（新增 prompt 模板）、`src/bmad_assist/twin/config.py`（新增配置字段）
- **延迟**：仅当正则失败时触发一次额外 LLM 调用（预计 1-3s），正则成功时零额外开销
- **成本**：每次抽取消耗约 3-12K input tokens（取决于输出长度），配置轻量模型可降低成本
- **向后兼容**：`format_self_audit()` 不变，所有现有测试通过；`audit_extract_model` 有默认值
