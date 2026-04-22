## ADDED Requirements

### Requirement: Self-audit section injection in output templates
Each workflow's `<output-template>` SHALL include an "Execution Self-Audit" section that forces the LLM to explicitly declare completion status at the end of its output. The section SHALL contain a "Completion Status" block with primary objective and status (COMPLETE/PARTIAL/DEFERRED), and an "If PARTIAL or DEFERRED" block with what remains, justification, and what was attempted.

#### Scenario: Phase completes successfully with self-audit
- **WHEN** a phase executes and its output-template includes the self-audit section
- **THEN** the LLM output SHALL include an "Execution Self-Audit" section with a "Completion Status" declaring the objective and status as COMPLETE

#### Scenario: Phase partially completes with self-audit
- **WHEN** a phase executes and only partially completes its objectives
- **THEN** the LLM output SHALL declare status as PARTIAL and list what remains and justification in the self-audit section

#### Scenario: Phase defers work with self-audit
- **WHEN** a phase defers some work items
- **THEN** the LLM output SHALL declare status as DEFERRED with specific items, justification, and what was attempted

### Requirement: Phase-specific audit items derived from upstream acceptances
The "Phase-Specific Audit" subsection within the self-audit template SHALL contain checklist items derived directly from each phase's upstream acceptance criteria (checklist.md / instructions.xml). These items SHALL be specific to each phase type and not generic.

#### Scenario: dev_story phase-specific audit
- **WHEN** the dev_story workflow executes
- **THEN** its self-audit section SHALL include audit items derived from the dev_story checklist: all AC satisfied, no test.fixme() remaining, tests pass, file list complete, story status set to "review"

#### Scenario: qa_remediate phase-specific audit
- **WHEN** the qa_remediate workflow executes
- **THEN** its self-audit section SHALL include audit items derived from the remediate checklist: each issue FIXED/SKIPPED/ESCALATED with reason, escalation justified, fix verified by tests, regression check done, safety cap respected

#### Scenario: create_story phase-specific audit
- **WHEN** the create_story workflow executes
- **THEN** its self-audit section SHALL include audit items derived from the create_story checklist: AC in BDD format, architecture analysis complete, 5 disaster categories checked, status set to "ready-for-dev"

#### Scenario: validate_story phase-specific audit
- **WHEN** the validate_story workflow executes
- **THEN** its self-audit section SHALL include audit items derived from the validate_story instructions: INVEST criteria scored, AC deep analysis done, evidence score calculated, verdict issued

### Requirement: Workflow XML modifications for self-audit injection
The following workflow instruction files SHALL be modified to include the self-audit section in their `<output-template>`: dev-story, create-story, code-review, validate-story, validate-story-synthesis, code-review-synthesis, retrospective, qa/prompts/remediate.xml, and TEA workflow instructions (tea_framework, tea_ci, tea_test_design, tea_automate via atdd/test_review/nfr_assess).

#### Scenario: All 12 workflows have self-audit section
- **WHEN** any of the 12 workflow instruction files is compiled
- **THEN** the compiled prompt SHALL include the "Execution Self-Audit" section in the output template

#### Scenario: Self-audit placement at end of output
- **WHEN** a workflow's compiled prompt is generated
- **THEN** the self-audit section SHALL be the last section in the output-template, leveraging recency bias for the LLM

### Requirement: Common self-audit template structure
All phases SHALL share a common template structure for the "Completion Status" block. The template SHALL be:
```
## Execution Self-Audit
### Completion Status
- Primary objective: [one sentence stating what was accomplished]
- Status: [COMPLETE / PARTIAL / DEFERRED]
### If PARTIAL or DEFERRED:
- What remains: [specific list]
- Justification: [specific reason for each item]
- What was attempted: [what you tried before deferring]
```

#### Scenario: Template enforces explicit status declaration
- **WHEN** the LLM produces output using a workflow with self-audit
- **THEN** it SHALL explicitly choose one of COMPLETE, PARTIAL, or DEFERRED as the status

#### Scenario: PARTIAL or DEFERRED requires justification
- **WHEN** the LLM declares status as PARTIAL or DEFERRED
- **THEN** the output SHALL include specific items that remain, justification for each, and what was attempted
