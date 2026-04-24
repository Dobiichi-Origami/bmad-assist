## Context

Digital Twin 的 `format_self_audit()` 使用正则 `r"^## (?:Execution )?Self[- ]Audit\s*\n(.*?)(?=^## |\Z)"` 从 LLM 输出中提取自审段落。当前架构：

```
build_execution_record()  [无 provider 访问]
  → format_self_audit(llm_output)  [纯正则]
  → record.self_audit

Twin.reflect(record)  [有 self._provider]
  → build_reflect_prompt(self_audit=record.self_audit)
  → _invoke_llm(full_prompt)
```

正则仅匹配 `## Self-Audit` / `## Execution Self-Audit` / `## Self Audit` 三种标题，对中文标题（"审查"）、非 h2 标题、语义等价但命名不同的段落完全丢失。Twin 已有 `_invoke_llm()` 和 provider 管道，可直接复用。

## Goals / Non-Goals

**Goals:**
- 当正则匹配失败时，用 LLM 语义抽取补齐自审信息
- 最小化额外延迟和成本（正则成功时零开销）
- 支持中英文多语言标题变体、任意标题级别
- 可配置抽取模型，推荐轻量模型

**Non-Goals:**
- 不修改 `format_self_audit()` 正则本身
- 不修改 `build_execution_record()` 的签名或流程
- 不引入新的 provider 或依赖
- 不在正则匹配成功时额外调用 LLM 校验内容准确性

## Decisions

### Decision 1: LLM 抽取放在 Twin.reflect() 内部

**选择**：在 `Twin.reflect()` 中，`build_reflect_prompt()` 之前，检查 `record.self_audit is None`，若为 None 则调用 `_extract_self_audit_llm()`。

**理由**：
- `Twin` 已有 `self._provider`，无需修改 `build_execution_record` 的签名或引入新的依赖注入路径
- 抽取是 reflect 的关注点——reflect 已处理 `record.self_audit`，且已执行 LLM 调用
- 避免暴露 provider 到 `build_execution_record` 层（打破关注点分离）

**备选**：
- (a) 在 `build_execution_record` 中加 provider 参数 → 需改 runner 调用签名，侵入性强
- (b) 独立函数需要调用方传 provider → 破坏现有调用约定

### Decision 2: 两层抽取（正则优先 → LLM 兜底）

**选择**：保留正则作为快速路径，仅当 `format_self_audit()` 返回 None 时触发 LLM。

**理由**：正则匹配时零延迟零成本，LLM 仅处理边缘情况。

### Decision 3: audit_extract_model 默认 None 回退主模型

**选择**：`TwinProviderConfig.audit_extract_model: str | None = None`，None 时回退 `self.config.model`。

**理由**：默认 None 对非 Claude 提供者（gemini、kimi 等）更安全，用户可按需配置轻量模型（如 "haiku"）。

### Decision 4: 抽取 prompt 返回 YAML

**选择**：抽取 prompt 要求 LLM 返回 `found: bool` + `content: |` 的 YAML，复用 `extract_yaml_block()` 解析。

**理由**：与 Twin 其他输出格式一致；`found: false` 明确区分"未找到"和"找到但为空"；复用已有解析管道。

### Decision 5: 抽取失败时降级为 None

**选择**：LLM 抽取失败（provider 异常、YAML 解析失败、`found: false`）→ 返回 None，reflect 继续使用 `(No Self-Audit section found in output)`。

**理由**：抽取是尽力而为的增强，不是关键路径。当前系统在 `self_audit=None` 时已正常工作。

## Risks / Trade-offs

- **[额外延迟]** → 仅正则失败时触发，预计 1-3s（轻量模型）；可接受因为正则失败是非标准格式场景
- **[Token 成本]** → 每次抽取约 3-12K input tokens（取决于输出长度）；配置轻量模型降低成本
- **[超大输出]** → `llm_output` 可能超出抽取模型上下文窗口；使用 `prepare_llm_output()` 做智能截断（head 1/4 + tail 3/4），确保文档头尾信息不丢
- **[循环风险]** → 抽取 LLM 输出格式不规范；YAML 中 `found: false` 安全门防止误提取
- **[向后兼容]** → `format_self_audit()` 不变，`audit_extract_model` 有默认值，所有现有测试通过
