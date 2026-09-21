"""Tests for StoryService and context auto-discovery."""

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from src.client.models import Project, Sprint, StoryItem, Subitem, Team
from src.client.sprints_api import SprintsAPI
from src.client.zoho_client import SprintsNotFoundError
from src.config import Settings
from src.services.story_service import StoryContext, StoryService, StoryServiceError


@pytest.fixture
def mock_settings(tmp_path: Path) -> Settings:
    return Settings(
        zoho_client_id="dummy",
        zoho_client_secret="dummy",
        runtime_dir=tmp_path / ".runtime",
    )


def test_resolve_context_explicit_args(mock_settings: Settings) -> None:
    service = StoryService(mock_settings, sprints_api=MagicMock())
    ctx = service.resolve_context(
        story_id="STORY-100",
        team_id="T1",
        project_id="P1",
        sprint_id="S1",
    )
    assert ctx.story_id == "STORY-100"
    assert ctx.team_id == "T1"
    assert ctx.project_id == "P1"
    assert ctx.sprint_id == "S1"


def test_resolve_context_auto_discovery(mock_settings: Settings) -> None:
    mock_api = MagicMock(spec=SprintsAPI)
    mock_api.list_teams.return_value = [Team(id="T_ONLY", name="Single Team")]
    mock_api.list_projects.return_value = [Project(id="P_ONLY", name="Single Project")]
    mock_api.list_sprints.return_value = [Sprint(id="S_ONLY", name="Single Sprint")]
    mock_api.get_backlog_id.return_value = None
    mock_api.get_item.return_value = StoryItem(
        id="STORY-200", name="Story", team_id="T_ONLY", project_id="P_ONLY", sprint_id="S_ONLY"
    )

    service = StoryService(mock_settings, sprints_api=mock_api)
    ctx = service.resolve_context(story_id="STORY-200")

    assert ctx.team_id == "T_ONLY"
    assert ctx.project_id == "P_ONLY"
    assert ctx.sprint_id == "S_ONLY"


def test_resolve_context_multi_sprint_search(mock_settings: Settings) -> None:
    mock_api = MagicMock(spec=SprintsAPI)
    mock_api.get_backlog_id.return_value = None
    mock_api.list_sprints.return_value = [
        Sprint(id="S_OLD", name="Sprint Old"),
        Sprint(id="S_CURR", name="Sprint Current"),
    ]

    # First sprint check raises 404, second sprint succeeds
    def mock_get_item(t, p, s, item_id):
        if s == "S_OLD":
            raise SprintsNotFoundError("Not in this sprint", status_code=404)
        return StoryItem(id=item_id, name="Story", team_id=t, project_id=p, sprint_id=s)

    mock_api.get_item.side_effect = mock_get_item

    service = StoryService(mock_settings, sprints_api=mock_api)
    ctx = service.resolve_context(
        story_id="STORY-FIND",
        team_id="T1",
        project_id="P1",
    )
    assert ctx.sprint_id == "S_CURR"


def test_fetch_story_and_ac_extraction(mock_settings: Settings) -> None:
    mock_api = MagicMock(spec=SprintsAPI)
    desc_text = (
        "User should be able to reset password.\n\n"
        "### Acceptance Criteria\n"
        "- Email containing reset token is sent\n"
        "- Token expires in 15 minutes\n"
    )
    mock_api.get_item.return_value = StoryItem(
        id="STORY-PW",
        name="Password Reset Flow",
        description=desc_text,
        team_id="T1",
        project_id="P1",
        sprint_id="S1",
        subitems=[Subitem(id="SUB-1", name="FE - Reset Form")],
    )

    service = StoryService(mock_settings, sprints_api=mock_api)
    story = service.fetch_story("STORY-PW", team_id="T1", project_id="P1", sprint_id="S1")

    assert story.id == "STORY-PW"
    assert story.name == "Password Reset Flow"
    assert story.acceptance_criteria is not None
    assert "- Email containing reset token is sent" in story.acceptance_criteria
    assert len(story.subitems) == 1


def test_fetch_story_empty_id_raises(mock_settings: Settings) -> None:
    service = StoryService(mock_settings, sprints_api=MagicMock())
    with pytest.raises(StoryServiceError) as exc:
        service.fetch_story("   ")
    assert "empty" in str(exc.value)
