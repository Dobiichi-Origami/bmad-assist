"""Tests for compass injection through execute_phase() -> handler._compass.

Verifies that compass flows from execute_phase(state, compass=X) into
handler._compass attribute, and that render_prompt() can access it.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from bmad_assist.core.loop.dispatch import execute_phase
from bmad_assist.core.loop.types import PhaseResult
from bmad_assist.core.state import Phase, State


class TestExecutePhaseCompassInjection:
    """Verify execute_phase(state, compass=X) injects compass into handlers."""

    def test_compass_sets_handler_attribute(self) -> None:
        """handler._compass is set before handler(state) is called."""
        state = State(current_phase=Phase.DEV_STORY)
        seen_compass: list[str | None] = []

        def handler_side_effect(s: State) -> PhaseResult:
            # Record what _compass was at call time
            seen_compass.append(getattr(mock_handler, "_compass", None))
            return PhaseResult.ok()

        mock_handler = MagicMock(side_effect=handler_side_effect)

        with patch("bmad_assist.core.loop.dispatch.get_handler", return_value=mock_handler):
            execute_phase(state, compass="test-compass-content")

        assert seen_compass[0] == "test-compass-content"

    def test_no_compass_no_attribute_set(self) -> None:
        """When compass=None, handler._compass is NOT overwritten."""
        state = State(current_phase=Phase.DEV_STORY)
        mock_handler = MagicMock(return_value=PhaseResult.ok())
        # Pre-set a _compass value to verify dispatch doesn't clear it
        mock_handler._compass = "pre-existing"

        with patch("bmad_assist.core.loop.dispatch.get_handler", return_value=mock_handler):
            execute_phase(state, compass=None)

        # _compass should still be the pre-existing value
        assert mock_handler._compass == "pre-existing"

    def test_compass_accessible_in_overridden_execute(self) -> None:
        """Handler overriding execute(self, state) can read self._compass."""
        state = State(current_phase=Phase.DEV_STORY)
        seen_compass: list[str | None] = []

        class CustomHandler:
            def __call__(self, s: State) -> PhaseResult:
                seen_compass.append(getattr(self, "_compass", None))
                return PhaseResult.ok()

        handler = CustomHandler()

        with patch("bmad_assist.core.loop.dispatch.get_handler", return_value=handler):
            execute_phase(state, compass="custom-compass")

        assert seen_compass[0] == "custom-compass"

    def test_compass_flows_into_render_prompt(
        self, compass_aware_handler: "CompassAwareHandler",  # type: ignore[name-defined]  # noqa: F821
    ) -> None:
        """render_prompt() produces output with compass content via CompilerContext(compass=...)."""
        state = State(current_phase=Phase.DEV_STORY)

        with patch(
            "bmad_assist.core.loop.dispatch.get_handler",
            return_value=compass_aware_handler,
        ):
            execute_phase(state, compass="navigation-data")

        # render_prompt sees the compass
        prompt = compass_aware_handler.render_prompt(state)
        assert "<compass>navigation-data</compass>" in prompt

    def test_no_compass_no_tag_in_prompt(
        self, compass_aware_handler: "CompassAwareHandler",  # type: ignore[name-defined]  # noqa: F821
    ) -> None:
        """No compass → no <compass> tag in rendered prompt."""
        state = State(current_phase=Phase.DEV_STORY)

        with patch(
            "bmad_assist.core.loop.dispatch.get_handler",
            return_value=compass_aware_handler,
        ):
            execute_phase(state, compass=None)

        # compass_seen should remain None (never set by dispatch)
        # and render_prompt should have no compass tag
        prompt = compass_aware_handler.render_prompt(state)
        assert "<compass>" not in prompt

    def test_base_handler_execute_preserves_preset_compass(
        self, compass_aware_handler: "CompassAwareHandler",  # type: ignore[name-defined]  # noqa: F821
    ) -> None:
        """BaseHandler.execute(state, compass=None) does NOT overwrite dispatch-set _compass.

        In dispatch.py, compass is injected BEFORE handler(state) is called.
        If the handler's execute() also sets self._compass, the dispatch-set
        value should already be there and the handler should preserve it.
        """
        state = State(current_phase=Phase.DEV_STORY)

        with patch(
            "bmad_assist.core.loop.dispatch.get_handler",
            return_value=compass_aware_handler,
        ):
            # Dispatch sets handler._compass = "dispatch-compass" before calling handler
            execute_phase(state, compass="dispatch-compass")

        # The handler's __call__ recorded what _compass was at call time
        assert compass_aware_handler.compass_seen == "dispatch-compass"
