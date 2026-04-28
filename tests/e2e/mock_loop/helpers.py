"""Mock E2E test helpers: ScriptedPhaseExecutor, project fixtures, config factory, harness, assertions."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from unittest.mock import patch

from bmad_assist.core.config import Config, load_config
from bmad_assist.core.loop.types import LoopExitReason, PhaseResult
from bmad_assist.core.state import Phase, State
from bmad_assist.core.types import EpicId


# =============================================================================
# ScriptedPhaseExecutor (Task 1.2)
# =============================================================================


class ScriptedPhaseExecutor:
    """Mock execute_phase that returns scripted results based on (epic, story, phase) key.

    Accepts a mapping of ``{(epic_id, story_id, phase): PhaseResult}`` and returns
    the corresponding result when called with a ``State`` object.  Unmapped phases
    return ``PhaseResult.ok()`` by default.

    All invocations are recorded for later assertion.
    """

    def __init__(
        self,
        script: dict[tuple[EpicId, str, Phase], PhaseResult] | None = None,
        *,
        default_result: PhaseResult | None = None,
        on_call: Any = None,
    ) -> None:
        self.script: dict[tuple[EpicId, str, Phase], PhaseResult] = script or {}
        self.default_result = default_result or PhaseResult.ok()
        self.invocations: list[tuple[EpicId | None, str | None, Phase | None]] = []
        # Optional callback invoked on every call (for signal injection etc.)
        self._on_call = on_call
        # Track compass values passed to each invocation
        self.compass_values: list[str | None] = []

    def __call__(self, state: State, compass: str | None = None) -> PhaseResult:
        key = (state.current_epic, state.current_story, state.current_phase)
        self.invocations.append(key)
        self.compass_values.append(compass)

        if self._on_call is not None:
            self._on_call(state, self)

        result = self.script.get(key, self.default_result)  # type: ignore[arg-type]
        return result

    @property
    def phases_called(self) -> list[Phase | None]:
        """Return just the phase component of every invocation."""
        return [inv[2] for inv in self.invocations]

    @property
    def compass_history(self) -> list[str | None]:
        """Return the compass value passed to each invocation."""
        return list(self.compass_values)


# =============================================================================
# Mock project fixture factory (Task 1.3)
# =============================================================================


@dataclass
class MockProject:
    """Container for a minimal BMAD project created in tmp_path."""

    project_path: Path
    epic_list: list[EpicId]
    epic_stories_loader: Any  # Callable[[EpicId], list[str]]
    stories_by_epic: dict[EpicId, list[str]] = field(default_factory=dict)


def create_mock_project(
    tmp_path: Path,
    epics: list[dict[str, Any]],
) -> MockProject:
    """Create a minimal BMAD project directory for E2E testing.

    Args:
        tmp_path: Temporary directory for the project.
        epics: List of ``{"id": <int|str>, "stories": [<str>, ...]}`` dicts.

    Returns:
        MockProject with project_path, epic_list, and epic_stories_loader.
    """
    project_path = tmp_path / "project"
    project_path.mkdir(exist_ok=True)

    # Create minimal directory structure
    bmad_dir = project_path / ".bmad-assist"
    bmad_dir.mkdir(exist_ok=True)

    docs_dir = project_path / "bmad-docs"
    docs_dir.mkdir(exist_ok=True)

    # Create minimal config file
    config_yaml = project_path / "bmad-assist.yaml"
    config_yaml.write_text(
        "providers:\n  master:\n    provider: claude\n    model: opus\n"
    )

    # Build epic list and stories mapping
    epic_list: list[EpicId] = []
    stories_by_epic: dict[EpicId, list[str]] = {}

    lines = ["# Epics\n"]
    for epic_cfg in epics:
        eid = epic_cfg["id"]
        stories = epic_cfg.get("stories", [])
        epic_list.append(eid)
        stories_by_epic[eid] = list(stories)
        lines.append(f"\n## Epic {eid}\n")
        for sid in stories:
            lines.append(f"- Story {sid}\n")

    epics_md = docs_dir / "epics.md"
    epics_md.write_text("".join(lines))

    def epic_stories_loader(epic: EpicId) -> list[str]:
        return stories_by_epic.get(epic, [])

    return MockProject(
        project_path=project_path,
        epic_list=epic_list,
        epic_stories_loader=epic_stories_loader,
        stories_by_epic=stories_by_epic,
    )


# =============================================================================
# Config factory (Task 1.4)
# =============================================================================


def create_e2e_config(
    *,
    qa_enabled: bool = False,
    tea_enabled: bool = False,
    twin_enabled: bool = False,
    twin_overrides: dict[str, Any] | None = None,
) -> Config:
    """Create a minimal Config suitable for mock E2E tests.

    The config is loaded into the singleton so ``get_config()`` works during the run.
    """
    from bmad_assist.core.config import _reset_config

    config_data: dict[str, Any] = {
        "providers": {
            "master": {
                "provider": "claude",
                "model": "mock",
            }
        },
        "timeout": 10,
    }

    if tea_enabled:
        config_data["testarch"] = {
            "engagement_model": "auto",
        }

    if qa_enabled:
        config_data["qa"] = {
            "enabled": True,
        }

    if twin_enabled:
        twin_data: dict[str, Any] = {
            "provider": "claude",
            "model": "mock",
            "enabled": True,
        }
        if twin_overrides:
            twin_data.update(twin_overrides)
        config_data["providers"]["twin"] = twin_data

    _reset_config()
    return load_config(config_data)


# =============================================================================
# Run-mock-loop harness (Task 1.5)
# =============================================================================


@dataclass
class MockLoopResult:
    """Container for the result of run_mock_loop()."""

    exit_reason: LoopExitReason
    final_state: State
    invocations: list[tuple[EpicId | None, str | None, Phase | None]]


def run_mock_loop(
    project: MockProject,
    executor: ScriptedPhaseExecutor,
    *,
    config: Config | None = None,
    initial_state: State | None = None,
    epic_list: list[EpicId] | None = None,
    epic_stories_loader: Any = None,
    cancel_ctx: Any = None,
    qa_enabled: bool = False,
    tea_enabled: bool = False,
    stop_after_epic: EpicId | None = None,
    start_epic: EpicId | None = None,
    start_story: str | None = None,
) -> MockLoopResult:
    """Wrap ``run_loop()`` with mock-friendly defaults for E2E testing.

    Patches execute_phase in BOTH runner and epic_phases modules,
    suppresses signal handlers/IPC, uses plain rendering.

    Returns MockLoopResult with exit_reason, final_state, and invocations.
    """
    import os

    from bmad_assist.core.config import load_loop_config, set_loop_config
    from bmad_assist.core.config.loop_config import _reset_loop_config
    from bmad_assist.core.loop.runner import run_loop
    from bmad_assist.core.state import load_state, save_state

    if config is None:
        config = create_e2e_config(qa_enabled=qa_enabled, tea_enabled=tea_enabled)

    elist = epic_list if epic_list is not None else project.epic_list
    loader = epic_stories_loader if epic_stories_loader is not None else project.epic_stories_loader

    # Handle --epic flag (filter epic_list)
    if start_epic is not None:
        elist = [e for e in elist if e == start_epic]

    # Handle --stop-after-epic flag (trim epic_list)
    if stop_after_epic is not None:
        trimmed: list[EpicId] = []
        for e in elist:
            trimmed.append(e)
            if e == stop_after_epic:
                break
        elist = trimmed

    # Handle --story flag (adjust stories loader to skip earlier stories)
    if start_story is not None:
        original_loader = loader

        def filtered_loader(epic: EpicId) -> list[str]:
            stories = original_loader(epic)
            if start_story in stories:
                idx = stories.index(start_story)
                return stories[idx:]
            return stories

        loader = filtered_loader

    # Set up QA env var
    old_qa = os.environ.get("BMAD_QA_ENABLED")
    if qa_enabled:
        os.environ["BMAD_QA_ENABLED"] = "1"
    else:
        os.environ.pop("BMAD_QA_ENABLED", None)

    # State capture reference
    captured_state: list[State] = []
    state_path_ref: list[Path] = []

    real_save_state = save_state

    def capturing_save_state(state: State, path: Path) -> None:
        captured_state.clear()
        captured_state.append(state)
        state_path_ref.clear()
        state_path_ref.append(path)
        real_save_state(state, path)

    real_load_state = load_state

    def maybe_initial_state(path: Path) -> State:
        if initial_state is not None:
            return initial_state
        return real_load_state(path)

    # _validate_resume_against_sprint receives (state, project_path, epic_list,
    # epic_stories_loader, state_path) and returns (state, is_project_complete).
    # We must pass through the state argument (arg[0]) so the fresh-start
    # initialisation done inside _run_loop_body is not overwritten.
    def _passthrough_validate(*args: Any, **kwargs: Any) -> tuple[State, bool]:
        return (args[0], False)

    try:
        with (
            patch("bmad_assist.core.loop.runner.execute_phase", side_effect=executor),
            patch("bmad_assist.core.loop.epic_phases.execute_phase", side_effect=executor),
            patch("bmad_assist.core.loop.runner.save_state", side_effect=capturing_save_state),
            patch("bmad_assist.core.loop.runner.load_state", side_effect=maybe_initial_state),
            patch("bmad_assist.core.loop.epic_phases.save_state", side_effect=capturing_save_state),
            patch("bmad_assist.core.loop.story_transitions.save_state", side_effect=capturing_save_state),
            patch("bmad_assist.core.loop.epic_transitions.save_state", side_effect=capturing_save_state),
            patch("bmad_assist.core.loop.runner._validate_resume_against_sprint", side_effect=_passthrough_validate),
            patch("bmad_assist.core.loop.runner._trigger_interactive_repair"),
            patch("bmad_assist.core.loop.runner._invoke_sprint_sync"),
            patch("bmad_assist.core.loop.runner._save_effective_config"),
            patch("bmad_assist.core.loop.runner.save_run_log"),
            patch("bmad_assist.core.loop.runner.checkpoint_and_prompt", return_value=True),
            patch("bmad_assist.core.loop.runner._run_archive_artifacts"),
            patch("bmad_assist.git.branch.is_git_enabled", return_value=False),
            patch("bmad_assist.core.loop.runner.is_skip_story_prompts", return_value=True),
        ):
            exit_reason = run_loop(
                config,
                project.project_path,
                elist,
                loader,
                cancel_ctx=cancel_ctx,
                skip_signal_handlers=True,
                ipc_enabled=False,
                plain=True,
            )
    finally:
        # Restore QA env var
        if old_qa is not None:
            os.environ["BMAD_QA_ENABLED"] = old_qa
        else:
            os.environ.pop("BMAD_QA_ENABLED", None)

    final_state = captured_state[-1] if captured_state else State()

    return MockLoopResult(
        exit_reason=exit_reason,
        final_state=final_state,
        invocations=executor.invocations,
    )


# =============================================================================
# Assertion helpers (Task 1.6)
# =============================================================================


def assert_stories_completed(state: State, expected: list[str]) -> None:
    """Assert that state.completed_stories contains exactly the expected story IDs."""
    actual = sorted(state.completed_stories)
    exp = sorted(expected)
    assert actual == exp, f"completed_stories mismatch:\n  actual:   {actual}\n  expected: {exp}"


def assert_epics_completed(state: State, expected: list[EpicId]) -> None:
    """Assert that state.completed_epics contains exactly the expected epic IDs."""
    actual = sorted(state.completed_epics, key=str)
    exp = sorted(expected, key=str)
    assert actual == exp, f"completed_epics mismatch:\n  actual:   {actual}\n  expected: {exp}"


def assert_phase_order(executor: ScriptedPhaseExecutor, expected_phases: list[Phase]) -> None:
    """Assert that the executor's phase invocations match the expected order."""
    actual = executor.phases_called
    assert actual == expected_phases, (
        f"Phase order mismatch:\n"
        f"  actual:   {[p.name if p else None for p in actual]}\n"
        f"  expected: {[p.name for p in expected_phases]}"
    )


def assert_invocation_order(
    executor: ScriptedPhaseExecutor,
    expected: list[tuple[EpicId, str, Phase]],
) -> None:
    """Assert the full (epic, story, phase) invocation order."""
    actual = executor.invocations
    assert actual == expected, (
        f"Invocation order mismatch:\n"
        f"  actual:   {actual}\n"
        f"  expected: {expected}"
    )
