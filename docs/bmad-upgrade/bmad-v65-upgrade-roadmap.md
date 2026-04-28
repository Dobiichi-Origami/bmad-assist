# BMAD v6.5 Upgrade Roadmap

> Branch: `feat/bmad-v65-upgrade` (based on `feat/digital-twin`)
> Created: 2026-04-28
> Upstream: BMAD-METHOD v6.5.0 + TEA v1.15.1
> Current baseline: BMAD ~v6.0.x + TEA v4.0~v5.0

## 1. Version Baseline

| Component | bmad-assist (current) | Upstream (latest) |
|-----------|----------------------|-------------------|
| Core BMAD | ~v6.0.x (workflow.yaml + instructions.xml) | **v6.5.0** (SKILL.md) |
| TEA Module | v4.0~v5.0 (workflow.yaml + instructions.md) | **v1.15.1** (SKILL.md + tri-modal) |
| bmad-assist | 0.4.34 | - |

### Upstream Repos

- Core: `bmad-code-org/BMAD-METHOD` (npm: `bmad-method`)
- TEA: `bmad-code-org/bmad-method-test-architecture-enterprise` (npm: `bmad-method-test-architecture-enterprise`)
- Other modules: bmad-builder, bmad-creative-intelligence-suite, bmad-game-dev-studio (out of scope)

---

## 2. Architecture-Level Diffs (Breaking Changes)

### 2.1 Workflow Format Revolution

| Dimension | bmad-assist (current) | Upstream v6.5.0 |
|-----------|----------------------|-----------------|
| Workflow definition | `workflow.yaml` + `instructions.{xml,md}` + `checklist.md` | **SKILL.md** (YAML frontmatter + Markdown body, single entry) |
| Customization | YAML patch (`*.patch.yaml`) | **TOML** four-file architecture |
| Activation protocol | None | **6-step unified activation** (resolve workflow block -> prepend -> persistent facts -> config -> greet -> append) |
| Step architecture | Embedded in instructions or partial steps-c/e/v | **Step-file micro-files** (just-in-time loading) + **tri-modal** (Create/Resume/Validate/Edit) |
| on_complete hook | None | All 23 workflow terminal steps |
| Release channels | None | **stable/next** dual channels, version pinning |
| Agent platforms | N/A | **42** supported platforms |

### 2.2 Agent Consolidation (v6.3.0 Breaking)

| bmad-assist (current) | Upstream v6.5.0 |
|----------------------|-----------------|
| References Barry (quick-flow), Quinn (QA), Bob (Scrum Master) | **Removed** — all merged into Amelia (Senior Software Engineer) |
| 6+ agent personas | 6 agents: Mary (Analyst), Paige (Tech Writer), John (PM), Sally (UX), Winston (Architect), Amelia (Dev) + Murat (TEA) |

### 2.3 Removed Features (v6.3.0 Breaking)

- `bmad-init` skill removed — agents load config directly from `_bmad/bmm/config.yaml`
- `spec-wip.md` singleton removed — quick-dev writes to `spec-{slug}.md` with status field
- Custom content installation removed — replaced by marketplace-based plugin installation

### 2.4 Customization System Replacement (v6.4.0 Breaking)

YAML patch system -> **TOML four-file architecture**:

```
_bmad/config.toml              # Defaults (installed)
_bmad/config.user.toml         # Personal overrides
_bmad/custom/{skill}.toml      # Team overrides per skill
_bmad/custom/{skill}.user.toml # Personal overrides per skill
```

Merge rules: scalars replace, tables deep-merge, code-keyed arrays replace by key, append arrays concatenate.

---

## 3. Workflow-Level Diffs

### 3.1 Shared Workflows (Content Version Gap)

| Workflow | bmad-assist Version | Upstream v6.5.0 Version | Gap |
|----------|--------------------|-----------------------|-----|
| **create-story** | workflow.yaml + instructions.xml | SKILL.md (6 steps: UPDATE file reading, git intelligence, web research) | **Large** |
| **dev-story** | workflow.yaml + instructions.xml | SKILL.md (10 steps: review continuation, red-green-refactor) | **Large** |
| **code-review** | workflow.yaml + instructions.xml (single adversarial layer) | SKILL.md + step-file (3 parallel layers: Blind Hunter + Edge Case Hunter + Acceptance Auditor) | **Extreme** |
| **retrospective** | workflow.yaml + instructions.xml | SKILL.md + step-file (dual-part: Epic Review + Next Epic Prep, Party Mode) | **Large** |
| **testarch-atdd** | v4.0, workflow.yaml + instructions.md | SKILL.md + tri-modal step-file + customize.toml | **Large** |
| **testarch-automate** | v5.0, workflow.yaml + steps-c/e/v | SKILL.md + tri-modal step-file + customize.toml | **Medium** |
| **testarch-ci** | v5.0, workflow.yaml + steps-c/e/v | SKILL.md + tri-modal step-file + customize.toml | **Medium** |
| **testarch-framework** | v5.0, workflow.yaml + steps-c/e/v | SKILL.md + tri-modal step-file + customize.toml | **Medium** |
| **testarch-nfr-assess** | v5.0, workflow.yaml + steps-c/e/v | SKILL.md + tri-modal step-file + customize.toml | **Medium** |
| **testarch-test-design** | v5.0, workflow.yaml + steps-c/e/v | SKILL.md + tri-modal step-file + customize.toml | **Medium** |
| **testarch-test-review** | v4.0, workflow.yaml + instructions.md | SKILL.md + tri-modal step-file + customize.toml | **Large** |
| **testarch-trace** | v4.0, workflow.yaml + instructions.md | SKILL.md + tri-modal step-file + customize.toml | **Large** |

