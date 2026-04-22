## ADDED Requirements

### Requirement: TwinResult Pydantic model
The system SHALL define a `TwinResult` Pydantic model with fields `decision: Literal["continue", "retry", "halt"]`, `rationale: str`, `drift_assessment: DriftAssessment | None = None`, and `page_updates: list[PageUpdate] | None = None`. The `decision` field MUST be lowercase and one of the three allowed values.

#### Scenario: Valid TwinResult with drift and page updates
- **WHEN** a TwinResult is constructed with `decision="retry"`, `rationale="AC skipped without justification"`, a `DriftAssessment`, and a list of `PageUpdate` objects
- **THEN** the model SHALL validate and store all fields without error

#### Scenario: TwinResult with minimal fields
- **WHEN** a TwinResult is constructed with only `decision="continue"` and `rationale="Execution satisfactory"`
- **THEN** `drift_assessment` SHALL default to `None` and `page_updates` SHALL default to `None`

#### Scenario: Invalid decision value rejected
- **WHEN** a TwinResult is constructed with `decision="skip"`
- **THEN** Pydantic validation SHALL reject the value with a validation error

### Requirement: DriftAssessment Pydantic model
The system SHALL define a `DriftAssessment` Pydantic model with fields `drifted: bool`, `evidence: str`, and `correction: str | None = None`. The `correction` field MUST be present when `drifted` is `True`.

#### Scenario: Drift detected with correction
- **WHEN** a DriftAssessment is constructed with `drifted=True`, `evidence="Self-audit says COMPLETE but git diff shows no changes"`, and `correction="Implement all acceptance criteria before declaring complete"`
- **THEN** the model SHALL store all fields

#### Scenario: No drift without correction
- **WHEN** a DriftAssessment is constructed with `drifted=False` and `evidence="Output matches mission requirements"`
- **THEN** `correction` SHALL default to `None`

### Requirement: PageUpdate Pydantic model
The system SHALL define a `PageUpdate` Pydantic model with fields `page_name: str`, `action: Literal["create", "update", "evolve"]`, `content: str`, `append_evidence: dict | None = None`, `section_patches: dict[str, str] | None = None`, and `reason: str`. The `action` field MUST NOT include "archive" -- only create, update, and evolve are valid actions.

#### Scenario: CREATE page update
- **WHEN** a PageUpdate is constructed with `action="create"`, `page_name="pattern-test-first"`, and `content` containing a full wiki page
- **THEN** the model SHALL store the update with `append_evidence=None` and `section_patches=None` by default

#### Scenario: UPDATE page update with evidence and patches
- **WHEN** a PageUpdate is constructed with `action="update"`, `page_name="pattern-test-first"`, `append_evidence={"context": "Rate limiter", "result": "Edge case found", "epic": "epic-22"}`, and `section_patches={"When This Applies": "All state mutations"}`
- **THEN** the model SHALL store both `append_evidence` and `section_patches`

#### Scenario: EVOLVE page update with evidence table placeholder
- **WHEN** a PageUpdate is constructed with `action="evolve"`, `page_name="pattern-test-first"`, and `content` containing the string `{{EVIDENCE_TABLE}}`
- **THEN** the model SHALL store the update without error

#### Scenario: Archive action rejected
- **WHEN** a PageUpdate is constructed with `action="archive"`
- **THEN** Pydantic validation SHALL reject the value with a validation error

### Requirement: Twin.reflect() single LLM call architecture
The `Twin.reflect(record, is_retry)` method SHALL operate as a single LLM call that produces structured YAML output. Twin is NOT an agent with tools -- the method MUST follow the pattern: assemble prompt from INDEX + guide page + execution record, call the LLM provider once, extract and parse the YAML block from the response, and return a `TwinResult`. No iterative tool calling or multi-turn conversation SHALL occur within a single reflect invocation.

