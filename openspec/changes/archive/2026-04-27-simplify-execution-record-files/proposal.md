## Why

ExecutionRecord 当前有两个字段 `files_diff`（完整 git diff 输出）和 `files_modified`（变更文件名列表），但 `files_diff` 体积大、需要智能截断，且 Twin LLM 从未有效利用过完整 diff 内容——它只需要知道"改了哪些文件"就足以做交叉验证，想看 diff 可以自己看。同时 `files_modified` 来源仅是 `git diff --name-only`，只覆盖已跟踪文件的修改，遗漏了未追踪的新文件和暂存文件，而 phase 执行中创建新文件是常见操作。

## What Changes

- **BREAKING**: 移除 `ExecutionRecord.files_diff` 字段
- **BREAKING**: 移除 `_capture_git_diff()` 函数，替换为 `_capture_files_modified()` 函数
- **BREAKING**: 移除 `build_execution_record()` 的 `files_diff` 相关逻辑
- 修改 `_capture_files_modified()` 使其覆盖全部变更类型：已跟踪修改、暂存文件、未追踪新文件
- 移除 `Twin.reflect()` 中对 `record.files_diff` 的截断和拼接逻辑
- 移除 prompt 中 `# Git Diff (prepared)` 段

## Capabilities

### New Capabilities

（无新增能力）

### Modified Capabilities

- `execution-record`: 移除 `files_diff` 字段，`files_modified` 扩展覆盖范围至全部变更类型

## Impact

- `src/bmad_assist/twin/execution_record.py`: 移除 `files_diff` 字段、替换采集函数
- `src/bmad_assist/twin/twin.py`: 移除 `prepared_diff` 拼接逻辑
- `src/bmad_assist/core/loop/runner.py`: 无需改动（只读 `record` 字段，不传 `files_diff`）
- `src/bmad_assist/core/loop/epic_phases.py`: 同上
- `tests/twin/test_execution_record.py`: 更新测试用例
- `tests/twin/test_twin.py`: 移除 `files_diff` 相关断言
- `tests/twin/test_integration.py`: 同上
