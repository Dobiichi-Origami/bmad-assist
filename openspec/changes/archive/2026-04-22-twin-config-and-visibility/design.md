## Context

Digital Twin 模块已实现并通过 199 项测试，但从未在真实运行中成功启用。根本原因链：

1. conda 环境中的发布包不包含 `twin/` 模块（`ModuleNotFoundError`）
2. `TwinProviderConfig.enabled` 默认 `True`，即使没配 `twin:` 段也"看起来启用"
3. Runner 中 `from bmad_assist.twin.twin import Twin` 失败被 `except Exception` 吞掉
4. 无 CLI 参数或环境变量可控制 Twin 开关
5. `hasattr(config.providers, 'twin')` 永远为 True（Pydantic 字段有默认值），形同虚设

当前类似功能（QA、TEA）的控制模式：
- QA: `--qa` CLI 参数 → `BMAD_QA_ENABLED=1` 环境变量
- TEA: `--tea` CLI 参数 → `BMAD_TEA_LOOP=1` 环境变量

Twin 应遵循相同的模式。

## Goals / Non-Goals

**Goals:**
- `TwinProviderConfig.enabled` 默认 `False`，需显式启用
- 提供 `--twin` CLI 参数和 `BMAD_TWIN_ENABLED` 环境变量
- Runner 中 Twin 状态有明确日志输出
- 清理无意义的 `hasattr` 防御代码
- 所有改动有对应测试覆盖

**Non-Goals:**
- 不修改 Twin 的 reflect/guide 核心逻辑
- 不修改 wiki 基础设施
- 不解决打包发布流程问题（editable install 已解决当前开发需求）
- 不添加 `--no-twin` 参数（默认就是关闭的，不需要）

## Decisions

### D1: `enabled` 默认值改为 `False`

**选择**: `enabled: bool = False`
**替代方案**: 保持 `True` 但在 runner 里加更多检查 → 不选，因为默认启用一个重度功能（每 phase 2 次 LLM 调用）不符合预期
**理由**: 与 QA/TEA 一致，默认关闭、按需开启。之前默认 True 但实际跑不通，给用户错误预期。

### D2: CLI 参数 `--twin` 映射到 `BMAD_TWIN_ENABLED` 环境变量

**选择**: 复用 QA/TEA 的模式：CLI 参数设环境变量 → 配置加载时读取覆盖
**替代方案**: 直接修改 Config 对象 → 不选，因为要和 QA/TEA 保持一致的模式
**实现**: 在 `cli.py` 添加 `--twin` 参数，设 `os.environ["BMAD_TWIN_ENABLED"] = "1"`；在 `loaders.py` 的配置后处理中检查此变量并覆盖 `providers.twin.enabled`

### D3: 环境变量覆盖优先级

**选择**: `BMAD_TWIN_ENABLED` 环境变量 > YAML 配置 > 默认值（False）
**理由**: CLI 参数是用户最强意图信号，应覆盖文件配置。与 `BMAD_QA_ENABLED` 行为一致。

### D4: Runner 日志改进

**选择**: 在 Twin 分支入口处加 `logger.info("Twin %s", "enabled" if twin_config.enabled else "disabled")`，guide 失败时用 `logger.warning("Twin guide failed: %s", e)` 替代现有隐式吞异常
**替代方案**: 抛出异常终止运行 → 不选，Twin 失败不应阻塞主流程
**理由**: 保持现有容错行为（Twin 失败不阻塞），但让用户能在日志中看到状态。

### D5: 清理 `hasattr` 防御

**选择**: 直接用 `config.providers.twin` 替换 `config.providers.twin if hasattr(config.providers, 'twin') else None`
**理由**: Pydantic 模型字段有默认值，`hasattr` 永远 True，代码无实际作用。

## Risks / Trade-offs

- **[Breaking] `enabled` 默认值变更** → 用户需在配置或 CLI 中显式启用。但之前的"启用"是假的（静默失败），所以实际无功能回退。
- **环境变量覆盖不可逆** → 一旦设了 `BMAD_TWIN_ENABLED=1`，YAML 中 `enabled: false` 无法关闭 → 可接受，因为这是 CLI 参数的明确意图，与 QA 行为一致。