#### Scenario: Successful reflect call
- **WHEN** `Twin.reflect(record, is_retry=False)` is called with a valid ExecutionRecord
- **THEN** the method SHALL (1) load INDEX.md and the guide page for the current phase type, (2) assemble the reflect prompt with these plus the execution record, (3) make exactly one `provider.invoke(prompt)` call, (4) extract the YAML block from the raw output, (5) parse it into a TwinResult, and (6) return the TwinResult

#### Scenario: Twin does not call tools
- **WHEN** the LLM provider returns output that contains tool-call-like instructions within the YAML
- **THEN** the reflect method SHALL treat the entire output as static text and parse only the YAML structure -- no tool execution SHALL occur

### Requirement: Reflect prompt assembly with Strategy D loading
The `build_reflect_prompt()` function SHALL load only the INDEX.md and the guide page for the current phase type (Strategy D: INDEX-driven minimal loading). It MUST NOT load linked pages or any pages beyond INDEX + guide page. The total wiki content loaded for a reflect call SHALL be approximately 800-1800 tokens.

#### Scenario: Loading INDEX and guide page for dev_story
- **WHEN** `build_reflect_prompt()` is called for a `dev_story` phase
- **THEN** it SHALL load INDEX.md and `guide-dev-story.md`, and no other wiki pages

#### Scenario: Guide page does not exist
- **WHEN** `build_reflect_prompt()` is called for a phase type that has no guide page (e.g., `validate_story`)
- **THEN** the guide section SHALL be empty or indicate no guide page exists, but the prompt SHALL still be assembled and the LLM call SHALL proceed

#### Scenario: INDEX is empty
- **WHEN** `build_reflect_prompt()` is called and the INDEX.md contains no pages
- **THEN** the prompt SHALL include the initialization guidance section and the empty INDEX, and the LLM call SHALL proceed

### Requirement: EVOLVE uses EVIDENCE_TABLE placeholder
When a PageUpdate has `action="evolve"`, the `content` field SHALL contain the literal string `{{EVIDENCE_TABLE}}` wherever the evidence table should appear. The `apply_page_updates()` function MUST extract the original evidence table from the existing page and replace `{{EVIDENCE_TABLE}}` with it, preserving all historical evidence rows exactly as they were.

#### Scenario: EVOLVE preserves evidence table
- **WHEN** `apply_page_updates()` processes an EVOLVE update for page "pattern-test-first" whose existing content contains an evidence table with 3 rows, and the update's `content` contains `{{EVIDENCE_TABLE}}` in the Evidence section
- **THEN** the code SHALL extract the original evidence table from the existing page, replace the `{{EVIDENCE_TABLE}}` placeholder with the original table, and write the resulting content

#### Scenario: EVOLVE without placeholder writes content as-is
- **WHEN** `apply_page_updates()` processes an EVOLVE update whose `content` does NOT contain `{{EVIDENCE_TABLE}}`
- **THEN** the code SHALL write the content as-is without evidence table substitution (the Twin chose to rewrite the evidence)

### Requirement: apply_page_updates() executes Twin output as file I/O
The `apply_page_updates()` function SHALL be called by runner.py after `twin.reflect()` returns, taking `twin_result.page_updates` as input. It SHALL execute each PageUpdate as file I/O against the wiki directory. For CREATE: write a new file if it does not exist. For UPDATE: append evidence rows and/or apply section patches to the existing file, then update frontmatter. For EVOLVE: replace the page content (with evidence table substitution). After all updates, it SHALL call `rebuild_index()`.

#### Scenario: CREATE writes new page
- **WHEN** `apply_page_updates()` processes a CREATE update with `page_name="env-async-session"`
- **THEN** it SHALL write the content to `env-async-session.md` in the wiki directory and call `rebuild_index()` after all updates

#### Scenario: CREATE rejected when page already exists
- **WHEN** `apply_page_updates()` processes a CREATE update for `page_name="pattern-test-first"` but `pattern-test-first.md` already exists
- **THEN** it SHALL skip the update, log a warning that Twin should have used UPDATE/EVOLVE, and continue processing other updates

