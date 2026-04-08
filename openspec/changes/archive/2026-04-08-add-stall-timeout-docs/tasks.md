## 1. Configuration Reference (docs/configuration.md)

- [x] 1.1 在 Timeouts 章节的 YAML 示例块中 `retries` 之后添加 `idle_timeout: 180` 并附注释
- [x] 1.2 在 YAML 块下方添加段落说明 idle_timeout 的作用、默认值（None/禁用）、最小值（30s）和推荐范围（120-300s）

## 2. Example Configuration (bmad-assist.yaml.example)

- [x] 2.1 在 timeouts 区块中 `retries` 之后添加注释行 `# idle_timeout: 180  # 3m stall detection (None=disabled, min=30s)`

## 3. Troubleshooting (docs/troubleshooting.md)

- [x] 3.1 添加 "Provider Stall / Hang" 章节，描述症状（provider 进程无输出长时间挂起）
- [x] 3.2 在该章节中给出解决方案：启用 idle_timeout 配置，附 YAML 示例

## 4. Provider Documentation (docs/providers.md)

- [x] 4.1 在 provider 文档中添加简要说明：所有 provider 支持 idle timeout stall 检测，并交叉引用 configuration.md 的 Timeouts 章节
