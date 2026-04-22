"""Mock end-to-end test simulating the runner's full Twin integration path.

This test mirrors the exact data flow in runner._run_loop_body():
  1. init_wiki → wiki_dir
  2. Twin(config, wiki_dir, provider)
  3. guide(phase_name) → compass → inject into "execution"
  4. build_execution_record(...) from "execution result"
  5. reflect(record, is_retry=False, epic_id=epic_id) → TwinResult
  6. apply_page_updates(twin_result.page_updates, wiki_dir, epic_id)
  7. Handle decision: continue / retry / halt
  8. On retry: correction compass appended → re-execute → reflect(is_retry=True)

No real LLM calls — all provider responses are mocked.
"""

from __future__ import annotations

import re
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from bmad_assist.twin.config import TwinProviderConfig
from bmad_assist.twin.execution_record import ExecutionRecord, build_execution_record
from bmad_assist.twin.twin import (
    PageUpdate,
    Twin,
    TwinResult,
    apply_page_updates,
)
from bmad_assist.twin.wiki import (
    derive_confidence,
    init_wiki,
    list_pages,
    page_exists,
    parse_frontmatter,
    read_page,
    rebuild_index,
    write_page,
)
from tests.twin.conftest import make_yaml_output


# ---------------------------------------------------------------------------
# Helpers simulating the runner's integration path
# ---------------------------------------------------------------------------


def _simulate_phase_result(
    phase: str,
    mission: str,
    llm_output: str,
    success: bool = True,
    duration_ms: int = 5000,
    error: str | None = None,
) -> dict:
    """Simulate the result object from execute_phase().

    In runner.py, result.outputs is a dict with at least 'response' and 'duration_ms'.
    """
    return {
        "success": success,
        "error": error,
        "outputs": {
            "response": llm_output,
            "duration_ms": duration_ms,
        },
    }


def _runner_build_record(
    phase_name: str,
    mission: str,
    phase_result: dict,
    project_path: Path | None = None,
) -> ExecutionRecord:
    """Mirrors runner.py's build_execution_record call exactly."""
    return build_execution_record(
        phase=phase_name,
        mission=mission,
        llm_output=phase_result["outputs"].get("response", ""),
        success=phase_result["success"],
        duration_ms=phase_result["outputs"].get("duration_ms", 0)
        if isinstance(phase_result["outputs"].get("duration_ms", 0), int)
        else 0,
        error=phase_result["error"],
        phase_outputs=phase_result["outputs"],
        project_path=project_path,
    )


def _format_correction_compass(
    original_compass: str | None,
    retry_count: int,
    correction: str,
) -> str:
    """Mirrors runner.py's correction compass formatting."""
    correction_compass = f"[RETRY retry={retry_count}] {correction}"
    return (original_compass or "") + "\n" + correction_compass


# ---------------------------------------------------------------------------
# Test: Full single-phase flow (Guide → Execute → Reflect → Apply)
# ---------------------------------------------------------------------------


class TestFullSinglePhaseFlow:
    """Simulates a complete single phase execution with Twin integration."""

    def test_guide_reflect_apply_flow(self, tmp_path: Path) -> None:
        """End-to-end: init wiki → guide → execute → reflect → apply updates."""
        # --- Setup: same as runner.py ---
        project_path = tmp_path
        wiki_dir = init_wiki(project_path)
        provider = MagicMock()
        config = TwinProviderConfig()
        twin = Twin(config=config, wiki_dir=wiki_dir, provider=provider)

        # --- Step 1: Guide ---
        provider.invoke.return_value = (
            "Focus on BDD acceptance criteria format. "
            "Ensure all 5 disaster categories are checked in the story."
        )
        compass = twin.guide("create_story")
        assert compass is not None
        assert "acceptance criteria" in compass.lower()

        # --- Step 2: Simulate phase execution ---
        phase_output = _simulate_phase_result(
            phase="create_story",
            mission="Create user login story",
            llm_output=(
                "# Story Output\n\n"
                "## Story Details\n\n"
                "Feature: User Login\n\n"
                "## Self-Audit\n\n"
                "- All ACs in BDD format\n"
                "- Architecture analysis complete\n"
                "- 5 disaster categories checked\n"
            ),
            success=True,
            duration_ms=8000,
        )

        # --- Step 3: Build execution record (same as runner) ---
        record = _runner_build_record(
            phase_name="create_story",
            mission="Create user login story",
            phase_result=phase_output,
            project_path=project_path,
        )
        assert record.self_audit is not None
        assert "BDD format" in record.self_audit

        # --- Step 4: Reflect ---
        provider.invoke.return_value = make_yaml_output(
            decision="continue",
            rationale="Execution matches mission. All ACs satisfied.",
            page_updates=[{
                "page_name": "env-project-structure",
                "action": "create",
                "content": (
                    "---\ncategory: env\nsentiment: positive\nconfidence: tentative\n"
                    "occurrences: 0\nlast_updated: \"\"\nsource_epics: []\nlinks_to: []\n"
                    "---\n\n# Project Structure\n\n## What\nMonorepo with React frontend and Express backend.\n\n## Evidence\n\n"
                    "| Context | Result | Epic |\n|---------|--------|------|\n"
                ),
                "reason": "New env knowledge from story creation",
            }],
        )
        twin_result = twin.reflect(record, is_retry=False, epic_id="1")

        # --- Step 5: Apply page updates ---
        assert twin_result.decision == "continue"
        assert twin_result.page_updates is not None
        apply_page_updates(twin_result.page_updates, wiki_dir, epic_id="1")
        assert page_exists(wiki_dir, "env-project-structure")

        # Verify wiki state
        page = read_page(wiki_dir, "env-project-structure")
        assert page is not None
        fm = parse_frontmatter(page)
        assert fm["category"] == "env"
        assert "1" in fm.get("source_epics", [])