#### Scenario: UPDATE with append_evidence on existing page
- **WHEN** `apply_page_updates()` processes an UPDATE with `append_evidence={"context": "...", "result": "...", "epic": "epic-22"}` for a page that exists
- **THEN** it SHALL append a new row to the Evidence table in the page, apply any section_patches, increment `occurrences` in frontmatter, re-derive `confidence` from occurrences and sentiment, and write the updated page

#### Scenario: UPDATE treated as CREATE when page does not exist
- **WHEN** `apply_page_updates()` processes an UPDATE for a page that does not exist and the update has non-empty `content`
- **THEN** it SHALL log a warning and treat the update as a CREATE, writing the content as a new page

#### Scenario: UPDATE append_evidence does not require reading page content beforehand
- **WHEN** a PageUpdate has `action="update"` with `append_evidence` set but no `section_patches`
- **THEN** the code SHALL append the evidence row to the page without requiring the Twin to have read the page content -- the code handles the append operation mechanically

#### Scenario: EVOLVE rejected when page modified outside Twin
- **WHEN** `apply_page_updates()` processes an EVOLVE update and the existing page's `last_updated` frontmatter value does not match the current epic ID
- **THEN** it SHALL skip the EVOLVE, log a warning that manual edits take priority, and continue processing other updates

#### Scenario: Invalid page name rejected
- **WHEN** `apply_page_updates()` processes an update with `page_name="My Cool Page"` that does not match the required pattern `(env|pattern|design|guide)-[a-z0-9-]+`
- **THEN** it SHALL skip the update and log a warning

### Requirement: Phase-specific review guidance in prompts
The reflect prompt SHALL include phase-specific review guidance that is hardcoded in `prompts.py`. The phases `dev_story`, `qa_remediate`, `atdd`, `create_story`, `code_review_synthesis`, and `retrospective` SHALL have specific review guidance injected into the prompt. All other phases SHALL use the generic review guidance (three-layer cross-validation + decision).

#### Scenario: dev_story phase gets specific guidance
- **WHEN** `build_reflect_prompt()` is called for a `dev_story` phase
- **THEN** the prompt SHALL include dev_story-specific guidance covering AC completion checks, test pass rates, "not essential" skip detection, file list completeness, and regression test status

#### Scenario: qa_remediate phase gets specific guidance
- **WHEN** `build_reflect_prompt()` is called for a `qa_remediate` phase
- **THEN** the prompt SHALL include qa_remediate-specific guidance covering fix rates, SKIPPED issue justification, new issue introduction, and escalation reasonableness

#### Scenario: Generic phase gets generic guidance
- **WHEN** `build_reflect_prompt()` is called for a phase like `tea_framework` or `trace` that has no specific guidance
- **THEN** the prompt SHALL include the generic review guidance based on three-layer cross-validation and decision

### Requirement: Initialization guidance for empty wiki
When the INDEX.md is empty or contains fewer than 3 pages, `build_reflect_prompt()` SHALL inject initialization guidance into the reflect prompt. This guidance SHALL instruct the Twin to establish the initial knowledge base by creating pages that capture environment knowledge (env-*), observed patterns (pattern-*), design preferences (design-*), and phase guidance (guide-*). The initialization guidance SHALL ONLY be injected when the wiki is sparse; it SHALL NOT be injected on subsequent reflect calls once the wiki has grown.

#### Scenario: First reflect call with empty wiki
- **WHEN** `build_reflect_prompt()` is called and INDEX.md contains no pages (or only seed guide pages)
- **THEN** the prompt SHALL include a "Wiki Initialization" section instructing the Twin to create initial knowledge base pages with evidence from the current execution, emphasizing project-SPECIFIC knowledge over generic platitudes

#### Scenario: Subsequent reflect call with populated wiki
- **WHEN** `build_reflect_prompt()` is called and INDEX.md lists 5 or more pages
- **THEN** the prompt SHALL NOT include the initialization guidance section

