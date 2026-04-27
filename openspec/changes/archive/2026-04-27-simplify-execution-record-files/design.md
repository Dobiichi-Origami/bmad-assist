## Context

ExecutionRecord 是 Twin reflect 的输入数据结构，当前包含 `files_diff`（完整 git diff）和 `files_modified`（文件名列表）两个字段。`files_diff` 在 `twin.py:181-204` 中被 `prepare_llm_output` 截断后拼到 prompt 末尾的 `# Git Diff (prepared)` 段，但 Twin LLM 主要依赖 `files_modified` 做"声称 vs 实际"的交叉验证，完整 diff 增加了 prompt 体积却价值有限。

同时 `files_modified` 通过 `git diff --name-only` 采集，只覆盖已跟踪文件的修改，遗漏未追踪新文件（phase 执行中常见）和暂存文件。

## Goals / Non-Goals

**Goals:**
- 移除 `files_diff` 字段及相关截断、拼接逻辑，简化 ExecutionRecord 和 reflect prompt
- 扩展 `files_modified` 覆盖全部变更类型（已跟踪修改、暂存、未追踪新文件）

**Non-Goals:**
- 不改变 reflect prompt 模板中 `Files modified:` 的嵌入方式
- 不改变 `files_modified` 的类型（保持 `list[str]`）
- 不引入新的 diff 采集策略（如按 phase 前后 snapshot 对比）

## Decisions

### D1: 用 `git status --porcelain` 替代 `git diff --name-only`

**选择**: `git status --porcelain`

**替代方案**:
- `git diff HEAD --name-only` + `git ls-files --others --exclude-standard`: 两条命令，覆盖全但冗余
- `git diff --name-only` (现状): 遗漏未追踪和暂存文件

**理由**: `git status --porcelain` 一条命令覆盖所有变更类型，输出格式稳定（XY filename）。解析需处理：XY 状态前缀（2 字符）、重命名格式（`XY old -> new`，取新路径）、引号包裹的特殊文件名。committer.py 的 `stash_working_changes` 已有相同格式的解析逻辑，`_capture_files_modified` 采用一致的解析方式，但不抽取共享函数——逻辑仅 ~5 行且两处职责不同，抽取收益不大。

### D2: 直接移除 `files_diff`，不保留过渡期

**选择**: 一步到位移除

**替代方案**:
- 标记 deprecated，下个版本移除
- 保留字段但置空

**理由**: `files_diff` 只在 `twin.py` 内部使用，无外部消费者，不存在兼容性问题。保留空字段只会增加维护困惑。

### D3: 函数重命名 `_capture_git_diff` → `_capture_files_modified`

**选择**: 重命名以准确反映职责

**理由**: 旧名暗示返回 diff，新名明确返回文件列表。返回类型从 `tuple[list[str], str]` 简化为 `list[str]`。

## Risks / Trade-offs

- [风险] Twin 失去查看完整 diff 的能力 → 可接受：Twin 的三层交叉验证中"Self-audit vs git diff"改为"Self-audit vs files_modified"，仍能检测"声称改了但实际没改"的不一致；若需深入查看 diff，Twin 的 runner 调用方可在 RETRY 时的 correction compass 中提供
- [风险] `git status --porcelain` 在非 git 仓库中会报错 → 已有 try/except 兜底，行为不变（返回空列表）
