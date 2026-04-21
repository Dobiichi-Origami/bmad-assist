# Phase → Wiki 操作映射

> 每个 atomic phase 执行后，Twin reflect 的审查重点、wiki 操作倾向和自检清单来源

---

## Phase 分类

18 个原子 phase 分三个 scope：

```
epic_setup (可选, TEA):  tea_framework → tea_ci → tea_test_design → tea_automate
story (每个 story 循环):  create_story → validate_story → validate_story_synthesis
                         → atdd → dev_story → test_review → code_review → code_review_synthesis
epic_teardown:           trace → tea_nfr_assess → retrospective
                         → qa_plan_generate → qa_plan_execute → qa_remediate
```

---

## 映射表

### Story Scope

| Phase | Twin 审查重点 | Wiki 操作倾向 | guide 页 |
|-------|-------------|-------------|---------|
| **create_story** | Story 质量：AC 可测试性、架构分析完整性、灾难性遗漏 | UPDATE guide-create-story | guide-create-story |
| **validate_story** | 验证质量：INVEST 评分合理性、发现有效性（注：多 LLM 并行，Twin 看不到单个 reviewer 输出） | 较少操作 | — |
| **validate_story_synthesis** | 综合裁决：是否正确合并 reviewer 意见、critical/high 是否处理 | UPDATE guide-create-story（从验证角度） | guide-create-story |
| **atdd** | 测试质量：RED 阶段验证、覆盖率、数据工厂、no flaky patterns | CREATE env-*（测试框架知识）UPDATE guide-atdd | guide-atdd |
| **dev_story** | 实现完整性：AC 覆盖、测试通过、是否跑偏（最高漂移风险） | CREATE pattern-*/env-*/design-* UPDATE guide-dev-story | guide-dev-story |
| **test_review** | 测试审查质量：质量分数、BDD 格式、flaky patterns | UPDATE guide-atdd | guide-atdd |
| **code_review** | 审查质量（注：多 LLM 并行，Twin 看不到单个 reviewer 输出） | 较少操作 | — |
| **code_review_synthesis** | 综合裁决 + 设计偏好提取 | UPDATE design-*（review 暴露的设计偏好）UPDATE guide-dev-story | guide-dev-story |

### Epic Setup Scope

| Phase | Twin 审查重点 | Wiki 操作倾向 | guide 页 |
|-------|-------------|-------------|---------|
| **tea_framework** | 测试框架初始化质量 | CREATE env-testing-framework | — |
| **tea_ci** | CI 管道配置质量 | UPDATE env-testing-framework | — |
| **tea_test_design** | 测试设计规划质量 | UPDATE guide-atdd | guide-atdd |
| **tea_automate** | 测试自动化扩展质量 | UPDATE guide-atdd | guide-atdd |

### Epic Teardown Scope

| Phase | Twin 审查重点 | Wiki 操作倾向 | guide 页 |
|-------|-------------|-------------|---------|
| **trace** | 追溯完整性、P0 覆盖率 | 较少操作 | — |
| **tea_nfr_assess** | NFR 评估质量、无阈值猜测 | UPDATE design-*（NFR 相关偏好） | — |
| **retrospective** | Epic 回顾质量 | UPDATE 多个 guide 页（跨 phase 总结） | — |
| **qa_plan_generate** | 测试计划质量：覆盖度、测试数量、无占位符 | UPDATE guide-qa-plan | guide-qa-plan |
| **qa_plan_execute** | 测试执行结果：通过率、发现的 bug | CREATE env-*（测试发现的环境问题） UPDATE guide-qa-execute | guide-qa-execute |
| **qa_remediate** | 修复质量：修复率、escalation 理由、是否又跳了 flaky test（高漂移风险） | CREATE/UPDATE pattern-*（修复失败模式） UPDATE guide-qa-remediate | guide-qa-remediate |

---

## 关键规律

1. **wiki 增长的两个高峰**：dev_story（CREATE pattern/env/design）和 qa_remediate（CREATE pattern）
2. **guide 页是每个 phase 的必更新项**：Twin reflect 至少检查当前 phase 的 guide 页
3. **epic_setup 主要是 env 页面创建**：一次性写入
4. **retrospective 是跨 guide 页更新的时机**：总结跨 phase 的经验
5. **前 1-2 个 epic 几乎只 CREATE，后面逐渐变为 UPDATE**
6. **code_review_synthesis 是 design 偏好的主要来源**

---

## Phase-Specific 审查指引（注入 reflect prompt）

每个 phase 类型在 reflect prompt 中注入特定的审查重点。这些指引硬编码在 prompts.py 中。

### dev_story
```
审查重点：
- AC 是否全部完成？self_audit 声称 COMPLETE 但 git diff 只有 2 个文件？
- 测试是否写了？passing rate？
- 有没有跳过 AC 并声称 "not essential"？
- 文件列表是否完整？
- 回归测试是否通过？
Wiki 倾向：CREATE pattern-*/env-*/design-*；UPDATE guide-dev-story
```

### qa_remediate
```
审查重点：
- 修复率如何？有没有 issue 被 SKIPPED 但理由不充分？
- "insufficient data" 是不是借口？（检查 git diff 有没有尝试过）
- 修复是否引入了新问题？
- escalation 是否合理？（需要架构重设计/产品决策/外部依赖/2+次失败）
Wiki 倾向：CREATE/UPDATE pattern-*；UPDATE guide-qa-remediate
```

### atdd
```
审查重点：
- RED 阶段是否验证？（所有测试应该失败）
- 测试是否覆盖了所有 AC？
- 数据工厂是否使用 faker？
- 有没有 flaky patterns？
Wiki 倾向：CREATE env-*；UPDATE guide-atdd
```

### create_story
```
审查重点：
- AC 是否具体可测试（BDD 格式）？
- 架构分析是否完整？
- 5 类灾难性遗漏是否检查？
Wiki 倾向：UPDATE guide-create-story
```

### code_review_synthesis
```
审查重点：
- 综合裁决是否合理？
- Critical/High 问题是否已修复？
- 修复后测试是否通过？
- 有没有从 review 中暴露设计偏好？
Wiki 倾向：UPDATE design-*；UPDATE guide-dev-story
```

### retrospective
```
审查重点：
- Epic 回顾是否完整？
- 行动项是否具体可执行？
Wiki 倾向：UPDATE 多个 guide 页（跨 phase 总结）
```

其他 phase 使用通用审查指引（三层对比 + decision）。