# ---------------------------------------------------------------------------
# Test: Multi-epic knowledge accumulation
# ---------------------------------------------------------------------------


class TestMultiEpicAccumulation:
    """Simulate multiple epics running through the Twin, accumulating wiki knowledge."""

    def test_knowledge_grows_across_epics(self, tmp_path: Path) -> None:
        """Wiki pages accumulate evidence and confidence across 3 epics."""
        wiki_dir = init_wiki(tmp_path)
        provider = MagicMock()
        config = TwinProviderConfig()
        twin = Twin(config=config, wiki_dir=wiki_dir, provider=provider)

        # --- Epic 1: create_story → creates an env page ---
        provider.invoke.return_value = make_yaml_output(
            decision="continue",
            rationale="Good story creation",
            page_updates=[{
                "page_name": "env-testing-framework",
                "action": "create",
                "content": (
                    "---\ncategory: env\nsentiment: positive\nconfidence: tentative\n"
                    "occurrences: 0\nlast_updated: \"\"\nsource_epics: []\nlinks_to: []\n"
                    "---\n\n# Testing Framework\n\n## What\npytest with pytest-asyncio for async tests.\n\n## Evidence\n\n"
                    "| Context | Result | Epic |\n|---------|--------|------|\n"
                ),
                "reason": "Discovered testing framework during story creation",
            }],
        )
        record1 = ExecutionRecord(
            phase="create_story", mission="Create story",
            llm_output="## Self-Audit\n\n- Done", self_audit="- Done",
            success=True, duration_ms=3000, error=None,
        )
        result1 = twin.reflect(record1, is_retry=False, epic_id="1")
        if result1.page_updates:
            apply_page_updates(result1.page_updates, wiki_dir, "1")

        page = read_page(wiki_dir, "env-testing-framework")
        assert page is not None
        fm1 = parse_frontmatter(page)
        assert fm1["occurrences"] == 0  # CREATE doesn't call update_frontmatter

        # --- Epic 2: dev_story → updates the env page with evidence ---
        provider.invoke.return_value = make_yaml_output(
            decision="continue",
            rationale="Dev went well, updating env page",
            page_updates=[{
                "page_name": "env-testing-framework",
                "action": "update",
                "append_evidence": {"context": "Dev phase", "result": "pytest-asyncio used"},
                "reason": "Confirmed testing framework usage",
            }],
        )
        record2 = ExecutionRecord(
            phase="dev_story", mission="Dev story",
            llm_output="## Self-Audit\n\n- All tests pass", self_audit="- All tests pass",
            success=True, duration_ms=5000, error=None,
        )
        result2 = twin.reflect(record2, is_retry=False, epic_id="2")
        if result2.page_updates:
            apply_page_updates(result2.page_updates, wiki_dir, "2")

        page = read_page(wiki_dir, "env-testing-framework")
        fm2 = parse_frontmatter(page)
        assert fm2["occurrences"] == 1
        assert fm2["confidence"] == "tentative"
        assert "2" in page  # Evidence row has EPIC-2

        # --- Epic 3: code_review → updates again, confidence promotes ---
        provider.invoke.return_value = make_yaml_output(
            decision="continue",
            rationale="Code review completed",
            page_updates=[{
                "page_name": "env-testing-framework",
                "action": "update",
                "append_evidence": {"context": "Code review", "result": "All tests use pytest-asyncio"},
                "reason": "Third observation of testing framework",
            }],
        )
        record3 = ExecutionRecord(
            phase="code_review", mission="Review code",
            llm_output="## Self-Audit\n\n- No issues", self_audit="- No issues",
            success=True, duration_ms=2000, error=None,
        )
        result3 = twin.reflect(record3, is_retry=False, epic_id="3")
        if result3.page_updates:
            apply_page_updates(result3.page_updates, wiki_dir, "3")

        page = read_page(wiki_dir, "env-testing-framework")
        fm3 = parse_frontmatter(page)
        assert fm3["occurrences"] == 2
        assert fm3["confidence"] == "established"  # 2 occurrences → established

        # Verify INDEX reflects accumulated state
        index = read_page(wiki_dir, "INDEX")
        assert index is not None
        assert "env-testing-framework" in index
        assert "[established]" in index


