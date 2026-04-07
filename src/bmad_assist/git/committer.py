"""Git commit automation for bmad-assist phases.

Handles automatic commits after successful phase execution.
"""

import logging
import os
import subprocess
from pathlib import Path

from bmad_assist.core.state import Phase

logger = logging.getLogger(__name__)

# Phase to conventional commit type mapping (all phases)
PHASE_COMMIT_TYPES: dict[Phase, str] = {
    Phase.CREATE_STORY: "docs",
    Phase.VALIDATE_STORY: "test",
    Phase.VALIDATE_STORY_SYNTHESIS: "test",
    Phase.ATDD: "test",
    Phase.DEV_STORY: "feat",
    Phase.CODE_REVIEW: "test",
    Phase.CODE_REVIEW_SYNTHESIS: "refactor",
    Phase.TEST_REVIEW: "test",
    Phase.TRACE: "test",
    Phase.TEA_FRAMEWORK: "test",
    Phase.TEA_CI: "test",
    Phase.TEA_TEST_DESIGN: "test",
    Phase.TEA_AUTOMATE: "test",
    Phase.TEA_NFR_ASSESS: "test",
    Phase.RETROSPECTIVE: "chore",
    Phase.QA_PLAN_GENERATE: "ci",
    Phase.QA_PLAN_EXECUTE: "ci",
    Phase.QA_REMEDIATE: "ci",
}


def is_git_enabled() -> bool:
    """Check if git auto-commit is enabled via environment variable."""
    return os.environ.get("BMAD_GIT_COMMIT") == "1"


def _run_git(args: list[str], cwd: Path) -> tuple[int, str, str]:
    """Run a git command and return exit code, stdout, stderr.

    Args:
        args: Git command arguments (without 'git' prefix).
        cwd: Working directory for git command.

    Returns:
        Tuple of (exit_code, stdout, stderr).

    """
    try:
        result = subprocess.run(
            ["git", *args],
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=30,
        )
        return result.returncode, result.stdout, result.stderr
    except subprocess.TimeoutExpired:
        return 1, "", "Git command timed out"
    except FileNotFoundError:
        return 1, "", "Git not found in PATH"


def get_modified_files(project_path: Path) -> list[str]:
    """Get list of modified files in the repository.

    Returns both staged and unstaged changes, EXCLUDING output directories
    that contain generated artifacts (validation reports, benchmarks, etc.).

    Args:
        project_path: Path to git repository.

    Returns:
        List of modified file paths relative to repo root.

    """
    # Get both staged and unstaged changes
    exit_code, stdout, _ = _run_git(
        ["status", "--porcelain", "-uall"],
        project_path,
    )

    if exit_code != 0:
        return []

    # Directories to exclude from auto-commit (ephemeral artifacts only)
    exclude_prefixes = (
        ".bmad-assist/prompts/",
        ".bmad-assist/cache/",
        ".bmad-assist/debug/",
    )

    files = []
    for line in stdout.strip().split("\n"):
        if line:
            # porcelain format: XY filename
            # Skip the status prefix (2 chars + space)
            filename = line[3:].strip()
            # Handle renamed files (old -> new)
            if " -> " in filename:
                filename = filename.split(" -> ")[1]

            # Skip files in excluded directories
            if any(filename.startswith(prefix) for prefix in exclude_prefixes):
                continue

            files.append(filename)

    return files


