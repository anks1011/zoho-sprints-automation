"""Zoho Sprints AI Story-to-Tasks Automation CLI."""

from __future__ import annotations

import sys
from typing import Optional

import typer
from rich.console import Console
from rich.prompt import Prompt
from rich.table import Table

from src.auth.oauth_client import OAuthError, ZohoOAuthClient
from src.client.sprints_api import SprintsAPI
from src.client.zoho_client import SprintsAPIError
from src.config import get_settings
from src.logging_config import setup_logging
from src.services.ai_analyzer import AIAnalyzerError, AIStoryAnalyzer
from src.services.duplicate_detector import DuplicateDetector
from src.services.execution_tracker import ExecutionTracker
from src.services.plan_store import PlanStore
from src.services.story_service import StoryService, StoryServiceError
from src.services.task_creator import TaskCreator
from src.services.task_generator import TaskGenerationError, TaskGenerator
from src.utils.formatting import display_plan_preview, display_story_details

app = typer.Typer(
    name="zs-automate",
    help="Production-ready Zoho Sprints AI Story-to-Tasks Automation CLI",
    add_completion=False,
    no_args_is_help=True,
)
console = Console()


@app.callback()
def main_callback(
    log_level: Optional[str] = typer.Option(
        None, "--log-level", help="Override logging level (DEBUG, INFO, WARNING, ERROR)"
    ),
) -> None:
    """Initialize logging and environment."""
    settings = get_settings()
    level = log_level or settings.log_level
    setup_logging(level)


# =========================================================================
# 1. Authentication Commands
# =========================================================================

@app.command("auth")
def auth_command(
    code: Optional[str] = typer.Option(
        None, "--code", help="OAuth authorization code (if already obtained)"
    ),
    redirect_uri: Optional[str] = typer.Option(
        None, "--redirect-uri", help="Override redirect URI registered in Zoho API Console"
    ),
) -> None:
    """Authorize CLI with Zoho Sprints via OAuth 2.0."""
    settings = get_settings()
    if redirect_uri:
        settings.zoho_redirect_uri = redirect_uri
    oauth = ZohoOAuthClient(settings)

    if code:
        try:
            stored = oauth.exchange_code(code)
            console.print("[bold green]✓ Authorization successful! Tokens securely saved.[/bold green]")
        except OAuthError as e:
            console.print(f"[bold red]✗ Authorization failed:[/bold red] {str(e)}")
            raise typer.Exit(code=1)
        return

    # Interactive flow
    try:
        url = oauth.get_authorization_url()
    except OAuthError as e:
        console.print(f"[bold red]✗ Configuration error:[/bold red] {str(e)}")
        raise typer.Exit(code=1)

    console.print("\n[bold cyan]=== Zoho Sprints OAuth 2.0 Authorization ===[/bold cyan]\n")
    console.print(f"[dim]Using Redirect URI: {settings.zoho_redirect_uri}[/dim]\n")
    console.print("1. Open the following URL in your browser to grant permissions:")
    console.print(f"\n[link={url}]{url}[/link]\n")
    console.print("2. After consenting, Zoho will redirect you to your redirect URI.")
    console.print("3. Copy the [bold yellow]'code'[/bold yellow] query parameter from the URL address bar.\n")

    input_code = Prompt.ask("Paste the authorization code here").strip()
    if not input_code:
        console.print("[bold yellow]Operation cancelled. No code provided.[/bold yellow]")
        raise typer.Exit(code=1)

    try:
        stored = oauth.exchange_code(input_code)
        console.print("\n[bold green]✓ Authorization successful![/bold green] Tokens securely stored in `.runtime/tokens/`.")
    except OAuthError as e:
        console.print(f"\n[bold red]✗ Authorization failed:[/bold red] {str(e)}")
        raise typer.Exit(code=1)


