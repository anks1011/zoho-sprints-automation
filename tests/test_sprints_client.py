"""Tests for Zoho Sprints HTTP client and SprintsAPI methods."""

from unittest.mock import MagicMock, patch

import pytest
import requests

from src.auth.oauth_client import ZohoOAuthClient
from src.auth.token_store import StoredToken
from src.client.sprints_api import SprintsAPI
from src.client.zoho_client import (
    SprintsAPIError,
    SprintsNotFoundError,
    SprintsRateLimitError,
    SprintsValidationError,
    ZohoHTTPClient,
)
from src.config import Settings


@pytest.fixture
def mock_settings() -> Settings:
    return Settings(
        zoho_client_id="dummy_client",
        zoho_client_secret="dummy_secret",
        zoho_api_base_url="https://sprintsapi.zoho.in/zsapi",
        zoho_access_token="initial_access_token",
    )


@pytest.fixture
def mock_oauth_client(mock_settings: Settings) -> MagicMock:
    client = MagicMock(spec=ZohoOAuthClient)
    client.get_valid_access_token.return_value = "valid_token_xyz"
    client.refresh_access_token.return_value = StoredToken(access_token="refreshed_token_abc")
    return client


def test_http_client_request_headers(mock_settings: Settings, mock_oauth_client: MagicMock) -> None:
    session = MagicMock()
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {"teams": [{"teamId": "101", "teamName": "Alpha"}]}
    session.request.return_value = mock_resp

    http_client = ZohoHTTPClient(mock_settings, oauth_client=mock_oauth_client, session=session)
    result = http_client.request("GET", "teams/")

    assert result == {"teams": [{"teamId": "101", "teamName": "Alpha"}]}
    session.request.assert_called_once()
    args, kwargs = session.request.call_args
    assert kwargs["headers"]["Authorization"] == "Zoho-oauthtoken valid_token_xyz"


def test_http_client_401_refresh_and_retry(mock_settings: Settings, mock_oauth_client: MagicMock) -> None:
    session = MagicMock()
    # First response: 401 Unauthorized
    resp_401 = MagicMock()
    resp_401.status_code = 401
    resp_401.text = "Unauthorized"

    # Second response: 200 OK after refresh
    resp_200 = MagicMock()
    resp_200.status_code = 200
    resp_200.json.return_value = {"data": "success"}

    session.request.side_effect = [resp_401, resp_200]

    http_client = ZohoHTTPClient(mock_settings, oauth_client=mock_oauth_client, session=session)
    res = http_client.request("GET", "teams/")

    assert res == {"data": "success"}
    mock_oauth_client.refresh_access_token.assert_called_once()
    assert session.request.call_count == 2


def test_http_client_404_raises_not_found(mock_settings: Settings, mock_oauth_client: MagicMock) -> None:
    session = MagicMock()
    resp_404 = MagicMock()
    resp_404.status_code = 404
    resp_404.text = "Story not found"
    session.request.return_value = resp_404

    http_client = ZohoHTTPClient(mock_settings, oauth_client=mock_oauth_client, session=session)
    with pytest.raises(SprintsNotFoundError) as exc:
        http_client.request("GET", "team/1/projects/2/sprints/3/item/999/")
    assert exc.value.status_code == 404


def test_http_client_429_rate_limit(mock_settings: Settings, mock_oauth_client: MagicMock) -> None:
    session = MagicMock()
    resp_429 = MagicMock()
    resp_429.status_code = 429
    resp_429.headers = {"Retry-After": "1"}
    session.request.return_value = resp_429

    http_client = ZohoHTTPClient(
        mock_settings, oauth_client=mock_oauth_client, session=session, max_retries=2, backoff_factor=0.01
    )
    with patch("time.sleep") as mock_sleep:
        with pytest.raises(SprintsRateLimitError):
            http_client.request("GET", "teams/")
        assert mock_sleep.called


def test_http_client_zoho_error_in_200_body(mock_settings: Settings, mock_oauth_client: MagicMock) -> None:
    session = MagicMock()
    resp = MagicMock()
    resp.status_code = 200
    resp.json.return_value = {
        "status": "error",
        "message": "Invalid project ID specified",
        "code": "7001",
    }
    session.request.return_value = resp

    http_client = ZohoHTTPClient(mock_settings, oauth_client=mock_oauth_client, session=session)
    with pytest.raises(SprintsAPIError) as exc:
        http_client.request("GET", "team/1/projects/invalid/")
    assert "Invalid project ID" in str(exc.value)
    assert exc.value.error_code == "7001"


