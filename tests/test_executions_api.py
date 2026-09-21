"""Tests for dry-run preview, task execution, and execution tracking endpoints."""

import pytest
from unittest.mock import MagicMock
from fastapi.testclient import TestClient

from src.api.app import app
from src.api.routes.plans import get_plan_store, get_task_creator
from src.api.routes.executions import (
    get_execution_tracker as exec_get_tracker,
    get_plan_store as exec_get_plan_store,
    get_task_creator as exec_get_task_creator,
)
from src.client.models import Subitem
from src.services.execution_tracker import ExecutionRecord, TaskExecutionState
from src.services.task_creator import CreationResult, DryRunOperation
from src.services.task_models import GeneratedTask, GeneratedTaskPlan, TaskOwner


@pytest.fixture
def sample_plan():
    dev = TaskOwner(user_id="39713000000188256", display_name="Ankit Singh")
    qa = TaskOwner(user_id="39713000000188149", display_name="Ketan Singh Tanwar")
    return GeneratedTaskPlan(
        plan_id="plan_test_exec_123",
        story_id="39713000007827664",
        story_title="Sample Story for Execution",
        story_summary="Summary of story",
        team_id="team_123",
        project_id="proj_456",
        sprint_id="sprint_789",
        status="draft",
        dev_owner=dev,
        qa_owner=qa,
        tasks=[
            GeneratedTask(
                id="task_fe_1",
                title="FE - Build Review Dialog",
                task_type="FE",
                objective="Build dialog",
                scope="FE scope",
                expected_behavior="Dialog displays",
                assignee=dev,
                qa_owner=qa,
            ),
            GeneratedTask(
                id="task_be_1",
                title="BE - 01 - API Endpoint",
                task_type="BE",
                index=1,
                objective="Build API",
                scope="BE scope",
                expected_behavior="API returns 200",
                assignee=dev,
                qa_owner=qa,
            ),
        ],
    )


@pytest.fixture
def sample_execution_record(sample_plan):
    return ExecutionRecord(
        execution_id="exec_test_abc",
        plan_id=sample_plan.plan_id,
        story_id=sample_plan.story_id,
        team_id=sample_plan.team_id,
        project_id=sample_plan.project_id,
        sprint_id=sample_plan.sprint_id,
        status="PARTIAL",
        tasks=[
            TaskExecutionState(
                title="FE - Build Review Dialog",
                task_type="FE",
                status="CREATED",
                zoho_task_id="39713000009999001",
            ),
            TaskExecutionState(
                title="BE - 01 - API Endpoint",
                task_type="BE",
                status="FAILED",
                error_message="Network timeout connecting to Zoho API",
            ),
        ],
    )


def test_dry_run_endpoint_success(sample_plan):
    client = TestClient(app)
    mock_plan_store = MagicMock()
    mock_plan_store.load_plan.return_value = sample_plan

    mock_task_creator = MagicMock()
    mock_task_creator.dry_run.return_value = [
        DryRunOperation(
            task_title="FE - Build Review Dialog",
            method="POST",
            endpoint="https://sprintsapi.zoho.in/team/team_123/projects/proj_456/sprints/sprint_789/item/39713000007827664/subitem/",
            payload={"name": "FE - Build Review Dialog", "projitemtypeid": "item_1", "projpriorityid": "prio_1"},
        ),
        DryRunOperation(
            task_title="BE - 01 - API Endpoint",
            method="POST",
            endpoint="https://sprintsapi.zoho.in/team/team_123/projects/proj_456/sprints/sprint_789/item/39713000007827664/subitem/",
            payload={"name": "BE - 01 - API Endpoint", "projitemtypeid": "item_1", "projpriorityid": "prio_1"},
        ),
    ]

    app.dependency_overrides[get_plan_store] = lambda: mock_plan_store
    app.dependency_overrides[get_task_creator] = lambda: mock_task_creator

    try:
        response = client.post(f"/api/v1/plans/{sample_plan.plan_id}/dry-run")
        assert response.status_code == 200
        data = response.json()
        assert data["plan_id"] == sample_plan.plan_id
        assert data["total_operations"] == 2
        assert len(data["operations"]) == 2
        assert data["operations"][0]["task_title"] == "FE - Build Review Dialog"
        assert data["operations"][0]["method"] == "POST"
        assert "endpoint" in data["operations"][0]
        assert "payload" in data["operations"][0]
    finally:
        app.dependency_overrides.clear()


def test_dry_run_endpoint_not_found():
    client = TestClient(app)
    mock_plan_store = MagicMock()
    mock_plan_store.load_plan.return_value = None

    app.dependency_overrides[get_plan_store] = lambda: mock_plan_store

    try:
        response = client.post("/api/v1/plans/plan_missing/dry-run")
        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()
    finally:
        app.dependency_overrides.clear()


