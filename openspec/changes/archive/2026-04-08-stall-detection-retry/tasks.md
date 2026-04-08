## 1. Configuration Layer

- [x] 1.1 在 `core/config/models/features.py` 的 `TimeoutsConfig` 中添加 `idle_timeout: int | None = None` 字段（ge=30），描述为 idle timeout 阈值
- [x] 1.2 在 `TimeoutsConfig` 中添加 `get_idle_timeout(phase: str) -> int | None` 方法，返回 idle_timeout 值（当前全局，后续可扩展 per-phase）
- [x] 1.3 在 `core/config/loaders.py` 中添加 `get_phase_idle_timeout(config, phase)` 辅助函数，与 `get_phase_timeout` 风格一致

## 2. Subprocess Provider Stall Detection

- [x] 2.1 在 `providers/base.py` 中创建 `StallDetector` 类：封装 `threading.Lock` + `last_output_time` 浮点数时间戳，提供 `update()` 和 `is_stalled(idle_timeout: int) -> bool` 方法
- [x] 2.2 修改 `providers/base.py` 的 `read_stream_lines()` 函数，支持可选的 `StallDetector` 参数，在每次 readline 时调用 `detector.update()`
- [x] 2.3 在 `providers/claude.py` 的 `ClaudeSubprocessProvider` poll loop（约 L685-752）中集成 stall 检测：创建 `StallDetector`，传入 stream reader，在 poll loop 的 deadline 检查之前添加 idle timeout 检查
- [x] 2.4 idle timeout 触发时：终止进程，收集 partial result，抛出 `ProviderTimeoutError`，message 包含 "idle timeout" 关键词以区分
- [x] 2.5 在 `providers/gemini.py` 的 `GeminiProvider` 中集成 stall 检测（复用 StallDetector）
- [x] 2.6 在 `providers/kimi.py` 的 `KimiProvider` 中集成 stall 检测
- [x] 2.7 在其他 subprocess providers（codex, copilot, amp, cursor_agent, opencode）中集成 stall 检测

## 3. SDK Provider Stall Detection

- [x] 3.1 在 `providers/claude_sdk.py` 的 `_invoke_async` 方法中，添加 last_message_time 跟踪：每次从 `client.receive_messages()` 收到消息时更新时间戳
- [x] 3.2 将 `asyncio.wait_for` 替换为自定义 async 循环，在每个消息接收周期中检查 idle timeout（可通过 asyncio.wait + 定时 task 实现）

## 4. Handler 层集成

- [x] 4.1 在 `core/loop/handlers/base.py` 的 `invoke_provider()` 中，从 config 获取 `idle_timeout` 并传递给 provider 的 invoke 方法
- [x] 4.2 确认 `invoke_with_timeout_retry`（`core/retry.py`）已自动处理 stall 触发的 `ProviderTimeoutError`——验证无需代码改动

## 5. 测试

- [x] 5.1 为 `StallDetector` 类编写单元测试：验证 `update()` 重置时间、`is_stalled()` 正确判断
- [x] 5.2 为 `TimeoutsConfig.get_idle_timeout()` 编写单元测试：验证 None 默认值、最小值校验
- [x] 5.3 为 Claude subprocess provider 编写 stall 检测集成测试：mock 一个不产生输出的子进程，验证 idle timeout 触发 `ProviderTimeoutError`
- [x] 5.4 为 retry 路径编写测试：验证 stall 触发的 `ProviderTimeoutError` 被 `invoke_with_timeout_retry` 正确重试
