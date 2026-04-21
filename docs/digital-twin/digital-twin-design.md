# 数字孪生（Digital Twin）架构设计 v6

> 面向 bmad-assist 自动化开发流程的独立观察-审查-经验层

---

## 0. 核心定位

**数字孪生是使用者在自动化流程中的代理**——它在 phase 执行后审查结果、积累项目经验、判断是否跑偏、决定是否重试。

两个等价的核心价值：
1. **经验积累**——凝聚项目开发中的经验、设计偏好、环境知识，跨 epic 持久化
2. **跑偏审查 + 纠正重试**——检测执行模型的范围缩减、过早放弃、无依据跳过，并通过 RETRY 纠正

### 关键认知：防跑偏不能靠注入，只能靠审查

评审发现：单次注入的 compass/control sentences 在长执行中会被稀释——dev_story 有 10 个 step、几十次 tool call，顶部的引导必然滚出注意力窗口。

因此设计转向：**不试图在执行中防跑偏，而是让跑偏可检测、可恢复**。

- 跑偏一定会在长执行中发生——这是事实
- 顶部注入防不住——结构性地不可能
- 但执行后审查可以查出——Twin 有独立的上下文窗口，看完整输出
- 查到就能修——RETRY + 纠正 compass 重新执行
- 自检清单让跑偏显性化——LLM 必须在输出末尾声明完成状态

### 与被否决方案的区别

| 被否决的方案 | 否决原因 | 数字孪生如何不同 |
|-------------|---------|-----------------|
| Knowledge Bus + capture() | capture() 是空壳 | Twin 用 LLM 推理生成经验，不做机械提取 |
| SQLite 知识库 | 人不可读的二进制 | markdown 文件，人可读可编辑 |
| 手动经验积累 | 自动化项目不可能人工审查 | Twin 自主生成和更新经验 |
| 规则校验 | 模型输出不确定，规则不够可靠 | Twin 用 LLM 判断，能处理不确定输出 |
| 顶部 compass 防跑偏 | 长执行中必然被稀释 | 改为事后审查 + 自检清单 + RETRY |
| 逐 task 拆分 | 太细 | Twin 在 phase 粒度工作 |

---

## 1. 架构

### 1.1 双模运作，优先级重排

```
优先级：  reflect(审查) > RETRY(纠正) > guide(辅助) > 经验积累(同时发生)
```

```
┌──────────────────────────────────────────────────────────────┐
│  runner.py 主循环                                             │
│                                                               │
│  while True:                                                  │
│    ┌──────────────┐                                           │
│    │ Twin.guide() │ ──→ 从经验生成 compass（辅助，非关键）      │
│    └──────────────┘                                           │
│           │                                                   │
│           ▼                                                   │
│    ┌──────────────────┐                                       │
│    │ execute_phase()  │  现有执行流程                          │
│    └──────────────────┘                                       │
│           │                                                   │
│           ▼                                                   │
│    ┌─────────────────────────────┐                            │
│    │ Twin.reflect()              │ ──→ 核心能力：              │
│    │  1. 审查完整输出，判断跑偏   │     审查跑偏               │
│    │  2. 提取经验，更新文件       │     积累经验               │
│    │  3. 决策 CONTINUE/RETRY/HALT│     纠正重试               │
│    └─────────────────────────────┘                            │
│           │                                                   │
│           ▼                                                   │
│    CONTINUE → 下一个 phase                                    │
│    RETRY   → 带纠正 compass 重新执行当前 phase                │
│    HALT    → 停机，交由人工                                    │
└──────────────────────────────────────────────────────────────┘
```

### 1.2 三层对比：Twin 如何判断跑偏

Twin 拿到 ExecutionRecord 后，对比三层信息：

| 对比层 | 对比内容 | 检测什么 |
|-------|---------|---------|
| mission vs llm_output + self_audit | 被要求做什么 vs LLM 声称做了什么 | 范围缩减、目标偏离 |
| self_audit vs phase_outputs + git_diff | LLM 声称的结果 vs 客观事实 | 虚假完成声明 |
| 当前执行 vs experiences | 本次执行 vs 项目历史经验 | 重复失败模式、环境陷阱 |

### 1.3 模型独立性

```
执行模型：config.providers.master（如 claude-sonnet，用于代码生成）
Twin 模型：config.twin.provider / model（如 claude-opus，用于判断和推理）
```

独立的原因：
1. 执行模型有跑偏倾向时，同一模型可能有相同盲点
2. Twin 需要强推理（检测微妙跑偏、生成抽象经验），应使用更强模型
3. Twin 调用量少（每 phase 1-2 次），但需要深度思考

---

## 2. 完整输出定义（ExecutionRecord）

### 2.1 result.stdout 的实际内容

经代码验证，两个 provider（claude_sdk.py / claude.py）行为一致：

| 消息类型 | 是否进入 stdout | 去向 |
|---------|---------------|------|
| `assistant` → `TextBlock` | ✅ | 拼接成 `result.stdout` |
| `assistant` → `ToolUseBlock` | ❌ | 仅用于 guard 检查 + 进度显示 |
| `tool_result` | ❌ | 不捕获 |
| `result`（统计） | ❌ | 仅显示 cost/duration/turns |

**结论：`result.stdout` = 纯文本输出，不含工具调用和返回。**

Twin 看不到 LLM 读了什么文件、改了什么文件、跑了什么命令。但这些信息可以从 git diff 获取客观事实。

### 2.2 ExecutionRecord 结构

Twin reflect() 收到的完整输入：

```python
@dataclass
class ExecutionRecord:
    # ── 1. 任务定义（被要求做什么）──
    phase: Phase
    mission: str                    # compiled prompt 的 <mission> 段
    epic_id: str
    story_id: str

    # ── 2. 执行产出（做了什么）──
    llm_output: str                 # result.stdout 完整输出，不截断
    self_audit: SelfAudit | None    # 从 llm_output 解析的自检结果

    # ── 3. 执行事实（客观发生了什么）──
    success: bool
    duration_ms: int
    error: str | None
    phase_outputs: dict[str, Any]   # PhaseResult.outputs（verdict, issues 等）
    termination_info: dict | None   # 是否被 guard 终止
    files_modified: list[str]       # git diff --name-only
    files_diff: str                 # git diff（全文，超长时截断，用于 Twin 交叉验证）
```

**关键设计决策**：
- `llm_output` 是**完整**的 `result.stdout`，不做截断。Twin 有独立的上下文窗口，吃得起
- `files_modified` 和 `files_diff` 从 git 获取——这是客观事实，不受 LLM 自述影响
- `files_diff` 是完整的 git diff（不加 --stat），让 Twin 可以交叉验证 LLM 的声明 vs 实际代码变更。超长时通过 `prepare_llm_output()` 截断——新建模块的 diff 可能几千行，head(1/4) 看到文件头和模块定义，tail(3/4) 看到测试和收尾
- 不包含工具调用链（tool_use/tool_result 量太大，轻量路径够用）

### 2.3 各 phase 的 PhaseResult.outputs 内容

| Phase | `response` (LLM输出) | 结构化输出 | 缺失/需修补 |
|-------|---------------------|-----------|------------|
| dev_story | ✅ `result.stdout` | `model`, `duration_ms` | 无 |
| create_story | ✅ `result.stdout` | `model`, `duration_ms` | 无 |
| validate_story_synthesis | ✅ `result.stdout` | `verdict`(PASS/FAIL) | 无 |
| code_review_synthesis | ✅ `result.stdout` | `verdict`(APPROVE/REJECT) | 无 |
| **qa_remediate** | **❌ 没有** | `status`, `issues_found/fixed`, `pass_rate` | **LLM 输出完全丢失，需修补** |
| validate_story / code_review | ❌ 多LLM并行 | `session_id`, `reviewer_count` | 各 reviewer 具体意见不可见 |

**qa_remediate 修补方案**：在 `_build_remediate_prompt()` 的每次迭代后，将 `result.stdout` 追加到 `all_llm_outputs: list[str]`。最终在 PhaseResult.ok() 中增加 `"response": "\n---\n".join(all_llm_outputs)`。

---

## 3. 自检清单（SelfAudit）

### 3.1 设计原理

自检清单的核心目的：**让 LLM 在输出末尾显式声明完成状态**。

- 跑偏发生在输出的结尾——"剩下的不做了"、"数据不足"
- 自检清单强制 LLM 在收尾时做显式声明
- 跑偏从隐性变为显性——Twin 可以直接对比 self_audit vs 客观事实

**注入位置：output-template 末尾**，不是 prompt 顶部。

- 当前大部分 workflow 的 `<output-template>` 是空的（dev_story、code_review 等）
- output-template 是 LLM 生成输出前最后看到的内容——recency bias 效果最强的位置
- 自检清单不需要"不被遗忘"——它就在 LLM 开始写输出时的眼前

### 3.2 通用自检（所有 phase）

```markdown
## Execution Self-Audit

### Completion Status
- Primary objective: [one sentence stating what was accomplished]
- Status: [COMPLETE / PARTIAL / DEFERRED]

### If PARTIAL or DEFERRED:
- What remains: [specific list]
- Justification: [specific reason for each item — "insufficient data" alone is NOT acceptable]
- What was attempted: [what you tried before deferring]
```

### 3.3 dev_story 专用

```markdown
### Implementation Audit
- Acceptance criteria addressed: [list each AC with DONE/PARTIAL/SKIPPED]
- Tests written: [count by type — unit/integration/e2e]
- Tests passing: [count] / Tests failing: [count + reason]
- Files created: [list]
- Files modified: [list]
- Deviations from architecture: [any, with reason]
```

### 3.4 qa_remediate 专用

