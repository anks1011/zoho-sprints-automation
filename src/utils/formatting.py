"""Rich CLI formatting and preview rendering utilities."""

from __future__ import annotations

from typing import List, Optional
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from src.client.models import StoryItem
from src.services.duplicate_detector import DuplicateMatch
from src.services.task_models import GeneratedTask, GeneratedTaskPlan

console = Console()


def print_header(title: str) -> None:
    """Print a styled section header."""
    console.print(Panel(Text(title, style="bold cyan"), expand=False))


def display_story_details(story: StoryItem) -> None:
    """Display parent story metadata and existing subtasks in rich tables."""
    table = Table(title="Zoho Sprints Story Details", show_header=True, header_style="bold magenta")
    table.add_column("Field", style="bold cyan", width=20)
    table.add_column("Value", style="white")

    table.add_row("Story ID", story.id)
    table.add_row("Title", story.name)
    table.add_row("Team ID", story.team_id)
    table.add_row("Project ID", story.project_id)
    table.add_row("Sprint ID", story.sprint_id)
    if story.item_type_name:
        table.add_row("Item Type", story.item_type_name)
    if story.priority_name:
        table.add_row("Priority", story.priority_name)
    table.add_row("Existing Subtasks", str(len(story.subitems)))

    console.print(table)

    if story.description:
        console.print(
            Panel(
                story.description.strip(),
                title="[bold yellow]Description[/bold yellow]",
                border_style="yellow",
            )
        )

    if story.acceptance_criteria:
        console.print(
            Panel(
                story.acceptance_criteria.strip(),
                title="[bold green]Acceptance Criteria[/bold green]",
                border_style="green",
            )
        )

    if story.subitems:
        sub_table = Table(title="Existing Subtasks", show_header=True, header_style="bold blue")
        sub_table.add_column("ID", style="dim", width=12)
        sub_table.add_column("Name", style="white")
        sub_table.add_column("Status", style="green", width=12)
        for s in story.subitems:
            sub_table.add_row(s.id, s.name, s.status or "Open")
        console.print(sub_table)


def display_plan_preview(
    plan: GeneratedTaskPlan,
    duplicates: Optional[List[DuplicateMatch]] = None,
) -> None:
    """Render the generated task plan preview with warnings and task descriptions."""
    console.print()
    console.print(f"[bold cyan]Parent Story:[/bold cyan] [bold white]{plan.story_id} - {plan.story_title}[/bold white]")
    console.print(f"[dim]Plan ID: {plan.plan_id} | Created: {plan.created_at}[/dim]")
    console.print()

    if plan.story_summary:
        console.print(f"[bold]Summary:[/bold] {plan.story_summary}")

    if plan.assumptions:
        console.print(
            Panel(
                "\n".join(f"• {a}" for a in plan.assumptions),
                title="[bold blue]Assumptions[/bold blue]",
                border_style="blue",
            )
        )

    if plan.ambiguities:
        console.print(
            Panel(
                "\n".join(f"⚠️  {a}" for a in plan.ambiguities),
                title="[bold yellow]Ambiguities Identified[/bold yellow]",
                border_style="yellow",
            )
        )

    if duplicates:
        dup_table = Table(
            title="⚠️  Existing Task Overlap Warnings",
            show_header=True,
            header_style="bold red",
        )
        dup_table.add_column("Generated Task", style="white")
        dup_table.add_column("Existing Subtask", style="dim")
        dup_table.add_column("Match Type", style="bold yellow")
        dup_table.add_column("Similarity", style="cyan")
        dup_table.add_column("Recommendation", style="white")

        for d in duplicates:
            dup_table.add_row(
                d.generated_title,
                f"{d.existing_title} (ID: {d.existing_id})",
                d.match_type,
                f"{int(d.similarity_score * 100)}%",
                d.recommendation,
            )
        console.print(dup_table)

    console.print()
    console.print("[bold green]Generated Tasks:[/bold green]")
    console.print("=" * 60)

    for task in plan.tasks:
        task_color = "bold cyan" if task.task_type == "FE" else "bold magenta"
        console.print(f"[{task_color}]{task.title}[/{task_color}]")
        console.print()
        console.print(task.format_description())
        console.print("-" * 60)

    console.print()
    console.print(
        f"[bold white]Total generated tasks: {plan.total_task_count} "
        f"({len(plan.fe_tasks)} FE, {len(plan.be_tasks)} BE)[/bold white]"
    )
    console.print()
