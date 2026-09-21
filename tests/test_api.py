"""Tests for FastAPI backend endpoints."""

import pytest
from fastapi.testclient import TestClient
from unittest.mock import MagicMock

from src.api.app import app
from src.api.routes.auth import get_oauth_client
from src.api.routes.stories import get_story_service
from src.auth.oauth_client import AuthStatus
from src.client.models import StoryItem, Subitem
from src.services.story_service import StoryServiceError

client = TestClient(app)


def test_health_check() -> None:
    """Verify health endpoint."""
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert "version" in data


def test_auth_status_endpoint() -> None:
    """Verify /api/v1/auth/status returns sanitized response."""
    mock_oauth = MagicMock()
    mock_oauth.get_status.return_value = AuthStatus(
        is_authenticated=True,
        has_refresh_token=True,
        is_expired=False,
        expires_at_iso="2026-09-21T16:00:00Z",
        api_domain="https://sprintsapi.zoho.in",
        accounts_url="https://accounts.zoho.in",
        message="Authenticated and valid",
    )

    app.dependency_overrides[get_oauth_client] = lambda: mock_oauth
    try:
        response = client.get("/api/v1/auth/status")
        assert response.status_code == 200
        data = response.json()
        assert data["is_authenticated"] is True
        assert data["has_refresh_token"] is True
        assert data["expires_at_iso"] == "2026-09-21T16:00:00Z"
        assert "client_secret" not in data
        assert "refresh_token" not in data
    finally:
        app.dependency_overrides.clear()


def test_get_story_details_success() -> None:
    """Verify /api/v1/stories/{story_id} returns story and subitems."""
    mock_story_service = MagicMock()
    mock_story = StoryItem(
        id="12345",
        name="Sample User Story",
        description="Sample story description text.",
        acceptance_criteria="Given when then.",
        team_id="T1",
        project_id="P1",
        sprint_id="S1",
        item_type_id="IT1",
        item_type_name="Story",
        priority_id="PR1",
        priority_name="High",
        status="In Progress",
        subitems=[
            Subitem(
                id="SUB1",
                name="FE - Task 1",
                item_type_id="IT2",
                item_type_name="Task",
                priority_id="PR1",
                priority_name="High",
                status="To Do",
            )
        ],
    )
    mock_story_service.fetch_story.return_value = mock_story

    app.dependency_overrides[get_story_service] = lambda: mock_story_service
    try:
        response = client.get("/api/v1/stories/12345")
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == "12345"
        assert data["name"] == "Sample User Story"
        assert data["description"] == "Sample story description text."
        assert data["acceptance_criteria"] == "Given when then."
        assert len(data["subitems"]) == 1
        assert data["subitems"][0]["name"] == "FE - Task 1"
    finally:
        app.dependency_overrides.clear()


def test_get_story_details_not_found() -> None:
    """Verify 404 is returned when story is not found."""
    mock_story_service = MagicMock()
    mock_story_service.fetch_story.side_effect = StoryServiceError("Story '99999' not found in workspace.")

    app.dependency_overrides[get_story_service] = lambda: mock_story_service
    try:
        response = client.get("/api/v1/stories/99999")
        assert response.status_code == 404
        data = response.json()
        assert "not found" in data["detail"].lower()
    finally:
        app.dependency_overrides.clear()


def test_get_story_details_empty_id() -> None:
    """Verify 400 is returned for whitespace story ID."""
    response = client.get("/api/v1/stories/%20")
    assert response.status_code == 400
    assert "cannot be empty" in response.json()["detail"].lower()