```markdown
### Fix Audit
- Issues addressed: [list each issue ID with FIXED/SKIPPED/ESCALATED]
- For each SKIPPED: [specific reason + what was attempted]
- For each ESCALATED: [what makes this unfixable]
- Files modified: [list]
- New issues potentially introduced: [yes/no + details]
```

### 3.5 code_review_synthesis 专用

```markdown
### Review Audit
- Verdict: [APPROVE / MINOR_REWORK / REJECT]
- Critical issues found: [count + summary]
- Files requiring changes: [list]
- Reviewer consensus: [unanimous / split — describe split]
```

### 3.6 注入实现

修改各 workflow 的 `instructions.xml`，在 `<output-template>` 中加入对应的自检清单。例如 dev-story：

```xml
<output-template>
## Execution Self-Audit
### Completion Status
- Primary objective: [one sentence stating what was accomplished]
- Status: [COMPLETE / PARTIAL / DEFERRED]

### If PARTIAL or DEFERRED:
- What remains: [specific list]
- Justification: [specific reason for each item]
- What was attempted: [what you tried before deferring]

### Implementation Audit
- Acceptance criteria addressed: [list each AC with DONE/PARTIAL/SKIPPED]
- Tests written: [count by type]
- Tests passing: [count] / Tests failing: [count + reason]
- Files created: [list]
- Files modified: [list]
- Deviations from architecture: [any, with reason]
</output-template>
```

qa_remediate 使用自己的 `_build_remediate_prompt()`，在其 XML 模板 `qa/prompts/remediate.xml` 末尾加入 Fix Audit。

---

## 4. Experience Wiki

### 4.1 设计哲学：Karpathy Wiki

核心原则来自 Karpathy 的 wiki 理念，映射到 Twin 的经验系统：

| Karpathy Wiki 原则 | 在 Twin 中的实现 |
|-------------------|-----------------|
| 一页一概念 | 每个 pattern/env/design/guide 独立文件 |
| 链接而非堆叠 | `[[page-name]]` 双向链接，guide↔pattern 互链 |
| 页面会进化 | 同一页面 v1→v2→v3，认知加深时重写 |
| 索引即导航 | INDEX.md 是轻量目录，从页面元数据自动生成 |
| 低摩擦 | Twin 每次最多创建 1 页 + 更新 1-2 页 |
| 人可编辑 | 每页 100-500 token，比大文件更容易审查 |

**为什么不用单文件**：单文件的 consolidation 是不可逆退化——合并两条经验时细节被抹掉。wiki 页面是原子化的，新证据追加到同一页，理解加深时页面进化，不存在"压缩丢弃信息"的问题。

### 4.2 目录结构

```
_bmad-output/implementation-artifacts/experiences/
├── INDEX.md                       # 自动生成，代码维护
├── env-async-session.md           # 环境知识：async session 陷阱
├── env-testing-framework.md       # 环境知识：测试框架
├── pattern-test-first.md          # 成功模式：先写测试
├── pattern-skip-flaky-test.md     # 失败模式：跳过 flaky test
├── design-repository-pattern.md   # 设计偏好：repository pattern
├── design-api-versioning.md       # 设计偏好：API 版本化
├── guide-dev-story.md             # 阶段指引：dev_story
└── guide-qa-remediate.md          # 阶段指引：qa_remediate
```

**命名规范**：`{category}-{concept-name}.md`

| 类别前缀 | 含义 | 对应旧分类 |
|---------|------|-----------|
| `env-` | 环境知识 | Environment |
| `pattern-` | 成功/失败模式 | Patterns That Worked / Failed |
| `design-` | 设计偏好 | Design Preferences |
| `guide-` | 阶段性指引 | Active Guidance |

### 4.3 页面格式

每个页面由 **YAML frontmatter**（代码读取）+ **Markdown 正文**（Twin 读写 + 人可读）组成：

```markdown
---
category: pattern
sentiment: positive          # positive=成功模式, negative=失败模式
confidence: definitive       # tentative / established / definitive
last_updated: epic-22
occurrences: 3
source_epics: [epic-12, epic-15, epic-22]
links_to:
  - env-testing-framework
  - pattern-skip-flaky-test
---

# Test-First Approach

## What
Write tests before implementation for state-mutating code.

## Evidence
| Context | Result | Epic |
|---------|--------|------|
| Auth middleware bug fix | All tests passed, zero regression | epic-12 |
| Cache layer refactor | Safe refactoring with green tests | epic-15 |
| Rate limiter implementation | Caught edge case early | epic-22 |

## When This Applies
- State mutations (auth, caching, rate limiting)
- Service layer changes with side effects

## Evolution
- **[v2] epic-22**: Confirmed pattern — added rate limiter case, broadened "when applies" from auth-only to all state mutations
- **[v1] epic-12**: Initial observation — test-first worked for auth bug fix

## Links
- Used by: [[guide-dev-story]]
- Related: [[env-testing-framework]], [[pattern-skip-flaky-test]] (anti-pattern)
```

> **注意**：frontmatter 中只有 `links_to`（本页链接到哪些页面），没有 `linked_from`。
> 反向引用（哪些页面链接到本页）由代码在 `rebuild_index()` 时自动计算，不依赖 Twin 维护。
> 详见 4.4 节。

**失败模式示例**：

```markdown
---
category: pattern
sentiment: negative
confidence: established       # negative patterns cap at established (challenge mode can promote to definitive)
last_updated: epic-15
occurrences: 3
source_epics: [epic-12, epic-14, epic-15]
links_to:
  - env-testing-framework
  - env-async-session
---

# Skip Flaky Tests

## What
Marking failing tests as "flaky" without investigation.

## Evidence
| Context | Root Cause | Real Impact | Epic |
|---------|-----------|-------------|------|
| Cache test skipped as flaky | Missing Lock on shared state | Same bug reappeared in production | epic-12 |
| Auth test skipped as flaky | Race condition in test setup | Real auth bypass discovered later | epic-14 |
| Rate limiter test skipped | Async session not committed | Rate limiting silently failed | epic-15 |

## Why This Fails
Every "flaky" test in this project has revealed a real concurrency or state issue. The project uses async patterns where non-deterministic failures are almost always real bugs.

## Evolution
- **[v2] epic-15**: Third occurrence — confidence=established (negative pattern cap). Added "Why This Fails" section.
- **[v1] epic-12**: Initial observation — first flaky test was a real bug

## Links
- Anti-pattern of: [[pattern-test-first]]
- Related: [[env-async-session]], [[env-testing-framework]]
```

**Guide 页面示例**：

```markdown
---
category: guide
sentiment: neutral
confidence: definitive
last_updated: epic-22
occurrences: 5
links_to:
  - pattern-test-first
  - env-async-session
  - pattern-skip-flaky-test
  - design-repository-pattern
---

# Guidance for dev_story

## Watch-outs
- **ALWAYS** verify async session commit patterns → [[env-async-session]]
- **DO NOT** skip failing tests as "flaky" → [[pattern-skip-flaky-test]]
- Async session needs explicit `await session.commit()` after writes

## Recommended Patterns
- **PREFER** test-first approach for state mutations → [[pattern-test-first]]
- Use repository pattern for data access → [[design-repository-pattern]]

## Quality Checklist
- All acceptance criteria must be addressed (DONE/PARTIAL/SKIPPED)
- "Not essential" is not valid justification for skipping an AC
- Tests must pass before declaring COMPLETE
```

### 4.4 INDEX.md（代码自动生成，Twin 不写）

INDEX.md 不是 Twin 的输出，而是代码从所有页面的 frontmatter 自动生成的导航文件。**这消除了 INDEX 过时的风险**。

```markdown
# Experience Index

> Auto-generated from page frontmatter. Do not edit manually.

## Environment (2 pages)
- [[env-async-session]] — SQLAlchemy async session commit pitfalls [definitive]
- [[env-testing-framework]] — pytest + httpx AsyncClient setup [established]

## Patterns (2 pages)
- [[pattern-test-first]] — Write tests before implementation [definitive]
- [[pattern-skip-flaky-test]] — Skipping flaky tests masks real bugs [established]

## Design (2 pages)
- [[design-repository-pattern]] — Repository pattern for data access [established]
- [[design-api-versioning]] — URL path versioning [tentative]

## Guidance (2 pages)
- [[guide-dev-story]] — Guidance for dev_story phases [definitive]
- [[guide-qa-remediate]] — Guidance for qa_remediate phases [established]

---
Confidence: tentative / established / definitive
Total: 8 pages
```

**置信度等级定义**（单一表达，YAML frontmatter 和 INDEX 统一使用单词）：

| 值 | 含义 | INDEX 显示 | 何时升级 |
|---|------|-----------|---------|
| `tentative` | 单次观察，模式尚未确认 | `[tentative]` | 初始创建时默认 |
| `established` | 2次以上独立验证，结果一致 | `[established]` | 第二次独立证据出现时 |
| `definitive` | 3次以上跨上下文验证，高置信度 | `[definitive]` | 第三次跨上下文证据出现时 |

```python
CONFIDENCE_LEVELS = ["tentative", "established", "definitive"]

def derive_confidence(occurrences: int, sentiment: str = "positive") -> str:
    """从 occurrences 自动推导 confidence（Twin 不设置，代码派生）

    Negative patterns cap at established — only challenge mode allows definitive.
    """
    if occurrences >= 3:
        if sentiment == "negative":
            return "established"  # Negative patterns cap at established
        return "definitive"
    elif occurrences >= 2:
        return "established"
    return "tentative"
```

YAML frontmatter 中 `confidence` 直接写单词（如 `confidence: tentative`），**由代码从 occurrences 自动推导，Twin 不设置 confidence**：
- occurrences = 1（CREATE 时）→ tentative
- occurrences = 2 → established
- occurrences ≥ 3 → definitive

