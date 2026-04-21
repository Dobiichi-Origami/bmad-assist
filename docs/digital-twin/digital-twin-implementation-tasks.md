# Digital Twin 实现任务拆解

> 主任务：实现 Digital Twin + Experience Wiki 系统
> 设计文档：docs/digital-twin-design.md (v6)

---

## 子任务 1: Wiki 基础设施

**目标**: 实现 wiki.py 模块，提供文件 I/O、INDEX 自动生成、frontmatter 解析、页面验证等基础能力

**改动**:
- 新建 `src/bmad_assist/twin/__init__.py`
- 新建 `src/bmad_assist/twin/wiki.py`
- 实现：read_page, write_page, list_pages, page_exists, extract_links
- 实现：parse_frontmatter, rebuild_index（含反向引用计算）
- 实现：apply_section_patches（段落级替换）
- 实现：validate_page_name（命名规范校验）
- 实现：append_evidence_row, update_frontmatter（含 source_epics 追踪）
- 实现：init_wiki（含 seed guide 页模板）
- 实现：load_guide_page（Strategy D：只加载 INDEX + guide 页）
- 实现：extract_evidence_table（EVOLVE 时保留原始 evidence 表）
- 实现：fix_content_block_scalars（YAML 解析容错）
- 实现：prepare_llm_output（超长输出 head+tail 截断）
- 实现：derive_confidence（含 negative pattern cap）
- 删除：load_pages_by_priority（已简化为 load_guide_page）

**置信度等级**：tentative / established / definitive（单一表达，YAML frontmatter 和 INDEX 统一使用单词，不经过数字映射）。

**页面生命周期**：只有两种状态——存在/不存在。无 DORMANT/ARCHIVED。
**PageUpdate**：3 种 action——create/update/evolve。无 archive。

**参考文件**:
- `docs/digital-twin-design.md` Section 4 (Wiki 设计), 8.2 (wiki.py 接口)

**代码量估算**: ~120 行

---

## 子任务 2: 自检清单注入

**目标**: 修改各 workflow 的 `<output-template>`，注入从上游 acceptances 派生的自检清单

**改动**:
- 修改 `workflows/dev-story/instructions.xml` — 加入 dev_story 自检清单
- 修改 `workflows/create-story/instructions.xml` — 加入 create_story 自检清单
- 修改 `workflows/code-review/instructions.xml` — 加入 code_review 自检清单
- 修改 `workflows/validate-story/instructions.xml` — 加入通用 + validate_story 自检
- 修改 `workflows/validate-story-synthesis/instructions.xml` — 加入 synthesis 自检
- 修改 `workflows/code-review-synthesis/instructions.xml` — 加入 synthesis 自检
- 修改 `workflows/retrospective/instructions.md` — 加入 retrospective 自检
- 修改 `qa/prompts/remediate.xml` — 加入 qa_remediate 自检
- 修改 TEA workflow 的 instructions — 加入 atdd/test_review/nfr_assess 等 自检

**通用自检模板**（所有 phase 共享）:
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

