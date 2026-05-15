# BMAD 自动化演变路径

> 记录从 Epic Agent Team 到 bmad-assist + Digital Twin 的架构演变历程

---

## 背景：为什么做这件事

BMAD Method 是一套完整的软件开发生命周期方法论——从产品需求、架构设计到代码实现，它用结构化的流程和文档把开发过程组织得井井有条。在实际使用中，我确认了一件事：**BMAD 在长程任务编排上是有效的**。一个包含多个 Epic、几十个 Story 的项目，BMAD 能够清晰地定义每一步该做什么、需要什么输入、产出什么结果。

但问题在于：**我不想手动盯每一次调用。**

BMAD 的第 4 阶段（Implementation）是一个高度重复的循环——每个 Story 都要经历创建规格、验证、开发、代码审查、测试等步骤，每一步都需要把正确的文档和上下文喂给 LLM，然后等待结果、判断是否通过、推进到下一步。一个项目可能有三五十个 Story，每个 Story 七八个步骤，这意味着上百次 LLM 调用需要人工触发和监控。

这不是 BMAD 的问题——BMAD 定义了"做什么"，但"怎么自动地做"是另一件事。我的目标很简单：

> **让 BMAD 的流程自动跑起来，不需要我盯着每一次调用，但最终结果仍然可靠。**

"可靠"是关键词。LLM 会跑偏——范围缩减、过早放弃、跳过关键步骤——这是长执行的固有特性。如果自动化只是简单地循环调用 LLM，跑偏了也不知道，那自动化就没有意义。所以自动化的核心挑战不是"怎么跑起来"，而是"怎么在没人盯的情况下仍然靠谱"。

这就是这条演变路径的出发点。从第一次尝试到现在的 bmad-assist + Digital Twin，每一次迭代都在回答同一个问题：**怎样在减少人工干预的同时，保证执行质量？**

---

## 总览

```
时间线 ─────────────────────────────────────────────────────────────────────────────▶

  v3.x            v4.0             v4.1            v5.0           bmad-assist          Digital Twin v6
  智能编排         确定性编排        路径隔离         状态简化         编译-执行引擎         观察-审查-经验层
  (废弃)          (转折点)         (补丁)          (简化)          (范式转移)           (新纪元)
    │                │                │               │                │                   │
    ▼                ▼                ▼               ▼                ▼                   ▼
  Agent 编排      Python 脚本      Fake Root       单一真相源      编译器+状态机        事后审查+RETRY
  "自由意志"      100%可预测       符号链接森林     sprint-status   18原子Phase          经验Wiki
```

三个核心认知的递进贯穿了整条演变路径：

| 认知 | 转折点 | 含义 |
|------|--------|------|
| 编排不需要智能 | v3 → v4 | 确定流程交给确定性系统，智能只在需要判断的地方使用 |
| Agent 不需要"自由" | v4 → bmad-assist | 编译器构建完整 Prompt，而非调用独立 Agent 进程 |
| 防跑偏不能靠注入 | bmad-assist → Twin | 事后审查可检测可恢复，优于执行前注入被稀释 |

---

## 第一阶段：v3.x — 智能编排层（已废弃）

**项目背景**：new-new-mobile-center / Epic Agent Team

**架构**：三层 Agent 架构，Coordinator 是智能 Agent

```
Epic-Coordinator（智能Agent，有"自由意志"）
    └── Subagent（智能Agent）
```

**核心理念**：用 Agent 编排 Agent，让 AI 自主协调开发流程

### 致命问题

1. Agent 有"自由意志"，会绕过约束——约束是"建议"而非"命令"
2. Agent 倾向于在同一上下文中直接执行（更方便）
3. 越"优化"越糟糕——因为优化的是不该存在的东西

### 核心教训

> **确定流程的编排不需要使用智能体**

这条教训成为后续所有设计的基石。

---

## 第二阶段：v4.0 — 确定性编排（转折点）

**项目背景**：new-new-mobile-center / Epic Agent Team

**核心洞察**：编排层改为 Python 脚本，100% 确定性，智能仅保留在任务层

```
❌ v3.x: 智能编排层（Coordinator Agent）→ 智能任务层（Subagent）
✅ v4.0: 确定性编排层（Python 脚本）    → 智能任务层（Subagent）
```

### 三层架构

| 层 | 类型 | 职责 | 是否智能 |
|---|---|---|---|
| Layer 1: Epic Runner | Claude Code Skill | Epic 级协调、异常决策 | 是 |
| Layer 2: Coordinator | Python 脚本 | Story 级编排、循环执行 | 否（100% 确定性） |
| Layer 3: Task Agent | Claude Code Subagent | 具体任务执行 | 是 |
| Layer 3.5: Review Agent | Claude Code Subagent | Epic 完成后审查 | 是 |

