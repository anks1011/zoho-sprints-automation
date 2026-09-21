"""Tests for FastAPI task plan generation, retrieval, and editing endpoints."""

import pytest
from unittest.mock import MagicMock
from fastapi.testclient import TestClient

from src.api.app import app
from src.api.routes.plans import (
    get_ai_analyzer,
    get_dup_detector,
    get_plan_store,
    get_story_service,
    get_task_generator,
)
from src.client.models import StoryItem, Subitem
from src.services.duplicate_detector import DuplicateMatch
from src.services.story_service import StoryServiceError
from src.services.task_models import (
    GeneratedTask,
    GeneratedTaskPlan,
    StoryAnalysisResult,
)

client = TestClient(app)


@pytest.fixture
def sample_story() -> StoryItem:
    return StoryItem(
        id="39713000007827664",
        name="Pre-Admissions Bulk CSV Import | Story 2 | Download the Sample CSV Template",
        description="Download sample template for pre-admissions bulk import.",
        acceptance_criteria="Given when then.",
        team_id="60043431118",
        project_id="39713000006643091",
        sprint_id="39713000007785711",
        subitems=[
            Subitem(
                id="SUB_EXISTING_1",
                name="FE - Implement Download Template Button",
            )
        ],
    )


@pytest.fixture
def sample_plan(sample_story: StoryItem) -> GeneratedTaskPlan:
    return GeneratedTaskPlan(
        plan_id="plan_test123456",
        story_id=sample_story.id,
        story_title=sample_story.name,
        story_summary="Summary of plan",
        team_id=sample_story.team_id,
        project_id=sample_story.project_id,
        sprint_id=sample_story.sprint_id,
        tasks=[
            GeneratedTask(
                id="task_fe_1",
                title="FE - Implement Download Template Button",
                task_type="FE",
                objective="Create UI button for template download.",
                scope="Implement button and disabled tooltip.",
                expected_behavior="Button triggers download or shows disabled tooltip.",
                dependencies="Layout validation API",
                testing_considerations="Test active and disabled states.",
                acceptance_criteria=["Button renders in step 2", "Downloads CSV"],
            ),
            GeneratedTask(
                id="task_be_1",
                title="BE - 01 - Implement Template Generation API",
                task_type="BE",
                index=1,
                objective="Create API endpoint to generate CSV template.",
                scope="Format headers and stream blank CSV.",
                expected_behavior="Returns 200 with CSV.",
                dependencies="Field Permission Matrix",
                testing_considerations="Test CSV header output.",
                acceptance_criteria=["Header matches layout", "1 blank row included"],
            ),
        ],
    )


def test_generate_plan_success(sample_story: StoryItem, sample_plan: GeneratedTaskPlan) -> None:
    """Verify POST /api/v1/plans/generate orchestrates services and returns plan with duplicate warnings."""
    mock_story_service = MagicMock()
    mock_story_service.fetch_story.return_value = sample_story

    mock_ai_analyzer = MagicMock()
    mock_ai_analyzer.analyze_story.return_value = StoryAnalysisResult(
        business_objective="Obj",
        summary="Summary",
        requires_frontend=True,
        requires_backend=True,
    )

    mock_task_generator = MagicMock()
    mock_task_generator.generate_plan.return_value = sample_plan

    mock_dup_detector = MagicMock()
    mock_dup_detector.analyze_plan_duplicates.return_value = [
        DuplicateMatch(
            generated_title="FE - Implement Download Template Button",
            existing_title="FE - Implement Download Template Button",
            existing_id="SUB_EXISTING_1",
            match_type="DUPLICATE_EXACT",
            similarity_score=1.0,
            recommendation="Exact duplicate detected. Review before creating.",
        )
    ]

    mock_plan_store = MagicMock()

    app.dependency_overrides[get_story_service] = lambda: mock_story_service
    app.dependency_overrides[get_ai_analyzer] = lambda: mock_ai_analyzer
    app.dependency_overrides[get_task_generator] = lambda: mock_task_generator
    app.dependency_overrides[get_dup_detector] = lambda: mock_dup_detector
    app.dependency_overrides[get_plan_store] = lambda: mock_plan_store

    try:
        response = client.post("/api/v1/plans/generate", json={"story_id": "39713000007827664"})
        assert response.status_code == 200
        data = response.json()
        assert data["plan_id"] == "plan_test123456"
        assert data["story_id"] == "39713000007827664"
        assert len(data["tasks"]) == 2
        assert len(data["duplicate_warnings"]) == 1
        assert data["duplicate_warnings"][0]["match_type"] == "DUPLICATE_EXACT"

        # Verify plan was saved locally
        mock_plan_store.save_plan.assert_called_once_with(sample_plan)

        # Verify zero secrets in response
        raw_text = response.text
        assert "client_secret" not in raw_text
        assert "refresh_token" not in raw_text
        assert "access_token" not in raw_text
    finally:
        app.dependency_overrides.clear()


def test_generate_plan_invalid_story_id() -> None:
    """Verify 422/400 for empty or whitespace story ID."""
    response = client.post("/api/v1/plans/generate", json={"story_id": "   "})
    assert response.status_code in (400, 422)


def test_generate_plan_story_not_found() -> None:
    """Verify 404 when story does not exist in workspace."""
    mock_story_service = MagicMock()
    mock_story_service.fetch_story.side_effect = StoryServiceError("Story '99999' not found in workspace.")

    app.dependency_overrides[get_story_service] = lambda: mock_story_service
    try:
        response = client.post("/api/v1/plans/generate", json={"story_id": "99999"})
        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()
    finally:
        app.dependency_overrides.clear()