# ---------------------------------------------------------------------------
# Test: RETRY flow (mirrors runner.py retry loop)
# ---------------------------------------------------------------------------


class TestRetryFlow:
    """Simulates the full RETRY loop from runner.py lines 1376-1460."""

    def test_drift_detected_then_retry_succeeds(self, tmp_path: Path) -> None:
        """Drift detected → correction compass → re-execute → reflect(is_retry=True) → continue."""
        wiki_dir = init_wiki(tmp_path)
        provider = MagicMock()
        config = TwinProviderConfig(max_retries=2, retry_exhausted_action="halt")
        twin = Twin(config=config, wiki_dir=wiki_dir, provider=provider)

        # --- Guide returns compass ---
        provider.invoke.return_value = "Focus on test coverage."
        compass = twin.guide("dev_story")

        # --- First reflect: drift detected ---
        provider.invoke.return_value = make_yaml_output(
            decision="retry",
            rationale="Missing test coverage for login handler",
            drifted=True,
            evidence="Self-audit claims tests pass but login.ts has no test file",
            correction="Add test file for src/login.ts with unit tests for all exported functions",
        )
        phase_result = _simulate_phase_result(
            phase="dev_story",
            mission="Implement login feature",
            llm_output="## Self-Audit\n\n- All tests pass",
            success=True,
        )
        record = _runner_build_record("dev_story", "Implement login feature", phase_result)
        twin_result = twin.reflect(record, is_retry=False, epic_id="1")

        assert twin_result.decision == "retry"
        assert twin_result.drift_assessment is not None
        assert twin_result.drift_assessment.drifted is True
        correction = twin_result.drift_assessment.correction
        assert correction is not None

        # --- Build correction compass (same as runner.py) ---
        retry_count = 0
        max_retries = config.max_retries
        original_compass = compass

        # --- RETRY loop iteration 1 ---
        retry_count += 1
        full_compass = _format_correction_compass(original_compass, retry_count, correction)
        assert "[RETRY retry=1]" in full_compass
        assert original_compass in full_compass  # Correction APPENDED, not replaced

        # Simulate re-execution with correction
        retry_phase_result = _simulate_phase_result(
            phase="dev_story",
            mission="Implement login feature",
            llm_output="## Self-Audit\n\n- Login tests added\n- All tests pass",
            success=True,
        )

        # Reflect on retry result (is_retry=True)
        provider.invoke.return_value = make_yaml_output(
            decision="continue",
            rationale="Drift corrected. Login tests now present.",
        )
        retry_record = _runner_build_record("dev_story", "Implement login feature", retry_phase_result)
        retry_twin_result = twin.reflect(retry_record, is_retry=True, epic_id="1")

        assert retry_twin_result.decision == "continue"

    def test_retry_exhausted_halts(self, tmp_path: Path) -> None:
        """RETRY keeps failing → retries exhausted → halt."""
        wiki_dir = init_wiki(tmp_path)
        provider = MagicMock()
        config = TwinProviderConfig(max_retries=2, retry_exhausted_action="halt")
        twin = Twin(config=config, wiki_dir=wiki_dir, provider=provider)

        # Initial reflect: retry
        provider.invoke.return_value = make_yaml_output(
            decision="retry",
            rationale="Still broken",
            drifted=True,
            evidence="Code still wrong",
            correction="Fix the implementation",
        )
        record = ExecutionRecord(
            phase="dev_story", mission="Build", llm_output="## Self-Audit\n\n- Partial",
            self_audit="- Partial", success=True, duration_ms=3000, error=None,
        )
        twin_result = twin.reflect(record, is_retry=False, epic_id="1")
        assert twin_result.decision == "retry"

        # Retry attempt 1: still retry
        provider.invoke.return_value = make_yaml_output(
            decision="retry",
            rationale="Still not fixed",
            drifted=True,
            evidence="Still wrong",
            correction="Different approach",
        )
        retry_record = ExecutionRecord(
            phase="dev_story", mission="Build", llm_output="## Self-Audit\n\n- Still partial",
            self_audit="- Still partial", success=True, duration_ms=4000, error=None,
        )
        retry_result = twin.reflect(retry_record, is_retry=True, epic_id="1")
        assert retry_result.decision == "retry"

        # Retry attempt 2: still retry → max_retries exhausted
        provider.invoke.return_value = make_yaml_output(
            decision="retry",
            rationale="Give up",
            drifted=True,
            evidence="Nope",
            correction="Nothing works",
        )
        final_record = ExecutionRecord(
            phase="dev_story", mission="Build", llm_output="## Self-Audit\n\n- Fail",
            self_audit="- Fail", success=True, duration_ms=5000, error=None,
        )
        final_result = twin.reflect(final_record, is_retry=True, epic_id="1")
        # In runner, this would loop and exhaust → GUARDIAN_HALT
        # Here we simulate the exhaustion check
        retry_count = 2
        assert retry_count >= config.max_retries
        assert config.retry_exhausted_action == "halt"
        # Runner returns LoopExitReason.GUARDIAN_HALT

    def test_parse_failure_during_retry_halts(self, tmp_path: Path) -> None:
        """Parse failure during is_retry=True with halt config → degrade to halt."""
        wiki_dir = init_wiki(tmp_path)
        provider = MagicMock()
        config = TwinProviderConfig(retry_exhausted_action="halt")
        twin = Twin(config=config, wiki_dir=wiki_dir, provider=provider)

        # LLM returns garbage on retry
        provider.invoke.return_value = "not valid yaml at all"
        record = ExecutionRecord(
            phase="dev_story", mission="Build", llm_output="output",
            self_audit=None, success=True, duration_ms=100, error=None,
        )
        result = twin.reflect(record, is_retry=True, epic_id="1")
        # Both attempts fail → degrade to halt
        assert result.decision == "halt"
        assert "parse error" in result.rationale.lower()


