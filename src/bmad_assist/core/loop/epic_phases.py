"""Epic-scope phase execution (setup and teardown).

Per ADR-007: Epic setup phases run before first story.
Per ADR-002: Epic teardown phases continue on failure.
Extracted from runner.py as part of the runner refactoring.

"""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Literal

from bmad_assist.core.loop.dispatch import execute_phase, resolve_twin_provider
from bmad_assist.core.loop.helpers import _print_phase_banner
from bmad_assist.core.loop.notifications import _dispatch_event
from bmad_assist.core.loop.types import PhaseResult
from bmad_assist.core.state import (
    Phase,
    State,
    get_phase_duration_ms,
    save_state,
    start_phase_timing,
)

if TYPE_CHECKING:
    from bmad_assist.core.config import Config

logger = logging.getLogger(__name__)

__all__ = ["_execute_epic_setup", "_execute_epic_teardown"]

# Type alias for state parameter
LoopState = State


def _execute_phase_with_twin(
    state: LoopState,
    config: Config,
    project_path: Path,
    retry_exhausted_action: Literal["halt", "continue"] = "halt",
) -> PhaseResult:
    """Execute a phase with Twin guide → execute → reflect → retry cycle.

    Encapsulates the Twin orchestration for epic setup/teardown phases.
    On Twin RETRY, git stash is used to roll back working directory changes
    before re-executing the phase with a correction compass.

    Args:
        state: Current loop state.
        config: Application configuration (for Twin provider access).
        project_path: Project root directory.
        retry_exhausted_action: "halt" → return failed result on retry exhaustion,
            "continue" → return the last retry result.

    Returns:
        PhaseResult from the final execution attempt.

    """
    # --- Twin Guide ---
    compass: str | None = None
    _twin_instance = None
    twin_config = config.providers.twin

    if twin_config.enabled:
        try:
            from bmad_assist.twin.twin import Twin
            from bmad_assist.twin.wiki import init_wiki

            wiki_dir = init_wiki(project_path)
            twin_provider = resolve_twin_provider(config)
            twin_instance = Twin(config=twin_config, wiki_dir=wiki_dir, provider=twin_provider)
            phase_type = state.current_phase.value if state.current_phase else ""
            compass = twin_instance.guide(phase_type)
            if compass:
                logger.info("Twin guide produced compass for phase %s (%d chars)",
                            phase_type, len(compass))
            _twin_instance = twin_instance
        except Exception as e:
            logger.warning("Twin guide failed, proceeding without compass: %s: %s", type(e).__name__, e)
            compass = None
            _twin_instance = None

    # --- Execute Phase ---
    result = execute_phase(state, compass=compass)

    # If phase failed or Twin is disabled, return immediately
    if not result.success or _twin_instance is None:
        return result

    # --- Twin Reflect ---
    try:
        from bmad_assist.twin.execution_record import build_execution_record
        from bmad_assist.twin.twin import apply_page_updates

        epic_id = state.current_epic
        phase_name = state.current_phase.value if state.current_phase else ""
        mission = result.outputs.get("response", "")
        duration_ms = result.outputs.get("duration_ms", 0)

        record = build_execution_record(
            phase=phase_name,
            mission=mission,
            llm_output=result.outputs.get("response", ""),
            success=result.success,
            duration_ms=duration_ms if isinstance(duration_ms, int) else 0,
            error=result.error,
            phase_outputs=result.outputs,
            project_path=project_path,
        )

        twin_result = _twin_instance.reflect(record, is_retry=False, epic_id=epic_id)

        # Apply page updates
        if twin_result.page_updates:
            apply_page_updates(
                twin_result.page_updates,
                _twin_instance.wiki_dir,
                epic_id=epic_id or "",
            )

        # Handle Twin decision
        if twin_result.decision == "halt":
            # Mark the result so callers can distinguish Twin halt from phase failure
            logger.warning("Twin HALT: %s", twin_result.rationale)
            return PhaseResult.fail(f"Twin HALT: {twin_result.rationale}")
        elif twin_result.decision == "retry":
            retry_count = 0
            max_retries = _twin_instance.config.max_retries
            original_compass = compass

            while retry_count < max_retries:
                # Git stash to restore working directory before RETRY
                try:
                    from bmad_assist.git import stash_working_changes

                    stash_working_changes(project_path)
                except Exception as e:
                    logger.warning("Git stash failed before RETRY: %s", e)

                # Format correction compass
                correction = ""
                if twin_result.drift_assessment and twin_result.drift_assessment.correction:
                    correction = twin_result.drift_assessment.correction

                retry_count += 1
                correction_compass = f"[RETRY retry={retry_count}] {correction}"
                # Append correction to original compass (not replace)
                full_compass = (original_compass or "") + "\n" + correction_compass

                logger.info(
                    "Twin RETRY %d/%d for phase %s: %s",
                    retry_count, max_retries, phase_name, correction[:100],
                )

                # Re-execute phase with correction compass
                retry_result = execute_phase(state, compass=full_compass)

                if not retry_result.success:
                    logger.warning("RETRY phase execution failed: %s", retry_result.error)
                    break

                # Reflect on retry result
                retry_record = build_execution_record(
                    phase=phase_name,
                    mission=mission,
                    llm_output=retry_result.outputs.get("response", ""),
                    success=retry_result.success,
                    duration_ms=retry_result.outputs.get("duration_ms", 0) if isinstance(retry_result.outputs.get("duration_ms", 0), int) else 0,
                    error=retry_result.error,
                    phase_outputs=retry_result.outputs,
                    project_path=project_path,
                )

                retry_twin_result = _twin_instance.reflect(
                    retry_record, is_retry=True, epic_id=epic_id,
                )

                if retry_twin_result.page_updates:
                    apply_page_updates(
                        retry_twin_result.page_updates,
                        _twin_instance.wiki_dir,
                        epic_id=epic_id or "",
                    )

                if retry_twin_result.decision == "continue":
                    logger.info("Twin RETRY successful after %d attempts", retry_count)
                    result = retry_result
                    break
                elif retry_twin_result.decision == "halt":
                    logger.warning("Twin HALT after RETRY: %s", retry_twin_result.rationale)
                    return PhaseResult.fail(f"Twin HALT after RETRY: {retry_twin_result.rationale}")
                elif retry_twin_result.decision == "retry":
                    twin_result = retry_twin_result
                    if retry_twin_result.drift_assessment and retry_twin_result.drift_assessment.correction:
                        correction = retry_twin_result.drift_assessment.correction
                    continue
            else:
                # Retries exhausted
                logger.error(
                    "Twin RETRY exhausted (%d/%d): %s",
                    retry_count, max_retries, twin_result.rationale,
                )
                if retry_exhausted_action == "halt":
                    return PhaseResult.fail(f"Twin RETRY exhausted: {twin_result.rationale}")
                # else continue with the last retry result
                result = retry_result
    except Exception as e:
        logger.warning("Twin reflect failed, proceeding: %s: %s", type(e).__name__, e)

    return result