### Requirement: Twin failure degradation on YAML parse failure
When `Twin.reflect()` fails to parse the LLM's YAML output (even after one automatic retry), the degradation behavior SHALL depend on the `is_retry` parameter. If `is_retry=False` (this is a first-run reflect, not after a RETRY), the system SHALL default to `decision="continue"` and log the parse failure. If `is_retry=True` (this reflect is evaluating a RETRY attempt) and `retry_exhausted_action="halt"`, the system SHALL default to `decision="halt"` to prevent uncontrolled execution. If `is_retry=True` and `retry_exhausted_action="continue"`, the system SHALL default to `decision="continue"`.

#### Scenario: Parse failure on first-run reflect
- **WHEN** the LLM returns malformed YAML on a reflect call where `is_retry=False` and the automatic retry also fails
- **THEN** the method SHALL return a TwinResult with `decision="continue"` and `rationale="Twin parse error, defaulting to continue"`

#### Scenario: Parse failure on retry reflect with halt action
- **WHEN** the LLM returns malformed YAML on a reflect call where `is_retry=True` and `retry_exhausted_action="halt"`
- **THEN** the method SHALL return a TwinResult with `decision="halt"` and `rationale="Twin parse error during RETRY, halting to prevent uncontrolled execution"`

#### Scenario: Parse failure on retry reflect with continue action
- **WHEN** the LLM returns malformed YAML on a reflect call where `is_retry=True` and `retry_exhausted_action="continue"`
- **THEN** the method SHALL return a TwinResult with `decision="continue"` and a rationale indicating the parse error

#### Scenario: Automatic retry on first parse failure
- **WHEN** the LLM returns malformed YAML on the first attempt of a reflect call
- **THEN** the method SHALL retry the LLM call exactly once before applying degradation logic

### Requirement: Challenge mode for negative patterns
Every 5 epics, the reflect prompt SHALL inject challenge mode instructions that require the Twin to critically evaluate each negative pattern page in the wiki. Challenge mode asks: (1) Is this a real project issue or an execution model limitation? (2) Would a different approach avoid this pattern? (3) Has any positive evidence contradicted this pattern? Only after the Twin defends the pattern with evidence from genuinely independent contexts may it promote a negative pattern from `established` to `definitive`. Negative patterns SHALL be capped at `established` confidence by default -- challenge mode is the ONLY mechanism to promote them to `definitive`.

#### Scenario: Challenge mode triggered at 5-epic boundary
- **WHEN** a negative pattern page has `source_epics` of length 5 (i.e., `len(source_epics) % 5 == 0`) and `sentiment="negative"`
- **THEN** the reflect prompt SHALL include challenge mode instructions for that page

#### Scenario: Challenge mode not triggered before 5-epic boundary
- **WHEN** a negative pattern page has `source_epics` of length 3 and `sentiment="negative"`
- **THEN** the reflect prompt SHALL NOT include challenge mode instructions for that page

#### Scenario: Negative pattern confidence cap
- **WHEN** `derive_confidence()` is called with `occurrences=3` and `sentiment="negative"`
- **THEN** it SHALL return `"established"`, NOT `"definitive"`

#### Scenario: Positive pattern reaches definitive normally
- **WHEN** `derive_confidence()` is called with `occurrences=3` and `sentiment="positive"`
- **THEN** it SHALL return `"definitive"`

### Requirement: Substring dedup warning without auto-convert
When `apply_page_updates()` processes a CREATE update and the new page name is a substring or superstring of an existing page name within the same category, the system SHALL log a warning but MUST NOT automatically convert the CREATE to an UPDATE. Auto-conversion is prohibited because it may lose the Twin's creation intent -- if the Twin determines that a new concept genuinely needs an independent page, converting it to an UPDATE would append irrelevant evidence to the wrong page.

#### Scenario: Substring match triggers warning only
- **WHEN** `apply_page_updates()` processes a CREATE for `page_name="pattern-test-first-auth"` and an existing page `"pattern-test-first"` exists in the same category
- **THEN** the system SHALL log a warning about potential duplication but SHALL proceed with creating the new page