`update_frontmatter()` 在每次 UPDATE/EVOLVE 后递增 occurrences 并重算 confidence。Twin 的职责是判断"新证据是否匹配已有页面"（决定 CREATE/UPDATE/EVOLVE），置信度等级是客观的派生数据，不需要 Twin 的主观判断。

**生成规则**（代码逻辑）：

```python
def rebuild_index(pages_dir: Path) -> str:
    """扫描所有 .md 文件，从 frontmatter 提取元数据，生成 INDEX.md"""
    pages = []
    for path in sorted(pages_dir.glob("*.md")):
        if path.name == "INDEX.md":
            continue
        meta = parse_frontmatter(path)  # 提取 YAML frontmatter
        # 从正文第一行提取标题（# Title）
        title = extract_title(path)
        pages.append({
            "name": path.stem,
            "category": meta["category"],
            "sentiment": meta.get("sentiment", "neutral"),
            "confidence": meta.get("confidence", 1),
            "title": title,
            "last_updated": meta.get("last_updated", "unknown"),
        })

    # 按 category 分组，每组内按 confidence 降序
    # 生成 INDEX.md 内容
    # 写入 pages_dir / "INDEX.md"
```

### 4.5 页面生命周期

```
页面只有两种状态：存在 / 不存在。

不存在 → Twin CREATE → 存在
存在 → Twin UPDATE（追加证据/修改段落）→ 存在
存在 → Twin EVOLVE（理解质变，重写页面）→ 存在
```

没有 DORMANT、ARCHIVED 状态。页面一旦创建就永久存在，除非人工手动删除。
增长遵循 Karpathy 哲学——**页面只增不减，不用的页面不被删除，只是不被加载**。Twin 在 reflect prompt 中受两个约束：每次最多 2 个 PageUpdate，Evidence 表超过 10 行时应主动 evolve 精简。

### 4.6 Twin 的操作：PageUpdate

Twin 对 wiki 的所有写操作通过 `PageUpdate` 表达：

```python
class PageUpdate(BaseModel):
    page_name: str                          # "pattern-test-first"
    action: Literal["create", "update", "evolve"]
    content: str                            # create/evolve: 完整页面内容；update: 可选（见下方）
    append_evidence: dict | None = None     # 追加证据行（update only）
    section_patches: dict[str, str] | None = None  # 段落级替换（update only）
    reason: str                             # 为什么做这个操作
```

| Action | 含义 | Twin 输出 | 代码执行 |
|--------|------|----------|---------|
| `create` | 新概念，新建页面 | 完整页面内容 | `atomic_write(新文件)` + `rebuild_index()` |
| `update` | 同一概念新实例 + 可能的局部修改 | `append_evidence` 和/或 `section_patches` | 追加证据 + 替换指定段落 + 更新 frontmatter + `rebuild_index()` |
| `evolve` | 理解质变，重写页面 | 完整页面内容（用 {{EVIDENCE_TABLE}} 占位） | 替换 {{EVIDENCE_TABLE}} 为原始 evidence 表 + `rebuild_index()` |

> 注意：去掉了 archive action。页面一旦创建就不删除——遵循 Karpathy 哲学。
> 如果某个页面确实不再需要，人工可以手动删除。这不是 Twin 的职责。

**UPDATE 的三种用法**（可组合）：

```
用法 1：只追加证据
  append_evidence = {context: "...", result: "...", epic: "epic-22"}
  section_patches = null
  content = ""

用法 2：追加证据 + 修改非 evidence 段
  append_evidence = {context: "...", result: "...", epic: "epic-22"}
  section_patches = {"When This Applies": "Updated scope text..."}
  content = ""

用法 3：只修改非 evidence 段（无新证据）
  append_evidence = null
  section_patches = {"Why This Fails": "Deeper root cause analysis..."}
  content = ""
```

**section_patches 的代码实现**：

```python
def apply_section_patches(content: str, patches: dict[str, str]) -> str:
    """替换页面中指定段的内容。段由 ## Title 标识。"""
    for section_title, new_content in patches.items():
        # 找到 ## {section_title} 段，替换到下一个 ## 之前
        pattern = rf'(##\s+{re.escape(section_title)}\s*\n)(.*?)(?=\n##\s|\Z)'
        content = re.sub(pattern, rf'\1{new_content}\n', content, flags=re.DOTALL)
    return content
```

**UPDATE vs EVOLVE 的区分**：

```
UPDATE: 同一概念，增量变化
  例：pattern-test-first 在 epic-22 又成功了 → 追加证据
  例：理解范围微调 → section_patches 修改 "When This Applies"
  判定：页面核心结构不变，只是添加或微调

EVOLVE: 同一概念，理解质变
  例：从 "test-first 对 auth 有效" → "test-first 对所有状态变更有效"
  判定：What/When This Applies 段发生了质变，需要整体重写
  安全保护：
  1. evolve 前代码检查页面内容是否与 Twin 看到的版本一致（防止覆盖人工修改）
  2. EVOLVE 时 Twin 输出的 content 中用 {{EVIDENCE_TABLE}} 占位符替代 evidence 表——代码自动替换为原始 evidence 表，防止 Twin 丢失或篡改历史证据
```

**evolve 的安全保护**：

```python
elif update.action == "evolve":
    existing = read_page(wiki_dir, update.page_name)
    if existing is None:
        logger.warning(f"Twin tried to EVOLVE '{update.page_name}' but it doesn't exist. Treating as CREATE.")
        write_page(wiki_dir, update.page_name, update.content)
        continue
    # 安全检查：如果页面自 Twin 上次读取后被人工修改，拒绝 evolve
    # 通过比较 frontmatter 中的 last_updated 与当前 epic 判断
    existing_meta = parse_frontmatter(existing)
    if existing_meta.get("last_updated", "") != current_epic:
        logger.warning(
            f"EVOLVE of '{update.page_name}' skipped: page was modified outside Twin "
            f"(last_updated={existing_meta.get('last_updated')}, current={current_epic}). "
            f"Manual edits take priority."
        )
        continue
    # 保留原始 evidence 表：提取 → 替换占位符 → 覆盖写入
    original_evidence = extract_evidence_table(existing)
    evolved_content = update.content.replace("{{EVIDENCE_TABLE}}", original_evidence)
    # 保留 frontmatter 中的 occurrences + 自动推导 confidence
    evolved_content = update_frontmatter(evolved_content, epic_id=current_epic)
    write_page(wiki_dir, update.page_name, evolved_content)
```

### 4.7 去重：防止 Twin 创建重复页面

**最大风险**：Twin 创建 `pattern-test-first-auth.md` 但 `pattern-test-first.md` 已存在。

**防御层级**：

```
层级 1：Prompt 规则（主要防线）
  reflect prompt 中明确要求：
  "Before creating a new page, check the INDEX below.
   If a page already covers this concept, UPDATE or EVOLVE it instead.
   Do NOT create a new page for a concept that already has one."

层级 2：代码校验（兜底防线）
  代码在执行 PageUpdate(action="create") 前：
  1. 检查同名页面是否已存在 → 拒绝创建，日志警告
  2. 检查新页面名是否是已有页面名的子串或超串 → 日志警告（不阻止，不自动转换）
     例：Twin 创建 "pattern-test-first-auth"，但 "pattern-test-first" 已存在
     检测：page_name.startswith(existing) or existing.startswith(page_name)
  3. 检查同 category 下已有页面的标题是否高度相似 → 日志警告（不阻止，不自动转换）
     （从新页面 content 的 # Title 行与已有页面标题做 Levenshtein 比较）
  对层级 2 的警告，代码只记录日志，不做自动转换。
  理由：自动转换（CREATE → UPDATE）可能丢失 Twin 的创建意图——也许 Twin 认为新概念确实需要独立页面。
  如果自动转换是错的，会导致不相关的证据被追加到错误页面，比创建一个冗余页面更糟。

层级 3：人工干预（安全网）
  代码在日志中输出所有 PageUpdate 操作，用户可以事后审查
```

### 4.8 加载策略（Strategy D：INDEX 驱动，最小加载）

核心思路：**只给 Twin INDEX + 当前 phase 的 guide 页，不加载任何链接页面**。

Twin 是 LLM，它能从 INDEX 的摘要和置信度标签判断哪些页面相关。不需要代码替它做选择——这比代码的简单优先级排序更智能。如果 Twin 需要某个链接页面的内容来决定 EVOLVE，它可以在下次 reflect 时请求加载（但当前版本不支持动态加载，Twin 只能 EVOLVE 已读到的页面）。

```
Twin reflect():
  1. 读取 INDEX.md（~500-1500 token）
  2. 读取 guide-{phase_type}（~300 token，如存在）
  总计：~800-1800 token

  Twin 基于 INDEX 知道所有页面存在，但只读到了 guide 页的完整内容。
  对于未加载的页面，Twin 可以：
  - CREATE 新页面（不需要读现有页面）
  - UPDATE 现有页面（用 append_evidence，代码追加证据行，Twin 不需要知道现有内容格式）
  - EVOLVE 已加载的页面（guide 页）——Twin 没读过的不应重写

Twin guide():
  1. 读取 INDEX.md（~500-1500 token）
  2. 只读取 guide-{phase_type}（~300 token）
  总计：~800-1800 token
```

**INDEX 中需要包含什么信息让 Twin 做决策**：

```markdown
## Patterns (3 pages)
- [[pattern-test-first]] — Write tests before implementation [definitive] | pos | epic-32 | 5
  ↑名称    ↑标题摘要             ↑confidence标签   ↑sentiment ↑last_updated ↑occurrences
- [[pattern-skip-flaky-test]] — Skipping flaky tests masks real bugs [established] | neg | epic-30 | 4
- [[pattern-async-session]] — Async session needs explicit commit [established] | neg | epic-28 | 2
```

