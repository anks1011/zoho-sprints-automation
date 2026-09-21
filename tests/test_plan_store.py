"""Tests for PlanStore serialization and retrieval."""

from pathlib import Path

from src.config import Settings
from src.services.plan_store import PlanStore
from src.services.task_models import GeneratedTask, GeneratedTaskPlan


def test_plan_store_save_and_load(tmp_path: Path) -> None:
    settings = Settings(runtime_dir=tmp_path / ".runtime")
    store = PlanStore(settings)

    plan = GeneratedTaskPlan(
        story_id="STORY-99",
        story_title="OAuth Integration",
        story_summary="Add OAuth2 login support",
        team_id="T1",
        project_id="P1",
        sprint_id="S1",
        tasks=[
            GeneratedTask(
                title="FE - OAuth Login Buttons",
                task_type="FE",
                objective="Add buttons",
                scope="Scope",
                expected_behavior="Behavior",
                testing_considerations="Test",
            )
        ],
    )

    path = store.save_plan(plan)
    assert path.exists()

    loaded = store.load_plan(plan.plan_id)
    assert loaded is not None
    assert loaded.plan_id == plan.plan_id
    assert loaded.story_id == "STORY-99"
    assert len(loaded.tasks) == 1
    assert loaded.tasks[0].title == "FE - OAuth Login Buttons"

    # Test loading latest by story_id
    latest = store.load_latest_for_story("STORY-99")
    assert latest is not None
    assert latest.plan_id == plan.plan_id