### Phase-Specific Audit
[从上游 acceptances 派生的具体检查项]
</output-template>
```

**参考文件**:
- `docs/ref-self-audit-acceptances.md` — 18 个 phase 的上游 acceptances 完整列表
- 各 workflow 的 `checklist.md` — 上游原始验收条件

**代码量估算**: ~15 行 XML 修改 × 12 个 workflow

---

## 子任务 3: ExecutionRecord + qa_remediate 修补

**目标**: 构建 Twin reflect 所需的完整输入数据；修补 qa_remediate 丢失 LLM 输出的问题

**改动**:
- 新建 `src/bmad_assist/twin/execution_record.py`
- 实现 ExecutionRecord dataclass（phase, mission, llm_output, self_audit, success, duration_ms, error, phase_outputs, files_modified, files_diff）
- 实现 build_execution_record()：从 state + result + git diff 构建
- 实现 format_self_audit()：从 llm_output 解析 Self-Audit 段
- 修改 `handlers/qa_remediate.py`：收集 all_llm_outputs，在 PhaseResult.ok() 中增加 `"response"` 字段

**关键设计决策**:
- llm_output 默认不截断，仅超长时 head(1/4)+tail(3/4) 截断（prepare_llm_output）
- files_modified 和 files_diff 从 git diff --name-only / git diff 获取
- files_diff 是完整 git diff（不用 --stat），让 Twin 可交叉验证

**参考文件**:
- `docs/digital-twin-design.md` Section 2 (ExecutionRecord 定义)
- `src/bmad_assist/core/loop/handlers/qa_remediate.py` — 当前实现（缺 response）
- `src/bmad_assist/providers/base.py` — ProviderResult 定义

**代码量估算**: ~80 行 (execution_record.py) + ~10 行 (qa_remediate.py)

---

## 子任务 4: Twin Reflect（核心）

**目标**: 实现 Twin 的 reflect 能力——审查执行结果、更新 wiki、做决策

**改动**:
- 新建 `src/bmad_assist/twin/twin.py` — Twin 类
- 新建 `src/bmad_assist/twin/prompts.py` — reflect prompt 模板
- 实现 TwinResult / PageUpdate / DriftAssessment Pydantic 模型
- 实现 Twin.reflect(record, is_retry) — 组装 prompt（INDEX + guide 页 + 执行记录）→ 调用 LLM → 解析 YAML
- 实现 apply_page_updates() — 执行 Twin 的 PageUpdate 输出（含 EVOLVE {{EVIDENCE_TABLE}} 保留）
- Phase-specific 审查指引（硬编码在 prompts.py 中）
- 初始化指引（INDEX 为空时注入）
- Twin 失败降级（YAML 解析失败 → 重试一次 → is_retry 决定 CONTINUE/HALT）
- Challenge mode（每 5 epics 对 negative pattern 做挑战）
- 去重警告（子串检测只警告不自动转换）

**加载策略（Strategy D：最小加载）**:
- reflect 只加载：INDEX.md + guide-{phase_type}
- 约 ~800-1800 token 的 wiki 内容
- Twin 通过 INDEX 了解所有页面，但只读 guide 页的完整内容
- EVOLVE 只能对已加载的页面执行（Twin 没读过的不应重写）
- UPDATE 的 append_evidence 不需要读页面内容（代码追加）

**参考文件**:
- `docs/digital-twin-design.md` Section 6.1 (Reflect Prompt), 7 (TwinResult), 9.5 (evolve 安全保护)
- `docs/ref-phase-wiki-mapping.md` — Phase → Wiki 操作映射 + phase-specific 审查指引

**代码量估算**: ~200 行

---

## 子任务 5: Twin Guide（compass 生成）

**目标**: 实现 Twin 的 guide 能力——从 wiki guide 页生成 phase-specific compass

**改动**:
- 在 `twin/twin.py` 中增加 Twin.guide() 方法
- 在 `twin/prompts.py` 中增加 guide prompt 模板
- Guide 加载：INDEX + guide-{phase_type}（不加载 linked pages）
- 当 guide 页不存在时，从所有 env/pattern/design 页面推理生成 compass
- Guide 不产生 wiki 更新

**参考文件**:
- `docs/digital-twin-design.md` Section 5 (Compass), 6.2 (Guide Prompt)

**代码量估算**: ~80 行

---

## 子任务 6: Twin 配置 + Runner 集成

**目标**: 将 Twin 接入 bmad-assist 主循环

**改动**:
- 新建 `src/bmad_assist/twin/config.py` — TwinProviderConfig
- 修改 `src/bmad_assist/core/config/models/providers.py` — 增加 twin 配置段
- 修改 `src/bmad_assist/core/loop/runner.py` — 主循环集成：
  - phase 执行前：twin.guide() → compass
  - phase 执行后：build_execution_record() → twin.reflect() → apply_page_updates() → decision 处理
  - RETRY 逻辑：git stash → retry_count < max_retries → 重试；retry_exhausted → retry_exhausted_action
  - 纠正 compass 追加到原有 compass 之后，不替换
- Twin 失败降级：guide 失败 → compass=None；reflect 失败（首次）→ CONTINUE；reflect 失败（RETRY后）→ HALT

**TwinProviderConfig**:
```python
class TwinProviderConfig(BaseModel):
    provider: str = "claude"
    model: str = "opus"
    enabled: bool = True
    max_retries: int = 2
    retry_exhausted_action: Literal["halt", "continue"] = "halt"
