## ADDED Requirements

### Requirement: Wiki page read operation
The `read_page(wiki_dir, name)` function SHALL read the contents of a wiki page identified by its name (without `.md` extension). When the page does not exist, the function SHALL return `None`.

#### Scenario: Reading an existing page
- **WHEN** `read_page` is called with a wiki directory and the name `"env-async-session"` and the file `env-async-session.md` exists in that directory
- **THEN** the function SHALL return the full file contents as a string

#### Scenario: Reading a non-existent page
- **WHEN** `read_page` is called with a wiki directory and the name `"env-nonexistent"` and no corresponding `.md` file exists
- **THEN** the function SHALL return `None`

### Requirement: Wiki page write operation
The `write_page(wiki_dir, name, content)` function SHALL atomically write the given content to a wiki page file identified by its name. The function SHALL use the codebase's existing `atomic_write` utility to prevent partial writes.

#### Scenario: Writing a new page
- **WHEN** `write_page` is called with name `"pattern-test-first"` and valid markdown content
- **THEN** the file `pattern-test-first.md` SHALL be created in the wiki directory with the exact content provided

#### Scenario: Overwriting an existing page
- **WHEN** `write_page` is called with a name that already has an existing `.md` file
- **THEN** the existing file SHALL be completely replaced with the new content via atomic write

### Requirement: Wiki page listing
The `list_pages(wiki_dir)` function SHALL return a sorted list of all wiki page names (file stems without `.md` extension) in the wiki directory. The function SHALL exclude `INDEX` from the returned list.

#### Scenario: Listing pages in a populated wiki
- **WHEN** `list_pages` is called on a wiki directory containing `env-async-session.md`, `INDEX.md`, and `pattern-test-first.md`
- **THEN** the function SHALL return `["env-async-session", "pattern-test-first"]` (sorted, excluding INDEX)

#### Scenario: Listing pages in an empty wiki
- **WHEN** `list_pages` is called on a wiki directory containing only `INDEX.md`
- **THEN** the function SHALL return an empty list

### Requirement: Wiki page existence check
The `page_exists(wiki_dir, name)` function SHALL return `True` if a page file with the given name exists in the wiki directory, and `False` otherwise.

#### Scenario: Page exists
- **WHEN** `page_exists` is called with name `"env-async-session"` and that file exists
- **THEN** the function SHALL return `True`

#### Scenario: Page does not exist
- **WHEN** `page_exists` is called with name `"env-nonexistent"` and that file does not exist
- **THEN** the function SHALL return `False`

### Requirement: Wiki link extraction
The `extract_links(content)` function SHALL extract all `[[page-name]]` style wiki links from page content and return them as a list of page name strings.

#### Scenario: Extracting links from page content
- **WHEN** `extract_links` is called with content containing `[[env-async-session]]` and `[[pattern-test-first]]`
- **THEN** the function SHALL return a list containing `"env-async-session"` and `"pattern-test-first"`

#### Scenario: Content with no links
- **WHEN** `extract_links` is called with content containing no `[[...]]` syntax
- **THEN** the function SHALL return an empty list

### Requirement: INDEX auto-generation with reverse references
The `rebuild_index(wiki_dir)` function SHALL scan all wiki pages, extract frontmatter metadata and titles from each page, compute reverse reference (backlink) mappings from the `links_to` fields, and write a formatted `INDEX.md` file. The INDEX SHALL group pages by category, display confidence labels, sentiment abbreviations, last_updated epic, and occurrence counts for each page entry.

#### Scenario: Rebuilding INDEX from multiple pages
- **WHEN** `rebuild_index` is called on a wiki directory containing pages with various categories (env, pattern, design, guide)
- **THEN** the function SHALL write an `INDEX.md` file that groups pages by category, includes each page's name, title summary, confidence label in brackets, sentiment abbreviation, last_updated epic, and occurrence count