@app.command("auth-status")
def auth_status_command() -> None:
    """Check current Zoho OAuth authentication status."""
    settings = get_settings()
    oauth = ZohoOAuthClient(settings)
    status = oauth.get_status()

    table = Table(title="Zoho OAuth Authentication Status", show_header=True, header_style="bold magenta")
    table.add_column("Property", style="bold cyan")
    table.add_column("Value", style="white")

    status_str = "[bold green]Authenticated[/bold green]" if status.is_authenticated else "[bold red]Not Authenticated[/bold red]"
    table.add_row("Status", status_str)
    table.add_row("Refresh Token Available", "Yes" if status.has_refresh_token else "No")
    table.add_row("Access Token Expired", "Yes" if status.is_expired else "No")
    table.add_row("Expires At (UTC)", status.expires_at_iso or "Unknown / Not stored")
    table.add_row("Accounts Domain", status.accounts_url)
    table.add_row("Message", status.message)

    console.print(table)


@app.command("refresh-token")
def refresh_token_command() -> None:
    """Explicitly refresh the Zoho OAuth access token."""
    settings = get_settings()
    oauth = ZohoOAuthClient(settings)
    try:
        stored = oauth.refresh_access_token()
        console.print("[bold green]✓ Access token refreshed successfully![/bold green]")
    except OAuthError as e:
        console.print(f"[bold red]✗ Token refresh failed:[/bold red] {str(e)}")
        raise typer.Exit(code=1)


# =========================================================================
# 2. Zoho Sprints Exploration Commands
# =========================================================================

@app.command("list-teams")
def list_teams_command() -> None:
    """List available Zoho Sprints teams/workspaces."""
    api = SprintsAPI()
    try:
        teams = api.list_teams()
    except Exception as e:
        console.print(f"[bold red]✗ Failed to fetch teams:[/bold red] {str(e)}")
        raise typer.Exit(code=1)

    if not teams:
        console.print("[yellow]No teams found for your account.[/yellow]")
        return

    table = Table(title="Zoho Sprints Teams", show_header=True, header_style="bold cyan")
    table.add_column("Team ID", style="bold white", width=16)
    table.add_column("Team Name", style="white")

    for t in teams:
        table.add_row(t.id, t.name)
    console.print(table)


@app.command("list-projects")
def list_projects_command(
    team_id: Optional[str] = typer.Option(
        None, "--team-id", help="Zoho Sprints Team ID (optional if configured or single team)"
    ),
) -> None:
    """List projects in the specified team."""
    settings = get_settings()
    api = SprintsAPI(settings)
    final_team_id = team_id or settings.zoho_team_id

    if not final_team_id:
        try:
            teams = api.list_teams()
            if len(teams) == 1:
                final_team_id = teams[0].id
            else:
                console.print("[bold red]Please specify --team-id or configure ZOHO_TEAM_ID.[/bold red]")
                raise typer.Exit(code=1)
        except Exception as e:
            console.print(f"[bold red]✗ Failed to resolve team:[/bold red] {str(e)}")
            raise typer.Exit(code=1)

    try:
        projects = api.list_projects(final_team_id)
    except Exception as e:
        console.print(f"[bold red]✗ Failed to fetch projects:[/bold red] {str(e)}")
        raise typer.Exit(code=1)

    table = Table(title=f"Projects in Team {final_team_id}", show_header=True, header_style="bold cyan")
    table.add_column("Project ID", style="bold white", width=16)
    table.add_column("Project Name", style="white")
    table.add_column("Prefix", style="dim", width=10)
    table.add_column("Status", style="green", width=12)

    for p in projects:
        table.add_row(p.id, p.name, p.prefix or "-", p.status or "active")
    console.print(table)


