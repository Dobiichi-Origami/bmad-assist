## Context

在 ca56493 中实现了 `idle_timeout` stall 检测功能，支持所有 provider 在输出停滞时自动终止并重试。但相关用户文档和示例配置没有同步更新，导致用户无法通过文档发现和正确使用该功能。

当前文档状态：
- `docs/configuration.md` Timeouts 章节列出了 `default`、`retries` 和各 phase 超时，但没有 `idle_timeout`
- `bmad-assist.yaml.example` 的 timeouts 区块没有 `idle_timeout`
- `docs/troubleshooting.md` 有 timeout 相关排查但没有 stall 场景
- `docs/providers.md` 没有提及 stall 检测能力

## Goals / Non-Goals

**Goals:**
- 用户能通过文档了解 `idle_timeout` 的作用、配置方式和推荐值
- 示例配置中包含 `idle_timeout`（注释形式），方便用户发现和启用
- 排查文档覆盖 provider 卡死场景，引导用户使用 stall 检测

**Non-Goals:**
- 不修改任何代码
- 不添加 per-phase idle_timeout 支持（当前是全局配置）
- 不修改 CHANGELOG（属于 release 流程）

## Decisions

### 1. idle_timeout 在 configuration.md 中的位置

放在 Timeouts 章节的 YAML 示例块内，紧跟 `retries` 之后，并在 YAML 块下方添加简短说明段落。

**理由**：`idle_timeout` 与 `retries` 是配合使用的功能，放在一起便于用户理解关联。

### 2. 示例配置中使用注释形式

在 `bmad-assist.yaml.example` 中以 `# idle_timeout: 180` 的注释形式呈现。

**理由**：该功能默认禁用（None），注释形式与现有约定一致（不强制启用），同时让用户知道该选项存在。

### 3. 推荐值范围

文档推荐 120-300 秒，默认示例用 180 秒。

**理由**：最小值 30 秒过于敏感（正常编译或测试可能短暂无输出），180 秒是设计文档建议的合理起点。

### 4. troubleshooting 采用独立章节

在 troubleshooting.md 中添加独立的 "Provider Stall / Hang" 章节，而非嵌入现有 timeout 章节。

**理由**：stall（无输出卡死）和 timeout（总时间超限）是不同症状，独立章节更清晰。

## Risks / Trade-offs

- [文档与代码版本脱节] → 文档引用 spec 中的精确字段名和约束（ge=30, default=None），降低偏差风险
- [推荐值可能因场景而异] → 文档明确说明推荐范围而非单一值，并提示用户根据 provider 特性调整
