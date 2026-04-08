## Why

在 ca56493 中我们添加了 `idle_timeout` stall 检测功能，但文档（`docs/configuration.md`、`docs/troubleshooting.md`）和示例配置（`bmad-assist.yaml.example`）都没有更新来说明这个新配置项。用户无法通过阅读文档发现和正确配置 stall 检测。

## What Changes

- 在 `docs/configuration.md` 的 Timeouts 章节中添加 `idle_timeout` 字段说明和用法
- 在 `bmad-assist.yaml.example` 的 timeouts 区块中添加 `idle_timeout` 示例（注释形式）
- 在 `docs/troubleshooting.md` 中添加 provider 卡死（stall）的排查和解决说明
- 在 `docs/providers.md` 中简要提及 stall 检测能力

## Capabilities

### New Capabilities

- `stall-timeout-docs`: 补充 idle_timeout / stall 检测功能的用户文档和示例配置

### Modified Capabilities

（无需修改已有 spec 的需求定义，本次变更仅涉及文档）

## Impact

- 仅涉及文档和示例配置文件，无代码变更
- 受影响文件：`docs/configuration.md`、`docs/troubleshooting.md`、`docs/providers.md`、`bmad-assist.yaml.example`
