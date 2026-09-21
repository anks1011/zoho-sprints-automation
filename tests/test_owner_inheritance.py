"""Comprehensive unit tests for Story owner inheritance, validation, and payload mapping."""

import json
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from src.client.models import StoryItem, Subitem
from src.client.sprints_api import SprintsAPI
from src.client.zoho_client import SprintsAPIError
from src.config import Settings
from src.services.execution_tracker import ExecutionTracker
from src.services.owner_validator import OwnerValidator, PlanValidationResult
from src.services.story_service import StoryService
from src.services.task_creator import TaskCreator
from src.services.task_generator import TaskGenerator
from src.services.task_models import (
    GeneratedTask,
    GeneratedTaskPlan,
    RawBackendTaskDraft,
    RawFrontendTaskDraft,
    StoryAnalysisResult,
    TaskOwner,
)


@pytest.fixture
def mock_story_with_owners() -> StoryItem:
    """StoryItem with Dev Owner and QA Owner populated."""
    return StoryItem(
        id="STORY-100",
        name="User Authentication Overhaul",
        description="Implement login and token verification",
        team_id="60043431118",
        project_id="39713000006643091",
        sprint_id="39713000007785711",
        raw_data={
            "UDF_USERPKL3": "39713000000188256",  # Dev Owner (Ankit Singh)
            "UDF_USERPKL2": "39713000000188149",  # QA Owner (Ketan Singh Tanwar)
            "ownerId": ["39713000000188149", "39713000000188256"],
            "userDisplayName": {
                "39713000000188256": "Ankit Singh",
                "39713000000188149": "Ketan Singh Tanwar",
            },
            "UDF_PKL13": "39713000007212764",  # Module
        },
    )


@pytest.fixture
def sample_analysis() -> StoryAnalysisResult:
    """Analysis result requiring both FE and BE tasks."""
    return StoryAnalysisResult(
        business_objective="Support login",
        summary="Frontend UI and Backend auth verification",
        requires_frontend=True,
        requires_backend=True,
        frontend_task=RawFrontendTaskDraft(
            title_suffix="Build Login Screen",
            objective="Login UI",
            scope="Render form and buttons",
            expected_behavior="User enters credentials",
        ),
        backend_tasks=[
            RawBackendTaskDraft(
                title_suffix="Implement Login API",
                objective="Authenticate user",
                scope="JWT issuing",
                expected_behavior="Returns token",
            ),
            RawBackendTaskDraft(
                title_suffix="Implement Token Verification",
                objective="Verify session",
                scope="Auth middleware",
                expected_behavior="Validates JWT header",
            ),
        ],
    )


def test_story_owners_extracted_from_story_service(mock_story_with_owners: StoryItem) -> None:
    """StoryService extracts Dev Owner and QA Owner accurately."""
    service = StoryService()
    project_users = {
        "39713000000188256": {"displayName": "Ankit Singh", "emailId": "ankit@meritto.com"},
        "39713000000188149": {"displayName": "Ketan Singh Tanwar", "emailId": "ketan@meritto.com"},
    }
    dev, qa = service.extract_story_owners(mock_story_with_owners, project_users)

    assert dev is not None
    assert dev.user_id == "39713000000188256"
    assert dev.display_name == "Ankit Singh"
    assert dev.email == "ankit@meritto.com"

    assert qa is not None
    assert qa.user_id == "39713000000188149"
    assert qa.display_name == "Ketan Singh Tanwar"
    assert qa.email == "ketan@meritto.com"


def test_story_owners_inherited_by_all_fe_and_be_tasks(
    mock_story_with_owners: StoryItem, sample_analysis: StoryAnalysisResult
) -> None:
    """1, 2, 3, 4: Dev Owner -> Task Assignee, QA Owner -> Task QA Owner across all FE & BE tasks."""
    generator = TaskGenerator()
    plan = generator.generate_plan(mock_story_with_owners, sample_analysis)

    assert plan.dev_owner is not None
    assert plan.dev_owner.user_id == "39713000000188256"
    assert plan.qa_owner is not None
    assert plan.qa_owner.user_id == "39713000000188149"

    # Verify all tasks have exact inherited owners
    assert len(plan.tasks) == 3
    for task in plan.tasks:
        assert task.assignee is not None
        assert task.assignee.user_id == "39713000000188256"
        assert task.assignee.display_name == "Ankit Singh"

        assert task.qa_owner is not None
        assert task.qa_owner.user_id == "39713000000188149"
        assert task.qa_owner.display_name == "Ketan Singh Tanwar"