每条约 30-50 token，30 页的 INDEX ≈ 1000-1500 token。Twin 看到这个索引就能判断：
- `pattern-test-first` [definitive] pos → 高置信度成功模式，值得在审查时对比
- `pattern-skip-flaky-test` [established] neg → 中等置信度失败模式（negative pattern cap），如果 qa_remediate 又跳了 flaky test，直接匹配
- `pattern-async-session` [established] neg → 中等置信度，可能不加载全文也够

**初始化指令**（在 bmad-assist 首次运行时注入）：

当 INDEX 为空或 wiki 刚初始化时，reflect prompt 增加一段初始化指引：

```markdown
## Wiki Initialization

This is the first time the Twin is running for this project. The Experience Wiki is empty.

Your job is to establish the initial knowledge base from this execution. Create pages that capture:

1. **Environment knowledge**: What tech stack, frameworks, tools did you observe?
   → Create env-* pages (e.g., env-testing-framework, env-async-session)

2. **Patterns observed**: What worked? What failed? What pitfalls did you notice?
   → Create pattern-* pages (e.g., pattern-test-first, pattern-skip-flaky-test)

3. **Design preferences**: What architectural patterns or coding conventions did you observe?
   → Create design-* pages (e.g., design-repository-pattern)

4. **Phase guidance**: What should future executions of this phase type watch out for?
   → Create or update guide-* pages (seed pages already exist with basic checklists)

Focus on project-SPECIFIC knowledge. Generic advice like "always test your code" is NOT a valid experience.
Every page must contain evidence from THIS execution.
```

这段指引只在 INDEX 为空或页面数 < 3 时注入。后续 reflect 调用中不再需要——Twin 从现有页面学习格式和风格。

### 4.9 初始化

项目首次运行 Twin reflect 时，experiences/ 目录不存在。初始化流程：

```python
SEED_PAGES = {
    "guide-dev-story": """---
category: guide
sentiment: neutral
confidence: tentative
last_updated: seed
occurrences: 0
links_to: []
---

# Guidance for dev_story

## Watch-outs
(_Twin will populate based on experience_)

## Recommended Patterns
(_Twin will populate based on experience_)

## Quality Checklist
- All acceptance criteria must be addressed (DONE/PARTIAL/SKIPPED)
- "Not essential" is not valid justification for skipping an AC
- Tests must pass before declaring COMPLETE
""",
    "guide-qa-remediate": """---
category: guide
sentiment: neutral
confidence: tentative
last_updated: seed
occurrences: 0
links_to: []
---

# Guidance for qa_remediate

## Watch-outs
(_Twin will populate based on experience_)

## Recommended Patterns
(_Twin will populate based on experience_)

## Quality Checklist
- Each issue must be addressed (FIXED/SKIPPED/ESCALATED)
- "Insufficient data" is not valid without listing what was tried
- Do NOT introduce new issues while fixing existing ones
""",
}

def init_wiki(project_root: Path):
    """首次运行时创建 wiki 目录 + seed guide 页面"""
    wiki_dir = project_root / "_bmad-output/implementation-artifacts/experiences"
    wiki_dir.mkdir(parents=True, exist_ok=True)

    # 创建 seed guide 页面——Twin 和人类都有格式参考
    for name, content in SEED_PAGES.items():
        if not (wiki_dir / f"{name}.md").exists():
            write_page(wiki_dir, name, content)

    rebuild_index(wiki_dir)
```

**为什么 seed guide 页面很重要**：

1. **格式参考**：空 wiki 时 Twin 看到这些页面，知道 frontmatter 格式、段落结构、Evidence 表格的列
2. **首次 compass**：guide 页有初始 Quality Checklist，首次 phase 就能生成基本 compass
3. **质量底线**：seed 中的 Quality Checklist 是人工策展的，即使 Twin 没有积累任何经验，执行模型也能得到基本的完成标准约束

### 4.10 与 antipatterns 的关系

| 方面 | antipatterns（现有） | Experience Wiki（Twin） |
|------|---------------------|------------------------|
| 覆盖范围 | 仅负面经验 | 正面 + 负面 + 环境 + 设计偏好 + 指引 |
| 提取方式 | 正则从 synthesis report | LLM 推理（Twin reflect） |
| 作用域 | 单 epic | 跨 epic（project 级） |
| 存储格式 | 单文件 markdown | wiki 目录（多页面 + 索引） |
| 注入方式 | 进入 `<context>` 但无 instruction 引用（ghost context） | guide 页 → compass 注入 + output-template 自检清单 |
| 可维护性 | 只追加，不进化 | 页面可进化、可链接 |

**过渡策略**：初期 wiki 和 antipatterns 并存。antipatterns 的加载路径不变。后续可让 Twin 接管 antipatterns 的提取，但不是 v1 目标。

---

## 5. Compass（辅助，非关键）

### 5.1 定位降级

Compass 从"防跑偏的核心机制"降级为"辅助引导"——对短 phase 有用，对长 phase 效果有限。

在 RETRY 时价值最大——重试时的纠正 compass 是针对性指令，不是泛泛原则，LLM 更容易遵循。

### 5.2 内容来源

Compass 由 Twin.guide() 从 wiki 的 guide 页提取，不需要重新推理：

```xml
<compass>
  <mission>Implement story 15.2: Add rate limiting to API endpoints</mission>
  <constraints>
    - Must not break existing endpoint contracts
    - Must use project's existing middleware pattern
  </constraints>
  <watch-outs>
    - Async sessions need explicit commit (recurring pitfall)
    - Previous code review flagged missing error handling in service layer
  </watch-outs>
  <focus>
    - Write tests first for rate limiting logic
    - Verify middleware integration with existing auth chain
  </focus>
</compass>
```

### 5.3 RETRY 时的纠正 Compass

重试时的 compass 不是从 Active Guidance 提取，而是 Twin.reflect() 根据跑偏的具体证据生成：

```xml
<compass retry="1" correction-for="dev_story">
  <mission>RETRY: You skipped acceptance criteria #3 (rate limit headers)</mission>
  <constraints>
    - MUST implement ALL acceptance criteria from the story file
    - You claimed "rate limit headers not essential" — this is NOT acceptable
  </constraints>
  <watch-outs>
    - Do NOT declare COMPLETE until ALL acceptance criteria are DONE
    - "Not essential" is not a valid justification for skipping an AC
  </watch-outs>
  <focus>
    - Implement rate limit headers in API responses
    - Verify headers appear in test assertions
  </focus>
</compass>
```

---

## 6. Twin Prompt 设计

### 6.1 Reflect Prompt

Reflect 是 Twin 最复杂的 prompt，承担四个职责：审查跑偏、更新 wiki、做决策、（RETRY 时）生成纠正 compass。

Prompt 由代码动态组装——先读 wiki，再拼入执行记录。

#### 6.1.1 Prompt 结构

```markdown
You are the Project Twin — an independent observer acting as the user's digital proxy.
Your job: Observe what just happened, judge quality, update the project wiki, decide what to do next.

## Project Experience Wiki — Index
{index_content}

## Guide Page
{guide_section}

## What Was Asked
{mission}

## What Was Produced (full LLM output)
{llm_output}

## Execution Self-Audit (from the LLM's own declaration)
{self_audit_section}

## Objective Facts
- Phase: {phase_name}
- Epic/Story: {epic_id}/{story_id}
- Success: {success}
- Duration: {duration_ms}ms
- Phase outputs: {phase_outputs}
- Files modified: {files_modified}
- Change diff: {files_diff}
- Error: {error_or_none}

## Your Tasks

### 1. Cross-Validation
Compare three layers:
- What was ASKED (mission) vs what was CLAIMED (self_audit) → scope reduction?
- What was CLAIMED (self_audit) vs what ACTUALLY HAPPENED (git diff, phase_outputs) → false completion?
- What happened vs PAST EXPERIENCES (loaded pages) → recurring pattern?

Watch for:
- Self-audit says COMPLETE but git diff shows no file changes
- Self-audit says PARTIAL but justification is weak ("insufficient data" without listing what was tried)
- Same failure pattern as past experiences (check guide page for this phase type)

### 2. Wiki Update
Based on this execution, update the experience wiki.

**CRITICAL RULES for page management:**

a) **Check INDEX before creating.** If a page already covers this concept, UPDATE or EVOLVE it — do NOT create a duplicate.

b) **When to CREATE:** A genuinely new concept not covered by any existing page.

c) **When to UPDATE:** Same concept, new independent instance (append evidence row to existing page).

d) **When to EVOLVE:** Same concept, understanding has qualitatively deepened (e.g., "works for auth" → "works for all state mutations"). Rewrite the page, keep Evolution section. **Use {{EVIDENCE_TABLE}} placeholder** instead of rewriting the evidence table — the code will preserve the original evidence automatically.

e) **Per-page limits:**
   - Evidence table: ≤ 10 rows. If exceeded, EVOLVE the page to consolidate older evidence.

f) **Link discipline:**
   - Every new page MUST link to at least one existing page (or the guide page for the current phase type).
   - Guide pages MUST link to all pattern/env/design pages they reference.
   - Use [[page-name]] syntax for links.

g) **At most 2 page updates per reflect call.** Prioritize the most impactful changes.

h) **Page content format:** Follow the exact structure shown in the existing pages — YAML frontmatter, then Markdown sections (What, Evidence, When This Applies / Why This Fails, Evolution, Links).

i) **Frontmatter fields:** category (pattern/env/design/guide), sentiment (positive/negative/neutral), confidence (代码自动从 occurrences 推导，Twin 不设置：1次=tentative, 2次=established, 3+次=definitive), last_updated (current epic), occurrences (total count, 代码自动递增), source_epics (list of epic IDs that contributed evidence, 代码自动追踪), links_to (list of page names this page links to).

k) **Negative pattern confidence cap:** Negative patterns (sentiment=negative) are capped at `established` confidence by default. Only after a **challenge mode** check (every 5 epics) can a negative pattern reach `definitive`. Challenge mode: Twin must explicitly confirm that the pattern has been observed across truly independent contexts (not just repeated by the same execution model with the same blind spots). This prevents self-reinforcing errors — where the execution model's consistent failure on a task is interpreted as a "pattern" when it's really the model's own limitation.

j) **Quality requirements — NO generic platitudes:**
   - What section MUST contain specific technical details (library/framework/method names), not universal principles.
   - Evidence Context column MUST contain enough detail to recreate the scenario.
   - Do NOT create pages that contain no project-specific information (e.g., "always test your code" is NOT a valid experience).
   - Each PageUpdate's reason field MUST cite specific evidence from this execution.

### 3. Decision
- CONTINUE: Execution satisfactory, proceed to next phase
- RETRY: Execution drifted or produced incomplete work; retry with specific correction
- HALT: Critical issue requiring human intervention

**Before deciding, you MUST complete this checklist:**
- [ ] Did the execution address all items in the mission?
- [ ] Does the self-audit match the objective facts (git diff, phase_outputs)?
- [ ] Are there any contradictions between claimed completion and actual file changes?
- [ ] Does this execution repeat any known failure patterns from the wiki?
- [ ] Is the self-audit status (COMPLETE/PARTIAL/DEFERRED) justified by the evidence?

Only after answering all five items should you set your decision.

Be strict about drift — the user cannot monitor every step, so you are their eyes.

Output as YAML:
```yaml
drift_assessment:
  drifted: true/false
  evidence: "specific evidence from the three-layer comparison"
  correction: "what to do differently"  # only if drifted