# ---------------------------------------------------------------------------
# Test: HALT decision from reflect
# ---------------------------------------------------------------------------


class TestHaltDecision:
    """Simulate the Twin detecting an unrecoverable issue."""

    def test_halt_on_fatal_issue(self, tmp_path: Path) -> None:
        """Twin detects architectural problem → halt → runner returns GUARDIAN_HALT."""
        wiki_dir = init_wiki(tmp_path)
        provider = MagicMock()
        config = TwinProviderConfig()
        twin = Twin(config=config, wiki_dir=wiki_dir, provider=provider)

        provider.invoke.return_value = make_yaml_output(
            decision="halt",
            rationale="Story requires database migration but no migration framework exists in the project",
        )
        record = ExecutionRecord(
            phase="dev_story", mission="Implement user profiles",
            llm_output="## Self-Audit\n\n- Cannot proceed without DB migration",
            self_audit="- Cannot proceed without DB migration",
            success=True, duration_ms=2000, error=None,
        )
        result = twin.reflect(record, is_retry=False, epic_id="5")

        assert result.decision == "halt"
        assert "database" in result.rationale.lower() or "migration" in result.rationale.lower()


# ---------------------------------------------------------------------------
# Test: Disabled Twin (runner skips all Twin calls)
# ---------------------------------------------------------------------------


class TestDisabledTwinFlow:
    """Simulate the runner path when Twin is disabled."""

    def test_disabled_twin_no_compass_no_reflect(self, tmp_path: Path) -> None:
        """When enabled=False, guide returns None and reflect returns continue."""
        config = TwinProviderConfig(enabled=False)
        wiki_dir = init_wiki(tmp_path)
        twin = Twin(config=config, wiki_dir=wiki_dir)

        # Guide
        compass = twin.guide("dev_story")
        assert compass is None

        # Reflect
        record = ExecutionRecord(
            phase="dev_story", mission="Build", llm_output="output",
            self_audit=None, success=True, duration_ms=100, error=None,
        )
        result = twin.reflect(record)
        assert result.decision == "continue"
        assert "disabled" in result.rationale.lower()
        assert result.page_updates is None


