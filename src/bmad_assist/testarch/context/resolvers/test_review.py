"""Test review artifact resolver.

Resolves test-review-{story}.md artifacts.
Used in code_review_synthesis to include test quality findings.
Supports condensed mode for efficient context injection into code_review.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from bmad_assist.testarch.context.resolvers.base import BaseResolver
from bmad_assist.testarch.paths import get_artifact_patterns

if TYPE_CHECKING:
    from bmad_assist.core.types import EpicId

logger = logging.getLogger(__name__)


class TestReviewResolver(BaseResolver):
    """Resolver for test review artifacts.

    Loads test-review-{story}.md files.
    Tries both dot and hyphen formats for story ID.

    Supports condensed mode: when condensed=True, prioritizes
    test-review-summary-*.md files over full reports for efficient
    context injection into downstream prompts.

    """

    @property
    def artifact_type(self) -> str:
        """Return artifact type identifier."""
        return "test-review"

    def resolve(
        self,
        epic_id: EpicId,
        story_id: str | None = None,
        condensed: bool = False,
    ) -> dict[str, str]:
        """Resolve test review artifact.

        Args:
            epic_id: Epic identifier (int or str).
            story_id: Story identifier (required for test-review).
            condensed: If True, prefer summary files over full reports.

        Returns:
            Dict with single entry {path: content} or empty dict.

        """
        result: dict[str, str] = {}

        if not story_id:
            logger.debug("Test review resolver requires story_id, skipping")
            return result

        subdir = self._get_artifact_dir()

        # When condensed=True, try summary files first
        if condensed:
            summary_patterns = get_artifact_patterns("test-review-summary", epic_id, story_id)
            for pattern in summary_patterns:
                matches = self._find_matching_files(pattern, subdir)
                if not matches:
                    continue

                path = matches[0]
                content = self._safe_read(path)
                if content is None:
                    continue

                truncated = self._truncate_content(content, self._max_tokens)
                result[str(path)] = truncated

                logger.info(
                    "TEA context: loaded condensed %s for story %s (%s)",
                    self.artifact_type,
                    story_id,
                    path.name,
                )
                return result

            logger.debug(
                "No summary file found for story %s, falling back to full report",
                story_id,
            )

        # Full report patterns (default or fallback from condensed)
        patterns = get_artifact_patterns(self.artifact_type, epic_id, story_id)

        for pattern in patterns:
            matches = self._find_matching_files(pattern, subdir)
            if not matches:
                continue

            # Take first match for this pattern
            path = matches[0]
            content = self._safe_read(path)
            if content is None:
                continue

            # Apply token truncation
            truncated = self._truncate_content(content, self._max_tokens)
            result[str(path)] = truncated

            logger.info(
                "TEA context: loaded %s for story %s (%s)",
                self.artifact_type,
                story_id,
                path.name,
            )
            # Return first found
            return result

        logger.info(
            "TEA artifact not found: %s for story %s (skipping)",
            self.artifact_type,
            story_id,
        )
        return result
