## MODIFIED Requirements

### Requirement: Twin.reflect() single LLM call architecture
The `Twin.reflect(record, is_retry)` method SHALL operate as a single LLM call that produces structured YAML output. Twin is NOT an agent with tools -- the method MUST follow the pattern: (1) if `record.self_audit is None` and `record.llm_output` is non-empty, attempt LLM-based extraction via `_extract_self_audit_llm(record.llm_output)` to obtain `self_audit`, (2) assemble prompt from INDEX + guide page + execution record using the resolved `self_audit` value, (3) call the LLM provider once, (4) extract and parse the YAML block from the response, and (5) return a `TwinResult`. No iterative tool calling or multi-turn conversation SHALL occur within a single reflect invocation.

The `self_audit` resolution SHALL use a local variable, not modify the `record` dataclass. If LLM extraction returns None, the prompt SHALL use "(No Self-Audit section found in output)" as before.

#### Scenario: Successful reflect call with regex-extracted self-audit
- **WHEN** `Twin.reflect(record, is_retry=False)` is called with a valid ExecutionRecord where `record.self_audit` is not None
- **THEN** the method SHALL NOT call `_extract_self_audit_llm()` and SHALL use `record.self_audit` directly in the prompt

#### Scenario: Reflect with LLM-extracted self-audit fallback
- **WHEN** `Twin.reflect(record, is_retry=False)` is called with `record.self_audit=None` and `record.llm_output` containing a Chinese audit section "## 审查\n- 完成"
- **THEN** the method SHALL call `_extract_self_audit_llm(record.llm_output)`, use the extracted content as `self_audit` in the prompt, and proceed with the normal reflect flow

#### Scenario: Reflect with LLM extraction also returns None
- **WHEN** `Twin.reflect(record, is_retry=False)` is called with `record.self_audit=None` and `_extract_self_audit_llm()` also returns None
- **THEN** the prompt SHALL contain "(No Self-Audit section found in output)" and the reflect SHALL proceed normally

#### Scenario: Twin does not call tools
- **WHEN** the LLM provider returns output that contains tool-call-like instructions within the YAML
- **THEN** the reflect method SHALL treat the entire output as static text and parse only the YAML structure -- no tool execution SHALL occur

#### Scenario: Record dataclass not modified by reflect
- **WHEN** `Twin.reflect(record)` is called and the LLM extraction finds a self-audit
- **THEN** `record.self_audit` SHALL remain None (the original value); only the local `self_audit` variable used for prompt building SHALL contain the extracted content
