# bmad-assist 与 OpenSpec 对比

> 两个 AI 原生开发工具的设计哲学、适用场景和实际取舍

---

## 各是什么

**bmad-assist** 是 BMAD Method 的自动化执行引擎。它把 BMAD 第 4 阶段（Implementation）中从 Story 到代码的全流程自动化——编译器构建完整 Prompt，状态机驱动 18 个原子 Phase 依次执行，多 LLM 协同工作，Digital Twin 事后审查防止跑偏。

**OpenSpec** 是 Fission AI 开源的 spec-driven 开发框架。它给项目加一层轻量规格——每次变更（change）都有独立的 proposal、specs、design、tasks，AI 按规格实现任务，完成后归档，规格增量同步到项目级持久化 spec 库。

两者都在解决"让 AI 可靠地写代码"这个问题，但切入角度和设计哲学完全不同。

---

## 核心差异一览

| 维度 | bmad-assist | OpenSpec |
|------|-------------|----------|
| **方法论绑定** | 深度绑定 BMAD Method | 不绑定任何方法论 |
| **自动化深度** | 全自动流水线，人工只做启动和异常决策 | 半自动，人工在每个 artifact 之间做审查和推进 |
| **执行模式** | 状态机驱动，18 原子 Phase 严格编排 | 流式推进，propose → specs → design → tasks → apply，可随时回退 |
| **Prompt 构建** | 编译器系统：XML 模板 + 补丁 + 变量注入 + 上下文压缩 | AI 自行理解上下文，OpenSpec 只提供结构化约束 |
| **质量保障** | 多 LLM 并行审查 + Digital Twin 事后审查 + RETRY | Spec 定义"做什么"，AI 按 spec 做，但无执行后审查 |
| **经验积累** | Experience Wiki（自动生成、跨 Epic 持久化） | 持久化 spec 库（delta sync 归档时同步） |
| **粒度** | Phase 级（dev_story、code_review 等） | Change 级（一次功能变更） |
| **学习曲线** | 高（需理解 BMAD 方法论 + 18 Phase + 配置体系） | 低（4 个 artifact + 4 条命令，10 分钟上手） |

---

## 设计哲学对比

### bmad-assist：确定性的极致

bmad-assist 的核心信条是**编译器优于 Agent**——不给 LLM 猜测上下文的机会，而是把一切塞进 Prompt：

```
工作流 XML → 补丁系统 → 战略上下文注入 → 源码上下文注入 → 变量解析 → Compass 注入
                                                              ↓
                                                         完整 Prompt
                                                              ↓
                                                         LLM 执行
```

代价是：系统复杂度高，配置项多，单个 Story 跑完全量流水线需要约 4 小时。但收益是：LLM 拿到的 Prompt 是完整的、确定的、可复现的。

### OpenSpec：流式的轻量约束

OpenSpec 的核心信条是**fluid not rigid**——不设严格的阶段门控，artifact 可以随时更新，实现过程中发现设计问题可以回头改 spec：

```
/opsx:propose  →  一次性生成 proposal + specs + design + tasks
/opsx:apply    →  按 tasks 逐项实现，随时可以更新上游 artifact
/opsx:archive  →  归档变更，delta spec 同步到持久化 spec 库
```

代价是：执行质量依赖 LLM 本身对 spec 的遵循程度，没有独立的审查层。但收益是：上手快，流程灵活，适合快速迭代。

---

## 各自擅长的场景

### bmad-assist 适合

- **长程、多 Epic 项目**——需要跨 Epic 积累经验，BMAD 的结构化流程提供长程指引
- **质量要求高**——多 LLM 审查 + Twin 事后审查 + RETRY，多层防护
- **团队有 BMAD 方法论基础**——已经用 BMAD 做了 PRD、架构、UX，第 4 阶段顺接
- **无人值守需求**——启动后希望自动跑完，不需要每步人工确认

### OpenSpec 适合

- **中短期功能开发**——一个 change 就是一个功能，做完归档
- **快速迭代**——spec 可以边写边改，不锁定
- **棕地项目**——不要求项目从 BMAD 方法论开始，直接在现有代码上加 spec 层
- **人工在环**——每个 artifact 之间人工审查，不追求全自动

---

## 实际使用中的取舍

