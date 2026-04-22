## ADDED Requirements

### Requirement: CompilerContext compass field
The `CompilerContext` dataclass SHALL include a `compass: str | None = None` field that carries the Twin guide's compass text through the compilation pipeline.

#### Scenario: Compass provided by the Twin guide system
- **WHEN** `CompilerContext` is constructed with `compass="Focus on edge-case validation for retry logic"`
- **THEN** the `compass` field SHALL store the provided string value

#### Scenario: Compass not provided
- **WHEN** `CompilerContext` is constructed without a `compass` argument
- **THEN** the `compass` field SHALL default to `None`

### Requirement: Compass section insertion in compiled prompt
The `generate_output()` method SHALL insert a `<compass>` section in the compiled prompt immediately after the `<mission>` section and before the `<context>` section. When `compass` is `None`, no `<compass>` section SHALL be inserted and the output SHALL be identical to the behavior before this change.

#### Scenario: Compass is present
- **WHEN** `CompilerContext.compass` is set to a non-None string value
- **THEN** `generate_output()` SHALL produce output containing a `<compass>` section with the compass text, positioned directly after the `<mission>` section and before the `<context>` section

#### Scenario: Compass is None
- **WHEN** `CompilerContext.compass` is `None`
- **THEN** `generate_output()` SHALL NOT include a `<compass>` section in the compiled prompt output

### Requirement: Dispatch passes compass parameter
The `execute_phase()` function in `dispatch.py` SHALL pass the `compass` parameter from the phase execution context to `BaseHandler.execute()`.

#### Scenario: Dispatch forwards compass to handler
- **WHEN** `execute_phase()` is called with a compass value
- **THEN** it SHALL forward that compass value to `BaseHandler.execute()`

#### Scenario: Dispatch forwards None compass
- **WHEN** `execute_phase()` is called with no compass value
- **THEN** it SHALL pass `None` as the compass parameter to `BaseHandler.execute()`

### Requirement: BaseHandler accepts and forwards compass
The `BaseHandler.execute()` method SHALL accept a `compass` parameter and pass it through to `render_prompt()` so it reaches the compiler context.

#### Scenario: Handler receives compass and forwards to render_prompt
- **WHEN** `BaseHandler.execute()` is called with `compass="Avoid redundant DB queries"`
- **THEN** it SHALL forward the compass value to `render_prompt()`

#### Scenario: Handler receives None compass
- **WHEN** `BaseHandler.execute()` is called with `compass=None`
- **THEN** it SHALL pass `compass=None` to `render_prompt()` without error