#### Scenario: No auto-convert to UPDATE
- **WHEN** `apply_page_updates()` detects a substring relationship between a CREATE page name and an existing page name
- **THEN** it SHALL NOT change the action from CREATE to UPDATE

### Requirement: Forced checklist before decision in reflect prompt
The reflect prompt SHALL require the Twin to complete a five-item checklist before making its decision. The checklist items are: (1) Did the execution address all items in the mission? (2) Does the self-audit match the objective facts (git diff, phase_outputs)? (3) Are there any contradictions between claimed completion and actual file changes? (4) Does this execution repeat any known failure patterns from the wiki? (5) Is the self-audit status justified by the evidence? The prompt SHALL instruct the Twin that only after answering all five items should it set its decision.

#### Scenario: Reflect prompt contains forced checklist
- **WHEN** the reflect prompt is assembled for any phase
- **THEN** the prompt SHALL contain a "Before deciding, you MUST complete this checklist" section with all five checklist items listed

#### Scenario: Checklist precedes decision in prompt structure
- **WHEN** the reflect prompt is rendered
- **THEN** the forced checklist SHALL appear before the decision output format section, ensuring the Twin processes the checklist before generating its decision

### Requirement: Watch-outs limit in reflect prompt
The reflect prompt SHALL constrain the Twin to output at most 5 watch-out items. If the Twin produces more than 5 watch-outs in its drift assessment or page updates, the system SHALL log a warning but SHALL NOT reject the output -- the limit is enforced through prompt instruction, not hard validation.

#### Scenario: Prompt instructs watch-outs limit
- **WHEN** the reflect prompt is assembled for any phase
- **THEN** the prompt SHALL contain an instruction stating that watch-outs MUST NOT exceed 5 items

#### Scenario: Twin outputs more than 5 watch-outs
- **WHEN** the Twin returns a YAML response with more than 5 watch-out items
- **THEN** the system SHALL log a warning about the exceeded limit but SHALL NOT fail or reject the TwinResult

### Requirement: Confidence derived from occurrences, not set by Twin
The `confidence` field in wiki page frontmatter SHALL be automatically derived by code from the `occurrences` count and `sentiment` value. The Twin MUST NOT set the confidence field directly. The `derive_confidence()` function SHALL return: `"tentative"` for occurrences=1, `"established"` for occurrences=2, `"definitive"` for occurrences>=3 with positive sentiment, and `"established"` for occurrences>=3 with negative sentiment (capped). The `update_frontmatter()` function SHALL increment occurrences, re-derive confidence, update last_updated, and track source_epics after every UPDATE or EVOLVE.

#### Scenario: Occurrences 1 yields tentative
- **WHEN** a new page is created with `occurrences=1` and `sentiment="positive"`
- **THEN** `derive_confidence(1, "positive")` SHALL return `"tentative"`

#### Scenario: Occurrences 2 yields established
- **WHEN** a page is updated and occurrences becomes 2
- **THEN** `derive_confidence(2, "positive")` SHALL return `"established"`

#### Scenario: Occurrences 3 positive yields definitive
- **WHEN** a page is updated and occurrences becomes 3 with `sentiment="positive"`
- **THEN** `derive_confidence(3, "positive")` SHALL return `"definitive"`

#### Scenario: Occurrences 3 negative yields established (cap)
- **WHEN** a page is updated and occurrences becomes 3 with `sentiment="negative"`
- **THEN** `derive_confidence(3, "negative")` SHALL return `"established"`

### Requirement: EVOLVE restricted to loaded pages
The Twin SHALL only EVOLVE pages that have been loaded into the reflect prompt (i.e., the INDEX and the guide page). The Twin MUST NOT EVOLVE pages it has not read, because rewriting without having seen the current content risks losing information. UPDATE with `append_evidence` is permitted on unloaded pages because the code appends evidence mechanically without requiring the Twin to know the existing content.

