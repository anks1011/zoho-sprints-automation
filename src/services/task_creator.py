"""Task creation service with dry-run support, idempotency, and resume capabilities."""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from rich.console import Console
from rich.table import Table

from src.client.models import Subitem
from src.client.sprints_api import SprintsAPI
from src.client.zoho_client import SprintsAPIError
from src.config import Settings, get_settings
from src.services.execution_tracker import ExecutionRecord, ExecutionTracker, TaskExecutionState
from src.services.owner_validator import OwnerValidator
from src.services.task_models import GeneratedTask, GeneratedTaskPlan
from src.utils.security import sanitize_payload

logger = logging.getLogger(__name__)
console = Console()


@dataclass
class DryRunOperation:
    """Represents a simulated API operation during dry-run."""

    task_title: str
    method: str
    endpoint: str
    payload: Dict[str, Any]


@dataclass
class CreationResult:
    """Outcome of a task creation batch."""

    execution_id: str
    total_tasks: int
    created_tasks: int
    skipped_tasks: int
    failed_tasks: int
    tasks: List[TaskExecutionState]
    is_dry_run: bool = False


class TaskCreator:
    """Creates approved subtasks under the parent story in Zoho Sprints."""

    def __init__(
        self,
        settings: Optional[Settings] = None,
        sprints_api: Optional[SprintsAPI] = None,
        tracker: Optional[ExecutionTracker] = None,
    ) -> None:
        self.settings = settings or get_settings()
        self.api = sprints_api or SprintsAPI(self.settings)
        self.tracker = tracker or ExecutionTracker(self.settings)

    def resolve_item_type_and_priority(
        self, team_id: str, project_id: str
    ) -> tuple[str, str]:
        """Resolve valid projitemtypeid and projpriorityid for subtasks."""
        # 1. Check configured item type
        item_type_id = self.settings.zoho_default_item_type_id
        if not item_type_id:
            try:
                available_types = self.api.get_item_types(team_id, project_id)
                # Look for "Task" or default
                task_type = next(
                    (t for t in available_types if t.name.lower() == "task"), None
                ) or next((t for t in available_types if t.is_default), None)
                if task_type:
                    item_type_id = task_type.id
                elif available_types:
                    item_type_id = available_types[0].id
            except Exception as e:
                logger.warning("Could not fetch project item types: %s", str(e))

        if not item_type_id:
            raise SprintsAPIError(
                f"No item type ID found for project {project_id}. "
                f"Please configure ZOHO_DEFAULT_ITEM_TYPE_ID in .env."
            )

        # 2. Check configured priority
        priority_id = self.settings.zoho_default_priority_id
        if not priority_id:
            try:
                available_priorities = self.api.get_priorities(team_id, project_id)
                # Look for "None", "Low", "Medium" or default
                prio = (
                    next((p for p in available_priorities if p.name.lower() in ("none", "medium", "normal")), None)
                    or next((p for p in available_priorities if p.is_default), None)
                    or (available_priorities[0] if available_priorities else None)
                )
                if prio:
                    priority_id = prio.id
            except Exception as e:
                logger.warning("Could not fetch project priority types: %s", str(e))

        if not priority_id:
            raise SprintsAPIError(
                f"No priority ID found for project {project_id}. "
                f"Please configure ZOHO_DEFAULT_PRIORITY_ID in .env."
            )

        return str(item_type_id), str(priority_id)

    def _extract_parent_custom_fields(self, plan: GeneratedTaskPlan) -> Dict[str, Any]:
        """Extract parent story custom UDF fields (e.g. Dev Owner, Module) to satisfy mandatory project fields."""
        try:
            story = self.api.get_item(plan.team_id, plan.project_id, plan.sprint_id, plan.story_id)
            custom_fields = {}
            if story and story.raw_data and isinstance(story.raw_data, dict):
                for k, v in story.raw_data.items():
                    if k.startswith("UDF_") and v and v != "-1" and v != -1:
                        custom_fields[k] = v
            return custom_fields
        except Exception as e:
            logger.warning("Could not extract parent story custom fields: %s", str(e))
            return {}

    def _build_task_url(self, team_id: str, project_id: str, task_id: str) -> str:
        """Construct direct web URL to the created subitem in Zoho Sprints."""
        base_portal = self.settings.zoho_accounts_url.replace("accounts", "sprints")
        if "sprints" not in base_portal:
            base_portal = "https://sprints.zoho.in"
        team_name = "nopaperforms"
        return f"{base_portal}/workspace/{team_name}#itemdetails/{project_id}/{task_id}"

    def resolve_dev_status_id(self, team_id: str, project_id: str) -> Optional[str]:
        """Resolve the status ID for 'In Dev' or 'Dev' in the project's workflow."""
        try:
            statuses = self.api.get_project_statuses(team_id, project_id)
            for s in statuses:
                sname = str(s.get("statusName") or s.get("name") or "").lower().strip()
                if sname in ("in dev", "dev", "development", "in development"):
                    return str(s.get("statusId") or s.get("id"))
            for s in statuses:
                sname = str(s.get("statusName") or s.get("name") or "").lower().strip()
                if "dev" in sname:
                    return str(s.get("statusId") or s.get("id"))
        except Exception as e:
            logger.warning("Could not resolve dev status ID from API: %s", str(e))
        return "39713000000198342"  # fallback default for this project

    def _build_task_payload(
        self,
        task: GeneratedTask,
        item_type_id: str,
        priority_id: str,
        base_custom_fields: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Construct Zoho Sprints subitem creation payload with inherited owners."""
        payload: Dict[str, Any] = {
            "name": task.title,
            "projitemtypeid": item_type_id,
            "projpriorityid": priority_id,
            "description": task.format_description(),
            **base_custom_fields,
        }
        # Task Assignee (Story Dev Owner) -> users JSONArray & UDF_USERPKL3
        if task.assignee and task.assignee.user_id:
            payload["users"] = json.dumps([task.assignee.user_id])
            payload["UDF_USERPKL3"] = task.assignee.user_id

        # Task QA Owner (Story QA Owner) -> UDF_USERPKL2
        if task.qa_owner and task.qa_owner.user_id:
            payload["UDF_USERPKL2"] = task.qa_owner.user_id

        return payload

    def dry_run(self, plan: GeneratedTaskPlan) -> List[DryRunOperation]:
        """Simulate subtask creation and return intended API operations without writing."""
        item_type_id, priority_id = self.resolve_item_type_and_priority(
            plan.team_id, plan.project_id
        )
        custom_fields = self._extract_parent_custom_fields(plan)

        operations: List[DryRunOperation] = []
        endpoint = (
            f"{self.settings.zoho_api_base_url}/team/{plan.team_id}/projects/{plan.project_id}/"
            f"sprints/{plan.sprint_id}/item/{plan.story_id}/subitem/"
        )

        for task in plan.tasks:
            raw_payload = self._build_task_payload(
                task=task,
                item_type_id=item_type_id,
                priority_id=priority_id,
                base_custom_fields=custom_fields,
            )
            operations.append(
                DryRunOperation(
                    task_title=task.title,
                    method="POST",
                    endpoint=endpoint,
                    payload=sanitize_payload(raw_payload),
                )
            )

        return operations

    def execute_plan(
        self,
        plan: GeneratedTaskPlan,
        dry_run: bool = False,
    ) -> CreationResult:
        """Create all tasks in the plan under the parent story, with full tracking."""
        if dry_run:
            ops = self.dry_run(plan)
            # Display dry run summary
            table = Table(title="[bold yellow]DRY-RUN: Intended Zoho Sprints API Calls (No Writes)[/bold yellow]")
            table.add_column("Task Title", style="white")
            table.add_column("HTTP Method", style="cyan")
            table.add_column("Endpoint", style="dim")
            table.add_column("Item Type ID", style="magenta")
            table.add_column("Priority ID", style="magenta")

            for op in ops:
                table.add_row(
                    op.task_title,
                    op.method,
                    op.endpoint,
                    str(op.payload.get("projitemtypeid")),
                    str(op.payload.get("projpriorityid")),
                )
            console.print(table)

            return CreationResult(
                execution_id="dry-run",
                total_tasks=len(plan.tasks),
                created_tasks=0,
                skipped_tasks=0,
                failed_tasks=0,
                tasks=[
                    TaskExecutionState(title=t.title, task_type=t.task_type, status="SKIPPED")
                    for t in plan.tasks
                ],
                is_dry_run=True,
            )

        # Live Execution Flow - validate owners first
        validation = OwnerValidator.validate_plan_owners(plan)
        if not validation.valid:
            err_messages = "; ".join(f"[{e.code}] {e.message}" for e in validation.errors)
            raise SprintsAPIError(f"Owner validation failed before execution: {err_messages}")

        item_type_id, priority_id = self.resolve_item_type_and_priority(
            plan.team_id, plan.project_id
        )
        custom_fields = self._extract_parent_custom_fields(plan)

        record = self.tracker.create_execution(plan)
        record.status = "IN_PROGRESS"
        self.tracker.save_execution(record)

        # Map tasks by title for fast lookup
        plan_task_map = {t.title: t for t in plan.tasks}
        dev_status_id = self.resolve_dev_status_id(plan.team_id, plan.project_id)

        for state in record.tasks:
            if state.status == "CREATED":
                logger.info("Task '%s' already created (ID: %s), skipping.", state.title, state.zoho_task_id)
                continue

            task_def = plan_task_map.get(state.title)
            if not task_def:
                continue

            state.attempted_at = datetime.now(timezone.utc).isoformat()
            task_payload = self._build_task_payload(
                task=task_def,
                item_type_id=item_type_id,
                priority_id=priority_id,
                base_custom_fields=custom_fields,
            )
            users_val = task_payload.pop("users", None)
            for k in ["name", "projitemtypeid", "projpriorityid", "description"]:
                task_payload.pop(k, None)

            try:
                subitem = self.api.create_subitem(
                    team_id=plan.team_id,
                    project_id=plan.project_id,
                    sprint_id=plan.sprint_id,
                    item_id=plan.story_id,
                    name=task_def.title,
                    item_type_id=item_type_id,
                    priority_id=priority_id,
                    description=task_def.format_description(),
                    custom_fields=task_payload,
                    users=users_val,
                )

                # Move created subitem to In Dev status
                if dev_status_id:
                    try:
                        self.api.update_item_status(
                            team_id=plan.team_id,
                            project_id=plan.project_id,
                            sprint_id=plan.sprint_id,
                            item_id=subitem.id,
                            status_id=dev_status_id,
                        )
                        logger.info("Moved subitem '%s' (%s) to 'In Dev' status (%s)", task_def.title, subitem.id, dev_status_id)
                    except Exception as status_err:
                        logger.warning("Subitem created (%s) but failed moving to In Dev: %s", subitem.id, str(status_err))

                state.status = "CREATED"
                state.zoho_task_id = subitem.id
                state.zoho_task_url = self._build_task_url(plan.team_id, plan.project_id, subitem.id)
                state.error_message = None
                console.print(f"[bold green]✓ Created & Moved to In Dev:[/bold green] {task_def.title} (ID: {subitem.id}) - {state.zoho_task_url}")
            except Exception as e:
                state.status = "FAILED"
                state.error_message = str(e)
                console.print(f"[bold red]✗ Failed:[/bold red] {task_def.title} - {str(e)}")
                logger.error("Failed to create subitem '%s': %s", task_def.title, str(e))

            # Save state after each task for resilience
            self.tracker.save_execution(record)

        # Final record status
        record.status = "COMPLETED" if record.failed_count == 0 else "PARTIAL"
        self.tracker.save_execution(record)

        return CreationResult(
            execution_id=record.execution_id,
            total_tasks=len(record.tasks),
            created_tasks=record.created_count,
            skipped_tasks=0,
            failed_tasks=record.failed_count,
            tasks=record.tasks,
            is_dry_run=False,
        )

    def resume_execution(self, execution_id: str, plan: GeneratedTaskPlan) -> CreationResult:
        """Resume a partially failed execution, skipping already created tasks."""
        # Validate owners before resuming
        validation = OwnerValidator.validate_plan_owners(plan)
        if not validation.valid:
            err_messages = "; ".join(f"[{e.code}] {e.message}" for e in validation.errors)
            raise SprintsAPIError(f"Owner validation failed before resume: {err_messages}")

        record = self.tracker.load_execution(execution_id)
        if not record:
            raise SprintsAPIError(f"Execution record '{execution_id}' not found.")

        if record.status == "COMPLETED":
            console.print(f"[bold green]Execution '{execution_id}' is already fully completed.[/bold green]")
            return CreationResult(
                execution_id=record.execution_id,
                total_tasks=len(record.tasks),
                created_tasks=record.created_count,
                skipped_tasks=0,
                failed_tasks=0,
                tasks=record.tasks,
            )

        item_type_id, priority_id = self.resolve_item_type_and_priority(
            record.team_id, record.project_id
        )
        custom_fields = self._extract_parent_custom_fields(plan)

        dev_status_id = self.resolve_dev_status_id(record.team_id, record.project_id)
        plan_task_map = {t.title: t for t in plan.tasks}
        record.status = "IN_PROGRESS"

        for state in record.tasks:
            if state.status == "CREATED":
                logger.info("Skipping already created task: %s (ID: %s)", state.title, state.zoho_task_id)
                continue

            task_def = plan_task_map.get(state.title)
            if not task_def:
                continue

            state.attempted_at = datetime.now(timezone.utc).isoformat()
            task_payload = self._build_task_payload(
                task=task_def,
                item_type_id=item_type_id,
                priority_id=priority_id,
                base_custom_fields=custom_fields,
            )
            users_val = task_payload.pop("users", None)
            for k in ["name", "projitemtypeid", "projpriorityid", "description"]:
                task_payload.pop(k, None)

            try:
                subitem = self.api.create_subitem(
                    team_id=record.team_id,
                    project_id=record.project_id,
                    sprint_id=record.sprint_id,
                    item_id=record.story_id,
                    name=task_def.title,
                    item_type_id=item_type_id,
                    priority_id=priority_id,
                    description=task_def.format_description(),
                    custom_fields=task_payload,
                    users=users_val,
                )

                # Move resumed subitem to In Dev status
                if dev_status_id:
                    try:
                        self.api.update_item_status(
                            team_id=record.team_id,
                            project_id=record.project_id,
                            sprint_id=record.sprint_id,
                            item_id=subitem.id,
                            status_id=dev_status_id,
                        )
                        logger.info("Moved resumed subitem '%s' (%s) to 'In Dev' status (%s)", task_def.title, subitem.id, dev_status_id)
                    except Exception as status_err:
                        logger.warning("Resumed subitem created (%s) but failed moving to In Dev: %s", subitem.id, str(status_err))

                state.status = "CREATED"
                state.zoho_task_id = subitem.id
                state.zoho_task_url = self._build_task_url(record.team_id, record.project_id, subitem.id)
                state.error_message = None
                console.print(f"[bold green]✓ Created & Moved to In Dev (Resumed):[/bold green] {task_def.title} (ID: {subitem.id}) - {state.zoho_task_url}")
            except Exception as e:
                state.status = "FAILED"
                state.error_message = str(e)
                console.print(f"[bold red]✗ Failed (Resumed):[/bold red] {task_def.title} - {str(e)}")

            self.tracker.save_execution(record)

        record.status = "COMPLETED" if record.failed_count == 0 else "PARTIAL"
        self.tracker.save_execution(record)

        return CreationResult(
            execution_id=record.execution_id,
            total_tasks=len(record.tasks),
            created_tasks=record.created_count,
            skipped_tasks=0,
            failed_tasks=record.failed_count,
            tasks=record.tasks,
        )

    def update_all_executed_tasks_descriptions(
        self, plan_store: Optional[Any] = None, dry_run: bool = False
    ) -> Dict[str, Any]:
        """Fetch all tasks created by this application from existing executions/plans,
        reformat each task description into clean Zoho-compatible readable format,
        and completely remove Testing Considerations and Acceptance Criteria sections and content.
        """
        if plan_store is None:
            from src.services.plan_store import PlanStore
            plan_store = PlanStore(settings=self.settings)

        records = self.tracker.list_records()
        processed_tasks = set()
        updated_tasks = []
        errors = []

        for record in records:
            plan = None
            if record.plan_id:
                try:
                    plan = plan_store.load_plan(record.plan_id)
                except Exception as e:
                    logger.warning("Could not load plan %s: %s", record.plan_id, e)

            plan_tasks = {t.title.strip(): t for t in plan.tasks} if plan else {}

            for state in record.tasks:
                zoho_task_id = state.zoho_task_id
                title = state.title.strip()

                if not zoho_task_id or zoho_task_id in processed_tasks:
                    continue

                # 1. Obtain clean formatted description
                plan_task = plan_tasks.get(title)
                if plan_task:
                    new_desc = plan_task.format_description()
                else:
                    # Fetch from Zoho and strip
                    try:
                        resp = self.api.client.request(
                            "GET",
                            f"team/{record.team_id}/projects/{record.project_id}/sprints/{record.sprint_id}/item/{zoho_task_id}/",
                            params={"action": "details"},
                        )
                        raw_item = (resp.get("items") or [{}])[0] if isinstance(resp, dict) else {}
                        new_desc = raw_item.get("desc") or raw_item.get("description") or ""
                    except Exception as fetch_err:
                        err_msg = f"Failed to fetch task {zoho_task_id} ({title}): {fetch_err}"
                        logger.error(err_msg)
                        errors.append(err_msg)
                        continue

                # 2. Guarantee removal of Testing Considerations and Acceptance Criteria (headings and contents)
                new_desc = re.sub(
                    r"(?im)^(?:##\s*)?Testing Considerations:?[\s\S]*?(?=(?:^|\n)(?:##\s*)?(?:Acceptance Criteria:|Objective:|Scope:|Expected Behavior:|Dependencies:)|\Z)",
                    "",
                    new_desc,
                ).strip()
                new_desc = re.sub(
                    r"(?im)^(?:##\s*)?Acceptance Criteria:?[\s\S]*?(?=(?:^|\n)(?:##\s*)?(?:Testing Considerations:|Objective:|Scope:|Expected Behavior:|Dependencies:)|\Z)",
                    "",
                    new_desc,
                ).strip()

                if not dry_run:
                    endpoint = f"team/{record.team_id}/projects/{record.project_id}/sprints/{record.sprint_id}/item/{zoho_task_id}/"
                    try:
                        self.api.client.request("POST", endpoint, data={"description": new_desc})
                        processed_tasks.add(zoho_task_id)
                        updated_tasks.append({
                            "zoho_task_id": zoho_task_id,
                            "title": title,
                            "plan_id": record.plan_id,
                            "story_id": record.story_id,
                            "status": "UPDATED",
                            "description": new_desc,
                        })
                        logger.info("Updated task %s (%s)", zoho_task_id, title)
                    except Exception as update_err:
                        err_msg = f"Failed to update task {zoho_task_id} ({title}): {update_err}"
                        logger.error(err_msg)
                        errors.append(err_msg)
                else:
                    processed_tasks.add(zoho_task_id)
                    updated_tasks.append({
                        "zoho_task_id": zoho_task_id,
                        "title": title,
                        "plan_id": record.plan_id,
                        "story_id": record.story_id,
                        "status": "DRY_RUN",
                        "description": new_desc,
                    })

        return {
            "total_processed": len(processed_tasks),
            "updated_count": len(updated_tasks),
            "errors": errors,
            "tasks": updated_tasks,
        }