### 3.2 Upstream-Only Workflows (bmad-assist Missing)

| Workflow | Module | Description |
|----------|--------|-------------|
| **bmad-quick-dev** | Core bmm | Intent-driven dev, most popular workflow |
| **bmad-sprint-planning** | Core bmm | Auto-generate sprint-status.yaml from epics |
| **bmad-correct-course** | Core bmm | Sprint change management with change proposals |
| **bmad-qa-generate-e2e-tests** | Core bmm | E2E test generation |
| **bmad-checkpoint-preview** | Core bmm (v6.3+) | Human-in-the-loop review, LLM-assisted focus |
| **bmad-sprint-status** | Core bmm | Sprint status viewer |
| **bmad-teach-me-testing** | TEA | Interactive testing education |

### 3.3 bmad-assist-Only Workflows (Upstream Missing)

These 6 workflows are bmad-assist originals with no upstream equivalent:

| Workflow | Description |
|----------|-------------|
| **validate-story** | Story validation |
| **validate-story-synthesis** | Multi-LLM validation consolidation |
| **code-review-synthesis** | Multi-LLM review consolidation |
| **qa-plan-generate** | QA plan generation |
| **qa-plan-execute** | QA plan execution |
| **security-review** | Security review (CWE-based analysis) |

### 3.4 TEA Module Diffs

#### Knowledge Base Gap

bmad-assist has 35 knowledge fragments; upstream TEA has 50. Missing 15:

```
pact-broker-webhooks.md          playwright-cli.md
pact-consumer-di.md              webhook-module-setup.md
pact-consumer-framework-setup.md webhook-providers.md
pact-mcp.md                      webhook-risk-guidance.md
pactjs-utils-consumer-helpers.md webhook-template-matchers.md
pactjs-utils-overview.md         webhook-testing-fundamentals.md
pactjs-utils-provider-verifier.md webhook-timeout-error.md
pactjs-utils-request-filter.md   webhook-waiting-querying.md
pactjs-utils-zod-to-pact.md
```

#### TEA Config Variables Gap

Upstream TEA module.yaml exposes these config variables that bmad-assist doesn't support:

| Variable | Description |
|----------|-------------|
| `tea_use_playwright_utils` | Playwright Utils integration |
| `tea_use_pactjs_utils` | Pact.js contract testing |
| `tea_pact_mcp` | SmartBear MCP for PactFlow |
| `tea_browser_automation` | Browser interaction strategy (auto/cli/mcp/none) |
| `tea_execution_mode` | Orchestration mode (auto/subagent/agent-team/sequential) |
| `tea_capability_probe` | Probe runtime capabilities |
| `test_stack_type` | Project type (auto/frontend/backend/fullstack) |
| `test_framework` | Test framework (auto/playwright/cypress/jest/vitest/pytest/junit/go-test/dotnet-test/rspec/other) |

---

## 4. Impact on bmad-assist Internals

| Module | Needs Change | Impact | Notes |
|--------|-------------|--------|-------|
| `compiler/` (compile pipeline) | **Yes** | **Critical** | Currently consumes workflow.yaml -> instructions.xml -> patch -> template cache. Need SKILL.md parsing path |
| `compiler/workflow_discovery.py` | **Yes** | **Medium** | Search paths need adapting for `bmm-skills/4-implementation/` + SKILL.md discovery |
| `compiler/patching/` | **Yes** | **Critical** | Patch system based on XML instructions. Upstream moved to TOML. Decision needed: keep patch or migrate to TOML |
| `bmad/parser.py` | No | None | Parses epic/story markdown, independent of BMAD workflow format |
| `bmad/state_reader.py` | **Yes** | **Low** | Reads sprint-status.yaml; upstream format mostly compatible |
| `workflows/` bundled resources | **Yes** | **Critical** | 12 shared workflows need content sync |
| `default_patches/` | **Yes** | **Critical** | If patch system retained, all patches need rewriting for new instructions |
| `digital_twin/` | Maybe | **Low** | Twin depends on workflow IR compilation output. If IR format stable, no impact |
| `runner.py` | **Yes** | **Medium** | Phase execution logic needs adapting for new workflow steps |
| `testarch/` Python module | **Yes** | **Medium** | engagement.py, eligibility.py, handlers/ need config variable additions |
| `testarch/knowledge_base/` | **Yes** | **Low** | +15 knowledge fragments to add |

---