### 新增机制

- **本地评审机制**：不提交远端 PR，本地 git diff → Review Agent → merge/feedback
- **准出基线**：单测通过 + E2E 无增量 Skip/Failed
- **Code-Review 自迭代循环**：修改模式下 code-review-enhanced 自己循环直到无问题
- **文件存档机制**：feedback/ready-for-pr + timestamp + status 状态流转

### 解决了什么

Agent 绕过约束、执行不可预测、远端 PR 依赖、文件状态不清晰

### 遗留问题

Agent 路径逃逸、状态文件不一致、编排层仍需 Python 脚本 + Shell 脚本 + JSON 文件的状态管理

---

## 第三阶段：v4.1 — 路径隔离（补丁）

**项目背景**：new-new-mobile-center / Epic Agent Team

### 核心问题

Worktree 路径（如 `worktrees/epic-5/`）不包含项目名，Agent 通过项目名向上搜索定位项目根目录时会"逃逸"到主仓库，写入错误位置。

### 解决方案：Fake Root

在 `/tmp/agent-dev/` 下创建包含项目名的符号链接森林：

```
Worktree（实际代码）: worktrees/epic-5/
Fake Root（Agent 工作目录）: /tmp/agent-dev/new-new-mobile-center-epic-5/
    ├── node_modules → 主仓库链接（共享）
    └── .claude → 主仓库链接（共享）
```

Agent 在 Fake Root 中运行，路径包含项目名，搜索到此停止，不再逃逸到主仓库。

### 本质

为 LLM Agent 路径搜索行为做的 workaround——用符号链接欺骗 Agent 的路径定位逻辑。这本身就说明了 Agent 作为独立进程运行时的脆弱性。

---

## 第四阶段：v5.0 — 状态简化（收尾）

**项目背景**：new-new-mobile-center / Epic Agent Team

### 核心变更

sprint-status.yaml 成为唯一真相源：

- 删除 `status.json`、`progress.json` 等冗余状态文件
- `epic-config.json` 极简化，仅保留 epic_id 和 fake_root
- Coordinator 直接读取 sprint-status.yaml 判断 Story 状态
- Epic Runner 流程简化（不再负责创建 epic-config.json）

```
旧流程：分析依赖 → 创建 worktree → 写入 epic-config.json → 调用 coordinator
新流程：分析依赖 → 调用 dev-session-create.sh → 调用 run-coordinator.sh
```

### 本质

v4.x 系列的收尾——通过消除冗余来降低复杂度，但架构框架没有本质改变。Epic Agent Team 方案走到这里，其核心矛盾已经暴露：**用 Python 脚本 + Shell 脚本 + JSON 文件 + 符号链接来编排 Agent 进程，复杂度太高，脆弱性太强**。

---

## 第五阶段：bmad-assist — 编译-执行引擎（范式转移）

**项目背景**：bmad-assist（fork of bmad-method）

### 与 Epic Agent Team 的根本区别

| 维度 | Epic Agent Team (v3-v5) | bmad-assist |
|---|---|---|
| 编排方式 | Python 脚本调用 Claude CLI | Python 状态机 + 编译器系统 |
| 执行模型 | Subagent（独立进程） | 单进程内 Prompt 构建 → LLM 调用 |
| 代码隔离 | Git Worktree + Fake Root | 单仓库，state.yaml 持久化 |
| Phase 粒度 | 4 个 Task Agent 类型 | 18 个原子 Phase，3 个 Scope |
| 状态管理 | JSON 文件 + sprint-status.yaml | state.yaml（Pydantic 模型） |
| Prompt 构建 | Agent 自行理解上下文 | 编译器系统：工作流 XML → 变量注入 → 补丁 → 完整 Prompt |
| 多 LLM | 单 LLM 执行 | 9+ Provider、多 LLM 并行编排、FallbackProvider |
| 经验积累 | 无 | Digital Twin（下一阶段） |

### 三个关键设计选择

1. **编译器优于 Agent**：把"Agent 自行理解上下文"变成"编译器把所有上下文注入 Prompt"——确定性大幅提升
2. **单进程优于多进程**：不需要 Worktree/Fake Root/多进程协调——复杂度从基础设施层降到应用层
3. **状态机优于自由编排**：18 个原子 Phase 的执行顺序由配置驱动，而非 Agent 自由决策

### 核心架构