def check_for_deleted_story_files(project_path: Path) -> list[str]:
    """Check if any story files are marked for deletion.

    Story files are critical artifacts that should never be auto-deleted.
    This function detects deleted story files before they get committed.

    Args:
        project_path: Path to git repository.

    Returns:
        List of deleted story file paths. Empty if none found.

    """
    exit_code, stdout, _ = _run_git(
        ["status", "--porcelain", "-uall"],
        project_path,
    )

    if exit_code != 0:
        return []

    import re

    deleted_files = []

    for line in stdout.strip().split("\n"):
        if not line:
            continue

        # porcelain format: XY filename
        # X = staged status, Y = unstaged status
        # D in either position means deleted
        status = line[:2]
        filename = line[3:].strip()
        if " -> " in filename:
            filename = filename.split(" -> ")[1]

        # Check if file is deleted (D in staged or unstaged status)
        if "D" not in status:
            continue

        # Check if it's a story file: docs/sprint-artifacts/{epic}-{story}-{slug}.md
        # or stories/{epic}-{story}-{slug}.md
        story_pattern = re.compile(r"^(docs/sprint-artifacts/|stories/)?\d+-\d+-[\w-]+\.md$")
        if story_pattern.match(filename):
            deleted_files.append(filename)

    return deleted_files


def _categorize_files(modified_files: list[str]) -> dict[str, list[str]]:
    """Group modified files by type category.

    Categories:
    - source: .ts, .tsx, .js, .jsx, .py files
    - reports: .md files in _bmad-output/ or docs/
    - tests: files matching test* or spec* patterns
    - config: everything else

    Args:
        modified_files: List of file paths relative to repo root.

    Returns:
        Dict mapping category name to list of file paths.

    """
    import os.path

    categories: dict[str, list[str]] = {
        "source": [],
        "reports": [],
        "tests": [],
        "config": [],
    }

    source_extensions = {".ts", ".tsx", ".js", ".jsx", ".py"}

    for filepath in modified_files:
        basename = os.path.basename(filepath)
        _, ext = os.path.splitext(basename)

        # Test files (by name pattern)
        if basename.startswith(("test", "spec")) or basename.startswith(("test_", "spec_")):
            categories["tests"].append(filepath)
        # Reports/docs (.md in _bmad-output/ or docs/)
        elif ext == ".md" and (filepath.startswith("_bmad-output/") or filepath.startswith("docs/")):
            categories["reports"].append(filepath)
        # Source code
        elif ext in source_extensions:
            categories["source"].append(filepath)
        # Everything else
        else:
            categories["config"].append(filepath)

    return categories


def _summarize_changes(modified_files: list[str]) -> str:
    """Produce a human-readable summary from categorized files.

    Args:
        modified_files: List of file paths relative to repo root.

    Returns:
        Summary string (e.g., "update source code in src/app/, add report").

    """
    if not modified_files:
        return "no changes"

    categories = _categorize_files(modified_files)
    parts: list[str] = []

    if categories["source"]:
        # Get unique top-level directories for source files
        dirs = sorted({f.split("/")[0] + "/" for f in categories["source"] if "/" in f})
        if dirs:
            parts.append(f"update source code in {', '.join(dirs[:3])}")
        else:
            parts.append("update source code")

    if categories["reports"]:
        count = len(categories["reports"])
        if count == 1:
            parts.append("add report")
        else:
            parts.append(f"add {count} reports")

    if categories["tests"]:
        count = len(categories["tests"])
        if count == 1:
            parts.append("update test file")
        else:
            parts.append(f"update {count} test files")

    if categories["config"]:
        count = len(categories["config"])
        if count == 1:
            parts.append("update configuration")
        else:
            parts.append(f"update {count} config files")

    return ", ".join(parts) if parts else "update files"


def generate_commit_message(
    phase: Phase,
    story_id: str | None,
    modified_files: list[str],
) -> str:
    """Generate deterministic conventional commit message for the phase.

    Args:
        phase: The completed phase.
        story_id: Current story ID (e.g., "1.2").
        modified_files: List of files that were modified.

    Returns:
        Commit message string.

    """
    return _generate_conventional_message(phase, story_id, modified_files)


