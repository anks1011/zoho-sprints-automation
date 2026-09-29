"""End-to-end CLI integration tests using Typer's CliRunner."""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from typer.testing import CliRunner

from src.auth.oauth_client import AuthStatus
from src.auth.token_store import StoredToken
from src.client.models import Project, Sprint, StoryItem, Subitem, Team
from src.main import app
from src.services.task_models import GeneratedTask, GeneratedTaskPlan, RawFrontendTaskDraft, StoryAnalysisResult

runner = CliRunner()


def test_cli_help() -> None:
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "Zoho Sprints AI Story-to-Tasks Automation CLI" in result.output
    assert "generate" in result.output
    assert "create" in result.output


def test_cli_auth_status() -> None:
    with patch("src.main.ZohoOAuthClient") as mock_oauth_cls:
        mock_instance = MagicMock()
        mock_instance.get_status.return_value = AuthStatus(
            is_authenticated=True,
            has_refresh_token=True,
            is_expired=False,
            expires_at_iso="2026-09-21T18:00:00Z",
            api_domain="https://sprintsapi.zoho.in",
            accounts_url="https://accounts.zoho.in",
            message="Authenticated",
        )
        mock_oauth_cls.return_value = mock_instance

        result = runner.invoke(app, ["auth-status"])
        assert result.exit_code == 0
        assert "Authenticated" in result.output
        assert "https://accounts.zoho.in" in result.output


def test_cli_refresh_token() -> None:
    with patch("src.main.ZohoOAuthClient") as mock_oauth_cls:
        mock_instance = MagicMock()
        mock_instance.refresh_access_token.return_value = StoredToken(access_token="new_tok")
        mock_oauth_cls.return_value = mock_instance

        result = runner.invoke(app, ["refresh-token"])
        assert result.exit_code == 0
        assert "refreshed successfully" in result.output


def test_cli_list_teams() -> None:
    with patch("src.main.SprintsAPI") as mock_api_cls:
        mock_instance = MagicMock()
        mock_instance.list_teams.return_value = [
            Team(id="T1", name="Engineering Core"),
            Team(id="T2", name="Product Design"),
        ]
        mock_api_cls.return_value = mock_instance

        result = runner.invoke(app, ["list-teams"])
        assert result.exit_code == 0
        assert "Engineering Core" in result.output
        assert "T1" in result.output
        assert "Product Design" in result.output


def test_cli_list_projects() -> None:
    with patch("src.main.SprintsAPI") as mock_api_cls:
        mock_instance = MagicMock()
        mock_instance.list_projects.return_value = [
            Project(id="P1", name="Payment Gateway", prefix="PAY", status="active")
        ]
        mock_api_cls.return_value = mock_instance

        result = runner.invoke(app, ["list-projects", "--team-id", "T1"])
        assert result.exit_code == 0
        assert "Payment Gateway" in result.output
        assert "PAY" in result.output


def test_cli_story() -> None:
    with patch("src.main.StoryService") as mock_service_cls:
        mock_instance = MagicMock()
        mock_instance.fetch_story.return_value = StoryItem(
            id="STORY-123",
            name="User Subscription Billing",
            description="Allow customers to subscribe to monthly recurring plans.",
            acceptance_criteria="- Supports Visa and Mastercard\n- Charges occur on 1st of month",
            team_id="T1",
            project_id="P1",
            sprint_id="S1",
            subitems=[Subitem(id="SUB-1", name="FE - Subscribe Modal")],
        )
        mock_service_cls.return_value = mock_instance

        result = runner.invoke(app, ["story", "--story-id", "STORY-123"])
        assert result.exit_code == 0
        assert "STORY-123" in result.output
        assert "User Subscription Billing" in result.output
        assert "Supports Visa and Mastercard" in result.output
        assert "FE - Subscribe Modal" in result.output