page_updates:
  - page_name: "pattern-test-first"
    action: update  # create / update / evolve
    content: |      # ALWAYS use | block scalar for multi-line content. NEVER use inline quoting.
      Full page content here...
    append_evidence:
      context: "Rate limiter implementation"
      result: "Caught edge case early"
      epic: "epic-22"
    section_patches:
      "When This Applies": |
        State mutations and service layer changes with side effects
    reason: "New evidence for existing test-first pattern, broadened scope"
  - page_name: "guide-dev-story"
    action: update
    content: ""
    append_evidence: null
    reason: "..."  # only if guide page needs updating
decision: CONTINUE/RETRY/HALT
rationale: "why this decision"
```

**YAML 格式要求**（必须严格遵守）：
- `content` 字段（create/evolve 时）：**必须使用 `|` block scalar**，不要用行内引号包裹多行内容
- `section_patches` 的值：如果含多行，也用 `|`
- 单行字段（reason、evidence 等）：用普通引号即可
```

#### 6.1.2 代码如何组装这个 Prompt

```python
def build_reflect_prompt(record: ExecutionRecord, wiki_dir: Path) -> str:
    # 1. 加载 INDEX + guide 页（Strategy D：最小加载）
    index_content, guide_content = load_guide_page(wiki_dir, record.phase)

    # 2. 格式化 guide 页
    guide_section = ""
    if guide_content:
        phase_type = record.phase.name.split("_")[0] if "_" in record.phase.name else record.phase.name
        guide_section = f"### [[guide-{phase_type}]]\n{guide_content}\n---\n"

    # 3. 填充模板
    return REFLECT_PROMPT.format(
        index_content=index_content,
        guide_section=guide_section,
        mission=record.mission,
        llm_output=prepare_llm_output(record.llm_output),  # 超长时 head+tail 截断
        self_audit_section=format_self_audit(record.self_audit),
        phase_name=record.phase.name,
        epic_id=record.epic_id,
        story_id=record.story_id,
        success=record.success,
        duration_ms=record.duration_ms,
        phase_outputs=record.phase_outputs,
        files_modified=record.files_modified,
        files_diff=prepare_llm_output(record.files_diff),    # 超长 diff 同样截断
        error=record.error or "none",
    )
```

#### 6.1.3 Twin.reflect() 的完整调用链

```python
# twin/twin.py
class Twin:
    def __init__(self, config: TwinProviderConfig, wiki_dir: Path):
        self.config = config
        self.wiki_dir = wiki_dir
        self.provider = create_provider(config.provider, config.model)  # 复用现有 provider 工厂

    def reflect(self, record: ExecutionRecord, is_retry: bool = False,
                retry_exhausted_action: str = "halt") -> TwinResult:
        """单次 LLM 调用 → 解析结构化输出 → 返回决策

        is_retry=True 表示这是 RETRY 后的 reflect
        retry_exhausted_action: 解析失败时的降级策略，受用户配置控制
        """
        # 1. 构建 prompt
        prompt = build_reflect_prompt(record, self.wiki_dir)

        # 2. 调用 LLM
        raw_output = self.provider.invoke(prompt)

        # 3. 从输出中提取 YAML 块并解析
        try:
            yaml_str = extract_yaml_block(raw_output)
            yaml_str = fix_content_block_scalars(yaml_str)  # 修复缩进/格式问题
            data = yaml.safe_load(yaml_str)
            result = TwinResult.model_validate(data)
        except (yaml.YAMLError, ValidationError) as e:
            logger.warning(f"Twin reflect YAML parse failed: {e}. Retrying once.")
            raw_output = self.provider.invoke(prompt)  # 重试一次
            try:
                yaml_str = extract_yaml_block(raw_output)
                yaml_str = fix_content_block_scalars(yaml_str)
                data = yaml.safe_load(yaml_str)
                result = TwinResult.model_validate(data)
            except Exception:
                if is_retry and retry_exhausted_action == "halt":
                    # RETRY 后的 reflect 解析失败 + 用户配了 halt → HALT
                    logger.error("Twin reflect failed after retry during RETRY cycle. Defaulting to HALT.")
                    return TwinResult(decision="halt", rationale="Twin parse error during RETRY, halting to prevent uncontrolled execution")
                else:
                    # 首次 reflect 失败 或 用户配了 continue → CONTINUE
                    logger.error("Twin reflect failed after retry. Defaulting to CONTINUE.")
                    return TwinResult(decision="continue", rationale="Twin parse error, defaulting to continue")

        return result
```

**`apply_page_updates()` 由 runner.py 在 `twin.reflect()` 返回后调用**（详见 §8.3 数据流图），输入来自 `twin_result.page_updates`。

#### 6.1.4 代码如何处理 Twin 的 PageUpdate 输出

```python
def apply_page_updates(updates: list[PageUpdate], wiki_dir: Path, current_epic: str):
    for update in updates:
        # 页面命名校验
        if not validate_page_name(update.page_name):
            logger.warning(f"Invalid page name '{update.page_name}'. Skipping.")
            continue

        if update.action == "create":
            # 兜底：检查同名页面是否已存在
            if page_exists(wiki_dir, update.page_name):
                logger.warning(
                    f"Twin tried to CREATE '{update.page_name}' but it already exists. "
                    f"Skipping — Twin should have used UPDATE/EVOLVE."
                )
                continue
            # 语义去重警告：检查同 category 下是否有子串/超串关系的页面名
            for existing in list_pages(wiki_dir):
                if (existing.startswith(update.page_name) or
                    update.page_name.startswith(existing)):
                    if parse_frontmatter(read_page(wiki_dir, existing) or "").get("category") == \
                       parse_frontmatter(update.content).get("category"):
                        logger.warning(
                            f"Twin CREATE '{update.page_name}' may duplicate existing '{existing}'. "
                            f"Proceeding — Twin should have used UPDATE/EVOLVE instead."
                        )
            write_page(wiki_dir, update.page_name, update.content)

        elif update.action == "update":
            existing = read_page(wiki_dir, update.page_name)
            if existing is None:
                logger.warning(f"Twin tried to UPDATE '{update.page_name}' but it doesn't exist. Treating as CREATE.")
                if update.content:
                    write_page(wiki_dir, update.page_name, update.content)
                else:
                    logger.warning(f"Skipping UPDATE with empty content for non-existent page '{update.page_name}'.")
                continue
            # 追加证据到 Evidence 表格
            if update.append_evidence:
                existing = append_evidence_row(existing, update.append_evidence)
            # 应用段落级替换
            if update.section_patches:
                existing = apply_section_patches(existing, update.section_patches)
            # 更新 frontmatter: last_updated, occurrences+1, confidence 从 occurrences 自动推导
            existing = update_frontmatter(existing, epic_id=current_epic)
            write_page(wiki_dir, update.page_name, existing)

        elif update.action == "evolve":
            existing = read_page(wiki_dir, update.page_name)
            if existing is None:
                logger.warning(f"Twin tried to EVOLVE '{update.page_name}' but it doesn't exist. Treating as CREATE.")
                write_page(wiki_dir, update.page_name, update.content)
                continue
            # 安全检查：防止覆盖人工修改
            existing_meta = parse_frontmatter(existing)
            if existing_meta.get("last_updated", "") != current_epic:
                logger.warning(
                    f"EVOLVE of '{update.page_name}' skipped: page was modified outside Twin "
                    f"(last_updated={existing_meta.get('last_updated')}, current={current_epic}). "
                    f"Manual edits take priority."
                )
                continue
            write_page(wiki_dir, update.page_name, update.content)

    # 所有更新后重建 INDEX（含反向引用计算）
    rebuild_index(wiki_dir)
```

### 6.2 Guide Prompt

Guide 从 wiki 的 guide 页提取 compass。比 reflect 简单得多——只读一个页面。