def _execute_epic_setup(
    state: LoopState,
    state_path: Path,
    project_path: Path,
    config: Config,
) -> tuple[LoopState, bool]:
    """Execute epic setup phases before first story.

    Iterates through all phases in loop_config.epic_setup and executes each.
    On failure, returns immediately with success=False (loop should HALT).
    On success, sets epic_setup_complete=True and persists state.

    Per ADR-007: If resuming after a crash during setup, this function will
    re-run ALL setup phases from the beginning (setup phases must be idempotent).

    Args:
        state: Current loop state.
        state_path: Path to state file for persistence.
        project_path: Project root directory.
        config: Application configuration (for Twin provider access).

    Returns:
        Tuple of (updated_state, success).
        - success=True: All setup phases completed, epic_setup_complete=True
        - success=False: A setup phase failed, loop should halt with GUARDIAN_HALT

    """
    from bmad_assist.core.config import get_loop_config

    loop_config = get_loop_config()

    if not loop_config.epic_setup:
        # No setup phases configured - nothing to do
        logger.debug("No epic_setup phases configured, skipping")
        return state, True

    logger.info(
        "Running %d epic setup phases for epic %s: %s",
        len(loop_config.epic_setup),
        state.current_epic,
        loop_config.epic_setup,
    )

    for phase_name in loop_config.epic_setup:
        # Set current phase for this setup phase
        now = datetime.now(UTC).replace(tzinfo=None)
        state = state.model_copy(
            update={
                "current_phase": Phase(phase_name),
                "updated_at": now,
            }
        )
        # Reset phase timing before execution (consistent with main loop)
        start_phase_timing(state)
        save_state(state, state_path)

        # CLI Observability: Print phase banner (visible regardless of log level)
        _print_phase_banner(
            phase=phase_name,
            epic=state.current_epic,
            story=None,  # Epic setup phases don't have a story
        )

        # Execute the setup phase with Twin orchestration
        logger.info("Executing epic setup phase: %s", phase_name)
        result = _execute_phase_with_twin(
            state, config, project_path, retry_exhausted_action="halt",
        )

        # Dispatch phase_completed notification (regardless of success/failure)
        phase_duration = get_phase_duration_ms(state)
        _dispatch_event(
            "phase_completed",
            project_path,
            state,
            phase=phase_name,
            duration_ms=phase_duration,
        )

        if not result.success:
            # Setup failure or Twin halt - halt the loop (per ADR-001)
            logger.error(
                "Epic setup phase %s failed for epic %s: %s",
                phase_name,
                state.current_epic,
                result.error,
            )
            # Save state with failed phase for resume
            save_state(state, state_path)
            return state, False

        logger.info("Epic setup phase %s completed successfully", phase_name)

        # Git auto-commit for the completed setup phase
        from bmad_assist.git import auto_commit_phase

        auto_commit_phase(
            phase=state.current_phase,
            story_id=state.current_story or str(state.current_epic),
            project_path=project_path,
        )

    # All setup phases completed successfully - set to first story phase from config
    first_story_phase = Phase(loop_config.story[0])
    now = datetime.now(UTC).replace(tzinfo=None)
    state = state.model_copy(
        update={
            "epic_setup_complete": True,
            "current_phase": first_story_phase,  # Ready for first story phase
            "updated_at": now,
        }
    )
    save_state(state, state_path)

    logger.info(
        "Epic setup complete for epic %s, ready for %s",
        state.current_epic,
        first_story_phase.name,
    )
    return state, True