def test_sprints_api_list_teams() -> None:
    mock_http = MagicMock()
    mock_http.request.return_value = {
        "teams": [
            {"teamId": "T1001", "teamName": "Core Engineering"},
            {"id": "T1002", "name": "Frontend Guild"},
        ]
    }
    api = SprintsAPI(http_client=mock_http)
    teams = api.list_teams()

    assert len(teams) == 2
    assert teams[0].id == "T1001"
    assert teams[0].name == "Core Engineering"
    assert teams[1].id == "T1002"
    assert teams[1].name == "Frontend Guild"


def test_sprints_api_list_projects() -> None:
    mock_http = MagicMock()
    mock_http.request.return_value = {
        "projects": [
            {"projectId": "P201", "projectName": "Billing Platform", "shortName": "BILL", "status": "active"}
        ]
    }
    api = SprintsAPI(http_client=mock_http)
    projects = api.list_projects(team_id="T1001")

    assert len(projects) == 1
    assert projects[0].id == "P201"
    assert projects[0].name == "Billing Platform"
    assert projects[0].prefix == "BILL"


def test_sprints_api_list_sprints() -> None:
    mock_http = MagicMock()
    mock_http.request.return_value = {
        "sprints": [
            {"sprintId": "S301", "sprintName": "Sprint 24", "status": "active"}
        ]
    }
    api = SprintsAPI(http_client=mock_http)
    sprints = api.list_sprints(team_id="T1001", project_id="P201")

    assert len(sprints) == 1
    assert sprints[0].id == "S301"
    assert sprints[0].name == "Sprint 24"


def test_sprints_api_get_item_with_subitems() -> None:
    mock_http = MagicMock()
    mock_http.request.return_value = {
        "itemDetail": {
            "itemId": "ITEM-501",
            "name": "User Registration Flow",
            "description": "Implement user signup and email verification",
            "subItems": [
                {
                    "subItemId": "SUB-101",
                    "name": "FE - User Signup Form",
                    "description": "Design form UI",
                }
            ],
        }
    }
    api = SprintsAPI(http_client=mock_http)
    story = api.get_item(team_id="T1", project_id="P1", sprint_id="S1", item_id="ITEM-501")

    assert story.id == "ITEM-501"
    assert story.name == "User Registration Flow"
    assert len(story.subitems) == 1
    assert story.subitems[0].id == "SUB-101"
    assert story.subitems[0].name == "FE - User Signup Form"


def test_sprints_api_create_subitem() -> None:
    mock_http = MagicMock()
    mock_http.request.return_value = {
        "subItemDetail": {
            "subItemId": "SUB-999",
            "name": "BE - 01 - User Model Migration",
        }
    }
    api = SprintsAPI(http_client=mock_http)
    created = api.create_subitem(
        team_id="T1",
        project_id="P1",
        sprint_id="S1",
        item_id="ITEM-501",
        name="BE - 01 - User Model Migration",
        item_type_id="IT_TASK",
        priority_id="PRIO_HIGH",
        description="Run DB migration",
        point=2.0,
    )

    assert created.id == "SUB-999"
    assert created.name == "BE - 01 - User Model Migration"
    mock_http.request.assert_called_once()
    _, kwargs = mock_http.request.call_args
    assert kwargs["data"]["name"] == "BE - 01 - User Model Migration"
    assert kwargs["data"]["projitemtypeid"] == "IT_TASK"
    assert kwargs["data"]["projpriorityid"] == "PRIO_HIGH"


def test_sprints_api_update_item_status() -> None:
    mock_http = MagicMock()
    mock_http.request.return_value = {"status": "success"}
    api = SprintsAPI(http_client=mock_http)
    res = api.update_item_status("T1", "P1", "S1", "ITEM-1", "STAT-DEV")

    assert res["status"] == "success"
    mock_http.request.assert_called_once_with(
        "POST",
        "team/T1/projects/P1/sprints/S1/item/ITEM-1/",
        data={"statusid": "STAT-DEV"},
    )


def test_sprints_api_delete_item() -> None:
    mock_http = MagicMock()
    mock_http.request.return_value = {"status": "success"}
    api = SprintsAPI(http_client=mock_http)
    res = api.delete_item("T1", "P1", "S1", "ITEM-1")

    assert res["status"] == "success"
    mock_http.request.assert_called_once_with(
        "DELETE",
        "team/T1/projects/P1/sprints/S1/item/ITEM-1/",
    )
