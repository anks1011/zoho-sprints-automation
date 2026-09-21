"""Execution tracking, history, and resume endpoints."""

from __future__ import annotations

import logging
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status

from src.api.schemas import (
    CreationResultResponse,
    ErrorResponse,
    ExecutionRecordResponse,
    TaskExecutionStateSchema,
)
from src.config import Settings, get_settings
from src.services.execution_tracker import ExecutionRecord, ExecutionTracker
from src.services.plan_store import PlanStore
from src.services.task_creator import TaskCreator

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/executions", tags=["Executions"])


def get_execution_tracker(settings: Settings = Depends(get_settings)) -> ExecutionTracker:
    return ExecutionTracker(settings=settings)


def get_plan_store(settings: Settings = Depends(get_settings)) -> PlanStore:
    return PlanStore(settings=settings)


def get_task_creator(settings: Settings = Depends(get_settings)) -> TaskCreator:
    return TaskCreator(settings=settings)


def _to_execution_response(record: ExecutionRecord) -> ExecutionRecordResponse:
    task_states = [
        TaskExecutionStateSchema(
            title=t.title,
            task_type=t.task_type,
            status=t.status,
            zoho_task_id=t.zoho_task_id,
            error_message=t.error_message,
            attempted_at=t.attempted_at,
        )
        for t in record.tasks
    ]

    return ExecutionRecordResponse(
        execution_id=record.execution_id,
        plan_id=record.plan_id,
        story_id=record.story_id,
        team_id=record.team_id,
        project_id=record.project_id,
        sprint_id=record.sprint_id,
        status=record.status,
        tasks=task_states,
        created_count=record.created_count,
        failed_count=record.failed_count,
        pending_count=record.pending_count,
        created_at=record.created_at,
        updated_at=record.updated_at,
    )


@router.get(
    "",
    response_model=List[ExecutionRecordResponse],
    summary="List execution history",
)
def list_executions(
    tracker: ExecutionTracker = Depends(get_execution_tracker),
) -> List[ExecutionRecordResponse]:
    """Retrieve all execution records sorted by updated_at descending."""
    exec_ids = tracker.list_executions()
    records: List[ExecutionRecord] = []
    for eid in exec_ids:
        rec = tracker.load_execution(eid)
        if rec:
            records.append(rec)

    # Sort descending by updated_at
    records.sort(key=lambda r: r.updated_at, reverse=True)
    return [_to_execution_response(r) for r in records]


@router.get(
    "/{execution_id}",
    response_model=ExecutionRecordResponse,
    responses={
        404: {"model": ErrorResponse, "description": "Execution record not found"},
    },
    summary="Get execution details",
)
def get_execution(
    execution_id: str,
    tracker: ExecutionTracker = Depends(get_execution_tracker),
) -> ExecutionRecordResponse:
    """Retrieve a single execution record by execution ID."""
    rec = tracker.load_execution(execution_id.strip())
    if not rec:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Execution record '{execution_id}' not found.",
        )
    return _to_execution_response(rec)


@router.post(
    "/{execution_id}/resume",
    response_model=CreationResultResponse,
    responses={
        404: {"model": ErrorResponse, "description": "Execution or plan not found"},
        500: {"model": ErrorResponse, "description": "Resume execution failure"},
    },
    summary="Resume partial execution",
)
def resume_execution(
    execution_id: str,
    tracker: ExecutionTracker = Depends(get_execution_tracker),
    plan_store: PlanStore = Depends(get_plan_store),
    task_creator: TaskCreator = Depends(get_task_creator),
) -> CreationResultResponse:
    """Resume a partially completed execution, skipping already created tasks."""
    clean_id = execution_id.strip()
    rec = tracker.load_execution(clean_id)
    if not rec:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Execution record '{clean_id}' not found.",
        )

    plan = plan_store.load_plan(rec.plan_id)
    if not plan:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Associated plan '{rec.plan_id}' not found to resume execution.",
        )

    try:
        result = task_creator.resume_execution(clean_id, plan)
    except Exception as e:
        logger.error("Resume failed for execution %s: %s", clean_id, str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to resume execution: {str(e)}",
        ) from e

    # Update plan status if fully completed
    if result.failed_tasks == 0:
        plan.status = "executed"
        plan_store.save_plan(plan)

    task_states = [
        TaskExecutionStateSchema(
            title=t.title,
            task_type=t.task_type,
            status=t.status,
            zoho_task_id=t.zoho_task_id,
            error_message=t.error_message,
            attempted_at=t.attempted_at,
        )
        for t in result.tasks
    ]

    exec_status = "COMPLETED"
    if result.failed_tasks > 0 and result.created_tasks > 0:
        exec_status = "PARTIAL"
    elif result.failed_tasks > 0:
        exec_status = "FAILED"

    return CreationResultResponse(
        execution_id=result.execution_id,
        plan_id=plan.plan_id,
        story_id=plan.story_id,
        total_tasks=result.total_tasks,
        created_tasks=result.created_tasks,
        skipped_tasks=result.skipped_tasks,
        failed_tasks=result.failed_tasks,
        status=exec_status,
        tasks=task_states,
        is_dry_run=result.is_dry_run,
    )
