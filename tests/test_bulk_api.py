"""Tests for bulk plan generation and bulk execution endpoints."""

from unittest.mock import MagicMock
import pytest
from fastapi.testclient import TestClient

from src.api.app import app
from src.api.routes.plans import (
    get_ai_analyzer,
    get_dup_detector,
    get_plan_store,
    get_story_service,
    get_task_creator,
    get_task_generator,
)
from src.client.models import StoryItem
from src.services.execution_tracker import TaskExecutionState
from src.services.story_service import StoryServiceError
from src.services.task_creator import CreationResult
from src.services.task_models import (
    GeneratedTask,
    GeneratedTaskPlan,
    StoryAnalysisResult,
)

client = TestClient(app)


@pytest.fixture
def story_a() -> StoryItem:
    return StoryItem(
        id="STORY_1",
        name="Story 1 Title",
        description="Desc 1",
        acceptance_criteria="AC 1",
        team_id="TEAM_1",
        project_id="PROJ_1",
        sprint_id="SPRINT_1",
        subitems=[],
    )


@pytest.fixture
def story_b() -> StoryItem:
    return StoryItem(
        id="STORY_2",
        name="Story 2 Title",
        description="Desc 2",
        acceptance_criteria="AC 2",
        team_id="TEAM_1",
        project_id="PROJ_1",
        sprint_id="SPRINT_1",
        subitems=[],
    )


def test_bulk_generate_success(story_a, story_b):
    mock_story_service = MagicMock()
    mock_story_service.fetch_story.side_effect = lambda story_id, **kw: story_a if story_id == "STORY_1" else story_b
    mock_story_service.get_project_users.return_value = {}
    mock_story_service.extract_story_owners.return_value = (None, None)

    mock_ai = MagicMock()
    mock_ai.analyze_story.return_value = StoryAnalysisResult(
        summary="AI Summary",
        fe_tasks=["FE Task"],
        be_tasks=["BE Task"],
    )

    mock_gen = MagicMock()
    mock_gen.generate_plan.side_effect = lambda story, **kw: GeneratedTaskPlan(
        plan_id=f"plan_{story.id}",
        story_id=story.id,
        story_title=story.name,
        story_summary=f"Summary for {story.id}",
        team_id=story.team_id,
        project_id=story.project_id,
        sprint_id=story.sprint_id,
        tasks=[
            GeneratedTask(
                id=f"task_{story.id}_1",
                title=f"FE - Task for {story.id}",
                task_type="FE",
                objective="Obj",
                scope="Scope",
                expected_behavior="Exp",
            )
        ],
    )

    mock_dup = MagicMock()
    mock_dup.analyze_plan_duplicates.return_value = []

    mock_store = MagicMock()
    mock_store.save_plan.return_value = "/tmp/plan.json"

    app.dependency_overrides[get_story_service] = lambda: mock_story_service
    app.dependency_overrides[get_ai_analyzer] = lambda: mock_ai
    app.dependency_overrides[get_task_generator] = lambda: mock_gen
    app.dependency_overrides[get_dup_detector] = lambda: mock_dup
    app.dependency_overrides[get_plan_store] = lambda: mock_store

    try:
        response = client.post(
            "/api/v1/plans/bulk-generate",
            json={"story_ids": ["STORY_1", "STORY_2"]},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 2
        assert data["successful"] == 2
        assert data["failed"] == 0
        assert len(data["results"]) == 2
        assert data["results"][0]["story_id"] == "STORY_1"
        assert data["results"][0]["success"] is True
        assert data["results"][0]["plan"]["plan_id"] == "plan_STORY_1"
        assert data["results"][1]["story_id"] == "STORY_2"
        assert data["results"][1]["success"] is True
    finally:
        app.dependency_overrides.clear()


def test_bulk_generate_partial_failure(story_a):
    mock_story_service = MagicMock()

    def fetch_side_effect(story_id, **kw):
        if story_id == "STORY_1":
            return story_a
        raise StoryServiceError(f"Story '{story_id}' not found.")

    mock_story_service.fetch_story.side_effect = fetch_side_effect
    mock_story_service.get_project_users.return_value = {}
    mock_story_service.extract_story_owners.return_value = (None, None)

    mock_ai = MagicMock()
    mock_ai.analyze_story.return_value = StoryAnalysisResult(summary="S", fe_tasks=[], be_tasks=[])

    mock_gen = MagicMock()
    mock_gen.generate_plan.return_value = GeneratedTaskPlan(
        plan_id="plan_STORY_1",
        story_id="STORY_1",
        story_title="Story 1",
        story_summary="Sum",
        team_id="TEAM_1",
        project_id="PROJ_1",
        sprint_id="SPRINT_1",
        tasks=[],
    )

    mock_dup = MagicMock()
    mock_dup.analyze_plan_duplicates.return_value = []
    mock_store = MagicMock()

    app.dependency_overrides[get_story_service] = lambda: mock_story_service
    app.dependency_overrides[get_ai_analyzer] = lambda: mock_ai
    app.dependency_overrides[get_task_generator] = lambda: mock_gen
    app.dependency_overrides[get_dup_detector] = lambda: mock_dup
    app.dependency_overrides[get_plan_store] = lambda: mock_store

    try:
        response = client.post(
            "/api/v1/plans/bulk-generate",
            json={"story_ids": ["STORY_1", "INVALID_ID"]},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 2
        assert data["successful"] == 1
        assert data["failed"] == 1
        assert data["results"][0]["success"] is True
        assert data["results"][1]["success"] is False
        assert "not found" in data["results"][1]["error"].lower()
    finally:
        app.dependency_overrides.clear()


def test_bulk_execute_dry_run():
    plan = GeneratedTaskPlan(
        plan_id="plan_1",
        story_id="STORY_1",
        story_title="Story 1",
        story_summary="Sum",
        team_id="TEAM_1",
        project_id="PROJ_1",
        sprint_id="SPRINT_1",
        tasks=[
            GeneratedTask(
                id="t1",
                title="FE - Test Task",
                task_type="FE",
                objective="Obj",
                scope="Scope",
                expected_behavior="Exp",
            )
        ],
    )

    mock_store = MagicMock()
    mock_store.load_plan.side_effect = lambda pid: plan if pid == "plan_1" else None

    mock_creator = MagicMock()
    mock_creator.execute_plan.return_value = CreationResult(
        execution_id="exec_bulk_1",
        total_tasks=1,
        created_tasks=0,
        skipped_tasks=0,
        failed_tasks=0,
        is_dry_run=True,
        tasks=[
            TaskExecutionState(
                task_id="t1",
                title="FE - Test Task",
                task_type="FE",
                status="SKIPPED",
            )
        ],
    )

    app.dependency_overrides[get_plan_store] = lambda: mock_store
    app.dependency_overrides[get_task_creator] = lambda: mock_creator

    try:
        response = client.post(
            "/api/v1/plans/bulk-execute",
            json={"plan_ids": ["plan_1"], "dry_run": True, "confirm": False},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 1
        assert data["successful"] == 1
        assert data["dry_run"] is True
        assert data["results"][0]["success"] is True
    finally:
        app.dependency_overrides.clear()


def test_bulk_execute_requires_confirmation_for_live():
    response = client.post(
        "/api/v1/plans/bulk-execute",
        json={"plan_ids": ["plan_1"], "dry_run": False, "confirm": False},
    )
    assert response.status_code == 400
    assert "confirmation" in response.json()["detail"].lower()