#### Scenario: EVOLVE guide page (loaded)
- **WHEN** the Twin outputs a PageUpdate with `action="evolve"` for the guide page that was loaded into the prompt
- **THEN** `apply_page_updates()` SHALL process the EVOLVE normally

#### Scenario: EVOLVE non-loaded page
- **WHEN** the Twin outputs a PageUpdate with `action="evolve"` for a page that was NOT loaded into the prompt (e.g., a pattern page only visible through the INDEX summary)
- **THEN** the prompt instructions SHALL discourage this; if the Twin still outputs such an EVOLVE, `apply_page_updates()` SHALL process it (since the code cannot know which pages the Twin "read") but the prompt design makes this unlikely

#### Scenario: UPDATE with append_evidence on non-loaded page
- **WHEN** the Twin outputs a PageUpdate with `action="update"` and `append_evidence` for a page that was not loaded (but is visible in the INDEX)
- **THEN** `apply_page_updates()` SHALL process the UPDATE normally, appending the evidence row mechanically

### Requirement: Maximum 2 page updates per reflect call
The reflect prompt SHALL instruct the Twin that at most 2 PageUpdate entries MAY be produced per reflect call. If the Twin returns more than 2 page updates, `apply_page_updates()` SHALL process only the first 2 and log a warning about the excess.

#### Scenario: Twin outputs 2 page updates
- **WHEN** the Twin returns exactly 2 PageUpdate entries
- **THEN** `apply_page_updates()` SHALL process both updates

#### Scenario: Twin outputs more than 2 page updates
- **WHEN** the Twin returns 3 or more PageUpdate entries
- **THEN** `apply_page_updates()` SHALL process only the first 2, log a warning about the excess, and skip the remaining updates

### Requirement: YAML block extraction and content block scalar fix
After the LLM returns raw output, the reflect pipeline SHALL extract the YAML code block (delimited by ```yaml ... ```), then apply `fix_content_block_scalars()` to repair common format issues where the Twin used inline quoting instead of `|` block scalar for multi-line `content` or `section_patches` values. The repaired YAML string SHALL then be parsed with `yaml.safe_load()` and validated with `TwinResult.model_validate()`.

#### Scenario: Twin uses inline quoting for content
- **WHEN** the Twin returns YAML where `content: "line1\nline2\nline3"` instead of `content: |` block scalar
- **THEN** `fix_content_block_scalars()` SHALL convert the inline quoting to block scalar format before YAML parsing

#### Scenario: Twin uses proper block scalar
- **WHEN** the Twin returns YAML where `content: |` is used correctly
- **THEN** `fix_content_block_scalars()` SHALL leave the content unchanged

### Requirement: Smart truncation for long LLM output and git diff
The `prepare_llm_output()` function SHALL apply smart truncation when the estimated token count of `llm_output` or `files_diff` exceeds 120K tokens. Truncation SHALL preserve the first 1/4 (head) and the last 3/4 (tail) by character position, joined by a truncation marker. This ensures the Twin sees the execution start context and the critical self-audit/completion sections at the end.

#### Scenario: Short output passes through unchanged
- **WHEN** `prepare_llm_output()` is called with an 8000-character llm_output (estimated ~2000 tokens)
- **THEN** it SHALL return the complete output without modification

#### Scenario: Long output truncated with head+tail
- **WHEN** `prepare_llm_output()` is called with a 600000-character llm_output (estimated ~150000 tokens, exceeding 120K)
- **THEN** it SHALL return the first 1/4 of characters (head) + a truncation marker + the last 3/4 of characters (tail)

### Requirement: TwinProviderConfig for reflect configuration
The system SHALL define a `TwinProviderConfig` Pydantic model with fields `provider: str`, `model: str`, `enabled: bool = True`, `max_retries: int = 2`, and `retry_exhausted_action: Literal["halt", "continue"] = "halt"`. The `Twin` class SHALL be initialized with this config and use the specified provider/model for LLM calls, independent of the execution model.