def _generate_conventional_message(
    phase: Phase,
    story_id: str | None,
    modified_files: list[str],
) -> str:
    """Generate conventional commit message with dynamic summary.

    Format: <type>(<scope>): <phase_name> — <dynamic_summary>

    Args:
        phase: The completed phase.
        story_id: Current story ID.
        modified_files: List of modified files.

    Returns:
        Conventional commit message.

    """
    commit_type = PHASE_COMMIT_TYPES.get(phase, "chore")

    # Determine scope
    # Epic-level phases use epic-based scope; story-level phases use story-based scope
    epic_phases = {
        Phase.RETROSPECTIVE,
        Phase.QA_PLAN_GENERATE,
        Phase.QA_PLAN_EXECUTE,
        Phase.QA_REMEDIATE,
        Phase.TEA_FRAMEWORK,
        Phase.TEA_CI,
        Phase.TEA_NFR_ASSESS,
    }

    if phase in epic_phases:
        epic_id = (
            story_id.split(".")[0] if story_id and "." in story_id else (story_id or "unknown")
        )
        scope = f"epic-{epic_id}"
    else:
        scope = f"story-{story_id}" if story_id else "bmad"

    # Dynamic description from changed files
    phase_label = phase.value.replace("_", " ")
    summary = _summarize_changes(modified_files)
    description = f"{phase_label} \u2014 {summary}"

    subject = f"{commit_type}({scope}): {description}"

    # Truncate subject line to 72 characters
    if len(subject) > 72:
        subject = subject[:69] + "..."

    message = subject

    # Add commit body with directory grouping when >3 files changed
    if len(modified_files) > 3:
        dir_counts: dict[str, int] = {}
        for f in modified_files:
            top_dir = f.split("/")[0] + "/" if "/" in f else f
            dir_counts[top_dir] = dir_counts.get(top_dir, 0) + 1

        body_lines = [f"{d}: {c} file{'s' if c > 1 else ''}" for d, c in sorted(dir_counts.items())]
        message += "\n\n" + ", ".join(body_lines)

    return message


def stage_all_changes(project_path: Path) -> bool:
    """Stage all modified files for commit.

    Args:
        project_path: Path to git repository.

    Returns:
        True if staging succeeded.

    """
    exit_code, _, stderr = _run_git(["add", "-A"], project_path)
    if exit_code != 0:
        logger.error("Failed to stage changes: %s", stderr)
        return False
    return True


def commit_changes(project_path: Path, message: str) -> bool:
    """Create a git commit with the given message.

    Args:
        project_path: Path to git repository.
        message: Commit message.

    Returns:
        True if commit succeeded.

    """
    exit_code, stdout, stderr = _run_git(
        ["commit", "-m", message],
        project_path,
    )

    if exit_code != 0:
        # "nothing to commit" is not an error
        if "nothing to commit" in stdout or "nothing to commit" in stderr:
            logger.info("Nothing to commit")
            return True
        logger.error("Failed to commit: %s", stderr)
        return False

    logger.info("Created commit: %s", message.split("\n")[0])
    return True


def _run_precommit_fix(project_path: Path) -> None:
    """Fix lint and typecheck errors that would fail the pre-commit hook.

    Detects which checks the pre-commit hook runs (ESLint, typecheck)
    and fixes errors for each. Uses eslint --fix for auto-fixable issues,
    then invokes an LLM for remaining errors in both categories.

    Best-effort: logs warnings on failure but never blocks the commit flow.

    Args:
        project_path: Path to project root.

    """
    package_json = project_path / "package.json"
    if not package_json.exists():
        return

    # Detect pre-commit checks from .husky/pre-commit
    checks = _detect_precommit_checks(project_path)

    # Fix ESLint errors
    if "eslint" in checks:
        # Layer 1: eslint --fix for auto-fixable issues
        eslint_output = _run_eslint_fix(project_path)

        # Layer 2: If errors remain, invoke LLM to fix them
        if eslint_output:
            _run_llm_lint_fix(project_path, eslint_output)

            # Layer 3: Second eslint --fix pass to clean up import ordering
            remaining = _run_eslint_fix(project_path)
            if remaining:
                error_lines = [
                    line for line in remaining.split("\n") if "error" in line.lower()
                ]
                logger.warning(
                    "Lint fix: %d errors remain after all fix layers",
                    len(error_lines),
                )

    # Fix TypeScript errors
    if "typecheck" in checks:
        tsc_output = _run_typecheck(project_path)
        if tsc_output:
            _run_llm_typecheck_fix(project_path, tsc_output)


