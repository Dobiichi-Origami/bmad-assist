## 1. Wiki 基础设施 (wiki.py)

- [x] 1.1 Create `src/bmad_assist/twin/__init__.py` module scaffold
- [x] 1.2 Implement `read_page()`, `write_page()`, `list_pages()`, `page_exists()` file I/O functions
- [x] 1.3 Implement `parse_frontmatter()` and `update_frontmatter()` with `source_epics` tracking
- [x] 1.4 Implement `extract_links()` for wiki page cross-reference resolution
- [x] 1.5 Implement `rebuild_index()` with reverse reference calculation from all pages' `links_to`
- [x] 1.6 Implement `validate_page_name()` with regex `(env|pattern|design|guide)-[a-z0-9-]+`
- [x] 1.7 Implement `apply_section_patches()` for section-level content replacement
- [x] 1.8 Implement `append_evidence_row()` to add evidence rows to existing pages
- [x] 1.9 Implement `extract_evidence_table()` for EVOLVE's evidence preservation
- [x] 1.10 Implement `init_wiki()` with seed guide page templates per phase type
- [x] 1.11 Implement `load_guide_page()` (Strategy D: only INDEX + guide-{phase_type})
- [x] 1.12 Implement `fix_content_block_scalars()` for YAML block scalar recovery
- [x] 1.13 Implement `prepare_llm_output()` with head(1/4)+tail(3/4) smart truncation (>120K tokens)
- [x] 1.14 Implement `derive_confidence()` with occurrence-based mapping and negative pattern cap at established

## 2. 自检清单注入 (Self-Audit Checklists)

- [x] 2.1 Add common self-audit template to `dev-story/instructions.xml` with dev_story specific items
- [x] 2.2 Add common self-audit template to `create-story/instructions.xml` with create_story specific items
- [x] 2.3 Add common self-audit template to `code-review/instructions.xml` with code_review specific items
- [x] 2.4 Add common self-audit template to `validate-story/instructions.xml` with validate_story specific items
- [x] 2.5 Add self-audit template to `validate-story-synthesis/instructions.xml` with synthesis specific items
- [x] 2.6 Add self-audit template to `code-review-synthesis/instructions.xml` with synthesis specific items
- [x] 2.7 Add self-audit template to `retrospective/instructions.md` with retrospective specific items
- [x] 2.8 Add self-audit template to `qa/prompts/remediate.xml` with qa_remediate specific items
- [x] 2.9 Add self-audit template to TEA workflow instructions (tea_framework, tea_ci, tea_test_design, tea_automate)

## 3. ExecutionRecord + qa_remediate 修补

- [x] 3.1 Create `src/bmad_assist/twin/execution_record.py` with ExecutionRecord dataclass (phase, mission, llm_output, self_audit, success, duration_ms, error, phase_outputs, files_modified, files_diff)
- [x] 3.2 Implement `build_execution_record()` to construct from state + result + git diff
- [x] 3.3 Implement `format_self_audit()` to parse Self-Audit section from llm_output
- [x] 3.4 Modify `handlers/qa_remediate.py` to collect `all_llm_outputs` and add "response" field to PhaseResult.ok()

## 4. Twin Reflect (核心)

- [x] 4.1 Create `src/bmad_assist/twin/twin.py` with Twin class and constructor (config, wiki_dir, provider)
- [x] 4.2 Define TwinResult / PageUpdate / DriftAssessment Pydantic models (PageUpdate max 2 items)
- [x] 4.3 Create `src/bmad_assist/twin/prompts.py` with reflect prompt template
- [x] 4.4 Implement phase-specific review guidance in prompts.py (dev_story, qa_remediate, atdd, create_story, code_review_synthesis, retrospective)
- [x] 4.5 Implement initialization guidance for empty wiki INDEX
- [x] 4.6 Implement challenge mode prompt injection (every 5 epics)
- [x] 4.7 Implement forced checklist before decision in reflect prompt
- [x] 4.8 Implement watch-outs ≤5 limit in reflect prompt
- [x] 4.9 Implement `Twin.reflect(record, is_retry)` with LLM call → YAML parse → TwinResult
- [x] 4.10 Implement YAML parse failure degradation: retry once, then is_retry=False→CONTINUE, is_retry=True→HALT
- [x] 4.11 Implement `apply_page_updates()`: create/update/evolve with validation, EVOLVE {{EVIDENCE_TABLE}} preservation, EVOLVE only on loaded pages
- [x] 4.12 Implement substring deduplication warning (no auto-convert CREATE→UPDATE)
- [x] 4.13 Implement `extract_yaml_block()` and `fix_content_block_scalars()` integration in reflect flow

## 5. Twin Guide (Compass 生成)

- [x] 5.1 Add guide prompt template to `twin/prompts.py`
- [x] 5.2 Implement `Twin.guide(phase_type)` method: load INDEX + guide page, call LLM, return compass string
- [x] 5.3 Implement guide fallback: when guide page doesn't exist, reason from all env/pattern/design pages
- [x] 5.4 Ensure guide does NOT produce wiki updates — only returns compass string
- [x] 5.5 Implement guide failure degradation: return compass=None on any error

## 6. Twin 配置 + Runner 集成

- [x] 6.1 Create `src/bmad_assist/twin/config.py` with TwinProviderConfig (provider, model, enabled, max_retries, retry_exhausted_action)
- [x] 6.2 Add twin config section to `providers.py` and YAML config schema
- [x] 6.3 Modify `runner.py`: add Twin.guide() call before phase execution → compass
- [x] 6.4 Modify `runner.py`: add build_execution_record() → twin.reflect() → apply_page_updates() after phase execution
- [x] 6.5 Implement RETRY logic: git stash → retry_count < max_retries → re-execute with correction compass
- [x] 6.6 Implement correction compass appending (not replacing) to original compass
- [x] 6.7 Implement retry_exhausted → retry_exhausted_action (halt/continue)
- [x] 6.8 Implement source_epics tracking in frontmatter for self-reinforcing error detection
- [x] 6.9 Implement failure degradation: guide fails → compass=None; reflect fails (first) → CONTINUE; reflect fails (RETRY) → HALT

## 7. Compiler Compass 支持

- [x] 7.1 Add `compass: str | None = None` field to `CompilerContext` in `compiler/types.py`
- [x] 7.2 Modify `generate_output()` in `compiler/output.py` to insert `<compass>` section after `<mission>` before `<context>`
- [x] 7.3 Modify `execute_phase()` in `dispatch.py` to pass compass parameter
- [x] 7.4 Modify `BaseHandler.execute()` in `handlers/base.py` to accept and forward compass to render_prompt
