## 1. ExecutionRecord 数据模型

- [x] 1.1 从 `ExecutionRecord` dataclass 移除 `files_diff` 字段
- [x] 1.2 将 `_capture_git_diff()` 替换为 `_capture_files_modified()`，使用 `git status --porcelain` 采集，返回 `list[str]`
- [x] 1.3 修改 `build_execution_record()` 返回类型：移除 `files_diff` 赋值，改用 `_capture_files_modified()` 的返回值

## 2. Twin Reflect 逻辑

- [x] 2.1 从 `Twin.reflect()` 移除 `prepared_diff` 的截断和拼接（删除 `prepare_llm_output(record.files_diff)` 和 `# Git Diff (prepared)` 段）

## 3. 测试更新

- [x] 3.1 更新 `tests/twin/test_execution_record.py`：移除 `files_diff` 断言，新增 `git status --porcelain` 各场景测试（已跟踪修改、未追踪新文件、暂存文件、混合变更、.gitignore 排除）
- [x] 3.2 更新 `tests/twin/test_twin.py`：移除 `files_diff` 相关断言
- [x] 3.3 更新 `tests/twin/test_integration.py`：移除 `files_diff` 相关断言
