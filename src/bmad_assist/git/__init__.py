"""Git utilities for bmad-assist.

Provides:
- Automatic git commits after successful phase execution
- Intelligent diff capture with filtering and validation
- Gitignore setup for proper project configuration
- Epic branch management for dogfooding workflow
"""

from bmad_assist.git.branch import (
    branch_exists,
    checkout_branch,
    create_branch,
    ensure_epic_branch,
    get_current_branch,
    get_epic_branch_name,
    is_git_enabled,
)
from bmad_assist.git.committer import auto_commit_phase, stash_working_changes
from bmad_assist.git.diff import (
    DiffQualityError,
    DiffValidationResult,
    capture_filtered_diff,
    extract_files_from_diff,
    get_merge_base,
    get_validated_diff,
    validate_diff_quality,
)
from bmad_assist.git.gitignore import (
    check_gitignore,
    ensure_gitignore,
    setup_gitignore,
)

__all__ = [
    "auto_commit_phase",
    "stash_working_changes",
    # Branch management (epic workflow)
    "ensure_epic_branch",
    "get_current_branch",
    "get_epic_branch_name",
    "branch_exists",
    "create_branch",
    "checkout_branch",
    "is_git_enabled",
    # Diff utilities (P0/P1 fixes)
    "capture_filtered_diff",
    "get_merge_base",
    "get_validated_diff",
    "validate_diff_quality",
    "extract_files_from_diff",
    "DiffQualityError",
    "DiffValidationResult",
    # Gitignore setup
    "check_gitignore",
    "setup_gitignore",
    "ensure_gitignore",
]