#### Scenario: Reverse reference calculation
- **WHEN** page `guide-dev-story` has `links_to: [pattern-test-first]` in its frontmatter
- **THEN** the backlinks map computed by `rebuild_index` SHALL include `pattern-test-first -> [guide-dev-story]`

#### Scenario: INDEX excludes itself from scanning
- **WHEN** `rebuild_index` scans the wiki directory
- **THEN** it SHALL skip `INDEX.md` and only process other `.md` files

### Requirement: Frontmatter parsing
The `parse_frontmatter(content)` function SHALL parse the YAML frontmatter delimited by `---` markers at the beginning of a page and return it as a dictionary. When the content has no valid frontmatter, the function SHALL return an empty dictionary.

#### Scenario: Parsing valid frontmatter
- **WHEN** `parse_frontmatter` is called with content starting with `---\ncategory: pattern\nconfidence: established\n---`
- **THEN** the function SHALL return `{"category": "pattern", "confidence": "established"}`

#### Scenario: Parsing content with no frontmatter
- **WHEN** `parse_frontmatter` is called with content that does not start with `---`
- **THEN** the function SHALL return an empty dictionary `{}`

#### Scenario: Parsing content with unterminated frontmatter
- **WHEN** `parse_frontmatter` is called with content starting with `---\ncategory: pattern` but no closing `---`
- **THEN** the function SHALL return an empty dictionary `{}`

### Requirement: Frontmatter update with source_epics tracking
The `update_frontmatter(content, epic_id)` function SHALL increment the `occurrences` field, re-derive `confidence` from the new occurrences count and sentiment using `derive_confidence`, update `last_updated` to the given `epic_id`, and append `epic_id` to `source_epics` if not already present. The function SHALL return the page content with the updated frontmatter.

#### Scenario: Updating frontmatter for a new epic
- **WHEN** `update_frontmatter` is called with content having `occurrences: 2, confidence: established, last_updated: epic-15, source_epics: [epic-12, epic-15]` and `epic_id="epic-22"`
- **THEN** the returned content SHALL have `occurrences: 3`, confidence re-derived by `derive_confidence`, `last_updated: epic-22`, and `source_epics: [epic-12, epic-15, epic-22]`

#### Scenario: Updating frontmatter for same epic (no duplicate source_epics)
- **WHEN** `update_frontmatter` is called with content where `epic_id="epic-22"` already exists in `source_epics`
- **THEN** `source_epics` SHALL NOT contain a duplicate entry for `"epic-22"`

### Requirement: Page name validation
The `validate_page_name(name)` function SHALL validate that a wiki page name conforms to the naming convention: it MUST start with one of the recognized category prefixes (`env-`, `pattern-`, `design-`, `guide-`) followed by a non-empty concept name consisting of lowercase alphanumeric characters and hyphens.

#### Scenario: Valid page name
- **WHEN** `validate_page_name` is called with `"pattern-test-first"`
- **THEN** the function SHALL return `True`

#### Scenario: Invalid page name without category prefix
- **WHEN** `validate_page_name` is called with `"test-first"`
- **THEN** the function SHALL return `False`

#### Scenario: Invalid page name with uppercase characters
- **WHEN** `validate_page_name` is called with `"pattern-TestFirst"`
- **THEN** the function SHALL return `False`

### Requirement: Section-level replacement
The `apply_section_patches(content, patches)` function SHALL replace the content of specified markdown sections (identified by `## Title` headings) in a page. For each entry in the patches dictionary, the function SHALL locate the section by its heading, replace the section body up to the next `##` heading or end of content, and preserve the heading line itself.

#### Scenario: Replacing a single section
- **WHEN** `apply_section_patches` is called with content containing `## When This Applies\nOld content here` and patches `{"When This Applies": "Updated scope text"}`
- **THEN** the section body SHALL be replaced with `"Updated scope text"` while the `## When This Applies` heading is preserved

