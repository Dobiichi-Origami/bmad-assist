"""Conftest for mock loop E2E tests.

Registers shared fixtures and ensures compatibility with root conftest autouse fixtures.
"""

from __future__ import annotations

import pytest

from tests.e2e.mock_loop.helpers import (
    MockProject,
    ScriptedPhaseExecutor,
    create_e2e_config,
    create_mock_project,
)

from bmad_assist.core.config import Config
from bmad_assist.core.loop.types import PhaseResult
from bmad_assist.core.state import Phase


@pytest.fixture
def single_story_project(tmp_path) -> MockProject:
    """A project with 1 epic and 1 story."""
    return create_mock_project(tmp_path, epics=[{"id": 1, "stories": ["1.1"]}])


@pytest.fixture
def two_story_project(tmp_path) -> MockProject:
    """A project with 1 epic and 2 stories."""
    return create_mock_project(tmp_path, epics=[{"id": 1, "stories": ["1.1", "1.2"]}])


@pytest.fixture
def three_story_project(tmp_path) -> MockProject:
    """A project with 1 epic and 3 stories."""
    return create_mock_project(
        tmp_path, epics=[{"id": 1, "stories": ["1.1", "1.2", "1.3"]}]
    )


@pytest.fixture
def two_epic_project(tmp_path) -> MockProject:
    """A project with 2 epics, each with 1 story."""
    return create_mock_project(
        tmp_path,
        epics=[
            {"id": 1, "stories": ["1.1"]},
            {"id": 2, "stories": ["2.1"]},
        ],
    )


@pytest.fixture
def multi_epic_project(tmp_path) -> MockProject:
    """A project with 3 epics and varying stories."""
    return create_mock_project(
        tmp_path,
        epics=[
            {"id": 1, "stories": ["1.1", "1.2"]},
            {"id": 2, "stories": ["2.1"]},
            {"id": 3, "stories": ["3.1", "3.2"]},
        ],
    )


@pytest.fixture
def all_success_executor() -> ScriptedPhaseExecutor:
    """An executor that returns success for all phases."""
    return ScriptedPhaseExecutor()


@pytest.fixture
def e2e_config() -> Config:
    """Default E2E config with mock provider."""
    return create_e2e_config()


# Default phase sequence for assertions (from DEFAULT_LOOP_CONFIG)
DEFAULT_STORY_PHASES = [
    Phase.CREATE_STORY,
    Phase.VALIDATE_STORY,
    Phase.VALIDATE_STORY_SYNTHESIS,
    Phase.DEV_STORY,
    Phase.CODE_REVIEW,
    Phase.CODE_REVIEW_SYNTHESIS,
]

DEFAULT_TEARDOWN_PHASES = [
    Phase.RETROSPECTIVE,
]