def test_missing_dev_owner_allowed_with_warning(sample_analysis: StoryAnalysisResult) -> None:
    """Missing Story Dev Owner returns a non-blocking warning and allows execution."""
    story = StoryItem(
        id="STORY-NO-DEV",
        name="No Dev Owner Story",
        team_id="T1",
        project_id="P1",
        sprint_id="S1",
        raw_data={"UDF_USERPKL2": "39713000000188149"},
    )
    generator = TaskGenerator()
    plan = generator.generate_plan(story, sample_analysis)

    result = OwnerValidator.validate_plan_owners(plan)
    assert result.valid  # Not mandatory, so valid is True
    warning_codes = [w.code for w in result.warnings]
    assert "STORY_DEV_OWNER_NOT_ASSIGNED" in warning_codes


def test_missing_qa_owner_allowed_with_warning(sample_analysis: StoryAnalysisResult) -> None:
    """Missing Story QA Owner returns a non-blocking warning and allows execution."""
    story = StoryItem(
        id="STORY-NO-QA",
        name="No QA Owner Story",
        team_id="T1",
        project_id="P1",
        sprint_id="S1",
        raw_data={"UDF_USERPKL3": "39713000000188256"},
    )
    generator = TaskGenerator()
    plan = generator.generate_plan(story, sample_analysis)

    result = OwnerValidator.validate_plan_owners(plan)
    assert result.valid  # Not mandatory, so valid is True
    warning_codes = [w.code for w in result.warnings]
    assert "STORY_QA_OWNER_NOT_ASSIGNED" in warning_codes
    qa_warn = next(w for w in result.warnings if w.code == "STORY_QA_OWNER_NOT_ASSIGNED")
    assert "does not have a QA Owner" in qa_warn.message


def test_invalid_or_unauthorized_owner_rejected(
    mock_story_with_owners: StoryItem, sample_analysis: StoryAnalysisResult
) -> None:
    """11: Invalid or unauthorized owner IDs are rejected during validation."""
    generator = TaskGenerator()
    plan = generator.generate_plan(mock_story_with_owners, sample_analysis)

    # Valid project users set does not include foreign user
    valid_users = {"39713000000188256"}  # Only Ankit, Ketan is missing from project
    result = OwnerValidator.validate_plan_owners(plan, valid_project_user_ids=valid_users)

    assert not result.valid
    error_codes = [e.code for e in result.errors]
    assert "INVALID_QA_OWNER_ID" in error_codes


def test_dry_run_payload_contains_verified_owner_fields(
    tmp_path: Path, mock_story_with_owners: StoryItem, sample_analysis: StoryAnalysisResult
) -> None:
    """8, 9, 10: Dry-run payload includes users JSONArray, UDF_USERPKL3, and UDF_USERPKL2."""
    generator = TaskGenerator()
    plan = generator.generate_plan(mock_story_with_owners, sample_analysis)

    settings = Settings(
        zoho_default_item_type_id="TYPE-1",
        zoho_default_priority_id="PRIO-1",
        runtime_dir=tmp_path / ".runtime",
    )
    creator = TaskCreator(settings=settings)
    operations = creator.dry_run(plan)

    assert len(operations) == 3
    for op in operations:
        payload = op.payload
        # Verify Task Assignee mapping
        assert payload.get("UDF_USERPKL3") == "39713000000188256"
        assert json.loads(payload.get("users")) == ["39713000000188256"]

        # Verify Task QA Owner mapping
        assert payload.get("UDF_USERPKL2") == "39713000000188149"

        # Verify zero credential exposure
        for sensitive_key in ["access_token", "refresh_token", "client_secret", "password"]:
            assert sensitive_key not in payload