#### Scenario: Replacing multiple sections
- **WHEN** `apply_section_patches` is called with patches for two different sections
- **THEN** both sections SHALL be replaced independently without affecting other sections or the content between them

#### Scenario: Patch for non-existent section
- **WHEN** `apply_section_patches` is called with a patch key that does not match any `##` heading in the content
- **THEN** the content SHALL remain unchanged for that patch entry (no error, no insertion)

### Requirement: Evidence row appending
The `append_evidence_row(content, evidence)` function SHALL append a new data row to the markdown table in the `## Evidence` section of a page. The row SHALL be constructed from the `evidence` dictionary's values, matching the existing table column order.

#### Scenario: Appending an evidence row
- **WHEN** `append_evidence_row` is called with content containing an Evidence table with columns `| Context | Result | Epic |` and evidence `{"context": "Rate limiter", "result": "Caught edge case", "epic": "epic-22"}`
- **THEN** a new table row `| Rate limiter | Caught edge case | epic-22 |` SHALL be appended after the last existing row in the Evidence table

### Requirement: Evidence table extraction
The `extract_evidence_table(content)` function SHALL extract the content of the `## Evidence` section (the markdown table including header and data rows, but excluding the section heading itself). This is used during EVOLVE operations to preserve the original evidence table. When no Evidence section exists, the function SHALL return an empty string.

#### Scenario: Extracting evidence from a page with Evidence section
- **WHEN** `extract_evidence_table` is called with content containing `## Evidence\n| Context | Result | Epic |\n|---|---|---|\n| Auth fix | Passed | epic-12 |`
- **THEN** the function SHALL return the table content (header separator and data rows) without the `## Evidence` heading

#### Scenario: Extracting evidence from a page without Evidence section
- **WHEN** `extract_evidence_table` is called with content that has no `## Evidence` heading
- **THEN** the function SHALL return an empty string

### Requirement: EVOLVE preserves original evidence table
When applying a PageUpdate with action `evolve`, the system SHALL replace the `{{EVIDENCE_TABLE}}` placeholder in the evolved content with the original evidence table extracted from the existing page. This prevents the Twin from losing or altering historical evidence during a page rewrite.

#### Scenario: EVOLVE with EVIDENCE_TABLE placeholder
- **WHEN** an evolve PageUpdate contains `{{EVIDENCE_TABLE}}` in its content and the existing page has an Evidence table
- **THEN** the placeholder SHALL be replaced with the original evidence table content from the existing page

#### Scenario: EVOLVE without EVIDENCE_TABLE placeholder
- **WHEN** an evolve PageUpdate does not contain `{{EVIDENCE_TABLE}}` in its content
- **THEN** the evolved content SHALL be written as-is without evidence table preservation

### Requirement: Strategy D loading (INDEX + guide page only)
The `load_guide_page(wiki_dir, phase)` function SHALL load exactly two items: the INDEX.md content and the guide page for the given phase type. The function SHALL NOT load any linked pages or use any priority-based loading strategy. The phase type SHALL be derived from the phase name by taking the portion before the first underscore.

#### Scenario: Loading for a phase with existing guide page
- **WHEN** `load_guide_page` is called with a `dev_story` phase and the wiki has a `guide-dev.md` page
- **THEN** the function SHALL return a tuple of (INDEX content string, guide page content string)

#### Scenario: Loading for a phase without a guide page
- **WHEN** `load_guide_page` is called with a phase type for which no guide page exists
- **THEN** the function SHALL return a tuple of (INDEX content string, `None`)

#### Scenario: Phase type derivation from compound name
- **WHEN** `load_guide_page` is called with a phase named `qa_remediate`
- **THEN** the phase type SHALL be derived as `"qa"` (portion before first underscore), and the function SHALL attempt to load `guide-qa.md`

