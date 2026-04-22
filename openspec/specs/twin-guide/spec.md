# twin-guide

The twin-guide capability provides phase-specific compass generation for the Digital Twin system. When invoked before a phase runs, the Twin produces a compass — a focused advisory string that orients the runner toward the most relevant wiki knowledge for the upcoming phase.

## ADDED Requirements

### Requirement: guide method

The Twin class SHALL expose a `guide(phase_type)` method that returns a compass string for the given phase type. The method SHALL load only the INDEX page and the guide page for the specified phase type (if it exists), then invoke the LLM with the guide prompt template to produce the compass.

The method signature SHALL be:

```python
def guide(self, phase_type: str) -> Optional[str]
```

When the guide page exists, the prompt SHALL include the INDEX and the guide page content. When the guide page does not exist, the prompt SHALL include the INDEX and all environment, pattern, and design pages, instructing the LLM to reason from those pages to generate a compass.

The guide method SHALL NOT produce any wiki page updates. It SHALL only return the compass string.

#### Scenario: guide with existing guide page

WHEN `guide("story")` is called
AND a wiki page named `guide-story` exists
THEN the method SHALL load the INDEX page and the `guide-story` page content
AND invoke the LLM with the guide prompt template using those two pages as context
AND return the resulting compass string

#### Scenario: guide with missing guide page

WHEN `guide("qa_plan_execute")` is called
AND no wiki page named `guide-qa_plan_execute` exists
THEN the method SHALL load the INDEX page
AND load all environment, pattern, and design wiki pages referenced in the INDEX
AND invoke the LLM with the guide prompt template, instructing it to reason from those pages to produce a compass
AND return the resulting compass string

### Requirement: guide prompt template

The file `prompts.py` SHALL define a guide prompt template string used for all guide LLM calls. The template SHALL instruct the LLM to produce a concise compass that identifies the most relevant wiki knowledge for the specified phase type.

The template MUST include placeholders for:
- `phase_type` — the phase being guided
- `index_content` — the rendered INDEX page
- `guide_content` — the rendered guide page (when available), or a collected set of environment/pattern/design page contents (when the guide page is absent)
- `is_guide_present` — a flag indicating whether a dedicated guide page was loaded

The template SHALL instruct the LLM to output only the compass string with no YAML, no frontmatter, and no page update directives.

#### Scenario: template with guide page present

WHEN the guide prompt template is rendered with `is_guide_present=True`
AND `guide_content` contains a dedicated guide page
THEN the rendered prompt SHALL instruct the LLM to derive the compass primarily from the guide page content, supplemented by the INDEX

#### Scenario: template without guide page

WHEN the guide prompt template is rendered with `is_guide_present=False`
AND `guide_content` contains collected environment, pattern, and design page contents
THEN the rendered prompt SHALL instruct the LLM to reason across all provided pages to synthesize a compass for the given phase type

### Requirement: strategy-D loading for guide

The guide method SHALL use the same Strategy-D loading pattern as reflect: load only the INDEX page and the single guide page (or the set of environment/pattern/design pages when the guide page is absent). The method SHALL NOT follow links or load additional pages referenced within the guide page.

#### Scenario: no linked page loading

WHEN the `guide-story` page contains wiki-links to other pages
THEN the guide method SHALL NOT load those linked pages
AND the LLM context SHALL contain only the INDEX page and the `guide-story` page content

### Requirement: guide produces no wiki updates

The guide method SHALL NOT return, produce, or emit any PageUpdate objects. The return type is `Optional[str]` — either a compass string or `None`. The guide prompt MUST explicitly instruct the LLM that no wiki updates are allowed in the guide output.

#### Scenario: compass is a plain string

WHEN the guide method successfully produces a compass
THEN the return value SHALL be a plain string containing the compass text
AND no PageUpdate objects SHALL be created or returned

### Requirement: non-critical failure handling

The guide method is non-critical. If the LLM call fails, times out, or returns unparseable output, the method SHALL return `None` instead of raising an exception. The runner SHALL continue execution without a compass when `guide()` returns `None`.

The method MUST catch all exceptions from the LLM call and return `None` in the error case. Logging the failure at warning level is permitted but not required.

#### Scenario: LLM call fails

WHEN `guide("epic_setup")` is called
AND the LLM call raises an exception or times out
THEN the method SHALL return `None`
AND the runner SHALL continue execution without a compass

#### Scenario: unparseable LLM output

WHEN `guide("story")` is called
AND the LLM returns output that cannot be interpreted as a compass string
THEN the method SHALL return `None`
AND the runner SHALL continue execution without a compass

#### Scenario: successful guide returns compass

WHEN `guide("story")` is called
AND the LLM returns a valid compass string
THEN the method SHALL return that string
AND the runner SHALL use the compass to orient phase execution