def test_get_plan_success(sample_plan: GeneratedTaskPlan, sample_story: StoryItem) -> None:
    """Verify GET /api/v1/plans/{plan_id} returns saved plan."""
    mock_plan_store = MagicMock()
    mock_plan_store.load_plan.return_value = sample_plan

    mock_story_service = MagicMock()
    mock_story_service.fetch_story.return_value = sample_story

    mock_dup_detector = MagicMock()
    mock_dup_detector.analyze_plan_duplicates.return_value = []

    app.dependency_overrides[get_plan_store] = lambda: mock_plan_store
    app.dependency_overrides[get_story_service] = lambda: mock_story_service
    app.dependency_overrides[get_dup_detector] = lambda: mock_dup_detector

    try:
        response = client.get(f"/api/v1/plans/{sample_plan.plan_id}")
        assert response.status_code == 200
        data = response.json()
        assert data["plan_id"] == sample_plan.plan_id
        assert len(data["tasks"]) == 2
    finally:
        app.dependency_overrides.clear()


def test_get_plan_not_found() -> None:
    """Verify 404 when plan_id does not exist."""
    mock_plan_store = MagicMock()
    mock_plan_store.load_plan.return_value = None

    app.dependency_overrides[get_plan_store] = lambda: mock_plan_store
    try:
        response = client.get("/api/v1/plans/nonexistent_plan")
        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()
    finally:
        app.dependency_overrides.clear()


def test_update_plan_success(sample_plan: GeneratedTaskPlan) -> None:
    """Verify PUT /api/v1/plans/{plan_id} allows editing task fields and updates timestamp."""
    mock_plan_store = MagicMock()
    mock_plan_store.load_plan.return_value = sample_plan

    app.dependency_overrides[get_plan_store] = lambda: mock_plan_store

    update_payload = {
        "tasks": [
            {
                "id": "task_fe_1",
                "title": "FE - Revised Template Download Button UI",
                "task_type": "FE",
                "objective": "Revised objective for download button.",
                "scope": "Revised scope text.",
                "expected_behavior": "Revised expected behavior.",
                "dependencies": "BE - 02 Layout validation",
                "testing_considerations": "Revised tests.",
                "acceptance_criteria": ["New AC 1", "New AC 2"],
            }
        ],
        "story_summary": "Updated story summary",
    }

    try:
        response = client.put(f"/api/v1/plans/{sample_plan.plan_id}", json=update_payload)
        assert response.status_code == 200
        data = response.json()
        assert data["tasks"][0]["title"] == "FE - Revised Template Download Button UI"
        assert data["tasks"][0]["id"] == "task_fe_1"  # Stable ID preserved
        assert data["story_summary"] == "Updated story summary"
        assert data["updated_at"] is not None
        mock_plan_store.save_plan.assert_called_once()

        # Verify Zoho-compatible HTML format is preserved on edit and save
        desc = data["tasks"][0]["description"]
        assert "##" not in desc
        assert "**" not in desc
        assert not any(line.strip().startswith("- ") for line in desc.splitlines())

        assert "<p><strong>Objective:</strong>" in desc
        assert "<p><strong>Scope:</strong>" in desc
        assert "<p><strong>Expected Behavior:</strong>" in desc
        assert "<p><strong>Dependencies:</strong>" in desc
        assert "Testing Considerations" not in desc
        assert "Acceptance Criteria" not in desc

        obj_idx = desc.index("<strong>Objective:</strong>")
        scope_idx = desc.index("<strong>Scope:</strong>")
        exp_idx = desc.index("<strong>Expected Behavior:</strong>")
        deps_idx = desc.index("<strong>Dependencies:</strong>")
        assert obj_idx < scope_idx < exp_idx < deps_idx

        assert "<li>Revised scope text.</li>" in desc
        assert "<li>Revised expected behavior.</li>" in desc
        assert "<li>BE - 02 Layout validation</li>" in desc
    finally:
        app.dependency_overrides.clear()


def test_update_plan_invalid_task_data(sample_plan: GeneratedTaskPlan) -> None:
    """Verify validation errors for missing title, empty AC, or invalid prefix."""
    mock_plan_store = MagicMock()
    mock_plan_store.load_plan.return_value = sample_plan

    app.dependency_overrides[get_plan_store] = lambda: mock_plan_store

    try:
        # 1. Invalid prefix (does not start with FE - or BE -)
        payload_invalid_prefix = {
            "tasks": [
                {
                    "id": "task_fe_1",
                    "title": "Invalid Title Prefix",
                    "task_type": "FE",
                    "objective": "Obj",
                    "scope": "Scope",
                    "expected_behavior": "Expected",
                    "testing_considerations": "Tests",
                    "acceptance_criteria": ["AC 1"],
                }
            ]
        }
        response = client.put(f"/api/v1/plans/{sample_plan.plan_id}", json=payload_invalid_prefix)
        assert response.status_code == 422

        # 2. Empty mandatory objective
        payload_empty_obj = {
            "tasks": [
                {
                    "id": "task_fe_1",
                    "title": "FE - Valid Title",
                    "task_type": "FE",
                    "objective": "   ",
                    "scope": "Scope",
                    "expected_behavior": "Expected",
                }
            ]
        }
        response = client.put(f"/api/v1/plans/{sample_plan.plan_id}", json=payload_empty_obj)
        assert response.status_code == 422
    finally:
        app.dependency_overrides.clear()