### Requirement: Wiki initialization with seed guide pages
The `init_wiki(project_root)` function SHALL create the wiki directory structure under `_bmad-output/implementation-artifacts/experiences/`, write seed guide page templates for `guide-dev-story` and `guide-qa-remediate` (if they do not already exist), and call `rebuild_index` to generate the initial INDEX. Seed pages SHALL contain YAML frontmatter with `category: guide`, `sentiment: neutral`, `confidence: tentative`, `occurrences: 0`, and placeholder sections for Watch-outs, Recommended Patterns, and Quality Checklist.

#### Scenario: Initializing a new wiki
- **WHEN** `init_wiki` is called on a project root where the experiences directory does not exist
- **THEN** the directory SHALL be created, seed guide pages SHALL be written, and INDEX.md SHALL be generated

#### Scenario: Initializing wiki when seed pages already exist
- **WHEN** `init_wiki` is called and a seed guide page file already exists
- **THEN** the existing seed page SHALL NOT be overwritten

#### Scenario: Seed guide page Quality Checklist
- **WHEN** the `guide-dev-story` seed page is created
- **THEN** it SHALL contain a Quality Checklist section with entries for acceptance criteria coverage, prohibition of "not essential" as skip justification, and test passing requirements

### Requirement: YAML tolerance for content block scalars
The `fix_content_block_scalars(yaml_str)` function SHALL repair common formatting errors in the Twin's YAML output where `content` fields or `section_patches` values use inline quoting instead of the required `|` block scalar notation. The function SHALL convert such inline-quoted multi-line content to proper block scalar form so that `yaml.safe_load` can parse it.

#### Scenario: Fixing inline-quoted content field
- **WHEN** `fix_content_block_scalars` is called with YAML containing `content: "multi\nline\ncontent"` where multi-line content is wrapped in inline quotes
- **THEN** the function SHALL convert it to `content: |` block scalar form

#### Scenario: Already correct block scalar
- **WHEN** `fix_content_block_scalars` is called with YAML that already uses `content: |` block scalar notation
- **THEN** the function SHALL return the YAML string unchanged

### Requirement: Smart truncation of LLM output
The `prepare_llm_output(llm_output, max_tokens=120000)` function SHALL estimate the token count of the output (at approximately 4 characters per token) and, when the estimated tokens exceed `max_tokens`, truncate the output by keeping the first 1/4 of the character budget (head) and the last 3/4 of the character budget (tail), joined by a truncation marker. When the output is within the budget, the function SHALL return it unchanged.

#### Scenario: Output within token budget
- **WHEN** `prepare_llm_output` is called with content estimated at 80,000 tokens (below the 120,000 default)
- **THEN** the function SHALL return the content unchanged

#### Scenario: Output exceeds token budget
- **WHEN** `prepare_llm_output` is called with content estimated at 160,000 tokens (above the 120,000 default)
- **THEN** the function SHALL return the first 1/4 of the character budget concatenated with a truncation marker and the last 3/4 of the character budget

#### Scenario: Custom max_tokens threshold
- **WHEN** `prepare_llm_output` is called with `max_tokens=50000` and content estimated at 60,000 tokens
- **THEN** the function SHALL apply the head(1/4) + tail(3/4) truncation based on the 50,000 token budget

### Requirement: Confidence derivation from occurrences
The `derive_confidence(occurrences, sentiment)` function SHALL derive the confidence level as a single word from the occurrences count and sentiment. Confidence values SHALL be `tentative`, `established`, or `definitive` (not numbers, not symbols). The Twin SHALL NOT set confidence directly; it is always code-derived from occurrences. Negative patterns (sentiment=negative) SHALL be capped at `established` regardless of occurrences count. Only challenge mode (every 5 epics) can promote a negative pattern to `definitive`.

#### Scenario: First occurrence (tentative)
- **WHEN** `derive_confidence` is called with `occurrences=1` and `sentiment="positive"`
- **THEN** the function SHALL return `"tentative"`

#### Scenario: Second occurrence (established)
- **WHEN** `derive_confidence` is called with `occurrences=2` and `sentiment="positive"`
- **THEN** the function SHALL return `"established"`

