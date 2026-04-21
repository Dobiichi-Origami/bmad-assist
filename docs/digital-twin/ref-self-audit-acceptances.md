# 各 Phase 的上游 Acceptances（用于派生自检清单）

> 来源：各 workflow 的 checklist.md / instructions.xml / instructions.md
> 自检清单直接从这些验收条件派生，不是凭空发明

---

## Story Scope

### create_story
**来源**: workflows/create-story/checklist.md

- Story file created with all required sections
- AC extracted in BDD format from epics
- Architecture analysis complete (tech stack, code structure, API patterns, DB schema, security, performance, test standards)
- Disaster prevention gaps checked (5 categories: reinvention, tech spec, file structure, regression, implementation)
- LLM-Dev-Agent optimization applied (token efficiency, scannable structure, unambiguous instructions)
- Previous story intelligence included (if applicable)
- Git intelligence included (if available)
- Status set to "ready-for-dev"
- Sprint status updated

### validate_story
**来源**: workflows/validate-story/instructions.xml (bmad-assist 新增，上游不存在)

- INVEST criteria scored (each dimension 1-10, 10 = severe violation)
- AC deep analysis done (vague/untestable/missing/conflicting/incomplete)
- Hidden dependencies discovered (undocumented tech/cross-team/infra/data/sequential)
- Estimation reality-check performed
- Technical alignment with architecture verified
- Evidence score calculated: CRITICAL(+3)/IMPORTANT(+1)/MINOR(+0.3)/CLEAN PASS(-0.5)
- Verdict: EXCELLENT(<=-3) / PASS(<3) / MAJOR_REWORK(3-7) / REJECT(>=7)

### validate_story_synthesis
**来源**: workflows/validate-story-synthesis/instructions.xml (bmad-assist 新增)

- All reviewer findings cross-validated
- DV findings integrated
- Issues by severity: Critical/High/Medium/Low
- False positives dismissed with rationale
- Changes applied to story file (natural, no review process references)
- All Critical and High issues addressed
- VALIDATION_SYNTHESIS report generated

### atdd
**来源**: workflows/testarch-atdd/checklist.md

- AC mapped to appropriate test levels (E2E/API/Component)
- Failing tests created at all appropriate levels
- Given-When-Then format used consistently
- RED phase verified (all tests fail as expected)
- Network-first mode applied for E2E tests with network requests
- Data factories use faker (no hardcoded test data)
- Fixtures with auto-cleanup created in teardown
- Mock requirements documented
- data-testid attributes listed for dev team
- Implementation checklist created (test → code task mapping)
- Red-green-refactor workflow documented
- Execution commands provided and verified
- ATDD checklist doc created and saved to correct location
- No test quality issues (flaky patterns, race conditions, hardcoded data)

### dev_story
**来源**: workflows/dev-story/checklist.md

- All tasks/subtasks checked [x]
- Every AC satisfied (implementation meets each acceptance criterion)
- No vague implementations
- No test.fixme() remaining in completed tasks
- Unit tests added/updated for all core functionality
- Integration tests where required
- E2E tests where specified
- Tests cover AC and edge cases
- All existing tests pass (no regression)
- Linting and static checks pass
- File list complete (new/modified/deleted files with relative paths)
- Dev Agent Record updated
- Change Log updated
- Story status set to "review"
- Sprint status updated to "review"
- Only allowed story file sections modified

### test_review
**来源**: workflows/testarch-test-review/checklist.md

- All enabled quality standards assessed (BDD Format/Test IDs/Priority Markers/Hard Waits/Determinism/Isolation/Fixture Patterns/Data Factories/Network-First/Assertions/Test Length/Test Duration/Flakiness)
- Quality score calculated (start 100, Critical -10, High -5, Medium -2, Low -1, bonus up to +30)
- Quality grade: A+(90-100)/A(80-89)/B(70-79)/C(60-69)/F(<60)
- Review report with all sections (Header/Executive Summary/Quality Criteria/Critical Issues/Recommendations/Best Practices/KB References)
- Recommendation: Approve/Approve with comments/Request changes/Block

### code_review
**来源**: workflows/code-review/checklist.md

- Story & context loaded and validated
- Git reality check performed (status, diff, file list comparison)
- All AC validated (IMPLEMENTED/PARTIAL/MISSING)
- Task completion audited (no false completions → CRITICAL)
- 7 quality dimensions assessed: SOLID/Hidden Bugs/Abstraction/Test Quality/Performance/Tech Debt/Security
- At least 3 issues found (adversarial requirement)
- Evidence score calculated
- Verdict: APPROVE/MAJOR_REWORK/REJECT