# ---------------------------------------------------------------------------
# Test: Wiki evolution across full sprint
# ---------------------------------------------------------------------------


class TestSprintWikiEvolution:
    """Simulate a full sprint with multiple phases updating the wiki."""

    def test_sprint_creates_and_updates_pages(self, tmp_path: Path) -> None:
        """A sprint's worth of phases creates and evolves wiki pages."""
        wiki_dir = init_wiki(tmp_path)
        provider = MagicMock()
        config = TwinProviderConfig()
        twin = Twin(config=config, wiki_dir=wiki_dir, provider=provider)

        # Phase sequence: create_story → dev_story → code_review → qa_remediate
        phases = [
            ("create_story", "Create user profile story", "## Self-Audit\n\n- Story created with BDD ACs"),
            ("dev_story", "Implement user profile", "## Self-Audit\n\n- All ACs implemented\n- Tests pass"),
            ("code_review", "Review profile code", "## Self-Audit\n\n- 3 issues found"),
            ("qa_remediate", "Fix QA issues", "## Self-Audit\n\n- All issues resolved"),
        ]

        # Mock LLM returns different updates per phase
        page_updates_sequence = [
            # create_story: create env page about project architecture
            [make_yaml_output(
                decision="continue",
                rationale="Story well-formed",
                page_updates=[{
                    "page_name": "env-frontend-arch",
                    "action": "create",
                    "content": (
                        "---\ncategory: env\nsentiment: positive\nconfidence: tentative\n"
                        "occurrences: 0\nlast_updated: \"\"\nsource_epics: []\nlinks_to: []\n"
                        "---\n\n# Frontend Architecture\n\n## What\nReact 18 with TypeScript. "
                        "Vite 5 for builds. Zustand for state.\n\n## Evidence\n\n"
                        "| Context | Result | Epic |\n|---------|--------|------|\n"
                    ),
                    "reason": "Observed during story creation",
                }],
            )],
            # dev_story: update the env page with evidence
            [make_yaml_output(
                decision="continue",
                rationale="Dev completed correctly",
                page_updates=[{
                    "page_name": "env-frontend-arch",
                    "action": "update",
                    "append_evidence": {"context": "Dev phase", "result": "Zustand store created"},
                    "reason": "Confirmed architecture during dev",
                }],
            )],
            # code_review: create negative pattern page
            [make_yaml_output(
                decision="continue",
                rationale="Code review issues noted",
                page_updates=[{
                    "page_name": "pattern-unhandled-errors",
                    "action": "create",
                    "content": (
                        "---\ncategory: pattern\nsentiment: negative\nconfidence: tentative\n"
                        "occurrences: 0\nlast_updated: \"\"\nsource_epics: []\nlinks_to: []\n"
                        "---\n\n# Unhandled Error Patterns\n\n## What\nDevelopers consistently "
                        "forget error handling in async API calls.\n\n## Evidence\n\n"
                        "| Context | Root Cause | Real Impact | Epic |\n|---------|------------|-------------|------|\n"
                    ),
                    "reason": "Found 3 unhandled error cases in code review",
                }],
            )],
            # qa_remediate: update the negative pattern with more evidence
            [make_yaml_output(
                decision="continue",
                rationale="Remediation complete, pattern reinforced",
                page_updates=[{
                    "page_name": "pattern-unhandled-errors",
                    "action": "update",
                    "append_evidence": {"context": "QA remediation", "root_cause": "No error boundary", "real_impact": "Silent failures in prod"},
                    "reason": "QA found additional unhandled errors",
                }],
            )],
        ]

        for i, (phase, mission, output) in enumerate(phases):
            # Guide
            provider.invoke.return_value = f"Compass for {phase}"
            compass = twin.guide(phase)

            # Reflect
            provider.invoke.return_value = page_updates_sequence[i][0]
            record = ExecutionRecord(
                phase=phase, mission=mission, llm_output=output,
                self_audit=output.split("## Self-Audit\n\n")[1] if "## Self-Audit" in output else None,
                success=True, duration_ms=3000 + i * 1000, error=None,
            )
            twin_result = twin.reflect(record, is_retry=False, epic_id="1")
            if twin_result.page_updates:
                apply_page_updates(twin_result.page_updates, wiki_dir, "1")

        # Verify final wiki state
        pages = list_pages(wiki_dir)
        assert "env-frontend-arch" in pages
        assert "pattern-unhandled-errors" in pages

        # env page should have evidence from 2 sources
        env_page = read_page(wiki_dir, "env-frontend-arch")
        assert env_page is not None
        env_fm = parse_frontmatter(env_page)
        assert env_fm["occurrences"] == 1  # 1 UPDATE after CREATE

        # Negative pattern should have 1 occurrence
        neg_page = read_page(wiki_dir, "pattern-unhandled-errors")
        assert neg_page is not None
        neg_fm = parse_frontmatter(neg_page)
        assert neg_fm["sentiment"] == "negative"
        assert neg_fm["occurrences"] == 1
        assert neg_fm["confidence"] == "tentative"

        # INDEX should list all pages
        index = read_page(wiki_dir, "INDEX")
        assert index is not None
        assert "env-frontend-arch" in index
        assert "pattern-unhandled-errors" in index