def test_live_creation_sends_verified_zoho_fields(
    tmp_path: Path, mock_story_with_owners: StoryItem, sample_analysis: StoryAnalysisResult
) -> None:
    """10: Actual creation uses verified Zoho fields (users, UDF_USERPKL3, UDF_USERPKL2)."""
    generator = TaskGenerator()
    plan = generator.generate_plan(mock_story_with_owners, sample_analysis)

    settings = Settings(
        zoho_default_item_type_id="TYPE-1",
        zoho_default_priority_id="PRIO-1",
        runtime_dir=tmp_path / ".runtime",
    )
    mock_api = MagicMock(spec=SprintsAPI)
    mock_api.create_subitem.side_effect = [
        Subitem(id=f"SUB-{i}", name=t.title) for i, t in enumerate(plan.tasks, 1)
    ]

    creator = TaskCreator(settings=settings, sprints_api=mock_api)
    result = creator.execute_plan(plan, dry_run=False)

    assert result.created_tasks == 3
    assert mock_api.create_subitem.call_count == 3

    for call in mock_api.create_subitem.call_args_list:
        kwargs = call.kwargs
        # users argument passed as JSON string
        assert kwargs["users"] == json.dumps(["39713000000188256"])
        # Custom fields contain UDF_USERPKL3 and UDF_USERPKL2
        cf = kwargs["custom_fields"]
        assert cf.get("UDF_USERPKL3") == "39713000000188256"
        assert cf.get("UDF_USERPKL2") == "39713000000188149"


def test_retry_preserves_owner_mapping(
    tmp_path: Path, mock_story_with_owners: StoryItem, sample_analysis: StoryAnalysisResult
) -> None:
    """12: Resuming/retrying execution preserves original owner mapping."""
    generator = TaskGenerator()
    plan = generator.generate_plan(mock_story_with_owners, sample_analysis)

    settings = Settings(
        zoho_default_item_type_id="TYPE-1",
        zoho_default_priority_id="PRIO-1",
        runtime_dir=tmp_path / ".runtime",
    )
    tracker = ExecutionTracker(settings=settings)
    record = tracker.create_execution(plan)

    # Simulate first task created, second and third failed
    record.tasks[0].status = "CREATED"
    record.tasks[0].zoho_task_id = "SUB-1"
    record.tasks[1].status = "FAILED"
    record.tasks[2].status = "FAILED"
    record.status = "PARTIAL"
    tracker.save_execution(record)

    mock_api = MagicMock(spec=SprintsAPI)
    mock_api.create_subitem.side_effect = [
        Subitem(id="SUB-2", name=plan.tasks[1].title),
        Subitem(id="SUB-3", name=plan.tasks[2].title),
    ]

    creator = TaskCreator(settings=settings, sprints_api=mock_api, tracker=tracker)
    res = creator.resume_execution(record.execution_id, plan)

    assert res.created_tasks == 3
    assert mock_api.create_subitem.call_count == 2

    for call in mock_api.create_subitem.call_args_list:
        kwargs = call.kwargs
        assert kwargs["users"] == json.dumps(["39713000000188256"])
        cf = kwargs["custom_fields"]
        assert cf.get("UDF_USERPKL3") == "39713000000188256"
        assert cf.get("UDF_USERPKL2") == "39713000000188149"


def test_execution_allowed_when_owner_missing(
    sample_analysis: StoryAnalysisResult, tmp_path: Path
) -> None:
    """Execution is permitted when an owner is missing (owners are optional)."""
    story = StoryItem(
        id="STORY-NO-QA",
        name="No QA Owner Story",
        team_id="T1",
        project_id="P1",
        sprint_id="S1",
        raw_data={"UDF_USERPKL3": "39713000000188256"},
    )
    generator = TaskGenerator()
    plan = generator.generate_plan(story, sample_analysis)

    settings = Settings(
        zoho_default_item_type_id="TYPE-1",
        zoho_default_priority_id="PRIO-1",
        runtime_dir=tmp_path / ".runtime",
    )
    mock_api = MagicMock(spec=SprintsAPI)
    mock_api.create_subitem.side_effect = [
        Subitem(id=f"SUB-{i}", name=t.title) for i, t in enumerate(plan.tasks)
    ]

    creator = TaskCreator(settings=settings, sprints_api=mock_api)
    result = creator.execute_plan(plan, dry_run=False)

    assert result.created_tasks == len(plan.tasks)
    assert result.failed_tasks == 0

    # Ensure calls were made and QA Owner was not sent, but Dev Owner was
    for call in mock_api.create_subitem.call_args_list:
        kwargs = call.kwargs
        assert kwargs["users"] == json.dumps(["39713000000188256"])
        cf = kwargs["custom_fields"]
        assert cf.get("UDF_USERPKL3") == "39713000000188256"
        assert "UDF_USERPKL2" not in cf