@app.command("list-sprints")
def list_sprints_command(
    team_id: Optional[str] = typer.Option(None, "--team-id", help="Zoho Sprints Team ID"),
    project_id: str = typer.Option(..., "--project-id", help="Zoho Sprints Project ID"),
) -> None:
    """List sprints in the specified project."""
    settings = get_settings()
    api = SprintsAPI(settings)
    final_team_id = team_id or settings.zoho_team_id

    if not final_team_id:
        try:
            teams = api.list_teams()
            if len(teams) == 1:
                final_team_id = teams[0].id
            else:
                console.print("[bold red]Please specify --team-id or configure ZOHO_TEAM_ID.[/bold red]")
                raise typer.Exit(code=1)
        except Exception as e:
            console.print(f"[bold red]✗ Failed to resolve team:[/bold red] {str(e)}")
            raise typer.Exit(code=1)

    try:
        sprints = api.list_sprints(final_team_id, project_id)
    except Exception as e:
        console.print(f"[bold red]✗ Failed to fetch sprints:[/bold red] {str(e)}")
        raise typer.Exit(code=1)

    table = Table(title=f"Sprints in Project {project_id}", show_header=True, header_style="bold cyan")
    table.add_column("Sprint ID", style="bold white", width=16)
    table.add_column("Sprint Name", style="white")
    table.add_column("Status", style="green", width=12)

    for s in sprints:
        table.add_row(s.id, s.name, s.status or "-")
    console.print(table)


# =========================================================================
# 3. Story Details & Generation Commands
# =========================================================================

@app.command("story")
def story_command(
    story_id: str = typer.Option(..., "--story-id", help="Zoho Sprints parent Story/Item ID"),
    team_id: Optional[str] = typer.Option(None, "--team-id", help="Optional Team ID override"),
    project_id: Optional[str] = typer.Option(None, "--project-id", help="Optional Project ID override"),
    sprint_id: Optional[str] = typer.Option(None, "--sprint-id", help="Optional Sprint ID override"),
) -> None:
    """Fetch and display details for a parent Story ID."""
    story_service = StoryService()
    try:
        story = story_service.fetch_story(
            story_id=story_id,
            team_id=team_id,
            project_id=project_id,
            sprint_id=sprint_id,
        )
        display_story_details(story)
    except StoryServiceError as e:
        console.print(f"[bold red]✗ Story retrieval error:[/bold red] {str(e)}")
        raise typer.Exit(code=1)


@app.command("generate")
def generate_command(
    story_id: str = typer.Option(..., "--story-id", help="Zoho Sprints parent Story/Item ID"),
    team_id: Optional[str] = typer.Option(None, "--team-id", help="Optional Team ID override"),
    project_id: Optional[str] = typer.Option(None, "--project-id", help="Optional Project ID override"),
    sprint_id: Optional[str] = typer.Option(None, "--sprint-id", help="Optional Sprint ID override"),
) -> None:
    """Analyze story, synthesize FE and BE task plan, check duplicates, and save plan locally."""
    settings = get_settings()
    story_service = StoryService(settings)
    ai_analyzer = AIStoryAnalyzer(settings)
    task_generator = TaskGenerator()
    dup_detector = DuplicateDetector()
    plan_store = PlanStore(settings)

    # 1. Fetch story
    try:
        story = story_service.fetch_story(
            story_id=story_id,
            team_id=team_id,
            project_id=project_id,
            sprint_id=sprint_id,
        )
    except StoryServiceError as e:
        console.print(f"[bold red]✗ Story retrieval error:[/bold red] {str(e)}")
        raise typer.Exit(code=1)

    # 2. AI Analysis
    try:
        analysis = ai_analyzer.analyze_story(story)
    except AIAnalyzerError as e:
        console.print(f"[bold red]✗ AI analysis error:[/bold red] {str(e)}")
        raise typer.Exit(code=1)

    # 3. Generate Tasks
    try:
        plan = task_generator.generate_plan(story, analysis)
    except TaskGenerationError as e:
        console.print(f"[bold red]✗ Task generation error:[/bold red] {str(e)}")
        raise typer.Exit(code=1)

    # 4. Check Duplicates against existing subtasks
    duplicates = dup_detector.analyze_plan_duplicates(plan.tasks, story.subitems)

    # 5. Save plan locally
    plan_path = plan_store.save_plan(plan)

    # 6. Render preview
    display_plan_preview(plan, duplicates)
    console.print(f"[dim]Plan saved locally to {plan_path}.[/dim]")
    console.print(
        "\n[bold green]To create these tasks under the story, run:[/bold green]\n"
        f"  [cyan]python -m src.main create --story-id {story.id}[/cyan]\n"
        "Or test with dry-run:\n"
        f"  [cyan]python -m src.main create --story-id {story.id} --dry-run[/cyan]\n"
    )


