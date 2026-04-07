"""Test review handler for testarch module.

Runs the testarch-test-review workflow to validate test quality after
dev_story completes, before code_review. Its findings feed into code
review as context, and its quality score influences synthesis decisions.

"""

from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import TYPE_CHECKING, Any

from bmad_assist.core.loop.types import PhaseResult
from bmad_assist.core.paths import get_paths
from bmad_assist.core.state import State
from bmad_assist.testarch.core import extract_quality_score
from bmad_assist.testarch.handlers.base import TestarchBaseHandler

if TYPE_CHECKING:
    from bmad_assist.core.config import Config

logger = logging.getLogger(__name__)


class TestReviewHandler(TestarchBaseHandler):
    """Handler for test review workflow.

    Executes the testarch-test-review workflow when enabled. This handler
    runs after DEV_STORY (before CODE_REVIEW) to review test quality for
    stories that used ATDD. Findings are injected as condensed context into
    code_review prompts, and the quality score feeds into synthesis decisions.

    The handler:
    1. Checks test_review mode (off/auto/on) to determine if review should run
    2. Invokes the test review workflow for eligible stories
    3. Extracts quality score (0-100) from output
    4. Saves full review report and condensed summary to test-reviews/ directory
    5. Writes quality_score to state for downstream consumption

    Mode behavior:
    - off: Never run test review
    - auto: Only run if atdd_ran_for_story is True
    - on: Always run test review

    """

    def __init__(self, config: Config, project_path: Path) -> None:
        """Initialize handler with config and project path.

        Args:
            config: Application configuration with provider settings.
            project_path: Path to the project root directory.

        """
        super().__init__(config, project_path)

    @property
    def phase_name(self) -> str:
        """Return the phase name."""
        return "test_review"

    @property
    def workflow_id(self) -> str:
        """Return the workflow identifier for engagement model checks."""
        return "test-review"

    def build_context(self, state: State) -> dict[str, Any]:
        """Build context for test review prompt template.

        Args:
            state: Current loop state.

        Returns:
            Context dict with common variables:
            epic_num, story_num, story_id, project_path.

        """
        return self._build_common_context(state)

    def _extract_quality_score(self, output: str) -> int | None:
        """Extract quality score from test review workflow output.

        Delegates to centralized extraction function from testarch.core.

        Args:
            output: Raw test review workflow output.

        Returns:
            Quality score as integer (0-100) or None if not found.

        """
        return extract_quality_score(output)

    def _generate_condensed_summary(self, output: str) -> str:
        """Generate condensed summary from test review LLM output.

        Extracts quality score, critical issues, and recommendation into a
        short summary (~15-30 lines) for efficient context injection into
        downstream prompts.

        Uses regex-based extraction targeting well-known section headers
        from the test review template. Falls back to first 30 lines if
        extraction fails.

        Args:
            output: Full test review LLM output.

        Returns:
            Condensed summary string.

        """
        lines: list[str] = []

        # Extract quality score and grade
        score = self._extract_quality_score(output)
        grade_match = re.search(
            r"\*?\*?[Gg]rade\*?\*?:?\s*([A-F][+-]?\s*[-–—]\s*\w+)", output
        )
        grade_str = grade_match.group(1).strip() if grade_match else "N/A"
        score_str = f"{score}/100" if score is not None else "N/A"
        lines.append(f"# Test Review Summary")
        lines.append(f"")
        lines.append(f"**Quality Score:** {score_str} | **Grade:** {grade_str}")
        lines.append(f"")

        # Extract critical issues (P0/P1)
        critical_issues: list[str] = []
        # Look for lines with P0 or P1 markers, or lines under "Critical Issues" heading
        in_critical_section = False
        for line in output.splitlines():
            stripped = line.strip()
            # Detect critical issues section header
            if re.match(r"#{1,3}\s*(?:Critical|P0|P1)\s+(?:Issues?|Findings?)", stripped, re.IGNORECASE):
                in_critical_section = True
                continue
            # Detect next section header (exit critical section)
            if in_critical_section and re.match(r"#{1,3}\s", stripped):
                in_critical_section = False
                continue
            # Capture P0/P1 lines or lines in critical section with file references
            if re.search(r"\bP[01]\b", stripped) or (
                in_critical_section and stripped.startswith(("-", "*", "1"))
            ):
                # Extract file:line reference if present
                file_ref = re.search(r"[`]?(\S+\.\w+:\d+)[`]?", stripped)
                if file_ref:
                    critical_issues.append(f"- {file_ref.group(1)}: {stripped}")
                elif stripped:
                    critical_issues.append(f"- {stripped}")
                if len(critical_issues) >= 10:
                    break

        if critical_issues:
            lines.append("## Critical Issues")
            lines.append("")
            lines.extend(critical_issues[:10])
            lines.append("")

        # Extract recommendation
        rec_match = re.search(
            r"\*?\*?(?:Recommendation|Verdict)\*?\*?:?\s*((?:Approve|Request Changes|Block)\b[^\n]*)",
            output,
            re.IGNORECASE,
        )
        if rec_match:
            lines.append(f"**Recommendation:** {rec_match.group(1).strip()}")
        else:
            # Infer from score
            if score is not None:
                if score >= 70:
                    lines.append("**Recommendation:** Approve")
                elif score >= 50:
                    lines.append("**Recommendation:** Request Changes")
                else:
                    lines.append("**Recommendation:** Block")

        # Fallback: if we couldn't extract meaningful content, use first 30 lines
        if not critical_issues and score is None:
            logger.warning("Condensed summary extraction failed, falling back to first 30 lines")
            return "\n".join(output.splitlines()[:30])

        return "\n".join(lines)

    def _invoke_test_review_workflow(self, state: State) -> PhaseResult:
        """Invoke test review workflow via master provider.

        Delegates to base handler's _invoke_generic_workflow with test review
        specific parameters. Also saves a condensed summary file alongside
        the full report.

        Args:
            state: Current loop state.

        Returns:
            PhaseResult with workflow output containing:
            - response: Provider output
            - quality_score: 0-100 score if extracted
            - file: Path to saved review report
            - summary_file: Path to saved condensed summary

        """
        story_id = f"{state.current_epic}-{state.current_story}"

        try:
            paths = get_paths()
            report_dir = paths.output_folder / "test-reviews"
        except RuntimeError:
            logger.error("Paths not initialized")
            return PhaseResult.fail("Paths not initialized")

        result = self._invoke_generic_workflow(
            workflow_name="testarch-test-review",
            state=state,
            extractor_fn=self._extract_quality_score,
            report_dir=report_dir,
            report_prefix="test-review",
            story_id=story_id,
            metric_key="quality_score",
            file_key="review_file",
        )

        # Save condensed summary alongside the full report
        if result.success and result.outputs.get("response"):
            try:
                summary_content = self._generate_condensed_summary(result.outputs["response"])
                summary_path = self._save_report(
                    output_dir=report_dir,
                    filename_prefix="test-review-summary",
                    content=summary_content,
                    story_id=story_id,
                )
                outputs = dict(result.outputs)
                outputs["summary_file"] = str(summary_path)
                return PhaseResult.ok(outputs)
            except Exception as e:
                logger.warning("Failed to save condensed summary: %s", e)

        return result

    def execute(self, state: State) -> PhaseResult:
        """Execute test review phase. Called by main loop.

        Delegates to base handler's _execute_with_mode_check for standardized
        mode handling and workflow invocation. On success, writes the extracted
        quality_score to state for downstream consumption by synthesis.

        Args:
            state: Current loop state.

        Returns:
            PhaseResult with success/failure and outputs.

        """
        story_id = f"{state.current_epic}-{state.current_story}"
        logger.info("Test review handler starting for story %s", story_id)

        # Engagement model check (before all other checks)
        should_run, skip_reason = self._check_engagement_model()
        if not should_run:
            logger.info("Test review skipped: %s", skip_reason)
            return self._make_engagement_skip_result(skip_reason or "engagement_model disabled")

        result = self._execute_with_mode_check(
            state=state,
            mode_field="test_review_on_code_complete",
            state_flag="atdd_ran_for_story",
            workflow_fn=self._invoke_test_review_workflow,
            mode_output_key="test_review_mode",
            skip_reason_auto="no ATDD ran for story",
        )

        # Write quality_score to state for downstream phases
        if result.success and result.outputs.get("quality_score") is not None:
            state.test_review_quality_score = result.outputs["quality_score"]
            logger.info(
                "Written test_review_quality_score=%d to state",
                result.outputs["quality_score"],
            )

        return result