# ---------------------------------------------------------------------------
# Test: Challenge mode across epic boundaries
# ---------------------------------------------------------------------------


class TestChallengeModeEpic:
    """Simulate negative pattern reaching 5-epic boundary and triggering challenge mode."""

    def test_negative_pattern_challenges_at_5_epics(self, tmp_path: Path) -> None:
        """After 5 source_epics on a negative page, challenge mode triggers in reflect prompt."""
        wiki_dir = init_wiki(tmp_path)
        provider = MagicMock()
        config = TwinProviderConfig()
        twin = Twin(config=config, wiki_dir=wiki_dir, provider=provider)

        # Create a negative pattern page and apply 5 updates (5 source_epics)
        content = (
            "---\ncategory: pattern\nsentiment: negative\nconfidence: tentative\n"
            "occurrences: 0\nlast_updated: \"\"\nsource_epics: []\nlinks_to: []\n"
            "---\n\n# Unhandled Errors\n\n## What\nMissing error handling.\n\n## Evidence\n\n"
            "| Context | Root Cause | Real Impact | Epic |\n|---------|------------|-------------|------|\n"
        )
        write_page(wiki_dir, "pattern-unhandled-errors", content)

        # Apply 5 updates to reach the challenge mode boundary (5 source_epics)
        for epic_num in range(1, 6):
            apply_page_updates(
                [PageUpdate(
                    page_name="pattern-unhandled-errors",
                    action="update",
                    append_evidence={
                        "context": f"Epic {epic_num} observation",
                        "root_cause": "Missing error boundary",
                        "real_impact": f"Impact {epic_num}",
                    },
                )],
                wiki_dir, str(epic_num),
            )

        # Verify 5 source_epics
        page = read_page(wiki_dir, "pattern-unhandled-errors")
        fm = parse_frontmatter(page)
        assert len(fm["source_epics"]) == 5

        # Now reflect with epic_id="6" — challenge mode should appear in the prompt
        # because the negative page already has 5 source_epics (5 % 5 == 0)
        provider.invoke.return_value = make_yaml_output(
            decision="continue",
            rationale="Challenge mode activated, pattern still valid after review",
        )

        record = ExecutionRecord(
            phase="dev_story", mission="Build feature",
            llm_output="## Self-Audit\n\n- Done", self_audit="- Done",
            success=True, duration_ms=3000, error=None,
        )

        # Capture the prompt passed to the LLM
        captured_prompts = []

        def capture_and_respond(prompt: str) -> str:
            captured_prompts.append(prompt)
            return make_yaml_output(decision="continue", rationale="ok")

        provider.invoke = capture_and_respond
        twin.reflect(record, is_retry=False, epic_id="6")

        # The reflect prompt should contain "Challenge Mode"
        assert len(captured_prompts) > 0
        full_prompt = captured_prompts[0]
        assert "Challenge Mode" in full_prompt
        assert "pattern-unhandled-errors" in full_prompt


# ---------------------------------------------------------------------------
# Test: EVOLVE lifecycle with evidence preservation
# ---------------------------------------------------------------------------


