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

    Captures changed files via git status --porcelain if project_path
    is provided and success=True. Does NOT truncate llm_output —
    truncation is handled separately by prepare_llm_output.

    Args:
        phase: Phase name that was executed.
        mission: The mission/prompt sent to the LLM.
        llm_output: Raw LLM response text.
        success: Whether the phase completed without error.
        duration_ms: Wall-clock execution time in milliseconds.
        error: Error message if failed, else None.
        phase_outputs: Structured outputs from the phase.
        project_path: Project root for git status capture.

    Returns:
        Populated ExecutionRecord.
    """
    self_audit = format_self_audit(llm_output)

    files_modified: list[str] = []

    if project_path is not None and success:
        files_modified = _capture_files_modified(project_path)

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
    )


def _capture_files_modified(project_path: Path) -> list[str]:
    """Capture all changed file paths using git status --porcelain.

    Covers tracked modifications, staged changes, and untracked new files.
    Strips the XY status prefix; only the file path is stored.
    Handles renames (takes new path) and quoted filenames.

    Returns:
        List of file paths relative to project root.
    """
    try:
        result = subprocess.run(
            ["git", "status", "--porcelain"],
            cwd=str(project_path),
            capture_output=True,
            text=True,
            timeout=10,
        )
        files: list[str] = []
        for line in result.stdout.rstrip().split("\n"):
            if not line.strip():
                continue
            # XY status prefix is 2 chars + space; handle rename format "XY old -> new"
            entry = line[3:]  # strip "XY "
            if " -> " in entry:
                # Rename: take the new path
                entry = entry.split(" -> ", 1)[1]
            # Strip surrounding quotes if present
            entry = entry.strip().strip('"')
            if entry:
                files.append(entry)
        return files

    except (subprocess.TimeoutExpired, FileNotFoundError, OSError) as e:
        logger.warning("Failed to capture git status: %s", e)
        return []