def _execute_epic_teardown(
    state: LoopState,
    state_path: Path,
    project_path: Path,
    config: Config,
) -> tuple[LoopState, PhaseResult | None]:
    """Execute epic teardown phases after last story.

    Iterates through all phases in loop_config.epic_teardown and executes each.
    On failure, logs warning and CONTINUES to next phase (per ADR-002).
    Returns the last PhaseResult for metrics/logging purposes.

    Args:
        state: Current loop state after last story's CODE_REVIEW_SYNTHESIS.
        state_path: Path to state file for persistence.
        project_path: Project root directory.
        config: Application configuration (for Twin provider access).

    Returns:
        Tuple of (updated_state, last_result).
        - last_result: PhaseResult from the last executed phase (for metrics)
        - last_result is None if epic_teardown is empty

    """
    from bmad_assist.core.config import get_loop_config

    loop_config = get_loop_config()

    if not loop_config.epic_teardown:
        # No teardown phases configured - nothing to do
        logger.debug("No epic_teardown phases configured, skipping")
        return state, None

    logger.info(
        "Running %d epic teardown phases for epic %s: %s",
        len(loop_config.epic_teardown),
        state.current_epic,
        loop_config.epic_teardown,
    )

    last_result: PhaseResult | None = None

    for phase_name in loop_config.epic_teardown:
        # Set current phase for this teardown phase
        now = datetime.now(UTC).replace(tzinfo=None)
        state = state.model_copy(
            update={
                "current_phase": Phase(phase_name),
                "updated_at": now,
            }
        )
        # Reset phase timing before execution (consistent with main loop)
        start_phase_timing(state)
        save_state(state, state_path)

        # CLI Observability: Print phase banner (visible regardless of log level)
        _print_phase_banner(
            phase=phase_name,
            epic=state.current_epic,
            story=None,  # Epic teardown phases don't have a story
        )

        # Execute the teardown phase with Twin orchestration
        logger.info("Executing epic teardown phase: %s", phase_name)
        result = _execute_phase_with_twin(
            state, config, project_path, retry_exhausted_action="continue",
        )
        last_result = result

        # Dispatch phase_completed notification (regardless of success/failure)
        phase_duration = get_phase_duration_ms(state)
        _dispatch_event(
            "phase_completed",
            project_path,
            state,
            phase=phase_name,
            duration_ms=phase_duration,
        )

        if not result.success:
            # Teardown failure or Twin halt - log warning and CONTINUE (per ADR-002)
            # Twin halt in teardown is also treated as a warning, not a loop-stopper
            if result.error and "Twin HALT" in result.error:
                logger.warning(
                    "Twin HALT during epic teardown phase %s for epic %s: %s. "
                    "Continuing to next teardown phase (ADR-002 takes priority).",
                    phase_name,
                    state.current_epic,
                    result.error,
                )
            else:
                logger.warning(
                    "Epic teardown phase %s failed for epic %s: %s. Continuing to next teardown phase.",
                    phase_name,
                    state.current_epic,
                    result.error,
                )
            # Still save state even on failure
            save_state(state, state_path)
            continue

        logger.info("Epic teardown phase %s completed successfully", phase_name)

        # Git auto-commit for the completed teardown phase
        from bmad_assist.git import auto_commit_phase

        auto_commit_phase(
            phase=state.current_phase,
            story_id=state.current_story or str(state.current_epic),
            project_path=project_path,
        )

    logger.info("Epic teardown complete for epic %s", state.current_epic)
    return state, last_result