def _detect_precommit_checks(project_path: Path) -> set[str]:
    """Detect which checks the pre-commit hook runs.

    Returns:
        Set of check identifiers: "eslint", "typecheck".

    """
    checks: set[str] = set()
    husky_file = project_path / ".husky" / "pre-commit"

    if not husky_file.exists():
        checks.add("eslint")  # Default: always try eslint
        return checks

    try:
        content = husky_file.read_text(encoding="utf-8")
        if "lint" in content:
            checks.add("eslint")
        if "typecheck" in content or "tsc" in content:
            checks.add("typecheck")
    except OSError:
        checks.add("eslint")  # Safe default

    return checks


def _run_typecheck(project_path: Path) -> str | None:
    """Run typecheck and return error output, or None if clean."""
    try:
        result = subprocess.run(
            ["npx", "turbo", "run", "typecheck"],
            cwd=project_path,
            capture_output=True,
            text=True,
            timeout=180,
        )
        if result.returncode == 0:
            logger.info("Typecheck passed (zero errors)")
            return None

        output = result.stdout or result.stderr or ""
        error_lines = [line for line in output.split("\n") if "error TS" in line]
        if not error_lines:
            logger.info("Typecheck failed but no TS errors found in output")
            return None

        logger.info("Typecheck: %d TypeScript errors found, invoking LLM", len(error_lines))
        return output

    except subprocess.TimeoutExpired:
        logger.warning("Typecheck timed out after 180s, skipping")
        return None
    except FileNotFoundError:
        logger.debug("npx not found, skipping typecheck")
        return None
    except Exception as e:
        logger.warning("Typecheck failed (non-blocking): %s", e)
        return None


def _run_llm_typecheck_fix(project_path: Path, tsc_output: str) -> None:
    """Invoke a lightweight LLM to fix TypeScript errors. Best-effort."""
    try:
        from bmad_assist.providers.claude_sdk import ClaudeSDKProvider
    except ImportError:
        logger.debug("Claude SDK not available, skipping LLM typecheck fix")
        return

    error_lines = [line.strip() for line in tsc_output.split("\n") if "error TS" in line]
    errors_text = "\n".join(error_lines)

    prompt = (
        "Fix ALL TypeScript errors shown below. For each error:\n"
        "- `TS4111`: Change `obj.prop` to `obj['prop']`\n"
        "- `TS2322`: Fix the type assignment\n"
        "- `TS2339`: Add the missing property or use bracket notation\n"
        "- `TS7006`: Add explicit type annotations\n\n"
        "Use the Read tool to examine each file, then Edit tool to fix. "
        "Do NOT modify any logic — only fix type errors.\n\n"
        "TypeScript errors:\n```\n" + errors_text + "\n```"
    )

    try:
        provider = ClaudeSDKProvider()
        result = provider.invoke(
            prompt,
            model="sonnet",
            timeout=180,
            cwd=project_path,
            allowed_tools=["Read", "Edit", "Glob", "Grep"],
        )
        if result.exit_code == 0:
            logger.info("LLM typecheck fix completed successfully")
        else:
            logger.warning("LLM typecheck fix returned exit_code=%d", result.exit_code)
    except Exception as e:
        logger.warning("LLM typecheck fix failed (non-blocking): %s", e)