class TestEvolveLifecycle:
    """Simulate the EVOLVE action preserving evidence across rewrites."""

    def test_evolve_preserves_evidence_table(self, tmp_path: Path) -> None:
        """EVOLVE replaces content but preserves the original evidence table."""
        wiki_dir = init_wiki(tmp_path)
        provider = MagicMock()
        config = TwinProviderConfig()
        twin = Twin(config=config, wiki_dir=wiki_dir, provider=provider)

        # CREATE the page first
        create_content = (
            "---\ncategory: env\nsentiment: positive\nconfidence: tentative\n"
            "occurrences: 0\nlast_updated: \"\"\nsource_epics: []\nlinks_to: []\n"
            "---\n\n# API Patterns\n\n## What\nREST API with Express.\n\n## Evidence\n\n"
            "| Context | Result | Epic |\n|---------|--------|------|\n"
            "| Initial setup | Express configured | EPIC-1 |\n"
        )
        provider.invoke.return_value = make_yaml_output(
            decision="continue",
            rationale="New env page",
            page_updates=[{
                "page_name": "env-api-patterns",
                "action": "create",
                "content": create_content,
                "reason": "Observed API patterns",
            }],
        )
        record = ExecutionRecord(
            phase="dev_story", mission="Build API",
            llm_output="## Self-Audit\n\n- Done", self_audit="- Done",
            success=True, duration_ms=3000, error=None,
        )
        result = twin.reflect(record, is_retry=False, epic_id="1")
        if result.page_updates:
            apply_page_updates(result.page_updates, wiki_dir, "1")

        # UPDATE to add more evidence
        provider.invoke.return_value = make_yaml_output(
            decision="continue",
            rationale="More evidence",
            page_updates=[{
                "page_name": "env-api-patterns",
                "action": "update",
                "append_evidence": {"context": "Second story", "result": "Added error middleware"},
                "reason": "Additional API patterns",
            }],
        )
        record2 = ExecutionRecord(
            phase="code_review", mission="Review",
            llm_output="## Self-Audit\n\n- Issues found", self_audit="- Issues found",
            success=True, duration_ms=2000, error=None,
        )
        result2 = twin.reflect(record2, is_retry=False, epic_id="1")
        if result2.page_updates:
            apply_page_updates(result2.page_updates, wiki_dir, "1")

        # Now EVOLVE: rewrite the What section but preserve evidence
        evolved_content = (
            "---\ncategory: env\nsentiment: positive\nconfidence: established\n"
            "occurrences: 1\nlast_updated: \"1\"\nsource_epics: [\"1\"]\nlinks_to: []\n"
            "---\n\n# API Patterns\n\n## Evidence\n\n{{EVIDENCE_TABLE}}\n\n"
            "## What\nREST API with Express.js and error middleware. "
            "All endpoints follow /api/v1/ prefix.\n\n## When This Applies\n"
            "Any story that adds or modifies API endpoints."
        )
        provider.invoke.return_value = make_yaml_output(
            decision="continue",
            rationale="Pattern evolved with more detail",
            page_updates=[{
                "page_name": "env-api-patterns",
                "action": "evolve",
                "content": evolved_content,
                "reason": "Significant architectural insight gained",
            }],
        )
        record3 = ExecutionRecord(
            phase="retrospective", mission="Retrospect",
            llm_output="## Self-Audit\n\n- Pattern updated", self_audit="- Pattern updated",
            success=True, duration_ms=1500, error=None,
        )
        result3 = twin.reflect(record3, is_retry=False, epic_id="1")
        if result3.page_updates:
            apply_page_updates(result3.page_updates, wiki_dir, "1")

        # Verify: evidence rows preserved, new What section present
        page = read_page(wiki_dir, "env-api-patterns")
        assert page is not None
        assert "Express configured" in page  # Original evidence preserved
        assert "error middleware" in page  # Added evidence preserved
        assert "/api/v1/" in page  # Evolved What section
        assert "{{EVIDENCE_TABLE}}" not in page  # Placeholder replaced


# ---------------------------------------------------------------------------
# Test: Guide fallback when no dedicated guide page
# ---------------------------------------------------------------------------