### code_review_synthesis
**来源**: workflows/code-review-synthesis/instructions.xml (bmad-assist 新增)

- All reviewer findings cross-validated
- DV findings integrated (CC-*/SEC-*/DB-*/DT-*/GEN-* patterns)
- Issues by severity: Critical(security/data corruption/crash)/High/medium/Low
- Fixes applied to source code (not story file)
- Tests run after each fix (never continue on test failure)
- CODE_REVIEW_SYNTHESIS report generated
- Verdict: EXEMPLARY/APPROVED/MAJOR_REWORK/REJECT
- ATDD defect check: no test.fixme() in ATDD test files
- REJECT verdict → [AI-Review] follow-up task created

---

## Epic Setup Scope

### tea_framework
**来源**: workflows/testarch-framework/checklist.md

- All preflight checks passed
- Framework scaffold created
- Sample tests run successfully
- Directory structure correct
- No placeholders, no hardcoded credentials
- Code quality checks passed
- Best practices compliance (Fixture pure functions/Data Factories auto-cleanup/Network-first/data-testid selectors/Given-When-Then/no hardcoded waits)
- User can run test:e2e without errors

### tea_ci
**来源**: workflows/testarch-ci/checklist.md

- All preflight checks passed
- CI pipeline configured
- First CI run successful
- Performance targets met (lint <2min, tests <10min/shard, burn-in <30min, total <45min)
- No credentials in CI config

### tea_test_design
**来源**: workflows/testarch-test-design/checklist.md

- Risk assessment matrix validated (all risks have ID/category/probability/impact/score/mitigation)
- Coverage matrix: all requirements mapped to test levels with priorities
- Quality gates defined (P0 100%, P1 ≥95%)
- Resource estimates use ranges (not exact numbers)

### tea_automate
**来源**: workflows/testarch-automate/checklist.md

- Test files generated at appropriate levels
- Priority markers added (P0/P1/P2/P3)
- Quality standards enforced (no hard waits/no flaky patterns/self-cleaning/deterministic)
- Test suite runs locally
- Automation summary saved

---

## Epic Teardown Scope

### trace
**来源**: workflows/testarch-trace/checklist.md

- All AC mapped or gaps documented
- P0 coverage 100% or documented as BLOCKER
- Gap analysis complete and prioritized
- Quality gate decision: PASS/CONCERNS/FAIL/WAIVED

### tea_nfr_assess
**来源**: workflows/testarch-nfr-assess/checklist.md

- All NFR categories assessed (Performance/Security/Reliability/Maintainability)
- No threshold guessing (UNKNOWN if undefined)
- Status per NFR: PASS/CONCERNS/FAIL (deterministic with justification)
- Quick wins identified for CONCERNS/FAIL
- NFR Assessment Report generated

### retrospective
**来源**: workflows/retrospective/instructions.md (上游无 checklist)

- All stories reviewed and analyzed
- Epic Review: went well / didn't go well / improvements / team dynamics
- Next Epic Prep: action items + context transfer + open issues
- Action items created (specific, actionable, with owner)
- Knowledge transfer documented

### qa_plan_generate
**来源**: workflows/qa-plan-generate/instructions.md (bmad-assist 新增)

- ≥20 Category A tests for non-trivial epic
- ≥5 tests per story
- Each AC has at least one test
- Each test has complete executable code (not summary/outline)
- Test ID format consistent: E{epic_num}-A##/B##/C##
- Traceability matrix included
- No placeholders, no token-saving shortcuts

### qa_plan_execute
**来源**: workflows/qa-plan-execute/instructions.md (bmad-assist 新增)

- All test cases executed
- Each test status: PASS/PASS*/FAIL/SKIP/ERROR
- Bug reports generated for failures
- Result YAML generated
- Summary report generated

### qa_remediate
**来源**: qa/prompts/remediate.xml (bmad-assist 新增)

- Each issue: FIXED/SKIPPED/ESCALATED with specific reason
- Escalation only justified: architecture redesign / product decision / external dependency / 2+ failed fix attempts
- Fix verified by running relevant tests
- Regression check: fix didn't make things worse
- Safety cap respected (max auto-fix percentage)
- Status: clean/fixed/partial/escalated/unresolved
