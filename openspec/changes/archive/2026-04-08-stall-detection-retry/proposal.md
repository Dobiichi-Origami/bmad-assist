## Why

在运行 bmad-assist 的多阶段 LLM 编排循环时，偶尔会遇到某个 provider（Claude、Gemini、Kimi 等）的子进程长时间"卡住"——进程仍在运行但完全没有新的 stdout 输出。当前的超时机制只检查总运行时间（phase-level timeout），这意味着一个 stall 可能要等待数十分钟甚至一小时才会被发现，严重浪费时间并延迟整个 sprint 循环。我们需要一种更细粒度的"idle timeout"（空闲超时）机制，能在检测到 provider 长时间无输出后尽早终止并重试，从而显著提高服务的鲁棒性和效率。

## What Changes

- 新增 **idle timeout（空闲超时）** 检测机制：监控 provider 子进程的 stdout 输出流，当超过可配置的时间阈值没有新输出时，判定为 stall 并主动终止进程
- 新增 `ProviderStallError` 异常类型，区别于现有的 `ProviderTimeoutError`（总超时）
- 将 stall 检测集成到现有的 `invoke_with_timeout_retry` 重试机制中，stall 触发后自动重试请求
- 在 `TimeoutsConfig` 配置模型中新增 `idle_timeout` 参数，支持全局默认值和 per-phase 覆盖
- 支持 SDK 和 subprocess 两种 provider 模式的 stall 检测

## Capabilities

### New Capabilities
- `stall-detection`: 检测 provider 长时间无输出的 stall 状态，包括 idle timeout 配置、stall 判定逻辑、自动终止和重试集成

### Modified Capabilities

## Impact

- **核心模块**: `providers/base.py`（流读取基础设施）、`providers/claude.py`、`providers/claude_sdk.py`、`providers/gemini.py`、`providers/kimi.py` 等所有 subprocess provider
- **重试机制**: `core/retry.py`（`invoke_with_timeout_retry` 需要支持新的 stall error）
- **配置模型**: `core/config/models/features.py`（`TimeoutsConfig` 新增 idle_timeout 字段）
- **异常体系**: `core/exceptions.py`（新增 `ProviderStallError`）
- **无破坏性变更**: idle_timeout 默认为 None（禁用），不影响现有行为