```
CLI (bmad-assist run)
  → run_loop(config, project_path, epic_list)
    → 编译器系统
        ├── 工作流 XML 加载
        ├── 补丁系统（去除交互元素）
        ├── 战略上下文注入（PRD/Architecture/UX，含 LLM 压缩）
        ├── 源码上下文注入（可配置 token 预算）
        ├── 变量解析（epic/story 数据、sprint 状态、模式等）
        └── Compass 注入（Twin 经验，插入 mission 与 context 之间）
    → Provider 层
        ├── 9+ LLM Provider（Claude/Gemini/Codex/OpenCode/Kimi/Copilot/Cursor/Amp 等）
        ├── 多 LLM 并行编排（Master 写代码，其他只读审查）
        ├── FallbackProvider 自动故障切换
        └── ToolCallGuard 工具调用监控
    → 18 原子 Phase 执行
        ├── epic_setup: tea_framework, tea_ci, tea_test_design, tea_automate
        ├── story: create_story → validate_story → validate_story_synthesis
        │         → atdd → dev_story → test_review → code_review → code_review_synthesis
        └── epic_teardown: trace, tea_nfr_assess, retrospective,
                          qa_plan_generate, qa_plan_execute, qa_remediate
    → 状态持久化
        └── state.yaml（Pydantic 模型，支持崩溃恢复和 resume）
```

---

## 第六阶段：Digital Twin v6 — 观察-审查-经验层（新纪元）

**项目背景**：bmad-assist / feat/digital-twin

### 核心认知

> **防跑偏不能靠注入，只能靠审查**

这是对 v4-v5 阶段"顶部 Compass 防跑偏"思路的根本否定：

```
❌ 注入防跑偏：Compass/control sentences 在长执行中必然被稀释
   （dev_story 有 10 个 step、几十次 tool call，顶部引导滚出注意力窗口）

✅ 事后审查防跑偏：Twin 有独立的上下文窗口，看完整输出
   查到就能修——RETRY + 纠正 compass 重新执行
```

推理链：
- 跑偏一定会在长执行中发生——这是事实
- 顶部注入防不住——结构性地不可能
- 但执行后审查可以查出——Twin 有独立的上下文窗口，看完整输出
- 查到就能修——RETRY + 纠正 compass 重新执行
- 自检清单让跑偏显性化——LLM 必须在输出末尾声明完成状态

### Twin 的运作模式

```
Twin.guide()  → 从经验生成 compass（辅助，非关键）
       ↓
execute_phase()  → 现有执行流程
       ↓
Twin.reflect()  → 审查完整输出、积累经验、决策 CONTINUE/RETRY/HALT
       ↓
  CONTINUE → 下一个 phase
  RETRY    → 带纠正 compass 重新执行（git stash → re-execute）
  HALT     → 停机，交由人工
```

### 三层对比审查

Twin 拿到 ExecutionRecord 后，对比三层信息：

| 对比层 | 对比内容 | 检测什么 |
|---|---|---|
| mission vs llm_output + self_audit | 被要求做什么 vs LLM 声称做了什么 | 范围缩减、目标偏离 |
| self_audit vs phase_outputs + git_diff | LLM 声称的结果 vs 客观事实 | 虚假完成声明 |
| 当前执行 vs experiences | 本次执行 vs 项目历史经验 | 重复失败模式、环境陷阱 |

### 被否决方案与 Twin 的区别

| 被否决的方案 | 否决原因 | Twin 如何不同 |
|---|---|---|
| Knowledge Bus + capture() | capture() 是空壳 | LLM 推理生成经验，不做机械提取 |
| SQLite 知识库 | 人不可读的二进制 | Markdown 文件，人可读可编辑 |
| 手动经验积累 | 自动化项目不可能人工审查 | Twin 自主生成和更新经验 |
| 规则校验 | 模型输出不确定，规则不够可靠 | LLM 判断，能处理不确定输出 |
| 顶部 compass 防跑偏 | 长执行中必然被稀释 | 事后审查 + 自检清单 + RETRY |
| 逐 task 拆分 | 太细 | Phase 粒度工作 |

### Experience Wiki：Karpathy Wiki 理念

| Karpathy Wiki 原则 | 在 Twin 中的实现 |
|---|---|
| 一页一概念 | 每个 pattern/env/design/guide 独立文件 |
| 链接而非堆叠 | `[[page-name]]` 双向链接，guide↔pattern 互链 |
| 页面会进化 | 同一页面 v1→v2→v3，认知加深时重写 |
| 索引即导航 | INDEX.md 从页面元数据自动生成 |
| 低摩擦 | Twin 每次最多创建 1 页 + 更新 1-2 页 |
| 人可编辑 | 每页 100-500 token，比大文件更容易审查 |

### 模型独立性

```
执行模型：config.providers.master（如 claude-sonnet，用于代码生成）
Twin 模型：config.twin.provider / model（如 claude-opus，用于判断和推理）
```

独立的原因：
1. 执行模型有跑偏倾向时，同一模型可能有相同盲点
2. Twin 需要强推理（检测微妙跑偏、生成抽象经验），应使用更强模型
3. Twin 调用量少（每 phase 1-2 次），但需要深度思考

---

## 演变线索总结