```

**参考文件**:
- `docs/digital-twin-design.md` Section 8.3 (runner.py 集成), 9.7 (RETRY 兜底), 9.9 (失败降级)
- `src/bmad_assist/core/loop/runner.py` — 主循环代码
- `src/bmad_assist/core/config/models/providers.py` — 现有 provider 配置

**代码量估算**: ~60 行

---

## 子任务 7: Compiler Compass 支持

**目标**: 让 compiler 的 compiled prompt 支持 `<compass>` 段

**改动**:
- 修改 `src/bmad_assist/compiler/types.py` — CompilerContext 增加 `compass: str | None = None`
- 修改 `src/bmad_assist/compiler/output.py` — generate_output() 中在 `<mission>` 后、`<context>` 前插入 `<compass>` 段
- 修改 `src/bmad_assist/core/loop/dispatch.py` — execute_phase() 传递 compass 参数
- 修改 `src/bmad_assist/core/loop/handlers/base.py` — execute() 接受 compass 参数，传入 render_prompt

**参考文件**:
- `src/bmad_assist/compiler/output.py` — generate_output() 函数
- `src/bmad_assist/compiler/types.py` — CompilerContext 定义
- `src/bmad_assist/core/loop/dispatch.py` — execute_phase() 函数
- `src/bmad_assist/core/loop/handlers/base.py` — BaseHandler.execute()

**代码量估算**: ~30 行

---

## 依赖关系

```
子任务 1 (wiki.py) ──┐
                      ├── 子任务 4 (reflect) ──┐
子任务 3 (record)  ──┘                         ├── 子任务 6 (集成)
                                               │
子任务 5 (guide)  ─────────────────────────────┤
                                               │
子任务 7 (compiler) ───────────────────────────┘
子任务 2 (自检清单) ── 独立，无依赖
```

子任务 1 和 3 是子任务 4 的前置。子任务 4、5、7 是子任务 6 的前置。
子任务 2（自检清单注入）独立，可随时做。

---

## 验证顺序

1. 子任务 2 → 验证自检清单是否让跑偏显性化（手动执行 dev_story，检查输出）
2. 子任务 1 + 3 → 验证 wiki 基础设施和 execution record 是否正确构建
3. 子任务 4 → 验证 Twin reflect 是否能检测跑偏 + 生成合法的 PageUpdate
4. 子任务 6 → 验证 RETRY 逻辑和主循环集成
5. 子任务 5 → 验证 guide/compass 生成
6. 子任务 7 → 验证 compass 在 compiled prompt 中的呈现

---

## 总代码量估算

| 子任务 | 新增代码 | 修改代码 |
|-------|---------|---------|
| 1. Wiki 基础设施 | ~120 行 | 0 |
| 2. 自检清单注入 | 0 | ~180 行 XML |
| 3. ExecutionRecord + qa 修补 | ~80 行 | ~10 行 |
| 4. Twin Reflect | ~200 行 | 0 |
| 5. Twin Guide | ~80 行 | 0 |
| 6. 配置 + 集成 | ~40 行 | ~60 行 |
| 7. Compiler Compass | 0 | ~30 行 |
| **总计** | **~520 行** | **~280 行** |