def _run_eslint_fix(project_path: Path) -> str | None:
    """Run eslint --fix and return remaining error output, or None if clean."""
    try:
        result = subprocess.run(
            ["npx", "eslint", "--fix", "."],
            cwd=project_path,
            capture_output=True,
            text=True,
            timeout=120,
        )
        if result.returncode == 0:
            logger.info("Lint auto-fix completed successfully (zero errors)")
            return None

        output = result.stdout or result.stderr or ""
        error_lines = [line for line in output.split("\n") if "error" in line.lower()]
        logger.info("Lint auto-fix: %d errors remain after --fix, invoking LLM", len(error_lines))
        return output

    except subprocess.TimeoutExpired:
        logger.warning("Lint auto-fix timed out after 120s, skipping")
        return None
    except FileNotFoundError:
        logger.debug("npx not found, skipping lint auto-fix")
        return None
    except Exception as e:
        logger.warning("Lint auto-fix failed (non-blocking): %s", e)
        return None


def _run_llm_lint_fix(project_path: Path, eslint_output: str) -> None:
    """Invoke a lightweight LLM to fix remaining lint errors. Best-effort."""
    try:
        from bmad_assist.providers.claude_sdk import ClaudeSDKProvider
    except ImportError:
        logger.debug("Claude SDK not available, skipping LLM lint fix")
        return

    prompt = (
        "Fix ALL ESLint errors shown below. For each error:\n"
        "- `no-undef` for React: Add `import React from 'react'`\n"
        "- `@typescript-eslint/no-unused-vars`: Remove unused import/variable or prefix with `_`\n"
        "- `@typescript-eslint/no-explicit-any`: Replace `any` with correct type or `unknown`\n"
        "- `import/order`: Move the import to the correct position\n\n"
        "Use the Edit tool to fix each file. Do NOT modify any logic — only fix lint errors.\n\n"
        "ESLint output:\n```\n" + eslint_output + "\n```"
    )

    try:
        provider = ClaudeSDKProvider()
        result = provider.invoke(
            prompt,
            model="sonnet",
            timeout=180,
            cwd=project_path,
            allowed_tools=["Read", "Edit", "Glob", "Grep"],
        )
        if result.exit_code == 0:
            logger.info("LLM lint fix completed successfully")
        else:
            logger.warning("LLM lint fix returned exit_code=%d", result.exit_code)
    except Exception as e:
        logger.warning("LLM lint fix failed (non-blocking): %s", e)


def auto_commit_phase(
    phase: Phase | None,
    story_id: str | None,
    project_path: Path,
) -> bool:
    """Automatically commit changes after a successful phase.

    This is the main entry point called from runner.py.

    Args:
        phase: The completed phase.
        story_id: Current story ID.
        project_path: Path to project root.

    Returns:
        True if commit was successful or not needed, False on error.

    """
    if not is_git_enabled():
        return True

    # All phases proceed to modified-files check (no whitelist gate)
    # Check for modified files
    modified_files = get_modified_files(project_path)
    if not modified_files:
        logger.debug("No changes to commit for phase %s", phase)
        return True

    logger.info(
        "Auto-committing %d files after %s",
        len(modified_files),
        phase.value if phase else "unknown",
    )

    # CRITICAL: Check if any story files are marked for deletion
    # This prevents accidental permanent deletion of story artifacts
    deleted_story_files = check_for_deleted_story_files(project_path)
    if deleted_story_files:
        logger.error(
            "CRITICAL: Detected story file deletion(s): %s. "
            "Story files should NEVER be auto-deleted. "
            "Aborting commit to prevent data loss. "
            "Please investigate what caused these deletions.",
            deleted_story_files,
        )
        # Return False to halt the workflow - this is a critical error
        return False

    # Stage all changes
    if not stage_all_changes(project_path):
        return False

    # Auto-fix pre-commit hook issues (ESLint + typecheck)
    _run_precommit_fix(project_path)

    # Re-stage after lint fixes (eslint --fix may have modified files)
    stage_all_changes(project_path)

    # Generate commit message
    message = generate_commit_message(
        phase,  # type: ignore[arg-type]
        story_id,
        modified_files,
    )

    # Commit
    return commit_changes(project_path, message)