我们在 bmad-assist 项目自身的开发中同时使用了两个工具，实际的体验是：

### OpenSpec 的实际优势

**1. 上手即用，无需方法论铺垫**

OpenSpec 不要求项目先有 PRD、架构文档、Epic 拆分。任何项目，任何时候，`/opsx:propose add-dark-mode` 就开始。bmad-assist 则要求项目已经完成 BMAD 的前三个阶段，否则编译器注入的战略上下文就是空的。

**2. 变更粒度自然**

OpenSpec 的 change 就是一个功能变更，粒度自然——加暗色模式、修一个 bug、重构一个模块，都是一个 change。bmad-assist 的粒度是 Phase，一个 Story 要跑七八个 Phase 才能完成，中间不可中断。

**3. 流程灵活，容错好**

实现中发现设计有问题？OpenSpec 允许回头改 design 和 spec，然后继续 apply。bmad-assist 的 Phase 编排是线性的，如果 create_story 阶段产出的规格有问题，要到 dev_story 阶段才会暴露，这时只能靠 Twin 的 RETRY 来纠正。

**4. 持久化 spec 有增量价值**

每次归档时，OpenSpec 会把 change 级的 spec 同步到项目级 spec 库。随着项目演进，spec 库逐渐成为项目行为的权威描述——WHEN/THEN 格式的场景定义，比代码注释更精确。bmad-assist 的 Experience Wiki 是 Twin 自主生成的经验积累，侧重于"怎么做更好"而非"系统应该做什么"。

### bmad-assist 的实际优势

**1. 全自动，真正无人值守**

OpenSpec 的 `/opsx:apply` 仍然需要人在每个关键节点审查。bmad-assist 启动后可以跑完整个 Epic，中间不需要人工干预（除非 Twin HALT）。这是最根本的区别——OpenSpec 是半自动的，bmad-assist 是全自动的。

**2. 多层质量保障**

bmad-assist 有三层质量保障：
- 多 LLM 并行审查（validate_story、code_review）
- Digital Twin 事后审查（reflect → CONTINUE/RETRY/HALT）
- 经验积累（Wiki 跨 Epic 持久化，越用越准）

OpenSpec 的质量保障只有一层：spec 定义了"做什么"，AI 按照做。但 AI 是否真的按照做了？做出来的质量如何？没有独立的审查机制。

**3. 经验积累自动化**

bmad-assist 的 Twin 在每次 Phase 执行后自动提取经验、更新 Wiki。OpenSpec 的持久化 spec 需要在归档时显式同步——如果实现过程中发现的环境陷阱、设计偏好没有被显式写入 spec，它就丢了。

---

## 可以一起用吗

可以，而且我们实际就是这么做的。

在 bmad-assist 项目自身的开发中，OpenSpec 是主要的变更管理工具——16 次归档的变更记录了从 auto-commit 到 Digital Twin 的完整演进。bmad-assist 则被用于其他 BMAD 项目的自动化执行。

两者的分工可以这样理解：

| 关注点 | 用哪个 |
|--------|--------|
| 定义"做什么"（功能规格、设计决策） | OpenSpec |
| 自动执行"怎么做"（编译 Prompt、跑 LLM、审查结果） | bmad-assist |
| 经验积累（环境知识、模式偏好） | bmad-assist (Twin Wiki) |
| 系统行为规格（WHEN/THEN 场景） | OpenSpec (持久化 spec) |
| 快速功能开发（不绑定方法论） | OpenSpec |
| 长 Epic 全流水线自动化 | bmad-assist |

---

## 总结

```
bmad-assist:  重流程、全自动、多层审查、强方法论绑定
OpenSpec:     轻流程、半自动、spec 驱动、方法论无关
```

它们不是替代关系，而是互补关系：

- **bmad-assist 解决的是"怎么让 AI 自动且可靠地完成一整套流程"**——它的代价是复杂度高、耗时长
- **OpenSpec 解决的是"怎么让 AI 和人在功能级别对齐做什么"**——它的代价是执行质量依赖 AI 本身

如果项目已经有 BMAD 方法论的基础、需要无人值守的全流水线自动化，选 bmad-assist。如果项目只是想让 AI 开发功能时有个规格约束、需要快速上手，选 OpenSpec。两者可以共存——OpenSpec 管变更规格，bmad-assist 管自动化执行。