## 5. Upgrade Strategy: Dual-Track (Recommended)

### Rationale

- **Option A (Minimal)**: Manually translate upstream SKILL.md back to instructions.xml — unsustainable, repeated work on every upstream release
- **Option B (Dual-Track)**: Add SKILL.md parsing to compiler while retaining workflow.yaml path — incremental migration, lowest risk
- **Option C (Full Alignment)**: Complete migration to SKILL.md + TOML — highest upfront cost, lowest long-term maintenance

**Recommendation: Option B (Dual-Track)** — allows incremental migration while keeping bmad-assist's 6 custom workflows stable.

### Phase Breakdown

#### Phase 1: Compiler SKILL.md Support (Foundation)

**Goal**: Compiler can consume both workflow.yaml and SKILL.md as input, producing the same internal IR.

Tasks:
1. Design SKILL.md parser (YAML frontmatter + Markdown body -> WorkflowIR)
2. Add step-file loader (just-in-time step loading from `steps-c/`, `steps-r/`, `steps-v/`, `steps-e/`)
3. Add tri-modal routing (Create/Resume/Validate/Edit -> appropriate step chain)
4. Extend workflow_discovery.py for SKILL.md paths
5. Ensure template cache works for both formats
6. Update `_is_valid_workflow_dir()` to detect SKILL.md

#### Phase 2: Standard Workflows Migration

**Goal**: 4 core + 8 TEA workflows use upstream SKILL.md directly.

Tasks:
1. Replace bundled create-story with upstream SKILL.md version
2. Replace bundled dev-story with upstream SKILL.md version
3. Replace bundled code-review with upstream SKILL.md version
4. Replace bundled retrospective with upstream SKILL.md version
5. Replace 8 bundled TEA workflows with upstream SKILL.md versions
6. Adapt patches for SKILL.md-based workflows (or migrate to TOML for these)
7. Add 15 missing TEA knowledge fragments
8. Add TEA config variables to bmad-assist.yaml.example
9. Update testarch/ Python module for new config variables

#### Phase 3: New Upstream Workflows Integration

**Goal**: Add the 7 upstream-only workflows to bmad-assist.

Tasks:
1. Add bmad-quick-dev (highest priority — most popular upstream workflow)
2. Add bmad-sprint-planning
3. Add bmad-correct-course
4. Add bmad-qa-generate-e2e-tests
5. Add bmad-checkpoint-preview
6. Add bmad-sprint-status
7. Add bmad-teach-me-testing (TEA)

#### Phase 4: bmad-assist Custom Workflow Modernization

**Goal**: Migrate 6 bmad-assist-only workflows to SKILL.md format for consistency.

Tasks:
1. Convert validate-story to SKILL.md
2. Convert validate-story-synthesis to SKILL.md
3. Convert code-review-synthesis to SKILL.md
4. Convert qa-plan-generate to SKILL.md
5. Convert qa-plan-execute to SKILL.md
6. Convert security-review to SKILL.md

#### Phase 5: TOML Customization Migration (Future)

**Goal**: Replace YAML patch system with TOML customization, fully aligning with upstream.

Tasks:
1. Design TOML customization layer for bmad-assist
2. Implement four-file merge logic (config.toml -> config.user.toml -> custom/{skill}.toml -> custom/{skill}.user.toml)
3. Migrate all *.patch.yaml to TOML overrides
4. Add `bmad-customize` skill support
5. Add stable/next channel support
6. Deprecate and remove patch system

---

## 6. Effort Estimates

| Phase | Estimate | Risk | Dependency |
|-------|----------|------|------------|
| Phase 1: Compiler SKILL.md Support | 2-3 weeks | Medium | None (foundation) |
| Phase 2: Standard Workflows Migration | 2-3 weeks | Medium | Phase 1 |
| Phase 3: New Upstream Workflows | 1-2 weeks | Low | Phase 1 |
| Phase 4: Custom Workflow Modernization | 1-2 weeks | Low | Phase 1 |
| Phase 5: TOML Customization | 2-3 weeks | High | Phase 2+4 |
| **Total** | **8-13 weeks** | | |

Phases 1-2 are sequential (compiler must support SKILL.md before workflows can migrate). Phases 3 and 4 can proceed in parallel after Phase 1. Phase 5 is optional and can be deferred.

---

## 7. Compatibility Notes

### Digital Twin Coexistence

- Digital Twin operates on the compiled IR output, not raw workflow files
- As long as the compiler produces compatible IR from SKILL.md, Twin continues to work unchanged
- The `runner.py` phase execution may need minor adaptations for new step routing

### User Migration Path

- Existing `_bmad/bmm/` installations continue to work (workflow_discovery.py fallback)
- Users can opt-in to SKILL.md workflows by updating their `_bmad/` directory
- TOML customization is additive — doesn't break existing YAML patch users until Phase 5

### Backward Compatibility

- All 6 bmad-assist-only workflows remain on workflow.yaml format until Phase 4
- The patch system remains functional throughout Phases 1-4
- Phase 5 (TOML migration) is the only breaking change for existing bmad-assist users