def test_cli_generate_flow(tmp_path: Path) -> None:
    with patch("src.main.StoryService") as mock_story_cls, \
         patch("src.main.AIStoryAnalyzer") as mock_ai_cls, \
         patch("src.main.get_settings") as mock_settings_fn:

        from src.config import Settings
        settings = Settings(runtime_dir=tmp_path / ".runtime")
        mock_settings_fn.return_value = settings

        story = StoryItem(
            id="STORY-88",
            name="Dark Mode Support",
            description="Add toggle for dark mode across application",
            team_id="T1",
            project_id="P1",
            sprint_id="S1",
        )
        mock_story_cls.return_value.fetch_story.return_value = story

        analysis = StoryAnalysisResult(
            business_objective="Support dark theme",
            summary="Add theme context and toggle component",
            requires_frontend=True,
            requires_backend=False,
            frontend_task=RawFrontendTaskDraft(
                title_suffix="Dark Mode Toggle and Theme Provider",
                objective="Add theme switcher",
                scope="React Context for theme, toggle switch in navbar",
                expected_behavior="Toggles CSS theme variables",
                testing_considerations="Test toggle switch state changes",
                acceptance_criteria=["Saves preference to localStorage"],
            ),
        )
        mock_ai_cls.return_value.analyze_story.return_value = analysis

        result = runner.invoke(app, ["generate", "--story-id", "STORY-88"])
        assert result.exit_code == 0
        assert "Parent Story: STORY-88 - Dark Mode Support" in result.output
        assert "FE - Dark Mode Toggle and Theme Provider" in result.output
        assert "Total generated tasks: 1" in result.output

        # Verify plan was saved to disk
        plan_files = list((tmp_path / ".runtime" / "plans").glob("plan_*.json"))
        assert len(plan_files) == 1


def test_cli_create_dry_run(tmp_path: Path) -> None:
    with patch("src.main.get_settings") as mock_settings_fn, \
         patch("src.main.PlanStore") as mock_plan_cls, \
         patch("src.main.TaskCreator") as mock_creator_cls:

        from src.config import Settings
        settings = Settings(runtime_dir=tmp_path / ".runtime")
        mock_settings_fn.return_value = settings

        plan = GeneratedTaskPlan(
            story_id="STORY-88",
            story_title="Dark Mode",
            story_summary="Summary",
            team_id="T1",
            project_id="P1",
            sprint_id="S1",
            tasks=[
                GeneratedTask(
                    title="FE - Toggle Switch",
                    task_type="FE",
                    objective="Toggle",
                    scope="Scope",
                    expected_behavior="Expected",
                    testing_considerations="Tests",
                )
            ],
        )
        mock_plan_cls.return_value.load_latest_for_story.return_value = plan

        result = runner.invoke(app, ["create", "--story-id", "STORY-88", "--dry-run"])
        assert result.exit_code == 0
        assert "DRY-RUN" in result.output
        mock_creator_cls.return_value.execute_plan.assert_called_once_with(plan, dry_run=True)


def test_cli_create_user_declines() -> None:
    with patch("src.main.PlanStore") as mock_plan_cls, \
         patch("src.main.TaskCreator") as mock_creator_cls:

        plan = GeneratedTaskPlan(
            story_id="STORY-99",
            story_title="Test Story",
            story_summary="Summary",
            team_id="T1",
            project_id="P1",
            sprint_id="S1",
            tasks=[
                GeneratedTask(
                    title="FE - Test Task",
                    task_type="FE",
                    objective="Objective",
                    scope="Scope",
                    expected_behavior="Expected",
                    testing_considerations="Tests",
                )
            ],
        )
        mock_plan_cls.return_value.load_latest_for_story.return_value = plan

        # User types "NO"
        result = runner.invoke(app, ["create", "--story-id", "STORY-99"], input="NO\n")
        assert result.exit_code == 0
        assert "Creation cancelled by user" in result.output
        mock_creator_cls.return_value.execute_plan.assert_not_called()


