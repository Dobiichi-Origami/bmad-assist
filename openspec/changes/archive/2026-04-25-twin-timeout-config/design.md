## Context

Twin 的 LLM 调用（`_invoke_llm` 用于 reflect，`_extract_self_audit_llm` 用于 audit extract）通过 `invoke_with_timeout_retry` 路由，但未传递 `timeout` 参数。Provider 收到 `timeout=None` 后使用硬编码 `DEFAULT_TIMEOUT = 300s`。用户无法根据模型响应速度或项目规模调整此值。

现有 `TwinProviderConfig` 已有 `timeout_retries`（重试次数）但缺少 `timeout`（超时时长），形成不完整配置。

## Goals / Non-Goals

**Goals:**
- 在 `TwinProviderConfig` 中新增 `timeout` 字段，允许用户配置 Twin LLM 调用的超时时长（秒）
- 将 `timeout` 传递到 `_invoke_llm` 和 `_extract_self_audit_llm` 的 provider 调用链中
- 保持默认值 300s，无 breaking change
- 更新 YAML 配置示例和文档

**Non-Goals:**
- 不为 reflect 和 audit_extract 分别设置不同超时（共用一个 `timeout` 字段）
- 不修改 `invoke_with_timeout_retry` 的接口
- 不修改 phase-level 的 `timeouts` 配置体系

## Decisions

### D1: 单一 timeout 字段覆盖两次 LLM 调用

**选择**: `TwinProviderConfig` 加一个 `timeout: int` 字段，reflect 和 audit_extract 共用。

**替代方案**: 分别加 `reflect_timeout` 和 `audit_extract_timeout`。

**理由**: audit_extract 是轻量调用（提取审计文本），耗时远小于 reflect。分开配置增加复杂度但实际需求不大。如果未来确有需要，可以在 `audit_extract_model` 旁边加 `audit_extract_timeout`。

### D2: 默认值 300s

**选择**: `timeout: int = Field(default=300)`

**替代方案**: `default=None` 表示"用 provider 默认值"。

**理由**: 显式默认值更清晰。`None` 会引入语义歧义（"无超时"还是"用默认值"）。300s 与当前硬编码值一致，现有行为不变。

### D3: 传递方式

**选择**: `invoke_with_timeout_retry(..., timeout=self.config.timeout)` 通过 kwargs 透传到 `provider.invoke()`。

**理由**: `invoke_with_timeout_retry` 已支持 `**kwargs` 透传，无需修改其接口。

## Risks / Trade-offs

- [audit_extract 超时可能过长] → 轻量调用用 300s 偏宽松，但不会造成功能问题，且用户可自行调低。若未来需要独立控制，可加 `audit_extract_timeout`
- [用户设置过短导致频繁超时] → 用户已有 `timeout_retries` 兜底；文档中应建议合理值
