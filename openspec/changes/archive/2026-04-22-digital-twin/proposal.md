## Why

bmad-assist 的自动化开发流程在长执行（如 dev_story 有 10 个 step、几十次 tool call）中存在结构性跑偏问题——顶部注入的 compass/control sentences 在长执行中会被稀释出注意力窗口，导致范围缩减、过早放弃、无依据跳过等漂移。同时，跨 epic 的项目经验（设计偏好、环境知识、失败模式）无法自动积累和复用。单靠注入防不住跑偏，需要事后审查 + 自检清单 + RETRY 纠正机制。

## What Changes

- 新增 **Experience Wiki** 文件系统——markdown 页面存储项目经验（环境、模式、设计偏好、指南），INDEX 自动维护，Strategy D 最小加载
- 新增 **Twin Reflect** 审查能力——phase 执行后独立审查 LLM 输出，检测跑偏，生成 wiki 更新（create/update/evolve），做决策（CONTINUE/RETRY/HALT）
- 新增 **Twin Guide** 辅助能力——从 wiki guide 页生成 phase-specific compass，注入 phase 执行前
- 新增 **ExecutionRecord** 数据结构——构建 Twin reflect 所需的完整输入（phase 信息、LLM 输出、self-audit、git diff）
- 新增 **自检清单注入**——各 workflow output-template 增加从上游 acceptances 派生的自检清单段，让跑偏显性化
- 新增 **Compiler Compass 支持**——compiled prompt 支持 `<compass>` 段插入
- 修改 **Runner 主循环**——集成 Twin guide/reflect，实现 RETRY 逻辑（git stash → 重试 → 纠正 compass 追加）
- 修改 **qa_remediate handler**——收集 all_llm_outputs，补全缺失的 response 字段
- 新增 **TwinProviderConfig**——provider/model/enabled/max_retries/retry_exhausted_action 配置

## Capabilities

### New Capabilities
- `wiki-infrastructure`: Wiki 文件 I/O、INDEX 自动生成、frontmatter 解析、页面验证、Strategy D 加载（只加载 INDEX + guide 页）、evidence 表提取、confidence 派生、YAML 容错、智能截断
- `execution-record`: ExecutionRecord 数据结构构建——从 state + result + git diff 组装 reflect 输入，self-audit 段解析
- `twin-reflect`: Twin 核心审查能力——组装 reflect prompt → 调用 LLM → 解析 YAML → apply_page_updates，含 phase-specific 审查指引、challenge mode、RETRY 降级、EVOLVE 安全保护
- `twin-guide`: Twin compass 生成能力——从 guide 页生成 phase-specific compass，guide 页不存在时从 env/pattern/design 推理
- `self-audit-checklists`: 各 workflow output-template 注入自检清单——从上游 acceptances 派生的 Completion Status + Phase-Specific Audit 段
- `twin-runner-integration`: Runner 主循环集成 Twin——guide() → compass 注入、reflect() → apply_page_updates() → decision 处理、RETRY 逻辑（git stash + 纠正 compass 追加）、失败降级
- `compiler-compass`: Compiler 支持 `<compass>` 段——CompilerContext 增加 compass 字段，generate_output 中在 mission 后插入 compass

### Modified Capabilities
<!-- 无现有 spec 需要修改——qa_remediate 修补和 runner 集成属于新 capability 的实现细节 -->

## Impact

- **新增模块**: `src/bmad_assist/twin/`（__init__.py, wiki.py, execution_record.py, twin.py, prompts.py, config.py）
- **修改文件**: runner.py（主循环集成）、qa_remediate.py（response 字段）、compiler/types.py + output.py（compass 支持）、dispatch.py + handlers/base.py（compass 传递）、providers.py（twin 配置段）
- **修改 XML**: 12 个 workflow 的 instructions.xml/MD——注入自检清单段
- **新增目录**: `wiki/`（运行时生成的 wiki 页面存储，gitignored）
- **依赖**: 无新外部依赖，使用现有 LLM provider 基础设施
- **配置变更**: providers.yaml 增加 twin 段（provider, model, enabled, max_retries, retry_exhausted_action）