#### Scenario: Default configuration
- **WHEN** a TwinProviderConfig is constructed with no arguments
- **THEN** `enabled` SHALL be `True`, `max_retries` SHALL be `2`, and `retry_exhausted_action` SHALL be `"halt"`

#### Scenario: Custom configuration
- **WHEN** a TwinProviderConfig is constructed with `provider="claude"`, `model="opus"`, `max_retries=3`, and `retry_exhausted_action="continue"`
- **THEN** all fields SHALL store the provided values

### Requirement: No DORMANT or ARCHIVED page states
The wiki page lifecycle SHALL have only two states: exists or does not exist. There SHALL be no DORMANT, ARCHIVED, or other intermediate states. Pages, once created, SHALL persist permanently unless manually deleted by a human. The Twin SHALL NOT have an archive action.

#### Scenario: Page exists after creation
- **WHEN** a page is created by the Twin
- **THEN** the page file SHALL exist in the wiki directory and remain there indefinitely

#### Scenario: No archive action available
- **WHEN** a PageUpdate is constructed with `action="archive"`
- **THEN** Pydantic validation SHALL reject it because "archive" is not in the Literal type for action

### Requirement: source_epics tracking for self-reinforcing error detection
The `update_frontmatter()` function SHALL track `source_epics` -- a list of epic IDs that contributed evidence to the page. When a new epic ID is not already in `source_epics`, it SHALL be appended. This enables humans to audit whether evidence for a pattern comes from genuinely independent contexts or from repeated observations in the same area.

#### Scenario: New epic added to source_epics
- **WHEN** `update_frontmatter()` is called with `epic_id="epic-15"` on a page where `source_epics=["epic-12"]`
- **THEN** `source_epics` SHALL become `["epic-12", "epic-15"]`

#### Scenario: Duplicate epic not added
- **WHEN** `update_frontmatter()` is called with `epic_id="epic-12"` on a page where `source_epics=["epic-12"]`
- **THEN** `source_epics` SHALL remain `["epic-12"]` unchanged

### Requirement: INDEX auto-generated from page frontmatter
The `rebuild_index()` function SHALL scan all wiki pages, extract frontmatter metadata and titles, compute backlinks from all pages' `links_to` fields, and generate INDEX.md. The INDEX SHALL NOT be written by the Twin. After every `apply_page_updates()` call, `rebuild_index()` SHALL be invoked to ensure consistency.

#### Scenario: INDEX rebuilt after page updates
- **WHEN** `apply_page_updates()` creates or modifies any wiki page
- **THEN** it SHALL call `rebuild_index()` as the final step

#### Scenario: INDEX contains backlinks
- **WHEN** page A has `links_to: [B]` and page B has `links_to: [A]`
- **THEN** the INDEX SHALL show that A links to B and B links to A, with backlinks computed automatically

#### Scenario: Twin never writes INDEX
- **WHEN** a PageUpdate targets `page_name="INDEX"`
- **THEN** the page name validation SHALL reject it because "INDEX" does not match the required pattern `(env|pattern|design|guide)-[a-z0-9-]+`

### Requirement: Quality constraints on wiki content
The reflect prompt SHALL enforce quality constraints on wiki page content: (1) the What section MUST contain specific technical details (library/framework/method names), not universal principles; (2) the Evidence Context column MUST contain enough detail to recreate the scenario; (3) pages containing no project-specific information (e.g., "always test your code") are NOT valid experiences; (4) each PageUpdate's reason field MUST cite specific evidence from the current execution.

#### Scenario: Generic platitude in page content
- **WHEN** the Twin creates a page whose What section says "always test your code" without project-specific details
- **THEN** the prompt instructions SHALL have explicitly forbidden this, making such output unlikely; however, the code does not validate content quality beyond structural validation

#### Scenario: Reason field cites execution evidence
- **WHEN** the Twin outputs a PageUpdate with `reason="New evidence for existing test-first pattern, broadened scope"`
- **THEN** this satisfies the quality requirement that each reason must cite specific evidence
