## Context

bmad-assist 是一个自动化开发流程工具，基于 bmad-method 构建，提供 18 个 atomic phase 跨 3 个 scope（epic_setup、story、epic_teardown）的自动化执行。当前架构中，每个 phase 独立执行 LLM 调用，缺乏：

1. **跨 epic 的经验积累**——每个 epic 都从零开始，无法复用项目知识
2. **执行后审查**——LLM 输出无人检查，跑偏无法检测
3. **纠正重试**——检测到问题后无恢复机制

设计文档 v6 已完成（`docs/digital-twin/digital-twin-design.md`），明确了核心定位：Twin 是使用者在自动化流程中的代理，通过事后审查 + 自检清单 + RETRY 来应对结构性跑偏。

现有约束：
- Twin 不是 agent with tools——单次 LLM call → 解析 YAML → 代码执行文件 I/O
- 不引入 DORMANT/ARCHIVED 状态，页面只有存在/不存在
- 不使用数字 confidence——用 tentative/established/definitive 单词表达
- 不做 load_pages_by_priority——只有 INDEX + guide 页（Strategy D）

## Goals / Non-Goals

**Goals:**
- 实现 Experience Wiki 基础设施，支持 markdown 页面 I/O、INDEX 自动生成、Strategy D 最小加载
- 实现 Twin reflect——phase 执行后审查 LLM 输出、检测跑偏、生成 wiki 更新、做决策
- 实现 Twin guide——从 wiki 生成 compass 注入 phase 执行前
- 实现 ExecutionRecord 数据结构——组装 reflect 所需完整输入
- 实现自检清单注入——让跑偏在 LLM 输出中显性化
- 实现 Runner 集成——将 Twin 接入主循环，含 RETRY 逻辑和失败降级
- 实现 Compiler compass 支持——compiled prompt 支持 `<compass>` 段

**Non-Goals:**
- 不实现 DORMANT/ARCHIVED 页面状态或 archive action
- 不实现 reflect_budget_tokens 或 INDEX 截断（v6 已移除）
- 不实现 §4.8 链接一致性检查（v6 已移除）
- 不实现 §4.10 经验膨胀控制（v6 已移除）
- 不实现 ExecutionRecord.experiences: str 字段（wiki loading 由 build_reflect_prompt 处理）
- 不实现 Twin 主动干预执行过程——只做事后审查
- 不实现 Twin 多步 agent 调用——单次 LLM call 完成

## Decisions

### D1: Twin 是单次 LLM call，不是 agent

**选择**: Twin.reflect() 和 Twin.guide() 各自是单次 LLM 调用 → 解析 YAML → 代码执行
**否决**: Twin 作为 agent 持有 tools，多步推理和执行
**理由**: Agent 循环增加复杂度和不可预测性。单次调用 + 结构化输出（YAML）更可控、更可调试。文件 I/O 由代码执行而非 LLM 直接操作。

### D2: Strategy D 最小加载——只加载 INDEX + guide 页

**选择**: reflect 只加载 INDEX.md + guide-{phase_type}，约 800-1800 token
**否决**: Strategy A（全加载）、Strategy B（优先级加载 load_pages_by_priority）、Strategy C（按需加载）
**理由**: v6 评审结论——Twin 通过 INDEX 了解所有页面存在，但只读 guide 页的完整内容。EVOLVE 只能对已加载的页面执行。UPDATE 的 append_evidence 不需要读页面内容。最小加载减少 token 消耗和注意力稀释。

### D3: Confidence 用单词表达，代码派生而非 Twin 设定

**选择**: tentative / established / definitive，由 occurrences 派生
**否决**: 数字 confidence（1-5）、★符号、Twin 直接设定
**理由**: 数字映射引入人为判断偏差。代码从 evidence occurrences 派生更客观——1 次 = tentative，2-4 次 = established，5+ 次 = definitive（需 challenge mode）。Negative patterns 最高 established。

### D4: RETRY 逻辑——git stash + 纠正 compass 追加

**选择**: RETRY 时 git stash 还原工作目录，纠正 compass 追加到原有 compass 后面（不替换），correction compass 从 reflect result 生成
**否决**: 直接在脏工作目录重试、替换原有 compass
**理由**: 脏工作目录会导致 phase 误判已完成的工作。追加而非替换保留原始 compass 上下文，纠正信息作为补充。

### D5: EVOLVE 使用 {{EVIDENCE_TABLE}} 占位符

**选择**: EVOLVE 输出中用 {{EVIDENCE_TABLE}} 标记 evidence 表位置，代码保留原始 evidence 表
**否决**: 让 Twin 重写整个 evidence 表
**理由**: Twin 不应修改已有 evidence 数据，只更新页面其他内容。代码替换占位符为原始 evidence 表，保证数据完整性。

### D6: Parse 失败降级——区分首次和重试

**选择**: is_retry=False → CONTINUE（继续流程）；is_retry=True → HALT（停止流程）
**否决**: 任何解析失败都 HALT、任何失败都 CONTINUE
**理由**: 首次失败可能是偶发的输出格式问题，不应阻塞整个流程。但重试后仍失败说明系统性问题，继续可能导致不可控行为。

### D7: 子串去重只警告，不自动转换

**选择**: 检测到新页面名是已有页面名的子串时只发出警告，不自动将 CREATE 转为 UPDATE
**否决**: 自动将 CREATE pattern-x 转为 UPDATE pattern-x-y
**理由**: 自动转换可能误判意图。Twin 可能有充分理由创建子串页面。警告让人类有机会在审查时干预。

### D8: 自检清单从上游 acceptances 派生

**选择**: 每个 phase 的自检清单直接从该 phase 的上游验收条件（checklist.md / instructions.xml）派生
**否决**: Twin 动态生成自检清单、通用固定自检清单
**理由**: 上游 acceptances 是已定义的、可审查的标准。动态生成引入不确定性，固定清单无法覆盖 phase 特异性。

### D9: Challenge mode 每 5 epics 触发

**选择**: 每 5 个 epic 对 negative pattern 做 challenge——质疑其是否仍成立，避免过时 negative pattern 永久抑制行为
**否决**: 从不 challenge、每次 reflect 都 challenge
**理由**: Negative pattern 如果不再成立却永久存在，会不合理地限制行为。但每次 challenge 增加不必要的 token 消耗和判断负担。5 epics 是合理间隔。

## Risks / Trade-offs

- **[Twin LLM 输出不可靠]** → YAML 解析容错（fix_content_block_scalars）+ 重试一次 + 降级策略（CONTINUE/HALT）
- **[Wiki 页面膨胀]** → EVOLVE 只能对已加载页面执行 + challenge mode 定期审查 negative patterns + 子串去重警告
- **[Reflect 增加延迟]** → guide 是辅助非关键（失败 → compass=None 继续）；reflect 是关键但可降级
- **[RETRY 浪费 token]** → max_retries 限制（默认 2）+ retry_exhausted_action 可配置（halt/continue）
- **[Self-audit 自我报告不可信]** → Twin 独立审查 + git diff 交叉验证（files_diff 是完整 diff 非 --stat）
- **[Guide compass 被稀释]** → 这是已知结构性问题，v6 的答案是：不靠注入防跑偏，靠事后审查 + RETRY 纠正
- **[新增 ~800 行代码的维护成本]** → 模块化拆分（wiki/execution_record/twin/prompts/config），各 ~80-200 行，单一职责