@app.command("preview")
def preview_command(
    story_id: str = typer.Option(..., "--story-id", help="Zoho Sprints parent Story/Item ID"),
) -> None:
    """Preview the latest generated task plan for a story."""
    settings = get_settings()
    plan_store = PlanStore(settings)
    plan = plan_store.load_latest_for_story(story_id.strip())
    if not plan:
        console.print(
            f"[bold yellow]No existing plan found for Story ID '{story_id}'. "
            f"Please run 'generate' first:[/bold yellow]\n"
            f"  [cyan]python -m src.main generate --story-id {story_id}[/cyan]"
        )
        raise typer.Exit(code=1)

    dup_detector = DuplicateDetector()
    story_service = StoryService(settings)
    try:
        story = story_service.fetch_story(story_id=story_id)
        duplicates = dup_detector.analyze_plan_duplicates(plan.tasks, story.subitems)
    except Exception:
        duplicates = []

    display_plan_preview(plan, duplicates)


# =========================================================================
# 4. Task Creation & Resume Commands
# =========================================================================

@app.command("create")
def create_command(
    story_id: str = typer.Option(..., "--story-id", help="Zoho Sprints parent Story/Item ID"),
    dry_run: bool = typer.Option(
        False, "--dry-run", help="Simulate creation and display intended payloads without writing"
    ),
    confirm: bool = typer.Option(
        False, "--confirm", help="Bypass interactive confirmation prompt (non-interactive CI use)"
    ),
    team_id: Optional[str] = typer.Option(None, "--team-id", help="Optional Team ID override"),
    project_id: Optional[str] = typer.Option(None, "--project-id", help="Optional Project ID override"),
    sprint_id: Optional[str] = typer.Option(None, "--sprint-id", help="Optional Sprint ID override"),
) -> None:
    """Create approved tasks under the parent story in Zoho Sprints."""
    settings = get_settings()
    plan_store = PlanStore(settings)
    plan = plan_store.load_latest_for_story(story_id.strip())

    # If plan not generated yet, auto-generate it now
    if not plan:
        console.print(f"[bold blue]No cached plan found for Story '{story_id}'. Generating plan now...[/bold blue]")
        story_service = StoryService(settings)
        ai_analyzer = AIStoryAnalyzer(settings)
        task_generator = TaskGenerator()

        story = story_service.fetch_story(
            story_id=story_id, team_id=team_id, project_id=project_id, sprint_id=sprint_id
        )
        analysis = ai_analyzer.analyze_story(story)
        plan = task_generator.generate_plan(story, analysis)
        plan_store.save_plan(plan)

    dup_detector = DuplicateDetector()
    story_service = StoryService(settings)
    try:
        story = story_service.fetch_story(story_id=story_id)
        duplicates = dup_detector.analyze_plan_duplicates(plan.tasks, story.subitems)
    except Exception:
        duplicates = []

    # Display preview first
    display_plan_preview(plan, duplicates)

    creator = TaskCreator(settings=settings)

    # Dry-run execution
    if dry_run:
        console.print("\n[bold yellow]Executing in DRY-RUN mode. Zero write requests will be made.[/bold yellow]\n")
        creator.execute_plan(plan, dry_run=True)
        return

    # Explicit confirmation required
    if not confirm:
        console.print(f"[bold yellow]You are about to create {plan.total_task_count} tasks under Story ID {story_id}.[/bold yellow]")
        user_input = Prompt.ask(
            f"Do you want to create these tasks under Story ID {story_id}? Type YES to continue"
        ).strip()

        if user_input != "YES":
            console.print("\n[bold yellow]Creation cancelled by user. No tasks were created in Zoho Sprints.[/bold yellow]")
            raise typer.Exit(code=0)

    # Live execution
    console.print(f"\n[bold cyan]Creating {plan.total_task_count} subtasks under Story {story_id}...[/bold cyan]\n")
    try:
        result = creator.execute_plan(plan, dry_run=False)
    except Exception as e:
        console.print(f"[bold red]✗ Task creation failed:[/bold red] {str(e)}")
        raise typer.Exit(code=1)

    console.print(
        f"\n[bold green]Execution completed![/bold green] "
        f"Created: {result.created_tasks}/{result.total_tasks}, "
        f"Failed: {result.failed_tasks}, "
        f"Skipped: {result.skipped_tasks}"
    )
    console.print(f"[dim]Execution ID: {result.execution_id}[/dim]")

    if result.failed_tasks > 0:
        console.print(
            f"\n[bold yellow]Some tasks failed. You can resume this execution later via:[/bold yellow]\n"
            f"  [cyan]python -m src.main resume --execution-id {result.execution_id}[/cyan]"
        )


