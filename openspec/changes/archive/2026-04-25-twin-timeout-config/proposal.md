## Why

Twin 的 LLM 调用（reflect / audit_extract）没有独立的超时时长配置。`_invoke_llm` 和 `_extract_self_audit_llm` 调用 `invoke_with_timeout_retry` 时未传 `timeout` 参数，导致 provider 使用硬编码的 `DEFAULT_TIMEOUT = 300s`。用户无法根据项目规模或模型响应速度调整 Twin 的超时，只能被动接受 5 分钟默认值。

## What Changes

- 在 `TwinProviderConfig` 中新增 `timeout` 字段（秒），控制 Twin LLM 调用的超时时长
- `_invoke_llm` 和 `_extract_self_audit_llm` 将 `timeout` 传递给 `invoke_with_timeout_retry` → `provider.invoke()`
- `bmad-assist.yaml.example` 新增 `providers.twin.timeout` 配置示例
- 默认值保持 `300`（与当前硬编码值一致，无 breaking change）

## Capabilities

### New Capabilities
- `twin-timeout-config`: Twin LLM 调用的可配置超时时长，涵盖 reflect 和 audit_extract 两次调用

### Modified Capabilities
- `twin-timeout-retry`: timeout retries 现在基于可配置的超时时长（而非硬编码默认值），需更新场景描述

## Impact

- `src/bmad_assist/twin/config.py` — 新增 `timeout` 字段
- `src/bmad_assist/twin/twin.py` — `_invoke_llm` 和 `_extract_self_audit_llm` 传递 `timeout`
- `bmad-assist.yaml.example` — 新增配置示例
- `tests/twin/test_config.py` — 新增 timeout 字段测试
- `tests/twin/test_twin.py` — 验证 timeout 传递到 provider.invoke
