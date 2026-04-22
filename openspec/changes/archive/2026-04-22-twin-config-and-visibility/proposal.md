## Why

Digital Twin 模块虽已实现并通过 199 项测试，但在实际使用中从未成功运行：conda 环境中的发布包不包含 `twin/` 模块、`enabled` 默认 `True` 导致用户以为已启用但实际静默失败、没有 CLI 或环境变量开关、异常被 `except Exception` 吞掉无任何可见反馈。用户无法感知 Twin 状态，也无法方便地启用或关闭它。

## What Changes

- **BREAKING**: `TwinProviderConfig.enabled` 默认值从 `True` 改为 `False`，Twin 需显式启用
- 新增 CLI 参数 `--twin`，设置环境变量 `BMAD_TWIN_ENABLED=1` 以启用 Twin
- 新增环境变量 `BMAD_TWIN_ENABLED`，在配置加载阶段覆盖 YAML 中的 `enabled` 值
- Runner 中 Twin 启动时输出 info 级别日志（"Twin enabled" / "Twin disabled"），失败时输出结构化警告而非静默吞异常
- 清理 runner 中无意义的 `hasattr(config.providers, 'twin')` 防御代码（Pydantic 字段始终存在）
- 在实验配置 YAML 中为需要 Twin 的配置添加 `twin:` 段示例

## Capabilities

### New Capabilities
- `twin-cli-toggle`: CLI 参数 `--twin` 和环境变量 `BMAD_TWIN_ENABLED` 控制 Twin 启用/关闭
- `twin-visibility`: Runner 中 Twin 状态日志和错误可见性改进

### Modified Capabilities
- `twin-runner-integration`: `enabled` 默认值从 `True` 改为 `False`；环境变量覆盖 YAML；清理 hasattr 防御；启动日志

## Impact

- **Breaking**: 现有无 `twin:` 段的配置文件将不再默认启用 Twin（之前是假启用，实际静默失败）
- **代码**: `twin/config.py`、`cli.py`、`core/config/loaders.py`、`core/loop/runner.py`、实验配置 YAML
- **测试**: `tests/twin/test_config.py` 需更新默认值断言；新增 CLI toggle 和环境变量的测试