@app.command("resume")
def resume_command(
    execution_id: str = typer.Option(..., "--execution-id", help="Execution ID to resume"),
) -> None:
    """Resume a partially failed execution without recreating already completed tasks."""
    settings = get_settings()
    tracker = ExecutionTracker(settings)
    record = tracker.load_execution(execution_id.strip())
    if not record:
        console.print(f"[bold red]✗ Execution record '{execution_id}' not found.[/bold red]")
        raise typer.Exit(code=1)

    plan_store = PlanStore(settings)
    plan = plan_store.load_plan(record.plan_id)
    if not plan:
        console.print(f"[bold red]✗ Associated plan '{record.plan_id}' not found for execution.[/bold red]")
        raise typer.Exit(code=1)

    console.print(
        f"[bold cyan]Resuming execution '{execution_id}' for Story '{record.story_id}'...[/bold cyan]"
    )
    console.print(f"Previously created: {record.created_count}, Pending/Failed: {record.pending_count + record.failed_count}")

    creator = TaskCreator(settings=settings, tracker=tracker)
    try:
        result = creator.resume_execution(execution_id, plan)
    except Exception as e:
        console.print(f"[bold red]✗ Resume execution failed:[/bold red] {str(e)}")
        raise typer.Exit(code=1)

    console.print(
        f"\n[bold green]Resume finished![/bold green] "
        f"Total created: {result.created_tasks}/{result.total_tasks}, "
        f"Remaining failed: {result.failed_tasks}"
    )


@app.command("update-tasks")
def update_tasks_command(
    dry_run: bool = typer.Option(
        False, "--dry-run", help="Preview description updates without sending API requests"
    ),
) -> None:
    """Fetch all tasks created by this application from executions/plans and reformat their descriptions, removing Testing Considerations and Acceptance Criteria."""
    settings = get_settings()
    creator = TaskCreator(settings=settings)
    mode_str = "[yellow](DRY RUN)[/yellow]" if dry_run else "[green](LIVE API UPDATE)[/green]"
    console.print(
        f"[bold cyan]Scanning all executions and updating task descriptions {mode_str}...[/bold cyan]"
    )
    result = creator.update_all_executed_tasks_descriptions(dry_run=dry_run)

    table = Table(title=f"Task Description Reformatting Summary {mode_str}")
    table.add_column("Zoho Task ID", style="cyan", no_wrap=True)
    table.add_column("Task Title", style="white")
    table.add_column("Plan ID", style="dim")
    table.add_column("Status", style="green")

    for task_info in result["tasks"]:
        table.add_row(
            task_info["zoho_task_id"],
            task_info["title"],
            task_info["plan_id"] or "N/A",
            task_info["status"],
        )

    console.print(table)

    console.print(
        f"\n[bold green]✓ Done![/bold green] Total processed: {result['total_processed']}, updated: {result['updated_count']}."
    )
    if result["errors"]:
        console.print(f"[bold red]Errors ({len(result['errors'])}):[/bold red]")
        for err in result["errors"]:
            console.print(f" - {err}")



if __name__ == "__main__":
    app()

