"""Tests for AIStoryAnalyzer using mocked OpenAI responses."""

import json
from unittest.mock import MagicMock

import pytest

from src.client.models import StoryItem, Subitem
from src.config import Settings
from src.services.ai_analyzer import AIAnalyzerError, AIStoryAnalyzer
from src.services.task_models import StoryAnalysisResult


@pytest.fixture
def mock_story() -> StoryItem:
    return StoryItem(
        id="STORY-300",
        name="User Profile Avatar Upload",
        description="Users can upload an avatar image (JPEG/PNG, max 2MB) to customize their profile.",
        acceptance_criteria="- File size validated on client and server\n- Image saved to S3 and CDN URL returned",
        team_id="T1",
        project_id="P1",
        sprint_id="S1",
        subitems=[Subitem(id="S1", name="Old Subtask")],
    )


def test_ai_analyzer_missing_api_key() -> None:
    settings = Settings(openai_api_key="")
    analyzer = AIStoryAnalyzer(settings=settings)
    with pytest.raises(AIAnalyzerError) as exc:
        _ = analyzer.client
    assert "OPENAI_API_KEY" in str(exc.value)


def test_ai_analyzer_success(mock_story: StoryItem) -> None:
    mock_openai = MagicMock()
    mock_choice = MagicMock()
    mock_response = MagicMock()

    analysis_payload = {
        "business_objective": "Enable users to upload custom profile avatars",
        "summary": "Implement frontend avatar uploader and backend image validation/storage API",
        "requires_frontend": True,
        "requires_backend": True,
        "frontend_responsibilities": ["Avatar dropzone", "Client file size validation"],
        "backend_responsibilities": ["S3 upload handler", "Profile model update"],
        "frontend_task": {
            "title_suffix": "Implement Avatar Upload Component and Preview UI",
            "objective": "Build avatar upload UI with client-side validation",
            "scope": "Drag and drop uploader, preview image before upload",
            "expected_behavior": "User selects image, sees preview, and triggers upload",
            "dependencies": "BE Avatar Upload API",
            "testing_considerations": "Component tests for file type and size validation",
            "acceptance_criteria": ["Allows only JPEG/PNG under 2MB", "Displays error if invalid"],
        },
        "backend_tasks": [
            {
                "boundary": "API",
                "title_suffix": "Create Avatar Upload and S3 Storage Endpoint",
                "objective": "Provide secure endpoint for avatar upload",
                "scope": "Validate image MIME type, stream to S3, generate presigned URL",
                "expected_behavior": "Returns 200 with avatar URL on success, 400 on invalid format",
                "dependencies": "S3 bucket configuration",
                "testing_considerations": "Unit tests with mocked S3 client; integration test with test images",
                "acceptance_criteria": ["Rejects files over 2MB", "Stores image key in user profile record"],
            }
        ],
    }

    mock_choice.message.content = json.dumps(analysis_payload)
    mock_response.choices = [mock_choice]
    mock_openai.chat.completions.create.return_value = mock_response

    settings = Settings(openai_api_key="test-key")
    analyzer = AIStoryAnalyzer(settings=settings, openai_client=mock_openai)

    result = analyzer.analyze_story(mock_story)
    assert isinstance(result, StoryAnalysisResult)
    assert result.requires_frontend is True
    assert result.requires_backend is True
    assert result.frontend_task is not None
    assert len(result.backend_tasks) == 1
    assert "Avatar Upload Component" in result.frontend_task.title_suffix


def test_ai_analyzer_short_description_flags_ambiguity() -> None:
    short_story = StoryItem(
        id="STORY-SHORT",
        name="Fix button",
        description="Fix the button",
        team_id="T1",
        project_id="P1",
        sprint_id="S1",
    )

    mock_openai = MagicMock()
    mock_choice = MagicMock()
    mock_response = MagicMock()
    mock_choice.message.content = json.dumps(
        {
            "business_objective": "Fix button",
            "summary": "Fix button",
            "requires_frontend": True,
            "requires_backend": False,
            "ambiguities": [],
        }
    )
    mock_response.choices = [mock_choice]
    mock_openai.chat.completions.create.return_value = mock_response

    settings = Settings(openai_api_key="test-key")
    analyzer = AIStoryAnalyzer(settings=settings, openai_client=mock_openai)
    res = analyzer.analyze_story(short_story)

    # Must flag ambiguity due to brief description
    assert len(res.ambiguities) > 0
    assert any("brief" in a.lower() or "underspecified" in a.lower() for a in res.ambiguities)
