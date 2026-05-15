# bmad-assist 项目介绍

> BMAD Method 的自动化执行引擎——让 AI 按照方法论规范，可靠地完成从 Story 到代码的全流程

---

## 一句话说明

bmad-assist 是 [BMAD Method](https://github.com/bmad-method/bmad-method) 的自动化编排工具。它把 BMAD 第 4 阶段（Implementation）中原本需要人工一步步操作的工作流，变成由编译器构建 Prompt、状态机驱动执行、多 LLM 协同工作的自动化流水线。

---

## 为什么需要它

BMAD Method 是一套完整的软件开发生命周期方法论，从产品需求到代码实现分为多个阶段。在第 4 阶段，你需要：

1. 为每个 Story 创建开发规格
2. 验证 Story 质量
3. 按规格实现代码
4. 代码审查
5. QA 测试
6. 回顾总结

每一步都要把正确的文档、上下文、变量注入到 LLM 的 Prompt 中，然后执行、收集结果、推进状态。人工操作极其繁琐且容易出错——**这正是 bmad-assist 自动化的对象**。

---

## 核心架构

bmad-assist 的运行方式可以用一句话概括：

> **编译器构建完整 Prompt → LLM 执行 → 结果处理 → 状态推进**

```
┌─────────────────────────────────────────────────────────────────────────┐
│                        bmad-assist 执行引擎                             │
│                                                                         │
│  ┌─────────────┐    ┌──────────────┐    ┌─────────────┐    ┌────────┐ │
│  │ 编译器系统   │ →  │  Provider 层  │ →  │  结果处理    │ →  │ 状态机 │ │
│  │             │    │              │    │             │    │        │ │
│  │ 工作流 XML   │    │ 9+ LLM 接入  │    │ Phase 输出  │    │ Resume │ │
│  │ 变量注入    │    │ 多 LLM 并行   │    │ Git 集成    │    │ 崩溃恢复│ │
│  │ 上下文压缩  │    │ 自动 Fallback │    │ 自检清单    │    │ 持久化  │ │
│  │ 补丁系统    │    │ 超时重试      │    │ Twin 审查   │    │        │ │
│  └─────────────┘    └──────────────┘    └─────────────┘    └────────┘ │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

### 编译器系统

bmad-assist 最核心的设计是**编译器**。它不做"让 Agent 自己理解上下文"这件事，而是：

1. 加载 BMAD 工作流 XML 模板
2. 应用补丁（去除交互元素，适配自动化场景）
3. 注入战略上下文（PRD、架构文档，含 LLM 压缩）
4. 注入源码上下文（项目文件，可配置 token 预算）
5. 解析所有变量（epic/story 数据、sprint 状态、开发模式等）
6. 注入 Twin Compass（如果启用 Digital Twin）

最终输出一个完整的、上下文充分的 Prompt，交给 LLM 执行。**LLM 不需要猜测任何上下文——编译器已经把一切放到了它面前**。

### Provider 层

支持 9+ LLM Provider，可在配置中自由选择和组合：

| Provider | 说明 |
|----------|------|
| claude-subprocess | Claude CLI 子进程模式 |
| claude-sdk | Claude Python SDK（推荐） |
| gemini | Google Gemini |
| codex | OpenAI Codex |
| opencode / opencode-sdk | OpenCode |
| kimi | Moonshot Kimi |
| copilot | GitHub Copilot |
| cursor-agent | Cursor Agent |
| amp | Amp |

**多 LLM 并行编排**：Master LLM 负责写代码，多个独立 LLM 并行做验证和审查。还有自动故障切换（FallbackProvider）和工具调用监控（ToolCallGuard）。

---

## 执行流程

### 18 个原子 Phase，3 个 Scope

bmad-assist 把 BMAD 的 Implementation 阶段拆解为 18 个原子 Phase，按 3 个 Scope 依次执行：

```
epic_setup（可选，TEA 相关）
  ├── tea_framework    — 测试框架初始化
  ├── tea_ci           — CI 质量流水线
  ├── tea_test_design  — 测试设计
  └── tea_automate     — 测试自动化

story（每个 Story 循环执行）
  ├── create_story              — 创建 Story 开发规格
  ├── validate_story            — 多 LLM 并行验证
  ├── validate_story_synthesis  — 验证结果综合
  ├── atdd                      — 验收测试脚手架
  ├── dev_story                 — 代码实现
  ├── test_review               — 测试审查
  ├── code_review               — 多 LLM 并行代码审查
  └── code_review_synthesis     — 审查结果综合

epic_teardown
  ├── trace              — 追溯矩阵
  ├── tea_nfr_assess     — 非功能需求评估
  ├── retrospective      — 回顾总结
  ├── qa_plan_generate   — QA 计划生成
  ├── qa_plan_execute    — QA 计划执行
  └── qa_remediate       — QA 修复
```

### 执行循环

```
bmad-assist run --project ./my-project
  │
  ├── 加载配置（bmad-assist.yaml）
  ├── 加载/恢复状态（state.yaml）
  │
  ├── 对每个 Epic:
  │     ├── epic_setup（如果启用 TEA）
  │     ├── 对每个 Story:
  │     │     ├── create_story → validate → synthesis → atdd
  │     │     ├── dev_story（Twin guide → 执行 → Twin reflect）
  │     │     ├── test_review → code_review → code_review_synthesis
  │     │     └── 自动提交 git commit
  │     └── epic_teardown（trace → nfr → retro → QA）
  │
  └── 持久化状态（支持 Ctrl+C 后 resume）
```

---

## 编译 Prompt 长什么样

bmad-assist 最核心的设计是编译器——它把工作流模板、项目文档、源码文件、变量、Twin Compass 全部编译成一个完整的 XML Prompt，直接喂给 LLM。LLM 拿到的是一份不需要猜测任何上下文的完整指令。

编译产出的 XML 分为五个段，下面逐段拆解它的来源和作用，最后给出完整示例。

### 段 1：mission — 告诉 LLM 要做什么

mission 是一句简短的任务声明，告诉 LLM 当前 Phase 的目标。它由 workflow compiler 在编译时动态生成：

```
Execute a story by implementing tasks/subtasks, writing tests,
validating, and updating the story file per acceptance criteria.

Target: Story 3.1 - user-authentication
Implement all tasks and subtasks following TDD methodology.
```

**来源**：DevStoryCompiler 在 `compile()` 中拼接——模板句式 + 当前 Story 的 ID 和标题。每个 Phase 的 mission 格式不同，create_story 的 mission 是"Create a development story for..."，code_review 的 mission 是"Review code changes for..."。

**设计意图**：mission 放在 Prompt 最前面，是 LLM 看到的第一段内容。即使后续上下文很长，mission 的位置保证它不会被注意力稀释。

### 段 2：compass — Twin 的项目经验指引

compass 是 Digital Twin 在执行前从 Experience Wiki 生成的阶段指引。如果 Twin 未启用，这段为空。

```
## Dev Story Guide (from project experience)

- This project uses pytest with async fixtures — always @pytest.mark.asyncio
- The User model is in src/models/user.py — follow its field conventions
- Previous stories hit a pitfall: SQLAlchemy async session requires explicit
  commit in test teardown, otherwise tests pass locally but fail in CI
- The repository pattern is the team's preferred data access style
```

**来源**：`Twin.guide(phase_type)` 调用时，从 wiki 加载 `guide-dev-story.md` 页面，组合 INDEX.md 中相关页面的摘要，生成一段自然语言的 compass 字符串。

**设计意图**：compass 插在 mission 和 context 之间，位置可辨识。它不是"防跑偏"的（长执行中会被稀释），而是提供项目特异的实践经验——环境陷阱、团队偏好、历史踩坑。这些信息在 BMAD 的标准文档里不会有，只有跑过才知道。

### 段 3：context — 所有注入的文档和源码

context 是编译器最重的部分，包含所有需要 LLM 参考的文档和代码。文件按**从泛到精**的顺序排列（recency-bias 原则），最相关的 Story 文件放最后：

**3a. 项目上下文（project-context.md）**

```xml
<file id="a1b2c3d4" path="docs/project-context.md" label="PROJECT CONTEXT">
  技术栈、编码规范、项目约定...
</file>
```

**来源**：`StrategicContextService` 在 docs/ 或 planning-artifacts/ 中搜索 `project-context.md`，全文嵌入。这是项目级全局上下文，所有 Phase 都会加载。

**3b. 架构文档（architecture.md）**

```xml
<file id="e5f6a7b8" path="docs/architecture.md" label="ARCHITECTURE">
  [LLM-compressed from 4500 tokens → 1200 tokens]
  认证模块架构：JWT + refresh token rotation + UserRepository...
</file>
```

**来源**：`StrategicContextService` 按配置加载。每个 workflow 可以配置加载哪些战略文档（PRD、Architecture、UX）。第一个文档全文嵌入，后续文档如果超过 token 预算（默认 8000），会通过 helper LLM 压缩——压缩结果用 SHA-256 做磁盘缓存，同一文档不重复压缩。

**3c. Epic 文档**

```xml
<file id="1234abcd" path="docs/epic-3-auth.md" label="EPIC">
  Epic 目标、关键决策、约束...
</file>
```

**来源**：DevStoryCompiler 根据当前 `epic_num` 定位对应的 epic 文件，全文嵌入。这是当前 Story 所属 Epic 的完整规格。

**3d. 代码反模式（antipatterns）**

```xml
<file id="c0d1e2f3" path=".bmad-assist/antipatterns/code-epic-3.md" label="CODE ANTIPATTERNS">
  从历史 code review 中提取的注意事项...
</file>
```

**来源**：`load_antipatterns()` 加载当前 Epic 的代码反模式——来自之前 Story 的 code_review_synthesis 阶段产出的 "Issues Dismissed" 和常见错误。这些是项目实战中积累的"别这样做"清单，独立于战略文档的 token 预算。

**3e. 源码文件**

```xml
<file id="5678efgh" path="src/models/user.py" label="SOURCE CODE">
  当前 Story 需要参考或修改的源码...
</file>
<file id="9abc1234" path="src/repositories/user_repository.py" label="SOURCE CODE">
  ...
</file>
```

**来源**：`SourceContextService` 从 Story 文件的 "File List" 段中提取文件路径，然后：
1. 对每个文件评分（是否在 File List 中、是否在 git diff 中、是否测试文件等）
2. 按分数筛选 top N 文件
3. 小文件全文嵌入，大文件只取 git hunks（变更区域），超大文件按符号边界截断
4. 受 per-workflow token 预算控制

**3f. Story 文件（放最后）**

```xml
<file id="def56789" path="docs/sprint-artifacts/3-1-user-authentication.md" label="STORY FILE">
  Story 标题、验收标准、任务列表、开发笔记、文件列表...
</file>
```

**来源**：当前 Story 的完整文件，全文嵌入。**这是 LLM 最需要关注的内容，所以放在 context 最后——利用 LLM 的 recency-bias，最后出现的信息获得最高的注意力权重。**

### 段 4：variables — 编译器解析的变量

variables 段列出 Prompt 中所有可解析变量的值。嵌入到 context 中的文件通过 `file_id` 交叉引用：

```xml
<var name="project_context" file_id="a1b2c3d4" load_strategy="EMBEDDED">
  embedded in prompt, file id: a1b2c3d4
</var>
<var name="epic_num">3</var>
<var name="story_id">3.1</var>
<var name="story_key">3-1-user-authentication</var>
<var name="user_name">McQueen</var>
<var name="communication_language">English</var>
```

**来源**：11 步变量解析流水线（`variables/core.py`），按优先级从低到高：
1. config.yaml 全局配置 → 2. workflow.yaml 覆盖 → 3. CLI 参数 → 4. 计算变量（story_id, story_key） → 5. 递归解析 → ... → 11. 清理内部变量

**设计意图**：instructions 中的 `{story_key}`、`{date}` 等占位符在编译时被替换为实际值。嵌入文件用 `file_id` 引用而非重复内容——LLM 看到 `file_id="a1b2c3d4"` 就知道去 context 段找对应文件。

### 段 5：instructions — 执行指令

instructions 是从工作流 XML 模板过滤后的结构化执行步骤：

```xml
<step n="1" goal="Find next ready story and load it">
  <action>Use story_path directly</action>
  <action>Read COMPLETE story file</action>
</step>

<step n="5" goal="Implement task following red-green-refactor cycle">
  <critical>FOLLOW THE STORY FILE TASKS/SUBTASKS SEQUENCE EXACTLY</critical>
  <!-- RED: write failing tests first -->
  <!-- GREEN: minimal implementation -->
  <!-- REFACTOR: improve while keeping tests green -->
</step>

<step n="final" goal="Execution Self-Audit">
  <critical>DO NOT SKIP THIS STEP</critical>
  <output>
## Execution Self-Audit
### Completion Status
- Primary objective: [what was accomplished]
- Status: [COMPLETE / PARTIAL / DEFERRED]
  ...
  </output>
</step>
```

**来源**：加载工作流的 `instructions.xml`，经过编译器的过滤管线：
1. **XML 解析**：解析 `<workflow>` 下的所有标签
2. **白名单过滤**：保留 `<step>`、`<action>`、`<check>`、`<critical>`、`<mandate>` 等执行标签
3. **黑名单移除**：删除 `<ask>`（交互提示）、`<output>`（中间输出）、`<template-output>`、用户条件分支、HALT/GOTO（自动化不需要这些）
4. **变量替换**：将 `{story_key}`、`{date}` 等占位符替换为实际值
5. **后处理**：应用 patch 文件中定义的 regex 规则（如果项目有自定义 patch）

**设计意图**：原始的工作流 XML 是为人机交互设计的——有"问用户"、有"等待选择"、有"显示状态"。编译器把这些交互元素全部去掉，只保留 LLM 需要执行的指令。Self-Audit 放在最后一步，是 LLM 输出前最后看到的内容，利用 recency-bias 强制自检。

### 完整示例

下面是五个段组装后的完整 Prompt（以 dev_story Phase、Story 3.1 "user-authentication" 为例，内容做了简化）：

```xml
<?xml version="1.0" encoding="UTF-8"?>
<compiled-workflow>

  <!-- MISSION -->
  <mission><![CDATA[
Execute a story by implementing tasks/subtasks, writing tests, validating, and updating the story file per acceptance criteria.

Target: Story 3.1 - user-authentication
Implement all tasks and subtasks following TDD methodology.
  ]]></mission>

  <!-- COMPASS -->
  <compass><![CDATA[
## Dev Story Guide (from project experience)

- This project uses pytest with async fixtures — always @pytest.mark.asyncio
- The User model is in src/models/user.py — follow its field conventions
- Previous stories hit a pitfall: SQLAlchemy async session requires explicit commit
  in test teardown, otherwise tests pass locally but fail in CI
- The repository pattern is the team's preferred data access style (see design-repository-pattern)
  ]]></compass>

  <!-- CONTEXT -->
  <context>

    <file id="a1b2c3d4" path="docs/project-context.md" label="PROJECT CONTEXT"><![CDATA[
# Project Context
## Tech Stack
- Python 3.11+, FastAPI, SQLAlchemy 2.0 (async), PostgreSQL
- Testing: pytest + pytest-asyncio + httpx for API tests
- Package manager: uv

## Coding Standards
- Use repository pattern for data access
- All API endpoints must have request/response schemas
- Error responses follow RFC 7807 Problem Details format
    ]]></file>

    <file id="e5f6a7b8" path="docs/architecture.md" label="ARCHITECTURE"><![CDATA[
[LLM-compressed from 4500 tokens → 1200 tokens]

## Authentication Module
- JWT-based auth with refresh token rotation
- UserRepository handles all DB operations
- AuthService orchestrates login/register/logout flows
- Middleware: JWTValidationMiddleware on protected routes
- All auth routes under /api/auth/* prefix
    ]]></file>

    <file id="1234abcd" path="docs/epic-3-auth.md" label="EPIC"><![CDATA[
# Epic 3: Authentication System

## Goal
Implement secure JWT-based authentication with user registration, login, logout, and token refresh.

## Key Decisions
- Use bcrypt for password hashing (not argon2 — team familiarity)
- Refresh tokens stored in DB for revocation capability
- Rate limiting on login endpoint (5 attempts / minute)
    ]]></file>

    <file id="c0d1e2f3" path=".bmad-assist/antipatterns/code-epic-3.md" label="CODE ANTIPATTERNS"><![CDATA[
## Antipatterns from previous code reviews in this epic
- CRITICAL: Do not use sync SQLAlchemy session — use AsyncSession everywhere
- IMPORTANT: Do not catch broad Exception in auth handlers — catch specific auth errors
- MINOR: Avoid f-strings in SQL queries — use parameterized queries
    ]]></file>

    <file id="5678efgh" path="src/models/user.py" label="SOURCE CODE"><![CDATA[
from sqlalchemy import Column, String, Boolean, DateTime
from sqlalchemy.orm import DeclarativeBase
from datetime import datetime

class Base(DeclarativeBase):
    pass

class User(Base):
    __tablename__ = "users"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    email: Mapped[str] = mapped_column(String, unique=True, index=True)
    hashed_password: Mapped[str] = mapped_column(String)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    ]]></file>

    <file id="9abc1234" path="src/repositories/user_repository.py" label="SOURCE CODE"><![CDATA[
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

class UserRepository:
    def __init__(self, session: AsyncSession):
        self._session = session

    async def get_by_email(self, email: str) -> User | None:
        stmt = select(User).where(User.email == email)
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def create(self, user: User) -> User:
        self._session.add(user)
        await self._session.commit()
        await self._session.refresh(user)
        return user
    ]]></file>

    <file id="def56789" path="docs/sprint-artifacts/3-1-user-authentication.md" label="STORY FILE"><![CDATA[
# Story 3.1: User Authentication

## Status: ready-for-dev

## Acceptance Criteria
- AC1: User can register with email and password
- AC2: User can login and receive JWT access + refresh tokens
- AC3: User can refresh expired access token using refresh token
- AC4: User can logout (revokes refresh token)
- AC5: Login endpoint has rate limiting (5 attempts/min)

## Tasks/Subtasks
- [ ] 1.1 Create AuthService class with register/login/logout methods
- [ ] 1.2 Implement JWT token generation and validation
- [ ] 1.3 Add /api/auth/* endpoints with request/response schemas
- [ ] 1.4 Implement refresh token rotation and revocation
- [ ] 2.1 Write unit tests for AuthService
- [ ] 2.2 Write integration tests for auth API endpoints
- [ ] 2.3 Write tests for rate limiting behavior

## Dev Notes
- Use existing UserRepository from src/repositories/user_repository.py
- JWT secret from environment variable JWT_SECRET
- Refresh tokens: store in DB, 7-day expiry
- Rate limiting: use slowapi library (already in requirements)

## File List
- src/services/auth_service.py (new)
- src/api/auth_routes.py (new)
- src/schemas/auth.py (new)
- src/models/user.py (modify — add refresh_token fields)
- src/repositories/user_repository.py (modify — add refresh token methods)
- tests/unit/test_auth_service.py (new)
- tests/integration/test_auth_api.py (new)
    ]]></file>

  </context>

  <!-- VARIABLES -->
  <variables>
    <var name="project_context" file_id="a1b2c3d4" load_strategy="EMBEDDED">embedded in prompt, file id: a1b2c3d4</var>
    <var name="architecture_file" file_id="e5f6a7b8" load_strategy="EMBEDDED">embedded in prompt, file id: e5f6a7b8</var>
    <var name="epic_num">3</var>
    <var name="story_id">3.1</var>
    <var name="story_key">3-1-user-authentication</var>
    <var name="story_title">user-authentication</var>
    <var name="story_file" file_id="def56789">embedded in prompt, file id: def56789</var>
    <var name="story_dir">/path/to/_bmad-output/implementation-artifacts</var>
    <var name="sprint_status">/path/to/_bmad-output/implementation-artifacts/sprint-status.yaml</var>
    <var name="output_folder">/path/to/_bmad-output</var>
    <var name="user_name">McQueen</var>
    <var name="communication_language">English</var>
    <var name="document_output_language">English</var>
    <var name="user_skill_level">expert</var>
    <var name="date">2026-04-30</var>
  </variables>

  <!-- INSTRUCTIONS -->
  <instructions>

    <critical>Only modify the story file in these areas: Tasks/Subtasks checkboxes, Dev Agent Record, File List, Change Log, and Status</critical>
    <critical>Execute ALL steps in exact order; do NOT skip steps</critical>
    <critical>Absolutely DO NOT stop because of "milestones" or "significant progress". Continue until the story is COMPLETE unless a HALT condition is triggered.</critical>

    <step n="1" goal="Find next ready story and load it">
      <action>Use story_path directly</action>
      <action>Read COMPLETE story file</action>
      <action>Parse sections: Story, Acceptance Criteria, Tasks/Subtasks, Dev Notes, File List, Status</action>
      <action>Identify first incomplete task (unchecked [ ]) in Tasks/Subtasks</action>
    </step>

    <step n="2" goal="Load project context and story information">
      <action>Load project_context for coding standards and project-wide patterns</action>
      <action>Extract developer guidance from Dev Notes</action>
    </step>

    <step n="3" goal="Detect review continuation">
      <action>Check if Senior Developer Review section exists in story file</action>
      <action>Set review_continuation = false (fresh start)</action>
    </step>

    <step n="4" goal="Mark story in-progress">
      <action>Update sprint-status: 3-1-user-authentication → "in-progress"</action>
    </step>

    <step n="5" goal="Implement task following red-green-refactor cycle">
      <critical>FOLLOW THE STORY FILE TASKS/SUBTASKS SEQUENCE EXACTLY</critical>
      <!-- RED: write failing tests first -->
      <action>If test.fixme() tests exist: convert to test() and confirm they FAIL</action>
      <action>If no test.fixme(): write FAILING tests for the task</action>
      <!-- GREEN: minimal implementation -->
      <action>Implement MINIMAL code to make tests pass</action>
      <!-- REFACTOR: improve while keeping tests green -->
      <action>Improve code structure; follow architecture patterns</action>
      <critical>NEVER implement anything not mapped to a specific task/subtask</critical>
      <critical>NEVER proceed to next task until current task is complete AND tests pass</critical>
    </step>

    <step n="6" goal="Author comprehensive tests">
      <action>Create unit tests for business logic</action>
      <action>Add integration tests for component interactions</action>
      <action>Cover edge cases from Dev Notes</action>
    </step>

    <step n="7" goal="Run validations and tests">
      <action>Run all tests — no regressions</action>
      <action>Run linting and code quality checks</action>
      <action>Validate ALL acceptance criteria are satisfied</action>
    </step>

    <step n="8" goal="Validate and mark task complete">
      <critical>NEVER mark a task complete unless ALL conditions are met</critical>
      <action>Verify tests ACTUALLY EXIST and PASS 100%</action>
      <action>Confirm implementation matches task/subtask exactly</action>
      <action>Mark checkbox [x] only when all gates pass</action>
      <action>Update File List with ALL changed files</action>
    </step>

    <step n="9" goal="Story completion and mark for review">
      <action>Verify ALL tasks marked [x]</action>
      <action>Run full regression suite</action>
      <action>Update story Status to "review"</action>
    </step>

    <step n="final" goal="Execution Self-Audit">
      <critical>DO NOT SKIP THIS STEP</critical>
      <output>
## Execution Self-Audit
### Completion Status
- Primary objective: [one sentence stating what was accomplished]
- Status: [COMPLETE / PARTIAL / DEFERRED]

### If PARTIAL or DEFERRED:
- What remains: [specific list]
- Justification: [specific reason for each item]

### Phase-Specific Audit
- [ ] All acceptance criteria satisfied
- [ ] No "not essential" used as skip justification
- [ ] All tests pass (no test.fixme() remaining)
- [ ] File List complete with ALL changed files
- [ ] Story status set to "review"
      </output>
    </step>

  </instructions>

</compiled-workflow>
```

### 整体设计要点

| 设计 | 说明 |
|------|------|
| **Recency-bias 排序** | 文件按 项目上下文 → 架构 → Epic → 反模式 → 源码 → Story 排列，Story 放最后权重最高 |
| **File ID 交叉引用** | variables 中的 `file_id` 对应 context 中的文件，LLM 可交叉定位，无需重复内容 |
| **Compass 独立段** | Twin 的项目经验注入在 mission 和 context 之间，位置可辨识 |
| **Strategic Context 压缩** | 架构文档超过 token 预算时，helper LLM 压缩 + SHA-256 磁盘缓存，不重复压缩 |
| **指令过滤** | 交互元素（`<ask>`、`<output>`、用户条件分支）被编译器自动移除，只保留执行指令 |
| **Self-Audit 末尾注入** | 自检清单在 instructions 最后一步，LLM 输出前最后看到的内容，recency-bias 最强 |

---

## Digital Twin：你的自动化代理

Digital Twin 是 bmad-assist 最独特的设计——它是**使用者在自动化流程中的代理**。

### 解决什么问题

LLM 在长执行中会"跑偏"：范围缩减、过早放弃、无依据跳过。你不可能时刻盯着它，但你需要它按规范完成工作。

### 怎么解决

Twin 的核心思路：**不试图在执行中防跑偏，而是让跑偏可检测、可恢复**。

```
Twin.guide()     ← 执行前：从项目经验生成 compass，注入到 Prompt
       ↓
execute_phase()  ← 正常执行
       ↓
Twin.reflect()   ← 执行后：审查完整输出，对比三层信息
       ↓
  ┌─ CONTINUE → 继续
  ├─ RETRY    → git stash，带纠正 compass 重新执行
  └─ HALT     → 停机，交给你决策
```

### 三层对比审查

| 对比 | 检测什么 |
|------|---------|
| 被要求做什么 vs LLM 声称做了什么 | 范围缩减、目标偏离 |
| LLM 声称的结果 vs git diff 客观事实 | 虚假完成声明 |
| 本次执行 vs 项目历史经验 | 重复失败模式、环境陷阱 |

### 经验 Wiki

Twin 在运行中持续积累项目经验，以 Markdown 文件的形式存储：

```
experiences/
├── INDEX.md                     ← 自动生成的索引
├── env-async-session.md         ← 环境知识：async session 陷阱
├── pattern-test-first.md        ← 成功模式：先写测试
├── pattern-skip-flaky-test.md   ← 失败模式：跳过 flaky test
├── design-repository-pattern.md ← 设计偏好：repository pattern
├── guide-dev-story.md           ← 阶段指引：dev_story
└── ...
```

每页 100-500 token，人可读可编辑。Twin 每次运行最多创建 1 页 + 更新 1-2 页，低摩擦。经验跨 Epic 持久化，越用越准。

---

## 快速开始

### 安装

```bash
pip install bmad-assist
```

### 配置

在项目根目录创建 `bmad-assist.yaml`：

```yaml
providers:
  master:
    provider: claude-sdk
    model: sonnet
  helper:
    provider: claude-sdk
    model: haiku

loop:
  story:
    - create_story
    - validate_story
    - validate_story_synthesis
    - dev_story
    - code_review
    - code_review_synthesis
  epic_teardown:
    - retrospective

twin:
  enabled: true
  provider: claude-sdk
  model: opus
```

### 运行

```bash
# 运行所有 Epic
bmad-assist run --project ./my-project

# 指定 Epic 范围
bmad-assist run --project ./my-project -E 1-3

# 启用 Digital Twin
bmad-assist run --project ./my-project --twin

# 从中断处恢复
bmad-assist run --project ./my-project  # 自动检测 state.yaml 恢复
```

---

## 关键设计决策

| 决策 | 选择 | 原因 |
|------|------|------|
| 编排方式 | 编译器 + 状态机 | 确定性优于 Agent 自由编排 |
| 代码隔离 | 单仓库 + state.yaml | 不需要 Worktree/Fake Root 的基础设施复杂度 |
| Prompt 构建 | 编译器注入完整上下文 | LLM 不需要猜测上下文，减少跑偏 |
| 防跑偏 | 事后审查 + RETRY | 注入方式在长执行中必然被稀释 |
| 经验积累 | Markdown Wiki | 人可读可编辑，Karpathy Wiki 理念 |
| 多 LLM | Master + 并行审查 | 代码写一次，审查多视角 |
| Twin 模型 | 独立于执行模型 | 避免同模型同盲点，Twin 需要更强推理 |

---

## 项目来源

bmad-assist 是 [BMAD Method](https://github.com/bmad-method/bmad-method) 的社区项目，由 [Pawel-N-pl](https://github.com/Pawel-N-pl) 发起。它 fork 了 bmad-method 并添加了第 4 阶段（Implementation）的自动化能力。

Digital Twin 模块是在 bmad-assist 基础上的进一步演进，作者在经历了多个自动化方案的迭代后（详见 [automation-evolution.md](automation-evolution.md)），最终选择了"编译-执行-审查"的三层架构。
