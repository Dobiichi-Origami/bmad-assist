#!/bin/bash
# Archive non-master validation and review artifacts
# BMAD v6 compatible - uses _bmad-output/implementation-artifacts/

set -euo pipefail

# Find project root (look for _bmad-output or .git)
find_project_root() {
    local dir="$PWD"
    while [[ "$dir" != "/" ]]; do
        if [[ -d "$dir/_bmad-output" ]] || [[ -d "$dir/.git" ]]; then
            echo "$dir"
            return 0
        fi
        dir="$(dirname "$dir")"
    done
    echo "$PWD"
}

PROJECT_ROOT="$(find_project_root)"
ARTIFACTS_DIR="$PROJECT_ROOT/_bmad-output/implementation-artifacts"
SILENT=false

while getopts "s" opt; do
    case $opt in
        s) SILENT=true ;;
        *) echo "Usage: $0 [-s]" >&2; exit 1 ;;
    esac
done

archived=0
kept=0

archive_dir() {
    local src_dir="$1"
    local archive_subdir="$1/archive"

    [[ -d "$src_dir" ]] || return 0

    mkdir -p "$archive_subdir"

    for file in "$src_dir"/*.md; do
        [[ -f "$file" ]] || continue

        filename="$(basename "$file")"

        # Keep master and synthesis files, archive the rest
        if [[ "$filename" == *-master-* ]] || [[ "$filename" == synthesis-* ]]; then
            ((++kept))
        else
            [[ "$SILENT" == false ]] && echo "$file -> $archive_subdir/"
            mv "$file" "$archive_subdir/"
            ((++archived))
        fi
    done
}

archive_dir "$ARTIFACTS_DIR/code-reviews"
archive_dir "$ARTIFACTS_DIR/story-validations"

if [[ "$SILENT" == false ]]; then
    echo ""
    echo "Archived: $archived   Kept (master/synthesis): $kept"
fi
