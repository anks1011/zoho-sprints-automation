"""Tests for TaskCreator, dry-run mode, and execution resume."""

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from src.client.models import ItemType, PriorityType, Subitem
from src.client.sprints_api import SprintsAPI
from src.config import Settings
from src.services.execution_tracker import ExecutionTracker
from src.services.task_creator import TaskCreator
from src.services.task_models import GeneratedTask, GeneratedTaskPlan


from src.services.task_models import GeneratedTask, GeneratedTaskPlan, TaskOwner


@pytest.fixture
def mock_plan() -> GeneratedTaskPlan:
    dev = TaskOwner(user_id="USER-DEV-1", display_name="Dev Alice")
    qa = TaskOwner(user_id="USER-QA-1", display_name="QA Bob")
    return GeneratedTaskPlan(
        story_id="STORY-55",
        story_title="OAuth Google Login",
        story_summary="Allow users to login via Google",
        team_id="T1",
        project_id="P1",
        sprint_id="S1",
        dev_owner=dev,
        qa_owner=qa,
        tasks=[
            GeneratedTask(
                title="FE - Google Sign-In Button",
                task_type="FE",
                objective="Add sign-in button",
                scope="Render button and redirect",
                expected_behavior="Redirects to Google",
                testing_considerations="Click test",
                acceptance_criteria=["Button renders"],
                assignee=dev,
                qa_owner=qa,
            ),
            GeneratedTask(
                title="BE - 01 - Google Callback Exchange Endpoint",
                task_type="BE",
                index=1,
                objective="Exchange code for token",
                scope="Endpoint handler",
                expected_behavior="Returns user session",
                testing_considerations="Mock Google endpoint",
                acceptance_criteria=["Validates ID token"],
                assignee=dev,
                qa_owner=qa,
            ),
        ],
    )


def test_dry_run_mode(tmp_path: Path, mock_plan: GeneratedTaskPlan) -> None:
    settings = Settings(
        zoho_default_item_type_id="TYPE_TASK",
        zoho_default_priority_id="PRIO_NORMAL",
        runtime_dir=tmp_path / ".runtime",
    )
    mock_api = MagicMock(spec=SprintsAPI)

    creator = TaskCreator(settings=settings, sprints_api=mock_api)
    result = creator.execute_plan(mock_plan, dry_run=True)

    assert result.is_dry_run is True
    assert result.total_tasks == 2
    assert result.created_tasks == 0
    # Crucial: NO API write calls must be made in dry-run
    mock_api.create_subitem.assert_not_called()


def test_live_execution_success(tmp_path: Path, mock_plan: GeneratedTaskPlan) -> None:
    settings = Settings(
        zoho_default_item_type_id="TYPE_TASK",
        zoho_default_priority_id="PRIO_NORMAL",
        runtime_dir=tmp_path / ".runtime",
    )
    mock_api = MagicMock(spec=SprintsAPI)
    mock_api.create_subitem.side_effect = [
        Subitem(id="ZS-FE-1", name=mock_plan.tasks[0].title),
        Subitem(id="ZS-BE-1", name=mock_plan.tasks[1].title),
    ]

    creator = TaskCreator(settings=settings, sprints_api=mock_api)
    result = creator.execute_plan(mock_plan, dry_run=False)

    assert result.is_dry_run is False
    assert result.total_tasks == 2
    assert result.created_tasks == 2
    assert result.failed_tasks == 0
    assert mock_api.create_subitem.call_count == 2


def test_resume_skips_already_created(tmp_path: Path, mock_plan: GeneratedTaskPlan) -> None:
    settings = Settings(
        zoho_default_item_type_id="TYPE_TASK",
        zoho_default_priority_id="PRIO_NORMAL",
        runtime_dir=tmp_path / ".runtime",
    )
    tracker = ExecutionTracker(settings)
    record = tracker.create_execution(mock_plan)

    # Mark first task as already created
    record.tasks[0].status = "CREATED"
    record.tasks[0].zoho_task_id = "ALREADY-CREATED-1"
    record.tasks[1].status = "FAILED"
    record.status = "PARTIAL"
    tracker.save_execution(record)

    mock_api = MagicMock(spec=SprintsAPI)
    mock_api.create_subitem.return_value = Subitem(id="RESUMED-BE-1", name=mock_plan.tasks[1].title)

    creator = TaskCreator(settings=settings, sprints_api=mock_api, tracker=tracker)
    res = creator.resume_execution(record.execution_id, mock_plan)

    assert res.created_tasks == 2
    assert res.failed_tasks == 0
    # API was called ONLY ONCE for the second task
    assert mock_api.create_subitem.call_count == 1
    args, kwargs = mock_api.create_subitem.call_args
    assert kwargs["name"] == mock_plan.tasks[1].title