```markdown
You are the Project Twin — preparing guidance for the upcoming phase.

## Experience Index
{index_content}

## Guide Page for {phase_type}
{guide_page_content}

## Upcoming Phase
- Phase: {phase_name}
- Epic/Story: {epic_id}/{story_id}

## Your Task
Generate a concise compass entry from the guide page and its linked references.
This is auxiliary guidance — the main value comes from the self-audit checklist
in the output template, not from this compass.

1. Mission: What this phase MUST accomplish
2. Constraints: What must not be violated (from project experience)
3. Watch-outs: Specific pitfalls for THIS phase type (from guide page)
4. Focus: What aspects deserve extra attention

Be SPECIFIC, not generic. Reference actual past patterns from the loaded pages, not platitudes.
Keep under 500 tokens.

If no guide page exists for this phase type, generate compass from ALL available env/pattern/design pages
instead — focus on any content relevant to the upcoming phase type.
Do NOT create new wiki pages in guide mode — that's reflect's job.

Output as YAML:
```yaml
compass:
  mission: "..."
  constraints: [...]
  watch_outs: [...]
  focus: [...]
```
```

#### 6.2.1 代码如何组装 Guide Prompt

```python
def build_guide_prompt(phase: Phase, epic_id: str, story_id: str, wiki_dir: Path) -> str:
    # 1. 加载 INDEX
    index_content = read_page(wiki_dir, "INDEX")

    # 2. 加载 guide 页
    phase_type = phase.name.split("_")[0] if "_" in phase.name else phase.name
    guide_content = read_page(wiki_dir, f"guide-{phase_type}")

    return GUIDE_PROMPT.format(
        index_content=index_content or "(empty — no experiences yet)",
        phase_type=phase_type,
        guide_page_content=guide_content or "(no guide page for this phase type)",
        phase_name=phase.name,
        epic_id=epic_id,
        story_id=story_id,
    )
```

---

## 7. Twin 反射结果

```python
from pydantic import BaseModel
from typing import Literal

class DriftAssessment(BaseModel):
    drifted: bool
    evidence: str
    correction: str | None = None

class PageUpdate(BaseModel):
    page_name: str                          # "pattern-test-first"
    action: Literal["create", "update", "evolve"]
    content: str                            # 完整页面内容（create/evolve 时必填）
    append_evidence: dict | None = None     # 追加证据行（update only）
    section_patches: dict[str, str] | None = None  # 段落级替换（update only）
    reason: str                             # 为什么做这个操作

class TwinResult(BaseModel):
    decision: Literal["continue", "retry", "halt"]
    rationale: str
    drift_assessment: DriftAssessment | None = None
    page_updates: list[PageUpdate] | None = None  # 替代旧 ExperienceUpdates
```

使用 Pydantic（与 codebase 一致），自带 YAML 解析验证。

**与旧模型的对比**：

| 方面 | 旧 ExperienceUpdates | 新 PageUpdate |
|------|---------------------|---------------|
| 结构 | 5 个分类列表（successes/failures/env/design/guidance） | 页面级操作 |
| 输出粒度 | 按分类拼结构化数据 | 直接写 markdown 页面 |
| 验证 | 需要 5 个 list[dict] 各自校验 | 只校验 page_name + action + content |
| 去重责任 | 代码需要合并同类经验 | Twin 检查 INDEX 后决定 CREATE/UPDATE |
| 灵活性 | 固定分类，无法表达复杂关系 | 任意页面内容，支持链接和进化 |
| 代码复杂度 | 需要写 5 个分类的合并逻辑 | 只需 3 种 action 的文件操作 |

---

## 8. 集成实现

### 8.1 新增模块

```
src/bmad_assist/twin/
├── __init__.py
├── twin.py              # Twin 类：guide() + reflect()
├── wiki.py              # Wiki 文件 I/O + INDEX 生成 + 链接解析
├── execution_record.py  # ExecutionRecord 构建（收集 git diff 等）
├── prompts.py           # Prompt 模板
└── config.py            # Twin 配置
```

### 8.2 wiki.py 核心接口

**关键设计：Twin 不直接操作文件系统。** Twin 的 reflect() 输出结构化 YAML（含 `page_updates` 列表），Python 代码解析 YAML 后调用 wiki.py 执行文件 I/O。Twin 是"思考后输出决策"的模型，不是带工具的 agent。

```python
from pathlib import Path
import re
import yaml
from bmad_assist.utils import atomic_write  # 复用 codebase 现有

WIKI_DIR_NAME = "experiences"

CONFIDENCE_LEVELS = ["tentative", "established", "definitive"]

def derive_confidence(occurrences: int, sentiment: str = "positive") -> str:
    """从 occurrences 自动推导 confidence（Twin 不设置，代码派生）

    Negative patterns cap at established — only challenge mode allows definitive.
    """
    if occurrences >= 3:
        if sentiment == "negative":
            return "established"  # Negative patterns cap at established
        return "definitive"
    elif occurrences >= 2:
        return "established"
    return "tentative"

def update_frontmatter(content: str, epic_id: str) -> str:
    """递增 occurrences，从 occurrences 重算 confidence，更新 last_updated，追踪 source_epics"""
    meta = parse_frontmatter(content)
    meta["occurrences"] = meta.get("occurrences", 0) + 1
    meta["confidence"] = derive_confidence(meta["occurrences"], meta.get("sentiment", "positive"))
    meta["last_updated"] = epic_id
    # 追踪来源 epic（用于检测自我强化错误）
    source_epics = meta.get("source_epics", [])
    if epic_id not in source_epics:
        source_epics.append(epic_id)
    meta["source_epics"] = source_epics
    return replace_frontmatter(content, meta)

def get_wiki_dir(project_root: Path) -> Path:
    return project_root / "_bmad-output/implementation-artifacts" / WIKI_DIR_NAME

def read_page(wiki_dir: Path, name: str) -> str | None:
    """读一个页面，不存在返回 None"""
    path = wiki_dir / f"{name}.md"
    return path.read_text() if path.exists() else None

def write_page(wiki_dir: Path, name: str, content: str):
    """atomic write 一个页面"""
    path = wiki_dir / f"{name}.md"
    atomic_write(path, content)

def page_exists(wiki_dir: Path, name: str) -> bool:
    return (wiki_dir / f"{name}.md").exists()

def list_pages(wiki_dir: Path) -> list[str]:
    """列出所有页面名（不含 INDEX）"""
    return [
        p.stem for p in sorted(wiki_dir.glob("*.md"))
        if p.stem != "INDEX"
    ]

def extract_links(content: str) -> list[str]:
    """提取 [[link]] 语法"""
    return re.findall(r'\[\[([^\]]+)\]\]', content)

def parse_frontmatter(content: str) -> dict:
    """解析 YAML frontmatter"""
    if not content.startswith("---"):
        return {}
    end = content.find("---", 3)
    if end == -1:
        return {}
    return yaml.safe_load(content[3:end]) or {}

def extract_title(content: str) -> str:
    """从正文第一行提取标题（# Title）"""
    for line in content.split("\n"):
        line = line.strip()
        if line.startswith("# "):
            return line[2:].strip()
    return ""

def fix_content_block_scalars(yaml_str: str) -> str:
    """修复 Twin YAML 输出中常见的格式问题：
    1. content 字段用了行内引号而非 | block scalar → 转为 |
    2. section_patches 的值用了行内引号而非 | → 转为 |
    """
    import re
    # 修复 content: "..." → content: |，仅匹配多行内容
    yaml_str = re.sub(
        r'^(\s+content:)\s*"([^"]*\n[^"]*)"',
        r'\1 |\2',
        yaml_str,
        flags=re.MULTILINE,
    )
    return yaml_str

def prepare_llm_output(llm_output: str, max_tokens: int = 120000) -> str:
    """智能截断：如果 llm_output 太长，保留 head(1/4) + tail(3/4)

    默认不截断（opus 200K 上下文），仅在超长输出时使用。
    head 提供执行开始的上下文（任务理解），tail 包含关键的自检和收尾。
    """
    # 粗估 token 数（1 token ≈ 4 字符）
    estimated_tokens = len(llm_output) // 4
    if estimated_tokens <= max_tokens:
        return llm_output

    max_chars = max_tokens * 4
    head_chars = max_chars // 4
    tail_chars = max_chars * 3 // 4

    head = llm_output[:head_chars]
    tail = llm_output[-tail_chars:]
    return head + "\n\n... [truncated] ...\n\n" + tail

def load_guide_page(wiki_dir: Path, phase: Phase) -> tuple[str, str | None]:
    """加载 INDEX + guide 页（Strategy D：最小加载，不加载链接页面）"""
    index_content = read_page(wiki_dir, "INDEX") or ""
    phase_type = phase.name.split("_")[0] if "_" in phase.name else phase.name
    guide_content = read_page(wiki_dir, f"guide-{phase_type}")
    return index_content, guide_content

def extract_evidence_table(content: str) -> str:
    """从页面内容中提取 Evidence 表格段（含表头和数据行）

    用于 EVOLVE 时保留原始 evidence 表——Twin 用 {{EVIDENCE_TABLE}} 占位，
    代码将占位符替换为原始 evidence 表，防止 Twin 丢失历史证据。
    """
    import re
    # 匹配 ## Evidence 段到下一个 ## 之前的内容
    match = re.search(
        r'(##\s+Evidence\s*\n)(.*?)(?=\n##\s|\Z)',
        content,
        re.DOTALL,
    )
    if match:
        return match.group(2).rstrip()
    return ""

def rebuild_index(wiki_dir: Path):
    """从所有页面的 frontmatter 重新生成 INDEX.md"""
    pages_meta = []
    links_map: dict[str, list[str]] = {}
    for name in list_pages(wiki_dir):
        content = read_page(wiki_dir, name)
        if content:
            meta = parse_frontmatter(content)
            title = extract_title(content)
            pages_meta.append({
                "name": name,
                "category": meta.get("category", "unknown"),
                "sentiment": meta.get("sentiment", "neutral"),
                "confidence": meta.get("confidence", 1),
                "title": title,
                "last_updated": meta.get("last_updated", ""),
            })
            links_map[name] = meta.get("links_to", [])

    # 计算反向引用
    backlinks: dict[str, list[str]] = {}
    for name, targets in links_map.items():
        for target in targets:
            backlinks.setdefault(target, []).append(name)

    index_content = format_index(pages_meta, backlinks)
    write_page(wiki_dir, "INDEX", index_content)

def init_wiki(project_root: Path):
    """首次运行时创建 wiki 目录"""
    wiki_dir = get_wiki_dir(project_root)
    wiki_dir.mkdir(parents=True, exist_ok=True)
    if not (wiki_dir / "INDEX.md").exists():
        write_page(wiki_dir, "INDEX", "# Experience Index\n\n(No pages yet)\n")
```

