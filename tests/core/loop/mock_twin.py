"""Mock components for testing Twin production code paths.

Provides FakeTwin, FakeHandler, FakeWikiDir, and install_fake_handler
to test _execute_phase_with_twin, build_execution_record, apply_page_updates,
and compass injection without real LLM calls or full handler initialization.
"""

from pathlib import Path
from typing import Any

from bmad_assist.core.loop.dispatch import _handler_instances, _handlers_initialized
from bmad_assist.core.loop.types import PhaseResult
from bmad_assist.twin.config import TwinProviderConfig
from bmad_assist.twin.twin import DriftAssessment, PageUpdate, TwinResult


class FakeTwin:
    """Simulates the Twin interface (guide, reflect, config, wiki_dir) without LLM calls.

    Configurable via constructor parameters to control behavior precisely.
    """

    def __init__(
        self,
        *,
        guide_return: str | None = "compass",
        reflect_sequence: list[TwinResult] | None = None,
        page_updates: list[PageUpdate] | None = None,
        reflect_exception: Exception | None = None,
        max_retries: int = 2,
        retry_exhausted_action: str = "halt",
        wiki_dir: Path | None = None,
    ) -> None:
        self.guide_return = guide_return
        self._reflect_sequence = reflect_sequence or [
            TwinResult(decision="continue", rationale="ok")
        ]
        self.page_updates = page_updates
        self.reflect_exception = reflect_exception
        self.reflect_call_count = 0
        self.last_record = None

        self._config = TwinProviderConfig(
            enabled=True,
            max_retries=max_retries,
            retry_exhausted_action=retry_exhausted_action,
        )
        self._wiki_dir = wiki_dir or Path("/fake/wiki")

    @property
    def config(self) -> TwinProviderConfig:
        return self._config

    @property
    def wiki_dir(self) -> Path:
        return self._wiki_dir

    def guide(self, phase_type: str) -> str | None:
        """Return configured compass value."""
        return self.guide_return

    def reflect(
        self,
        record: Any,
        is_retry: bool = False,
        epic_id: str | None = None,
    ) -> TwinResult:
        """Iterate through reflect_sequence, capturing record and counting calls."""
        if self.reflect_exception is not None:
            raise self.reflect_exception

        self.last_record = record
        self.reflect_call_count += 1

        idx = min(self.reflect_call_count - 1, len(self._reflect_sequence) - 1)
        result = self._reflect_sequence[idx]

        # Inject page_updates if configured
        if self.page_updates is not None:
            result = TwinResult(
                decision=result.decision,
                rationale=result.rationale,
                drift_assessment=result.drift_assessment,
                page_updates=self.page_updates,
            )

        return result


class FakeHandler:
    """Simulates a real handler: instance with execute() bound method.

    Reads self._compass (injected by dispatch.execute_phase) and returns
    a PhaseResult with configurable response and duration_ms.
    """

    def __init__(
        self,
        *,
        response: str = "handler output",
        duration_ms: int = 100,
    ) -> None:
        self._compass = None
        self._response = response
        self._duration_ms = duration_ms
        self.compass_seen = None

    def execute(self, state: Any) -> PhaseResult:
        """Read _compass injected by dispatch, record it, return PhaseResult."""
        self.compass_seen = self._compass
        return PhaseResult.ok(
            outputs={"response": self._response, "duration_ms": self._duration_ms}
        )


class FakeWikiDir:
    """Helper to create a minimal wiki directory structure for I/O tests."""

    @staticmethod
    def create(tmp_path: Path) -> Path:
        """Create a wiki directory with INDEX.md and return the Path."""
        wiki_dir = tmp_path / "wiki"
        wiki_dir.mkdir(parents=True, exist_ok=True)

        index_content = """---
category: index
---

# Experience Index

(No pages yet)
"""
        (wiki_dir / "INDEX.md").write_text(index_content)
        return wiki_dir


def install_fake_handler(phase: Any, handler: FakeHandler) -> None:
    """Patch dispatch._handler_instances and _handlers_initialized to inject a FakeHandler.

    This allows execute_phase() to find the handler via get_handler() → bound method,
    and _compass injection to work through the real code path.
    """
    import bmad_assist.core.loop.dispatch as dispatch

    dispatch._handler_instances[phase] = handler
    dispatch._handlers_initialized = True