#### Scenario: Third or more occurrence for positive sentiment (definitive)
- **WHEN** `derive_confidence` is called with `occurrences=3` and `sentiment="positive"`
- **THEN** the function SHALL return `"definitive"`

#### Scenario: Negative pattern cap at established
- **WHEN** `derive_confidence` is called with `occurrences=5` and `sentiment="negative"`
- **THEN** the function SHALL return `"established"` (negative patterns are capped at established)

#### Scenario: Negative pattern at low occurrence (tentative)
- **WHEN** `derive_confidence` is called with `occurrences=1` and `sentiment="negative"`
- **THEN** the function SHALL return `"tentative"`

### Requirement: Page lifecycle is binary (exists / does not exist)
Wiki pages SHALL have exactly two lifecycle states: exists or does not exist. There SHALL be no DORMANT or ARCHIVED states. Once a page is created, it persists unless manually deleted by a human.

#### Scenario: Page creation transitions from non-existence to existence
- **WHEN** a PageUpdate with action `create` is applied for a page that does not exist
- **THEN** the page SHALL be written to the wiki directory and SHALL exist

#### Scenario: No archive action exists
- **WHEN** a PageUpdate is processed
- **THEN** the only valid actions SHALL be `create`, `update`, and `evolve`; no `archive` action SHALL be recognized

### Requirement: PageUpdate has three actions (create, update, evolve)
The `PageUpdate` model SHALL support exactly three action values: `create`, `update`, and `evolve`. There SHALL be no `archive` action. Each action has distinct semantics and code paths.

#### Scenario: Create action
- **WHEN** a PageUpdate with `action="create"` is applied
- **THEN** the system SHALL write a new page file, rejecting the operation if the page already exists

#### Scenario: Update action
- **WHEN** a PageUpdate with `action="update"` is applied
- **THEN** the system SHALL apply evidence appending and/or section patches to the existing page, updating frontmatter with incremented occurrences and re-derived confidence

#### Scenario: Evolve action
- **WHEN** a PageUpdate with `action="evolve"` is applied
- **THEN** the system SHALL replace the page content while preserving the original evidence table via `{{EVIDENCE_TABLE}}` placeholder substitution

### Requirement: EVOLVE safety check against manual edits
When applying an EVOLVE action, the system SHALL check whether the page's `last_updated` field in its frontmatter matches the current epic ID. If they do not match, the EVOLVE SHALL be skipped with a warning, because a mismatch indicates the page was modified outside of Twin control (e.g., by a human). Manual edits take priority over Twin rewrites.

#### Scenario: EVOLVE when page was updated by Twin in current epic
- **WHEN** an EVOLVE is applied and the page's `last_updated` equals the current epic ID
- **THEN** the EVOLVE SHALL proceed normally

#### Scenario: EVOLVE when page was modified outside Twin
- **WHEN** an EVOLVE is applied and the page's `last_updated` does not equal the current epic ID
- **THEN** the EVOLVE SHALL be skipped and a warning SHALL be logged indicating manual edits take priority

### Requirement: Substring deduplication warning only
When applying a CREATE action, the system SHALL check whether any existing page name is a substring prefix of or has a substring prefix relationship with the new page name, within the same category. When such a relationship is detected, the system SHALL log a warning but SHALL NOT automatically convert the CREATE to an UPDATE. Automatic conversion is prohibited because it may lose the Twin's creation intent.

#### Scenario: Substring overlap detected during CREATE
- **WHEN** a CREATE is attempted for `"pattern-test-first-auth"` and `"pattern-test-first"` already exists in the same category
- **THEN** the system SHALL log a warning about possible duplication and proceed with the CREATE

#### Scenario: No substring overlap during CREATE
- **WHEN** a CREATE is attempted for `"env-database-url"` and no existing page name has a substring prefix relationship
- **THEN** no warning SHALL be logged and the CREATE SHALL proceed
