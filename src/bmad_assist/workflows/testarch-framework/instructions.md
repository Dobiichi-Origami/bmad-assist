<!-- Powered by BMAD-CORE™ -->

# Test Framework Setup

**Workflow ID**: `_bmad/tea/testarch/framework`
**Version**: 5.0 (Step-File Architecture)

---

## Overview

Initialize a production-ready test framework (Playwright or Cypress) with fixtures, helpers, configuration, and best practices.

---

## WORKFLOW ARCHITECTURE

This workflow uses **step-file architecture**:

- **Micro-file Design**: Each step is self-contained
- **JIT Loading**: Only the current step file is in memory
- **Sequential Enforcement**: Execute steps in order without skipping

---

## INITIALIZATION SEQUENCE

### 1. Configuration Loading

From `workflow.yaml`, resolve:

- `config_source`, `output_folder`, `user_name`, `communication_language`, `document_output_language`, `date`
- `test_dir`, `use_typescript`, `framework_preference`, `project_size`

### 2. First Step

Load, read completely, and execute:
`{project-root}/_bmad/tea/workflows/testarch/framework/steps-c/step-01-preflight.md`

## Execution Self-Audit
### Completion Status
- Primary objective: [one sentence stating what was accomplished]
- Status: [COMPLETE / PARTIAL / DEFERRED]
### If PARTIAL or DEFERRED:
- What remains: [specific list]
- Justification: [specific reason for each item]
- What was attempted: [what you tried before deferring]

### Phase-Specific Audit
- [ ] Test architecture deliverables match framework requirements
- [ ] All acceptance criteria covered by test cases
- [ ] Integration points identified and tested
- [ ] Test infrastructure follows project conventions