def test_cli_create_with_confirm_flag() -> None:
    with patch("src.main.PlanStore") as mock_plan_cls, \
         patch("src.main.TaskCreator") as mock_creator_cls:

        from src.services.task_creator import CreationResult

        plan = GeneratedTaskPlan(
            story_id="STORY-99",
            story_title="Test Story",
            story_summary="Summary",
            team_id="T1",
            project_id="P1",
            sprint_id="S1",
            tasks=[
                GeneratedTask(
                    title="FE - Test Task",
                    task_type="FE",
                    objective="Objective",
                    scope="Scope",
                    expected_behavior="Expected",
                    testing_considerations="Tests",
                )
            ],
        )
        mock_plan_cls.return_value.load_latest_for_story.return_value = plan
        mock_creator_cls.return_value.execute_plan.return_value = CreationResult(
            execution_id="exec_123",
            total_tasks=1,
            created_tasks=1,
            skipped_tasks=0,
            failed_tasks=0,
            tasks=[],
        )

        result = runner.invoke(app, ["create", "--story-id", "STORY-99", "--confirm"])
        assert result.exit_code == 0
        assert "Execution completed!" in result.output
        assert "Created: 1/1" in result.output
        mock_creator_cls.return_value.execute_plan.assert_called_once_with(plan, dry_run=False)


def test_cli_bulk_generate(tmp_path: Path) -> None:
    csv_file = tmp_path / "stories.csv"
    csv_file.write_text("story_id\nSTORY-1\nSTORY-2\n")

    with patch("src.main.StoryService") as mock_story_cls, \
         patch("src.main.AIStoryAnalyzer") as mock_ai_cls, \
         patch("src.main.TaskGenerator") as mock_gen_cls, \
         patch("src.main.DuplicateDetector") as mock_dup_cls, \
         patch("src.main.PlanStore") as mock_store_cls:

        mock_story_instance = MagicMock()
        mock_story_instance.fetch_story.side_effect = lambda story_id, **kw: StoryItem(
            id=story_id,
            name=f"Title {story_id}",
            description="Desc",
            acceptance_criteria="AC",
            team_id="T1",
            project_id="P1",
            sprint_id="S1",
            subitems=[],
        )
        mock_story_instance.get_project_users.return_value = {}
        mock_story_instance.extract_story_owners.return_value = (None, None)
        mock_story_cls.return_value = mock_story_instance

        mock_ai_cls.return_value.analyze_story.return_value = StoryAnalysisResult(summary="S", fe_tasks=[], be_tasks=[])
        mock_gen_cls.return_value.generate_plan.side_effect = lambda story, **kw: GeneratedTaskPlan(
            plan_id=f"plan_{story.id}",
            story_id=story.id,
            story_title=story.name,
            story_summary="Sum",
            team_id=story.team_id,
            project_id=story.project_id,
            sprint_id=story.sprint_id,
            tasks=[
                GeneratedTask(
                    title=f"FE - Task for {story.id}",
                    task_type="FE",
                    objective="Obj",
                    scope="Scope",
                    expected_behavior="Exp",
                )
            ],
        )

        result = runner.invoke(app, ["bulk-generate", "--file", str(csv_file)])
        assert result.exit_code == 0
        assert "Bulk Task Plan Generation (2 Stories)" in result.output
        assert "2 successful" in result.output
        assert "STORY-1" in result.output
        assert "STORY-2" in result.output


def test_cli_bulk_create_dry_run() -> None:
    with patch("src.main.PlanStore") as mock_store_cls, \
         patch("src.main.TaskCreator") as mock_creator_cls:

        from src.services.task_creator import DryRunOperation

        plan = GeneratedTaskPlan(
            plan_id="p1",
            story_id="STORY-1",
            story_title="Story 1",
            story_summary="Sum",
            team_id="T1",
            project_id="P1",
            sprint_id="S1",
            tasks=[
                GeneratedTask(
                    title="FE - Task",
                    task_type="FE",
                    objective="Obj",
                    scope="Scope",
                    expected_behavior="Exp",
                )
            ],
        )
        mock_store_cls.return_value.load_latest_for_story.return_value = plan
        mock_creator_cls.return_value.dry_run.return_value = [
            DryRunOperation(task_title="FE - Task", method="POST", endpoint="/item", payload={})
        ]

        result = runner.invoke(app, ["bulk-create", "--story-ids", "STORY-1", "--dry-run"])
        assert result.exit_code == 0
        assert "Bulk Dry-Run Simulation Summary" in result.output
        assert "Total operations simulated: 1" in result.output