### 认知一：编排不需要智能（v3 → v4）

```
智能编排 → 确定性编排
"让 AI 自由协调" → "让脚本确定执行"
```

对 Agent 编排能力的否定——确定流程交给确定性系统，智能只在需要判断的地方使用。

### 认知二：Agent 不需要"自由"（v4 → bmad-assist）

```
脚本编排 Agent → 编译器编排 LLM
"调用 Agent 执行任务" → "构建完整 Prompt 让 LLM 执行"
```

对 Subagent 模式的否定——不需要独立的 Agent 进程，而是通过编译器把所有上下文注入到单个 Prompt 中，让 LLM 在充分信息下执行。消除了路径逃逸、状态文件协调等基础设施问题。

### 认知三：防跑偏不能靠注入，只能靠审查（bmad-assist → Digital Twin）

```
注入防跑偏 → 事后审查 + 纠正重试
"在执行前告诉 LLM 注意什么" → "在执行后审查是否跑偏，跑偏则重试"
```

对 Prompt 注入方式的否定——长执行中顶部的引导必然被稀释，唯有事后审查才能可靠检测跑偏，而 RETRY 机制让纠正成为可能。

---

## 当前系统的现实问题

演变到这里，并不意味着问题都解决了。bmad-assist + Digital Twin 这套系统仍然面对几个现实的困境。

### 流水线长度与成本的两难

bmad-assist 把 BMAD 的 Implementation 阶段拆解为 18 个原子 Phase。如果你全量配置——create_story、validate_story、validate_story_synthesis、atdd、dev_story、test_review、code_review、code_review_synthesis、retrospective……一个 Story 要跑七八个 Phase，每个 Phase 是一次独立的 LLM 调用（多 LLM 审查的 Phase 还不止一次）。再加上 Digital Twin 的 guide + reflect，每个 Phase 又多出 1-2 次调用。

实际效果：**单个 Story 全流程跑下来需要 4 个小时左右**，token 消耗更是可观。一个 Epic 有五六个 Story，跑完一整个 Epic 动辄一整天。

但如果你不全量配置——砍掉 validate_story、砍掉 atdd、砍掉 test_review——那质量保障就少了环节。BMAD 本身也有这个问题：方法论定义了完整流程，但人手动执行时也会因为时间压力跳步。自动化只是让这个两难更显性了——**每砍一个 Phase 省下的时间和钱，都以质量风险的形式转嫁到了下游**。

### 项目稳定性

bmad-assist 目前仍然不够稳定。作为一个活跃演进的项目，它在实际使用中会碰到不少 bug：

- Provider 层的兼容性问题——不同 LLM 的输出格式差异、SDK 版本更新导致的接口变化
- 编译器系统的边界情况——工作流 XML 模板解析失败、补丁应用异常
- 状态管理的竞态条件——resume 时状态不一致、Sprint 同步失败
- Twin 模块尚未经过大规模实战验证——reflect 的判断准确性、RETRY 的纠正效果、经验 Wiki 的积累质量，都需要更多项目验证

这些问题在手动执行 BMAD 时不会遇到（因为人在循环中可以随时修正），但在自动化流水线中，一个 bug 就可能导致整个 Epic 卡住。

### 模型稳定性的依赖

整个系统的可靠性深度依赖底层 LLM 的稳定性，而 LLM 并不可靠：

- **输出格式不稳定**：同样的 Prompt，不同时间可能产出不同格式的输出，导致解析失败
- **指令遵循波动**：LLM 有时遵循自检清单，有时忽略；有时按要求输出 YAML，有时输出自由文本
- **能力因模型而异**：Sonnet 和 Opus 对同一 Prompt 的遵循度不同，切换模型可能引入新的问题
- **长执行衰减**：即使有 Twin 审查，LLM 在单次执行中的注意力衰减仍是客观存在的

这些问题不是 bmad-assist 的代码能解决的——它们是当前 LLM 技术栈的固有局限。bmad-assist 做的是在 LLM 不可靠的前提下尽可能提高系统的容错能力，但"尽可能"不等于"足够"。

### 本质矛盾

这些问题的根源可以归结为一个本质矛盾：

> **自动化追求的是"无人值守"的可靠性，而 LLM 是一个不可靠的执行单元。**

每次演变都在缩小这个矛盾的张力——从"让不可靠的 Agent 编排"到"让确定性的编译器编排"，从"靠注入防跑偏"到"靠审查发现跑偏"——但矛盾本身没有消除，只是被管理在了更可控的范围内。在 LLM 本身变得更可靠之前，这个矛盾会一直存在。

---

## 一句话总结

> 从"让 AI 自由编排"到"让确定性系统编译 Prompt"，再到"让独立审查者事后检查并纠正"——每一次演变都在收窄 AI 的自由度，同时提高系统的可靠性和可预测性。