def test_execute_plan_requires_confirmation(sample_plan):
    """Calling execute without confirm=True must be rejected with 400."""
    client = TestClient(app)
    mock_plan_store = MagicMock()
    mock_plan_store.load_plan.return_value = sample_plan

    app.dependency_overrides[get_plan_store] = lambda: mock_plan_store

    try:
        # 1. confirm=False
        response = client.post(
            f"/api/v1/plans/{sample_plan.plan_id}/execute",
            json={"confirm": False, "dry_run": False},
        )
        assert response.status_code == 400
        assert "confirmation" in response.json()["detail"].lower()

        # 2. empty payload (defaults confirm=False)
        response = client.post(
            f"/api/v1/plans/{sample_plan.plan_id}/execute",
            json={},
        )
        assert response.status_code == 400
    finally:
        app.dependency_overrides.clear()


def test_execute_plan_success(sample_plan):
    """Calling execute with confirm=True creates tasks and returns result."""
    client = TestClient(app)
    mock_plan_store = MagicMock()
    mock_plan_store.load_plan.return_value = sample_plan

    mock_task_creator = MagicMock()
    mock_task_creator.execute_plan.return_value = CreationResult(
        execution_id="exec_live_123",
        total_tasks=2,
        created_tasks=2,
        skipped_tasks=0,
        failed_tasks=0,
        tasks=[
            TaskExecutionState(
                title="FE - Build Review Dialog",
                task_type="FE",
                status="CREATED",
                zoho_task_id="39713000009999001",
            ),
            TaskExecutionState(
                title="BE - 01 - API Endpoint",
                task_type="BE",
                status="CREATED",
                zoho_task_id="39713000009999002",
            ),
        ],
        is_dry_run=False,
    )

    app.dependency_overrides[get_plan_store] = lambda: mock_plan_store
    app.dependency_overrides[get_task_creator] = lambda: mock_task_creator

    try:
        response = client.post(
            f"/api/v1/plans/{sample_plan.plan_id}/execute",
            json={"confirm": True, "dry_run": False},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["execution_id"] == "exec_live_123"
        assert data["total_tasks"] == 2
        assert data["created_tasks"] == 2
        assert data["failed_tasks"] == 0
        assert data["status"] == "COMPLETED"
        assert len(data["tasks"]) == 2
        assert data["tasks"][0]["zoho_task_id"] == "39713000009999001"
        assert mock_plan_store.save_plan.called
    finally:
        app.dependency_overrides.clear()


def test_list_executions(sample_execution_record):
    client = TestClient(app)
    mock_tracker = MagicMock()
    mock_tracker.list_executions.return_value = ["exec_test_abc"]
    mock_tracker.load_execution.return_value = sample_execution_record

    app.dependency_overrides[exec_get_tracker] = lambda: mock_tracker

    try:
        response = client.get("/api/v1/executions")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) == 1
        assert data[0]["execution_id"] == "exec_test_abc"
        assert data[0]["created_count"] == 1
        assert data[0]["failed_count"] == 1
    finally:
        app.dependency_overrides.clear()


def test_get_execution_by_id(sample_execution_record):
    client = TestClient(app)
    mock_tracker = MagicMock()
    mock_tracker.load_execution.side_effect = lambda eid: sample_execution_record if eid == "exec_test_abc" else None

    app.dependency_overrides[exec_get_tracker] = lambda: mock_tracker

    try:
        response = client.get("/api/v1/executions/exec_test_abc")
        assert response.status_code == 200
        assert response.json()["execution_id"] == "exec_test_abc"

        # Not found
        response_missing = client.get("/api/v1/executions/exec_unknown")
        assert response_missing.status_code == 404
    finally:
        app.dependency_overrides.clear()


def test_resume_execution_success(sample_plan, sample_execution_record):
    client = TestClient(app)
    mock_tracker = MagicMock()
    mock_tracker.load_execution.return_value = sample_execution_record

    mock_plan_store = MagicMock()
    mock_plan_store.load_plan.return_value = sample_plan

    mock_task_creator = MagicMock()
    mock_task_creator.resume_execution.return_value = CreationResult(
        execution_id="exec_test_abc",
        total_tasks=2,
        created_tasks=2,
        skipped_tasks=0,
        failed_tasks=0,
        tasks=[
            TaskExecutionState(
                title="FE - Build Review Dialog",
                task_type="FE",
                status="CREATED",
                zoho_task_id="39713000009999001",
            ),
            TaskExecutionState(
                title="BE - 01 - API Endpoint",
                task_type="BE",
                status="CREATED",
                zoho_task_id="39713000009999002",
            ),
        ],
    )

    app.dependency_overrides[exec_get_tracker] = lambda: mock_tracker
    app.dependency_overrides[exec_get_plan_store] = lambda: mock_plan_store
    app.dependency_overrides[exec_get_task_creator] = lambda: mock_task_creator

    try:
        response = client.post("/api/v1/executions/exec_test_abc/resume")
        assert response.status_code == 200
        data = response.json()
        assert data["execution_id"] == "exec_test_abc"
        assert data["created_tasks"] == 2
        assert data["failed_tasks"] == 0
        assert data["status"] == "COMPLETED"
    finally:
        app.dependency_overrides.clear()
