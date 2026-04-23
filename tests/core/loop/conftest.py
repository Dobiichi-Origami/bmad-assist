"""Pytest fixtures for bmad_assist.core.loop tests.

Shared fixtures extracted from test_loop.py as part of loop.py refactor.
"""

from collections.abc import Iterator
from unittest.mock import MagicMock, patch

import pytest

from bmad_assist.core.loop.signals import reset_shutdown


@pytest.fixture(autouse=True)
def reset_shutdown_state() -> None:
    """Reset shutdown state before and after each test.

    This fixture ensures test isolation by clearing the shutdown state.
    The autouse=True makes it run automatically for all tests
    in the loop directory.
    """
    reset_shutdown()
    yield
    reset_shutdown()


@pytest.fixture(autouse=True)
def reset_handler_registry() -> None:
    """Reset handler registry before and after each test.

    init_handlers() mutates module-level state (_handlers_initialized,
    _handler_instances) that persists across test runs. Without resetting,
    a test that calls run_loop() (which calls init_handlers()) pollutes
    subsequent tests that assert on get_handler() returning stub handlers.
    """
    from bmad_assist.core.loop.dispatch import reset_handlers
    reset_handlers()
    yield
    reset_handlers()


@pytest.fixture(autouse=True)
def auto_continue_prompts() -> Iterator[None]:
    """Auto-continue all interactive prompts in tests.

    This fixture patches checkpoint_and_prompt to always return True,
    simulating user pressing Enter to continue. Tests that need to
    test the prompt behavior should patch it explicitly.
    """
    with patch(
        "bmad_assist.core.loop.runner.checkpoint_and_prompt",
        return_value=True,
    ):
        yield


class CompassAwareHandler:
    """Minimal handler that records compass access during render_prompt.

    Subclasses BaseHandler behavior enough for dispatch tests without
    requiring full project setup or workflow compilation.
    """

    def __init__(self) -> None:
        self._compass: str | None = None
        self.compass_seen: str | None = None

    def __call__(self, state: object) -> object:
        """Act as handler callable: record what _compass was at call time."""
        self.compass_seen = getattr(self, "_compass", None)
        from bmad_assist.core.loop.types import PhaseResult
        return PhaseResult.ok()

    def render_prompt(self, state: object) -> str:
        """Simulate render_prompt: record what _compass was via getattr."""
        self.compass_seen = getattr(self, "_compass", None)
        compass_tag = ""
        if self.compass_seen is not None:
            compass_tag = f"<compass>{self.compass_seen}</compass>"
        return f"<mission>test</mission>{compass_tag}"


@pytest.fixture
def compass_aware_handler() -> CompassAwareHandler:
    """Provide a CompassAwareHandler instance for testing compass injection."""
    return CompassAwareHandler()