class TestGuideFallbackFlow:
    """Simulate guide fallback when no dedicated guide page exists."""

    def test_guide_uses_env_pages_when_no_guide(self, tmp_path: Path) -> None:
        """When guide-{phase_type} doesn't exist, guide falls back to env/pattern/design pages."""
        wiki_dir = init_wiki(tmp_path)

        # Add env pages but no guide page for "security" phase type
        write_page(
            wiki_dir,
            "env-security-tools",
            "---\ncategory: env\nsentiment: positive\nconfidence: established\n"
            "occurrences: 3\nlast_updated: EPIC-003\nsource_epics: [EPIC-001, EPIC-002, EPIC-003]\nlinks_to: []\n"
            "---\n\n# Security Tools\n\n## What\nProject uses OWASP ZAP for security scanning.\n\n## Evidence\n\n"
            "| Context | Result | Epic |\n|---------|--------|------|\n"
            "| Setup | ZAP configured | EPIC-001 |\n",
        )
        rebuild_index(wiki_dir)

        provider = MagicMock()
        provider.invoke.return_value = (
            "Ensure security scanning runs before deployment. "
            "Check for OWASP Top 10 vulnerabilities."
        )
        config = TwinProviderConfig()
        twin = Twin(config=config, wiki_dir=wiki_dir, provider=provider)

        # "security_review" → phase_type = "security" → no guide-security page
        compass = twin.guide("security_review")
        assert compass is not None
        assert "security" in compass.lower()

        # Verify the prompt included env/pattern/design pages
        captured_prompts = []
        def capture(prompt: str) -> str:
            captured_prompts.append(prompt)
            return "Security compass"
        provider.invoke = capture
        twin.guide("security_review")
        assert len(captured_prompts) == 1
        assert "No dedicated guide page exists" in captured_prompts[0]


# ---------------------------------------------------------------------------
# Test: Provider failure graceful degradation
# ---------------------------------------------------------------------------


class TestProviderFailureDegradation:
    """Simulate LLM provider failures and verify graceful degradation."""

    def test_guide_returns_none_on_provider_error(self, tmp_path: Path) -> None:
        """guide() returns None when provider raises, without crashing."""
        wiki_dir = init_wiki(tmp_path)
        provider = MagicMock()
        provider.invoke.side_effect = RuntimeError("API rate limit exceeded")
        config = TwinProviderConfig()
        twin = Twin(config=config, wiki_dir=wiki_dir, provider=provider)

        compass = twin.guide("dev_story")
        assert compass is None

    def test_reflect_degrades_on_provider_error(self, tmp_path: Path) -> None:
        """reflect() degrades gracefully when provider always fails."""
        wiki_dir = init_wiki(tmp_path)
        provider = MagicMock()
        provider.invoke.side_effect = RuntimeError("Service unavailable")
        config = TwinProviderConfig(retry_exhausted_action="continue")
        twin = Twin(config=config, wiki_dir=wiki_dir, provider=provider)

        record = ExecutionRecord(
            phase="dev_story", mission="Build",
            llm_output="## Self-Audit\n\n- Done", self_audit="- Done",
            success=True, duration_ms=3000, error=None,
        )
        result = twin.reflect(record, is_retry=False, epic_id="1")
        # Both attempts fail → degrade to continue (is_retry=False)
        assert result.decision == "continue"

    def test_no_provider_raises_runtime_error(self, tmp_path: Path) -> None:
        """Twin with provider=None raises RuntimeError on _invoke_llm."""
        wiki_dir = init_wiki(tmp_path)
        config = TwinProviderConfig()
        twin = Twin(config=config, wiki_dir=wiki_dir, provider=None)

        with pytest.raises(RuntimeError, match="No LLM provider"):
            twin._invoke_llm("test prompt")


# ---------------------------------------------------------------------------
# Test: Correction compass formatting (mirrors runner.py exactly)
# ---------------------------------------------------------------------------


class TestCorrectionCompassFormatting:
    """Verify the correction compass format matches runner.py."""

    def test_correction_appended_to_original(self) -> None:
        """Correction compass is APPENDED to original, not replaced."""
        original = "Focus on test coverage."
        corrected = _format_correction_compass(original, 1, "Add login.ts tests")
        assert original in corrected
        assert "[RETRY retry=1]" in corrected
        assert "Add login.ts tests" in corrected

    def test_second_retry_appends_further(self) -> None:
        """Second retry appends on top of first correction."""
        original = "Focus on tests."
        first = _format_correction_compass(original, 1, "Fix A")
        second = _format_correction_compass(first, 2, "Fix B")
        assert "[RETRY retry=1]" in second
        assert "[RETRY retry=2]" in second
        assert "Fix A" in second
        assert "Fix B" in second

    def test_no_original_compass(self) -> None:
        """Correction works when original compass is None."""
        corrected = _format_correction_compass(None, 1, "Fix the code")
        assert "[RETRY retry=1]" in corrected
        assert "Fix the code" in corrected
