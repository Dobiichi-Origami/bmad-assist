## Context

bmad-assist 是一个多阶段 LLM 编排框架，通过 subprocess（`Popen`）或 SDK 方式调用 Claude、Gemini、Kimi 等 provider。当前的超时机制仅基于总运行时长（phase-level deadline），通过 `time.perf_counter() >= deadline` 检查。

现状问题：provider 子进程偶尔会进入"stall"状态——进程存活但 stdout 完全停止输出。这种情况下，用户需要等待整个 phase timeout（默认 3600 秒）才能发现问题。实际上，正常工作的 provider 会持续产生 stream-json 输出（assistant messages、tool use blocks 等），一个健康的 provider 不应该长时间没有任何输出。

现有基础设施：
- `read_stream_lines()` 和 `start_stream_reader_threads()` 在 `providers/base.py` 中已实现 stdout/stderr 的流式读取
- 每个 subprocess provider 的 poll loop（如 Claude 的 0.5s `process.wait(timeout=0.5)` 循环）已提供了插入检查逻辑的自然位置
- `invoke_with_timeout_retry` 在 `core/retry.py` 中已实现 `ProviderTimeoutError` 的重试
- `TimeoutsConfig` 在 `core/config/models/features.py` 中已支持 per-phase 配置

## Goals / Non-Goals

**Goals:**
- 检测 provider 长时间无 stdout 输出的 stall 状态，并在可配置的 idle timeout 后主动终止
- stall 触发后自动利用现有重试机制重新发起请求
- 提供全局默认和 per-phase 的 idle_timeout 配置
- 同时覆盖 subprocess 和 SDK 两种 provider 模式
- 默认禁用（idle_timeout = None），不影响现有行为

**Non-Goals:**
- 不做 stdout 内容层面的健康判断（如检测是否产生有意义输出）——仅检测"完全无输出"
- 不修改 deep_verify 模块的 LLM client（其调用模式不同且已有独立超时）
- 不做跨 phase 的 stall 模式学习或自适应调整
- 不在此变更中引入 provider 级别的 health check / heartbeat 协议

## Decisions

### 决策 1: Stall 检测基于 last-output timestamp，而非 heartbeat

**选择**: 在 stream reader callback 中记录最后一次 stdout 输出的时间戳（`last_output_time`），在 provider 的 poll loop 中检查 `now - last_output_time > idle_timeout`。

**理由**:
- 复用现有的 `read_stream_lines` callback 机制，改动最小
- 不需要 provider 端支持任何协议
- 对所有 subprocess provider 通用

**备选方案**:
- 定期向 stdin 发送 ping（provider 不支持）
- 使用独立 watchdog 线程（增加复杂度，且 poll loop 已提供自然检查点）

### 决策 2: 复用 ProviderTimeoutError，而非新建 ProviderStallError

**选择**: stall 检测触发时，抛出 `ProviderTimeoutError`，在 message 中标注 `"idle timeout"` 以区分。

**理由**:
- `invoke_with_timeout_retry` 已经处理 `ProviderTimeoutError` 的重试逻辑，复用即可
- stall 本质上就是一种超时（idle timeout vs total timeout），不需要独立的异常处理路径
- 减少对 retry.py 和 handler 层的改动

**备选方案**:
- 新建 `ProviderStallError(ProviderTimeoutError)` 子类——增加了异常层级但目前没有需要区分处理的场景

### 决策 3: 使用线程安全的共享时间戳实现 last_output_time

**选择**: 使用 `threading.Lock` 保护的浮点数时间戳，在 stdout callback 中更新，在 poll loop 中读取。

**理由**:
- stdout reader 和 poll loop 运行在不同线程
- Lock 开销极小（每次 readline 和每 0.5s poll 各一次）
- 简单可靠

**备选方案**:
- 使用 `threading.Event` + timer——更复杂，不如直接比较时间戳直观
- 使用 atomic float（Python 没有原生支持，需要 ctypes 或第三方库）

### 决策 4: idle_timeout 配置放在 TimeoutsConfig 中

**选择**: 在 `TimeoutsConfig` 中新增 `idle_timeout: int | None = None` 字段（全局），以及 `get_idle_timeout(phase)` 方法。

**理由**:
- 与现有的 `default` / per-phase timeout 配置风格一致
- 通过 `get_idle_timeout()` 统一解析，后续可扩展 per-phase idle timeout
- 默认 None 表示禁用，向后兼容

### 决策 5: SDK provider 使用 asyncio 定时检查

**选择**: 对于 `ClaudeSDKProvider`，在 `_invoke_async` 中使用 asyncio task 包装，定期检查 last message timestamp。

**理由**:
- SDK 的消息通过 async generator（`client.receive_messages()`）接收，不使用 subprocess poll loop
- 可以在 `asyncio.wait` 中加入周期性唤醒来检查 idle timeout
- 与 SDK 的 async 架构一致

## Risks / Trade-offs

**[Risk] 正常的长时间思考被误判为 stall** → Mitigation: 默认禁用 idle_timeout；建议 idle_timeout 设置为 180-300 秒（3-5 分钟），远大于正常思考间隔。Provider 在思考时通常也会产生工具调用的 stream-json 事件。

**[Risk] idle timeout 与 total timeout 交互** → Mitigation: idle timeout 触发时依然走 `ProviderTimeoutError` + retry 路径，total timeout 依然作为最终兜底。两者独立计算，互不干扰。

**[Risk] 线程安全竞态** → Mitigation: 使用 `threading.Lock` 保护时间戳读写。即使存在微小的竞态窗口（读到稍旧的值），也只会导致 stall 检测延迟最多 0.5 秒（一个 poll 周期），不影响正确性。

**[Trade-off] 不区分 stall error 和 total timeout error** → 在日志中通过 message 区分。如果未来需要不同的重试策略，可以在不破坏兼容性的前提下引入 `ProviderStallError` 子类。
