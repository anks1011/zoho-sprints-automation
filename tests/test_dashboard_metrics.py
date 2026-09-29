from datetime import datetime, timezone
from unittest.mock import patch
import pytest
from fastapi.testclient import TestClient

from src.api.app import app
from src.services.execution_tracker import ExecutionRecord, TaskExecutionState


@pytest.fixture
def test_client():
    return TestClient(app)


def test_dashboard_metrics_endpoint_structure(test_client):
    """Test dashboard metrics endpoint returns real numeric count format."""
    rec1 = ExecutionRecord(
        execution_id="exec_1",
        plan_id="plan_1",
        story_id="story_101",
        team_id="team_1",
        project_id="proj_1",
        sprint_id="sprint_1",
        status="COMPLETED",
        tasks=[
            TaskExecutionState(title="Task 1", task_type="FE", status="CREATED"),
            TaskExecutionState(title="Task 2", task_type="BE", status="CREATED"),
            TaskExecutionState(title="Task 3", task_type="FE", status="CREATED"),
        ],
        created_at=datetime.now(timezone.utc).isoformat(),
        updated_at=datetime.now(timezone.utc).isoformat(),
    )
    rec2 = ExecutionRecord(
        execution_id="exec_2",
        plan_id="plan_2",
        story_id="story_102",
        team_id="team_1",
        project_id="proj_1",
        sprint_id="sprint_1",
        status="FAILED",
        tasks=[
            TaskExecutionState(title="Task 4", task_type="BE", status="FAILED"),
        ],
        created_at=datetime.now(timezone.utc).isoformat(),
        updated_at=datetime.now(timezone.utc).isoformat(),
    )

    with patch("src.services.execution_tracker.ExecutionTracker.list_records", return_value=[rec1, rec2]):
        response = test_client.get("/api/v1/dashboard/metrics")
        assert response.status_code == 200
        data = response.json()

        # All 6 required fields must be present and numeric
        assert "storiesProcessedToday" in data
        assert "tasksCreatedToday" in data
        assert "storiesProcessed" in data
        assert "tasksCreated" in data
        assert "storiesAssignedToMe" in data
        assert "failedToday" in data

        assert isinstance(data["storiesProcessedToday"], int)
        assert isinstance(data["tasksCreatedToday"], int)
        assert isinstance(data["storiesProcessed"], int)
        assert isinstance(data["tasksCreated"], int)
        assert isinstance(data["storiesAssignedToMe"], int)
        assert isinstance(data["failedToday"], int)

        assert data["storiesProcessedToday"] == 2
        assert data["tasksCreatedToday"] == 3
        assert data["storiesProcessed"] == 2
        assert data["tasksCreated"] == 3
        assert data["failedToday"] == 1


def test_dashboard_metrics_counts_unique_stories_today(test_client):
    """Test COUNT(DISTINCT story_id) today even if a story was processed repeatedly today."""
    rec1 = ExecutionRecord(
        execution_id="exec_1",
        plan_id="plan_1",
        story_id="story_dup",
        team_id="team_1",
        project_id="proj_1",
        sprint_id="sprint_1",
        status="COMPLETED",
        tasks=[
            TaskExecutionState(title="Task 1", task_type="FE", status="CREATED"),
            TaskExecutionState(title="Task 2", task_type="BE", status="CREATED"),
        ],
        created_at=datetime.now(timezone.utc).isoformat(),
    )
    rec2 = ExecutionRecord(
        execution_id="exec_2",
        plan_id="plan_2",
        story_id="story_dup",  # Same story processed again today
        team_id="team_1",
        project_id="proj_1",
        sprint_id="sprint_1",
        status="COMPLETED",
        tasks=[
            TaskExecutionState(title="Task 3", task_type="FE", status="CREATED"),
        ],
        created_at=datetime.now(timezone.utc).isoformat(),
    )

    with patch("src.services.execution_tracker.ExecutionTracker.list_records", return_value=[rec1, rec2]):
        response = test_client.get("/api/v1/dashboard/metrics")
        assert response.status_code == 200
        data = response.json()
        # Unique stories today should be 1, total tasks created today should be 3
        assert data["storiesProcessedToday"] == 1
        assert data["tasksCreatedToday"] == 3
        assert data["storiesProcessed"] == 1
        assert data["tasksCreated"] == 3
        assert data["failedToday"] == 0