### 8.3 Twin 数据流：从 LLM 调用到 Wiki 写入

Twin 不是 agent，没有工具调用能力。整条链路是**单次 LLM 调用 → 解析结构化输出 → 代码执行文件 I/O**：

```
┌─ runner.py（主循环）─────────────────────────────────────────────┐
│                                                                    │
│  ① phase 执行前：                                                  │
│     compass = twin.guide(phase, epic_id, story_id)                │
│       │                                                            │
│       ├→ wiki.load_guide_page(wiki_dir, phase)          ← 读文件   │
│       ├→ build_guide_prompt(INDEX, guide_page)           ← 拼prompt │
│       ├→ provider.invoke(prompt)                         ← LLM调用  │
│       └→ parse YAML → compass dict                       ← 解析输出 │
│                                                                    │
│  ② execute_phase(state, compass=compass)                           │
│                                                                    │
│  ③ phase 执行后：                                                  │
│     record = build_execution_record(state, result, project_path)   │
│     twin_result = twin.reflect(record)                             │
│       │                                                            │
│       ├→ wiki.load_guide_page(wiki_dir, phase)          ← 读文件   │
│       ├→ build_reflect_prompt(INDEX, guide, record)      ← 拼prompt │
│       ├→ provider.invoke(prompt)                       ← LLM调用  │
│       └→ parse YAML → TwinResult                       ← 解析输出 │
│                                                                    │
│  ④ 应用 wiki 更新：                                                │
│     if twin_result.page_updates:                                   │
│       apply_page_updates(twin_result.page_updates, wiki_dir)       │
│         │                                                          │
│         ├→ validate_page_name()                        ← 校验     │
│         ├→ create/update/evolve → write_page()          ← 写文件   │
│         └→ rebuild_index()                              ← 重建索引 │
│                                                                    │
│  ⑤ 决策处理：                                                      │
│     CONTINUE → 下一个 phase                                        │
│     RETRY   → compass=correction, 重走 ②③④⑤                      │
│     HALT    → return LoopExitReason.GUARDIAN_HALT                  │
│                                                                    │
└────────────────────────────────────────────────────────────────────┘
```

**关键要点**：
- `twin.guide()` 和 `twin.reflect()` 各是一次 `provider.invoke(prompt)` 调用，不是 agent 循环
- LLM 返回纯文本，代码从中提取 YAML 块并解析为 Pydantic 模型
- `apply_page_updates()` 由 runner.py 在 `twin.reflect()` 返回后调用，输入来自 `twin_result.page_updates`
- 所有文件 I/O 集中在 `wiki.py`，Twin 代码不直接操作文件系统

### 8.4 修改点

#### runner.py（~30 行改动）

在主循环 `while True:` 内：

```python
# 现有代码 line ~976
start_phase_timing(state)

# === 新增：Twin Guide ===
compass = None
if twin_enabled:
    compass = twin.guide(state.phase, state.epic_id, state.story_id)

# 现有代码 line ~1037
result = execute_phase(state, compass=compass)

# 现有代码 line ~1044（phase 完成后）
# === 新增：Twin Reflect ===
if twin_enabled:
    record = build_execution_record(state, result, project_path)
    twin_result = twin.reflect(record)

    # 应用 wiki 页面更新
    if twin_result.page_updates:
        apply_page_updates(twin_result.page_updates, wiki_dir)

    # 决策处理
    if twin_result.decision == "retry" and state.retry_count < twin_config.max_retries:
        # RETRY：重置工作区 + 注入纠正 compass
        git_stash()  # 恢复到 phase 开始前的状态
        correction_compass = format_correction_compass(
            twin_result.drift_assessment.correction,
            retry_count=state.retry_count + 1,
            phase_name=state.phase.name,
        )
        state.retry_count += 1
        result = execute_phase(state, compass=correction_compass)
    elif twin_result.decision == "retry" and state.retry_count >= twin_config.max_retries:
        # RETRY 次数用尽 → HALT（回答第一个问题）
        logger.error(
            f"Twin requested RETRY but max_retries ({twin_config.max_retries}) reached. "
            f"Drift evidence: {twin_result.drift_assessment.evidence} | "
            f"Correction: {twin_result.drift_assessment.correction} | "
            f"Rationale: {twin_result.rationale}"
        )
        return LoopExitReason.GUARDIAN_HALT
    elif twin_result.decision == "halt":
        return LoopExitReason.GUARDIAN_HALT
```

#### qa_remediate handler（~10 行改动）

在 execute() 中收集每次迭代的 LLM 输出，最终放入 PhaseResult：

```python
all_llm_outputs: list[str] = []

for iteration in range(max_iterations):
    # ... existing code ...
    result = self.invoke_provider(prompt)
    all_llm_outputs.append(result.stdout)  # 新增
    # ... existing code ...

return PhaseResult.ok({
    "response": "\n---\n".join(all_llm_outputs),  # 新增
    "status": status,
    # ... existing outputs ...
})
```

#### dispatch.py / base.py / compiler（~20 行改动）

传递 compass 参数，新增 `CompilerContext.compass` 字段，在 `generate_output()` 中生成 `<compass>` 段。

详细改动同 v2，此处不重复。

#### workflow XML（自检清单注入）

修改各 workflow 的 `<output-template>`：

- `workflows/dev-story/instructions.xml` — 加入通用 + dev_story 自检
- `workflows/create-story/instructions.xml` — 加入通用 + create_story 自检
- `workflows/code-review/instructions.xml` — 加入通用 + code_review 自检
- `workflows/validate-story/instructions.xml` — 加入通用 + validate_story 自检
- `qa/prompts/remediate.xml` — 加入通用 + qa_remediate 自检

#### config 新增 TwinProviderConfig（~15 行改动）

```python
class TwinProviderConfig(BaseModel):
    provider: str = "claude"
    model: str = "opus"
    enabled: bool = True
    max_retries: int = 2
    retry_exhausted_action: Literal["halt", "continue"] = "halt"
```

YAML：
```yaml
providers:
  master:
    provider: claude
    model: sonnet
  twin:
    provider: claude
    model: opus
    enabled: true
    max_retries: 2
    retry_exhausted_action: halt
```

---

## 9. 关键设计决策

### 9.1 为什么默认不截断 llm_output，但保留条件截断

原设计截取前 3000 token，但跑偏偏偏在末尾——"剩下的不做了"这种声明出现在输出的最后。

Twin 的 reflect 是独立的 LLM 调用，有自己的上下文窗口。它不看 project-context、不看 PRD，只看 INDEX + guide 页 + mission + llm_output + self_audit + git_diff。这些加起来通常在 15K-40K token，opus 的 200K 上下文窗口完全可以容纳。

**但极端情况下需要截断**：某些 phase（如 dev_story 在大型 epic 上）可能产生超长输出。`prepare_llm_output()` 在输出超过 ~120K token 时触发条件截断：保留 head(1/4) + tail(3/4)。

- Head(1/4)：执行开始的上下文——任务理解、初始决策
- Tail(3/4)：收尾段——包含自检清单、完成声明、跑偏证据

按位置截断（而非按标记截断），避免依赖特定格式标记的脆弱性。

### 9.2 自检清单为什么放在 output-template 而不是 prompt 顶部

- 顶部注入在长执行中被稀释——这是评审确认的致命问题
- output-template 是 LLM 开始写输出时最后看到的内容——recency bias 效果最强
- 自检清单不是要"防止遗忘"，而是要"强制声明"——在 LLM 准备收尾时，要求它显式列出完成状态
- 跑偏从"我忘了要求"变成"我声明了 PARTIAL 但理由不充分"——后者可被 Twin 审查

### 9.3 为什么不用工具调用链

Tool_use/tool_result 的数据量太大（dev_story 一次执行可能有几十次 Read/Edit/Bash 调用，每次返回大量内容）。轻量路径足够：

- `llm_output` 告诉 Twin LLM 声称做了什么
- `git diff` 告诉 Twin 客观改了什么
- `phase_outputs` 告诉 Twin 结构化指标
- 对比 llm_output 的声明 vs git diff 的事实，就能检测大部分跑偏

### 9.4 为什么 INDEX 由代码自动生成而不是 Twin 维护

- Twin 可能忘记更新 INDEX，导致索引与实际页面不一致
- INDEX 的内容（页面列表、category、confidence、反向引用）完全可从 frontmatter + 页面内容推导——是**派生数据**
- 代码在每次 `apply_page_updates()` 后自动 `rebuild_index()`，保证一致性
- Twin 只负责页面内容和 `links_to`（本页链接到谁），不负责元数据维护和反向引用——降低 prompt 复杂度
- 反向引用（谁链接到本页）由 `rebuild_index()` 扫描所有页面的 `links_to` 自动计算，不依赖 Twin 维护

### 9.5 为什么页面用 YAML frontmatter 而不是纯 markdown

- 代码需要读取 category、confidence、last_updated 来做加载决策和 INDEX 生成
- 纯 markdown 需要正则或 LLM 来提取这些信息，不可靠
- YAML frontmatter 是 markdown 社区标准（Jekyll、Hugo 等都用），人可读且机器可解析
- Twin 写页面时自然包含 frontmatter（prompt 中有明确要求）

