"""ExecutionRecord for the Digital Twin.

Captures the full outcome of a single phase execution for consumption
by the Twin reflect step.
"""

from __future__ import annotations

import logging
import re
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

__all__ = [
    "ExecutionRecord",
    "build_execution_record",
    "format_self_audit",
]


@dataclass
class ExecutionRecord:
    """Full outcome of a single phase execution for Twin reflect.

    Attributes:
        phase: The atomic phase name that was executed.
        mission: The mission/prompt that was sent to the LLM.
        llm_output: The raw LLM response text (NOT truncated by default).
        self_audit: Parsed Self-Audit section from llm_output, or None.
        success: Whether the phase completed without error.
        duration_ms: Wall-clock execution time in milliseconds.
        error: Error message if the phase failed, otherwise None.
        phase_outputs: Structured outputs produced by the phase.
        files_modified: List of file paths changed during this phase.
        files_diff: Full git diff output for Twin cross-validation.
    """

    phase: str
    mission: str
    llm_output: str
    self_audit: str | None
    success: bool
    duration_ms: int
    error: str | None
    phase_outputs: dict[str, Any] = field(default_factory=dict)
    files_modified: list[str] = field(default_factory=list)
    files_diff: str = ""


# ---------------------------------------------------------------------------
# format_self_audit: Task 3.3
# ---------------------------------------------------------------------------

_SELF_AUDIT_RE = re.compile(
    r"^## (?:Execution )?Self[- ]Audit\s*\n(.*?)(?=^## |\Z)",
    re.MULTILINE | re.DOTALL,
)


def format_self_audit(llm_output: str) -> str | None:
    """Extract and parse the Self-Audit section from raw LLM output.

    Scans for a Self-Audit section demarcated by a ## heading pattern.
    Returns the full text of the section, or None if not found.
    """
    if not llm_output:
        return None

    match = _SELF_AUDIT_RE.search(llm_output)
    if match:
        return match.group(1).strip()

    return None


# ---------------------------------------------------------------------------
# build_execution_record: Task 3.2
# ---------------------------------------------------------------------------


def build_execution_record(
    phase: str,
    mission: str,
    llm_output: str,
    success: bool,
    duration_ms: int,
    error: str | None = None,
    phase_outputs: dict[str, Any] | None = None,
    project_path: Path | None = None,
) -> ExecutionRecord:
    """Construct an ExecutionRecord from phase execution state and result.

    Captures git diff for files_modified and files_diff if project_path
    is provided. Does NOT truncate llm_output — truncation is handled
    separately by prepare_llm_output.

    Args:
        phase: Phase name that was executed.
        mission: The mission/prompt sent to the LLM.
        llm_output: Raw LLM response text.
        success: Whether the phase completed without error.
        duration_ms: Wall-clock execution time in milliseconds.
        error: Error message if failed, else None.
        phase_outputs: Structured outputs from the phase.
        project_path: Project root for git diff capture.

    Returns:
        Populated ExecutionRecord.
    """
    self_audit = format_self_audit(llm_output)

    files_modified: list[str] = []
    files_diff = ""

    if project_path is not None and success:
        files_modified, files_diff = _capture_git_diff(project_path)

    return ExecutionRecord(
        phase=phase,
        mission=mission,
        llm_output=llm_output,
        self_audit=self_audit,
        success=success,
        duration_ms=duration_ms,
        error=error,
        phase_outputs=phase_outputs or {},
        files_modified=files_modified,
        files_diff=files_diff,
    )


def _capture_git_diff(project_path: Path) -> tuple[list[str], str]:
    """Capture git diff (full) and name-only list for current changes.

    Returns (files_modified, files_diff) tuple.
    """
    try:
        # Get full diff
        diff_result = subprocess.run(
            ["git", "diff"],
            cwd=str(project_path),
            capture_output=True,
            text=True,
            timeout=30,
        )
        files_diff = diff_result.stdout

        # Get name-only list
        name_result = subprocess.run(
            ["git", "diff", "--name-only"],
            cwd=str(project_path),
            capture_output=True,
            text=True,
            timeout=10,
        )
        files_modified = [
            line.strip() for line in name_result.stdout.strip().split("\n") if line.strip()
        ]

        return files_modified, files_diff

    except (subprocess.TimeoutExpired, FileNotFoundError, OSError) as e:
        logger.warning("Failed to capture git diff: %s", e)
        return [], ""
