"""Execution tracker for tracking subtask creation, idempotency, and resume support."""

from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Literal, Optional
from pydantic import BaseModel, Field

from src.config import Settings, get_settings
from src.services.task_models import GeneratedTask, GeneratedTaskPlan

logger = logging.getLogger(__name__)

ExecutionStatus = Literal["PENDING", "IN_PROGRESS", "COMPLETED", "FAILED", "PARTIAL"]
TaskStatus = Literal["PENDING", "CREATED", "FAILED", "SKIPPED"]


class TaskExecutionState(BaseModel):
    """Execution state for an individual task."""

    title: str
    task_type: Literal["FE", "BE"]
    status: TaskStatus = "PENDING"
    zoho_task_id: Optional[str] = None
    zoho_task_url: Optional[str] = None
    error_message: Optional[str] = None
    attempted_at: Optional[str] = None


class ExecutionRecord(BaseModel):
    """Full execution record for a task plan creation attempt."""

    execution_id: str = Field(default_factory=lambda: f"exec_{uuid.uuid4().hex[:12]}")
    plan_id: str
    story_id: str
    team_id: str
    project_id: str
    sprint_id: str
    status: ExecutionStatus = "PENDING"
    tasks: List[TaskExecutionState] = Field(default_factory=list)
    created_at: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    updated_at: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )

    @property
    def created_count(self) -> int:
        return sum(1 for t in self.tasks if t.status == "CREATED")

    @property
    def failed_count(self) -> int:
        return sum(1 for t in self.tasks if t.status == "FAILED")

    @property
    def pending_count(self) -> int:
        return sum(1 for t in self.tasks if t.status == "PENDING")


class ExecutionTracker:
    """Manages reading and writing execution records to disk."""

    def __init__(self, settings: Optional[Settings] = None) -> None:
        self.settings = settings or get_settings()

    def create_execution(self, plan: GeneratedTaskPlan) -> ExecutionRecord:
        """Initialize and persist a new execution record from a plan."""
        self.settings.ensure_runtime_dirs()

        task_states = [
            TaskExecutionState(
                title=t.title,
                task_type=t.task_type,
                status="PENDING",
            )
            for t in plan.tasks
        ]

        record = ExecutionRecord(
            plan_id=plan.plan_id,
            story_id=plan.story_id,
            team_id=plan.team_id,
            project_id=plan.project_id,
            sprint_id=plan.sprint_id,
            status="PENDING",
            tasks=task_states,
        )
        self.save_execution(record)
        return record

    def save_execution(self, record: ExecutionRecord) -> Path:
        """Persist execution record to .runtime/executions/{execution_id}.json."""
        self.settings.ensure_runtime_dirs()
        record.updated_at = datetime.now(timezone.utc).isoformat()

        exec_file = self.settings.executions_dir / f"{record.execution_id}.json"
        with open(exec_file, "w", encoding="utf-8") as f:
            f.write(record.model_dump_json(indent=2))
        return exec_file

    def load_execution(self, execution_id: str) -> Optional[ExecutionRecord]:
        """Load execution record by ID."""
        exec_file = self.settings.executions_dir / f"{execution_id}.json"
        if not exec_file.exists():
            return None
        try:
            with open(exec_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            return ExecutionRecord.model_validate(data)
        except Exception as e:
            logger.error("Failed to load execution record %s: %s", execution_id, str(e))
            return None

    def list_executions(self) -> List[str]:
        """List all execution IDs."""
        if not self.settings.executions_dir.exists():
            return []
        return [p.stem for p in self.settings.executions_dir.glob("exec_*.json")]

    def list_records(self) -> List[ExecutionRecord]:
        """List all loaded execution records."""
        records = []
        for eid in self.list_executions():
            rec = self.load_execution(eid)
            if rec:
                records.append(rec)
        return records