### 9.6 为什么限制每次 reflect 最多 2 个 PageUpdate

- 防止 Twin 过度修改——一次 reflect 产生 5+ 个页面更新会导致 wiki 不稳定
- 2 个更新足够：通常是一个 evidence UPDATE + 一个 guide UPDATE
- 如果 Twin 发现更多值得记录的经验，会在下一次 reflect 时继续
- 限制迫使 Twin 优先记录最有价值的经验

### 9.7 RETRY 兜底策略（回答第一个问题）

```
RETRY 次数用尽 → HALT

理由：
1. 连续 N 次 Twin 判定跑偏，说明执行模型在这个 phase 上确实有困难
2. 强行 CONTINUE 只会积累技术债——带着问题继续比停机更糟
3. HALT 是安全的失败模式——它告诉用户"这里需要你介入"
4. HALT 信息丰富——Twin 的 drift evidence、correction、rationale 全部记录在日志

可配置性：
- max_retries: int = 2（默认 2 次，可调）
- retry_exhausted_action: Literal["halt", "continue"] = "halt"
  - 高风险项目用 halt（默认）
  - 低风险项目可以用 continue（接受可能有问题的执行，不阻塞流程）
```

### 9.8 Twin 失败降级

Twin 的 LLM 调用可能超时、返回格式错误、或本身出错。降级策略：

- Twin guide() 失败 → compass = None，phase 正常执行（无 compass 不影响功能）
- Twin reflect() 失败（首次执行）→ decision = CONTINUE，不阻塞主循环
- Twin reflect() 失败（RETRY 后）→ 受 `retry_exhausted_action` 控制：halt→HALT，continue→CONTINUE
- Twin wiki 写入失败 → 记录 warning，不影响流程
- Twin YAML 解析失败 → 重试一次，仍失败则按 is_retry + retry_exhausted_action 决定
- PageUpdate 校验失败（如 CREATE 已存在页面）→ 跳过该更新，日志警告

### 9.9 RETRY 的风险缓解

- `max_retries: 2`（可配置），每个 phase 最多重试 2 次
- 重试时 Twin 必须提供具体的 correction compass，不能只说 "do better"
- 连续 2 次 RETRY 后 Twin 仍不满意 → 自动 HALT
- 重试的 compass 包含 `retry="N"` 标记，让执行模型知道这是重试
- **RETRY 前执行 `git stash`**：恢复工作区到 phase 开始前的状态，避免在已修改的代码上叠加修改。纠正 compass 只需指出该做什么，不需要说明如何回退
- 纠正 compass 是**追加**到原有 compass 之后，不是替换——保留原有的 watch-outs，加上纠正指令

### 9.10 qa_remediate 内部迭代与 Twin

qa_remediate 自己循环最多 3 次，Twin 的 guide/reflect 包裹整个 phase。内部迭代中 compass 不可用（`_build_remediate_prompt()` 不用 compiler）。

解决：在 `_build_remediate_prompt()` 中增加 compass 参数。但 compass 是 phase 开始时生成的，不能适应内部迭代的演变。这是已知的局限——qa_remediate 的内部迭代质量主要靠自检清单约束，不靠 compass。

### 9.11 Reflect 加载策略：最小加载

reflect 和 guide 都采用最小加载策略——只读 INDEX + guide 页，不加载链接页面：

```
加载内容：INDEX.md + guide-{phase_type}
总计：~800-1800 token
```

Twin 通过 INDEX 了解所有页面存在，但只读 guide 页的完整内容。这足够让 Twin：
- 判断是否需要 UPDATE/EVOLVE 已有的 guide 页
- 通过 append_evidence 更新未加载的页面（不需要读内容）
- CREATE 新页面（不需要读现有页面）

EVOLVE 只能对已加载的 guide 页执行——Twin 没读过的不应重写。

### 9.12 经验质量约束（防止泛泛而谈）

在 reflect prompt 的 Wiki Update 规则中增加以下约束（已整合到 6.1.1 的 prompt 中）：

- What 段必须包含具体技术细节（库/框架/方法名），不能只是通用原则
- Evidence 表的 Context 列必须包含足够信息让读者复现场景
- 禁止创建不包含项目特定信息的页面（如 "always test your code" 是无效经验）
- 每个 PageUpdate 的 reason 必须引用本次执行的具体证据

### 9.13 页面命名校验

`apply_page_updates()` 对 `page_name` 做格式校验：

```python
import re

VALID_PAGE_NAME = re.compile(r'^(env|pattern|design|guide)-[a-z0-9-]+$')

def validate_page_name(name: str) -> bool:
    """页面名只允许小写字母、数字、连字符，且必须以 category 前缀开头"""
    return bool(VALID_PAGE_NAME.match(name))
```

不符合规范的 page_name 拒绝执行，日志警告。

### 9.14 自我强化错误的防护

**问题**：执行模型的一致失败可能被 Twin 记录为"失败模式"，但实际上是执行模型自身的盲点而非项目真实问题。例如，某个 LLM 总是在 async session 上犯错，Twin 会记录 "async session always fails" 作为 definitive 失败模式，但真相是"这个 LLM 不擅长 async"。

**三层防护**：

1. **source_epics 追踪**：frontmatter 中的 `source_epics` 记录哪些 epic 贡献了证据。这让人可以审查——如果所有证据来自同一种 phase 类型或同一段代码区域，可能不是真正的跨上下文模式。

2. **Negative pattern confidence cap**：`derive_confidence()` 对 sentiment=negative 的页面 capped at `established`。即使 occurrences≥3，negative pattern 也只能到 established，不会自动到 definitive。防止一个失败模式从"观察到几次"变成"这是项目铁律"。

3. **Challenge mode**：每 5 个 epic，reflect prompt 中注入挑战指令：
   ```
   ## Challenge Mode (every 5 epics)

   For each negative pattern page in the wiki, challenge your assumptions:
   - Is this a real project issue, or is the execution model consistently bad at this?
   - Would a different execution model or approach avoid this "pattern"?
   - Has any positive evidence contradicted this pattern since it was recorded?

   If you can defend the pattern with evidence from genuinely independent contexts
   (different code areas, different phase types), you may promote it to definitive.
   Otherwise, keep it at established and note the challenge result.
   ```
   Challenge mode 通过 `source_epics` 的长度判断——当 `len(source_epics) % 5 == 0` 且 `sentiment == "negative"` 时，注入挑战指令，允许 Twin 在确信证据跨上下文独立时手动 promote 到 definitive。

---

## 10. 实现路径

### Phase 1：基础设施 + 自检清单

**目标**：验证自检清单是否能让跑偏显性化

改动：
1. 修改各 workflow 的 `<output-template>`，加入自检清单
2. 修补 qa_remediate 的 PhaseResult，包含 LLM 输出
3. `twin/execution_record.py` — ExecutionRecord 构建（收集 git diff）
4. `compiler/output.py` — 支持 `<compass>` 段

**验证点**：执行 dev_story 后，LLM 的输出是否包含有意义的 Self-Audit 段

### Phase 2：Wiki 基础 + Twin reflect

**目标**：Twin 能审查执行结果、更新 wiki、做基本决策

改动：
1. `twin/wiki.py` — Wiki 文件 I/O + INDEX 自动生成 + 链接解析
2. `twin/twin.py` — reflect() 实现
3. `twin/prompts.py` — reflect prompt 模板（含 wiki 管理规则）
4. `twin/config.py` — TwinProviderConfig
5. `runner.py` — 在主循环中集成 Twin reflect + apply_page_updates

**验证点**：
- Twin 是否能从 llm_output + self_audit + git_diff 中检测出跑偏
- Twin 是否能生成合法的 PageUpdate（create/update/evolve）
- Wiki 页面是否被正确创建/更新
- INDEX.md 是否在更新后自动重建

### Phase 3：RETRY 能力

**目标**：Twin 能检测跑偏并触发重试

改动：
1. 启用 `GuardianDecision.RETRY`（当前被注释为 "Future Epic 8"）
2. Twin 的 drift assessment 触发 RETRY
3. 重试时注入纠正 compass
4. 重试计数和 retry_exhausted → HALT 机制

**验证点**：RETRY 是否能纠正 dev_story 的范围缩减

### Phase 4：Twin guide（compass 生成）

**目标**：Twin 能从 wiki guide 页生成 phase-specific 引导

改动：
1. `twin/twin.py` — guide() 实现（读 INDEX + guide 页 + 链接页）
2. `twin/prompts.py` — guide prompt 模板
3. `runner.py` — 在 phase 执行前调用 guide()
4. `dispatch.py` / `base.py` — 传递 compass 参数

**验证点**：compass 对短 phase（create_story）是否有效

### Phase 5：Wiki 成熟

**目标**：经验 wiki 足够丰富，能显著影响执行质量

改动：
1. Evidence 表格超 10 行时自动触发 evolve
2. Twin 接管 antipatterns 提取（可选）

---

## 11. 开源参考映射

| Twin 能力 | 采用模式 | 参考来源 |
|----------|---------|---------|
| Reflect（三层对比审查） | Reflector 角色 | ACE (Generator/Reflector/Curator) |
| 经验积累 | 跨任务知识 wiki | Karpathy Wiki + TELL (MEMORY.md) |
| 经验提取 | Insight 提取 | ExpeL (NeurIPS 2023) |
| 自检清单 | recency bias 末尾注入 | Control Sentences (arXiv:2512.03001) |
| 决策（CONTINUE/RETRY/HALT） | Heartbeat 自检 | OpenClaw Stability Plugin |
| 纠正 compass | 定向修正指令 | GSD-2 精准注入 |
| Wiki 页面进化 | 版本化笔记 | Karpathy Wiki (v1→v2 进化) |
| 按需加载 | 三级上下文 + 索引导航 | OpenViking (L0/L1/L2) + Bonsai Memory |
