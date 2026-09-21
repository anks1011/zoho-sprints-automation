"""Tests for ExecutionTracker persistence and status updates."""

from pathlib import Path

from src.config import Settings
from src.services.execution_tracker import ExecutionTracker
from src.services.task_models import GeneratedTask, GeneratedTaskPlan


def test_execution_tracker_lifecycle(tmp_path: Path) -> None:
    settings = Settings(runtime_dir=tmp_path / ".runtime")
    tracker = ExecutionTracker(settings)

    plan = GeneratedTaskPlan(
        story_id="STORY-77",
        story_title="Payment Gateway",
        story_summary="Integrate payment gateway",
        team_id="T1",
        project_id="P1",
        sprint_id="S1",
        tasks=[
            GeneratedTask(
                title="FE - Checkout Modal",
                task_type="FE",
                objective="Checkout modal",
                scope="Modal",
                expected_behavior="Displays modal",
                testing_considerations="Test",
            ),
            GeneratedTask(
                title="BE - 01 - Charge Card API",
                task_type="BE",
                index=1,
                objective="Charge card",
                scope="Stripe charge",
                expected_behavior="Charges card",
                testing_considerations="Test",
            ),
        ],
    )

    record = tracker.create_execution(plan)
    assert record.story_id == "STORY-77"
    assert record.status == "PENDING"
    assert len(record.tasks) == 2
    assert record.tasks[0].status == "PENDING"

    # Simulate first task created, second task failed
    record.tasks[0].status = "CREATED"
    record.tasks[0].zoho_task_id = "ZS-SUB-101"
    record.tasks[1].status = "FAILED"
    record.tasks[1].error_message = "Timeout"
    record.status = "PARTIAL"

    tracker.save_execution(record)

    loaded = tracker.load_execution(record.execution_id)
    assert loaded is not None
    assert loaded.status == "PARTIAL"
    assert loaded.created_count == 1
    assert loaded.failed_count == 1
    assert loaded.tasks[0].zoho_task_id == "ZS-SUB-101"
