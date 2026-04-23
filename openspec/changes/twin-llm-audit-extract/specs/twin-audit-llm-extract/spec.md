## ADDED Requirements

### Requirement: LLM-based self-audit extraction method
The `Twin` class SHALL provide a private method `_extract_self_audit_llm(llm_output: str) -> str | None` that uses an LLM call to semantically identify and extract a self-audit, review, or quality-check section from raw LLM output when the regex-based `format_self_audit()` returns None.

The method SHALL:
1. Build an extraction prompt via `build_extract_self_audit_prompt(llm_output)`
2. Call `self._provider.invoke(prompt, model=audit_extract_model or self.config.model)`
3. Parse the YAML output containing `found: bool` and `content: str`
4. Return the extracted content if `found=True` and content is non-empty, otherwise return None
5. Return None on any failure (provider error, YAML parse error, unexpected format)

#### Scenario: LLM extraction finds Chinese heading audit section
- **WHEN** `_extract_self_audit_llm()` is called with llm_output containing "## 审查\n- 所有验收标准已满足\n- 无回归问题" and the regex `format_self_audit()` has already returned None
- **THEN** the method SHALL call the LLM provider with the extraction prompt, parse the YAML response with `found: true` and `content`, and return "- 所有验收标准已满足\n- 无回归问题"

#### Scenario: LLM extraction finds non-standard heading level
- **WHEN** `_extract_self_audit_llm()` is called with llm_output containing "### Quality Check\n- Code reviewed\n- Tests passing" where the heading is h3, not h2
- **THEN** the method SHALL return the extracted audit content "- Code reviewed\n- Tests passing"

#### Scenario: LLM extraction finds no audit section
- **WHEN** `_extract_self_audit_llm()` is called with llm_output that contains no self-audit or equivalent section, and the LLM returns YAML with `found: false`
- **THEN** the method SHALL return None

#### Scenario: LLM extraction provider failure
- **WHEN** `_extract_self_audit_llm()` is called and the provider raises an exception
- **THEN** the method SHALL log a warning and return None without raising

#### Scenario: LLM extraction YAML parse failure
- **WHEN** `_extract_self_audit_llm()` is called and the LLM returns output that does not contain a valid YAML block
- **THEN** the method SHALL log a warning and return None without raising

#### Scenario: LLM extraction with empty llm_output
- **WHEN** `_extract_self_audit_llm()` is called with an empty string
- **THEN** the method SHALL return None without making an LLM call

### Requirement: Self-audit extraction prompt template
The system SHALL provide a `build_extract_self_audit_prompt(llm_output: str) -> str` function in `prompts.py` that constructs a prompt instructing the LLM to find and extract a self-audit or quality review section.

The prompt SHALL:
1. List heading variants to look for: "Self-Audit", "Execution Self-Audit", "审查", "自审", "执行自审", "Quality Check", "Quality Review", and any heading at any level containing a self-assessment or audit
2. Request YAML output with `found: bool` and `content: |` (verbatim extraction, not summarization)
3. Instruct the model to return `found: false` when no such section exists
4. Include the full `llm_output` as the document to scan

#### Scenario: Prompt contains document content
- **WHEN** `build_extract_self_audit_prompt("some output text")` is called
- **THEN** the returned prompt SHALL contain the string "some output text"

#### Scenario: Prompt requests YAML output format
- **WHEN** `build_extract_self_audit_prompt()` is called with any input
- **THEN** the returned prompt SHALL instruct the LLM to return YAML with `found` and `content` fields

#### Scenario: Prompt lists Chinese and English heading variants
- **WHEN** `build_extract_self_audit_prompt()` is called with any input
- **THEN** the returned prompt SHALL include both Chinese ("审查", "自审") and English ("Self-Audit", "Quality Check") heading examples

### Requirement: audit_extract_model configuration field
The `TwinProviderConfig` SHALL include an `audit_extract_model: str | None` field with default value None. When None, the extraction SHALL fall back to `self.config.model` (the Twin's main model). When set to a string value, the extraction SHALL use that model identifier.

#### Scenario: Default None falls back to main model
- **WHEN** `TwinProviderConfig()` is constructed with no `audit_extract_model` argument
- **THEN** `audit_extract_model` SHALL be None, and extraction SHALL use `self.config.model`

#### Scenario: Custom model for extraction
- **WHEN** `TwinProviderConfig(audit_extract_model="haiku")` is constructed
- **THEN** extraction SHALL use "haiku" as the model for the provider invoke call

### Requirement: Smart truncation applied to extraction prompt input
When `llm_output` is very large (exceeding 120K tokens estimated), `_extract_self_audit_llm()` SHALL apply `prepare_llm_output()` to truncate the input before building the extraction prompt, using the same head(1/4) + tail(3/4) strategy.

#### Scenario: Short output passed through unchanged
- **WHEN** `_extract_self_audit_llm()` is called with llm_output of 5000 characters
- **THEN** the full llm_output SHALL be included in the extraction prompt without truncation

#### Scenario: Long output truncated before extraction
- **WHEN** `_extract_self_audit_llm()` is called with llm_output exceeding 120K tokens
- **THEN** the extraction prompt SHALL contain the truncated version from `prepare_llm_output()`
