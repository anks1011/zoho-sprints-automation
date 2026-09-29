"""Plan generation, retrieval, and editing endpoints."""

from __future__ import annotations

import logging
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status

from src.api.schemas import (
    BulkExecuteItemResponse,
    BulkExecuteRequest,
    BulkExecuteResponse,
    BulkGenerateRequest,
    BulkGenerateResponse,
    BulkPlanItemResponse,
    CreationResultResponse,
    DryRunOperationSchema,
    DryRunResponse,
    DuplicateWarningSchema,
    ErrorResponse,
    ExecutePlanRequest,
    GeneratedTaskSchema,
    GeneratePlanRequest,
    PlanResponse,
    PlanValidationResultSchema,
    TaskExecutionStateSchema,
    TaskOwnerSchema,
    UpdatePlanRequest,
    ValidationIssueSchema,
)
from src.config import Settings, get_settings
from src.services.ai_analyzer import AIAnalyzerError, AIStoryAnalyzer
from src.services.duplicate_detector import DuplicateDetector
from src.services.owner_validator import OwnerValidator
from src.services.plan_store import PlanStore
from src.services.story_service import StoryService, StoryServiceError
from src.services.task_creator import TaskCreator
from src.services.task_generator import TaskGenerationError, TaskGenerator
from src.services.task_models import (
    GeneratedTask,
    GeneratedTaskPlan,
    TaskOwner,
    ensure_bullet_points,
    ensure_numbered_list,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/plans", tags=["Plans"])


def get_story_service(settings: Settings = Depends(get_settings)) -> StoryService:
    return StoryService(settings=settings)


def get_ai_analyzer(settings: Settings = Depends(get_settings)) -> AIStoryAnalyzer:
    return AIStoryAnalyzer(settings=settings)


def get_task_generator() -> TaskGenerator:
    return TaskGenerator()


def get_dup_detector() -> DuplicateDetector:
    return DuplicateDetector()


def get_plan_store(settings: Settings = Depends(get_settings)) -> PlanStore:
    return PlanStore(settings=settings)


def get_task_creator(settings: Settings = Depends(get_settings)) -> TaskCreator:
    return TaskCreator(settings=settings)


def _to_plan_response(
    plan: GeneratedTaskPlan,
    duplicates: Optional[List[DuplicateWarningSchema]] = None,
    validation: Optional[PlanValidationResultSchema] = None,
) -> PlanResponse:
    """Helper to convert domain GeneratedTaskPlan to PlanResponse with owners and validation."""
    task_schemas = [
        GeneratedTaskSchema(
            id=t.id,
            title=t.title,
            task_type=t.task_type,
            index=t.index,
            objective=t.objective,
            scope=t.scope,
            expected_behavior=t.expected_behavior,
            dependencies=t.dependencies,
            description=t.format_description(),
            testing_considerations=t.testing_considerations or "",
            acceptance_criteria=t.acceptance_criteria or [],
            assignee=TaskOwnerSchema(
                user_id=t.assignee.user_id,
                display_name=t.assignee.display_name,
                email=t.assignee.email,
            ) if t.assignee else None,
            qa_owner=TaskOwnerSchema(
                user_id=t.qa_owner.user_id,
                display_name=t.qa_owner.display_name,
                email=t.qa_owner.email,
            ) if t.qa_owner else None,
        )
        for t in plan.tasks
    ]

    dev_owner_schema = (
        TaskOwnerSchema(
            user_id=plan.dev_owner.user_id,
            display_name=plan.dev_owner.display_name,
            email=plan.dev_owner.email,
        )
        if plan.dev_owner
        else None
    )

    qa_owner_schema = (
        TaskOwnerSchema(
            user_id=plan.qa_owner.user_id,
            display_name=plan.qa_owner.display_name,
            email=plan.qa_owner.email,
        )
        if plan.qa_owner
        else None
    )

    if validation is None:
        raw_val = OwnerValidator.validate_plan_owners(plan)
        validation = PlanValidationResultSchema(
            valid=raw_val.valid,
            errors=[
                ValidationIssueSchema(code=e.code, message=e.message, field=e.field)
                for e in raw_val.errors
            ],
            warnings=[
                ValidationIssueSchema(code=w.code, message=w.message, field=w.field)
                for w in raw_val.warnings
            ],
        )

    return PlanResponse(
        plan_id=plan.plan_id,
        story_id=plan.story_id,
        story_title=plan.story_title,
        story_summary=plan.story_summary,
        team_id=plan.team_id,
        project_id=plan.project_id,
        sprint_id=plan.sprint_id,
        status=getattr(plan, "status", "draft"),
        assumptions=plan.assumptions,
        ambiguities=plan.ambiguities,
        tasks=task_schemas,
        dev_owner=dev_owner_schema,
        qa_owner=qa_owner_schema,
        validation=validation,
        duplicate_warnings=duplicates or [],
        created_at=plan.created_at,
        updated_at=getattr(plan, "updated_at", None),
    )


def generate_single_plan_helper(
    story_id: str,
    story_service: StoryService,
    ai_analyzer: AIStoryAnalyzer,
    task_generator: TaskGenerator,
    dup_detector: DuplicateDetector,
    plan_store: PlanStore,
    team_id: Optional[str] = None,
    project_id: Optional[str] = None,
    sprint_id: Optional[str] = None,
) -> PlanResponse:
    """Core logic to fetch story, run AI analysis, generate tasks, detect duplicates, and store plan."""
    clean_id = story_id.strip()
    if not clean_id:
        raise ValueError("Story ID cannot be empty.")

    # 1. Fetch story details
    story = story_service.fetch_story(
        story_id=clean_id,
        team_id=team_id,
        project_id=project_id,
        sprint_id=sprint_id,
    )

    # 2. AI Analysis
    analysis = ai_analyzer.analyze_story(story)

    # 3. Resolve story Dev Owner and QA Owner
    project_users = {}
    try:
        project_users = story_service.get_project_users(story.team_id, story.project_id)
    except Exception as e:
        logger.debug("Could not fetch project users for owner lookup: %s", str(e))

    dev_owner = None
    qa_owner = None
    try:
        owners_tuple = story_service.extract_story_owners(story, project_users)
        if isinstance(owners_tuple, (tuple, list)) and len(owners_tuple) == 2:
            dev_owner, qa_owner = owners_tuple[0], owners_tuple[1]
    except Exception as e:
        logger.debug("Failed to extract story owners: %s", str(e))

    # 4. Synthesize tasks with inherited owners
    plan = task_generator.generate_plan(
        story=story,
        analysis=analysis,
        dev_owner=dev_owner,
        qa_owner=qa_owner,
    )

    # 5. Detect duplicates against existing subtasks
    raw_duplicates = dup_detector.analyze_plan_duplicates(plan.tasks, story.subitems)
    dup_warnings = [
        DuplicateWarningSchema(
            generated_title=d.generated_title,
            existing_title=d.existing_title,
            existing_id=d.existing_id,
            match_type=d.match_type,
            similarity_score=d.similarity_score,
            recommendation=d.recommendation,
        )
        for d in raw_duplicates
    ]

    # 6. Persist plan locally
    plan_store.save_plan(plan)

    return _to_plan_response(plan, dup_warnings)


@router.post(
    "/generate",
    response_model=PlanResponse,
    status_code=status.HTTP_200_OK,
    responses={
        400: {"model": ErrorResponse, "description": "Invalid generation request or empty story"},
        404: {"model": ErrorResponse, "description": "Story not found"},
        500: {"model": ErrorResponse, "description": "AI analysis failure"},
    },
)
def generate_task_plan(
    req: GeneratePlanRequest,
    story_service: StoryService = Depends(get_story_service),
    ai_analyzer: AIStoryAnalyzer = Depends(get_ai_analyzer),
    task_generator: TaskGenerator = Depends(get_task_generator),
    dup_detector: DuplicateDetector = Depends(get_dup_detector),
    plan_store: PlanStore = Depends(get_plan_store),
) -> PlanResponse:
    """Generate task plan for a single Zoho Sprints Story ID using AI analyzer and save locally."""
    try:
        return generate_single_plan_helper(
            story_id=req.story_id,
            story_service=story_service,
            ai_analyzer=ai_analyzer,
            task_generator=task_generator,
            dup_detector=dup_detector,
            plan_store=plan_store,
            team_id=req.team_id,
            project_id=req.project_id,
            sprint_id=req.sprint_id,
        )
    except StoryServiceError as e:
        err_str = str(e)
        if "not found" in err_str.lower():
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=err_str) from e
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=err_str) from e
    except AIAnalyzerError as e:
        logger.error("AI analyzer error for story %s: %s", req.story_id, str(e))
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"AI analysis failed: {str(e)}") from e
    except TaskGenerationError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)) from e
    except Exception as e:
        logger.error("Unexpected error generating plan for %s: %s", req.story_id, str(e))
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e)) from e


@router.post(
    "/bulk-generate",
    response_model=BulkGenerateResponse,
    status_code=status.HTTP_200_OK,
)
def bulk_generate_plans(
    req: BulkGenerateRequest,
    story_service: StoryService = Depends(get_story_service),
    ai_analyzer: AIStoryAnalyzer = Depends(get_ai_analyzer),
    task_generator: TaskGenerator = Depends(get_task_generator),
    dup_detector: DuplicateDetector = Depends(get_dup_detector),
    plan_store: PlanStore = Depends(get_plan_store),
) -> BulkGenerateResponse:
    """Generate task plans for multiple Story IDs concurrently with per-story error isolation."""
    def _process_single(sid: str) -> BulkPlanItemResponse:
        try:
            plan_resp = generate_single_plan_helper(
                story_id=sid,
                story_service=story_service,
                ai_analyzer=ai_analyzer,
                task_generator=task_generator,
                dup_detector=dup_detector,
                plan_store=plan_store,
                team_id=req.team_id,
                project_id=req.project_id,
                sprint_id=req.sprint_id,
            )
            return BulkPlanItemResponse(story_id=sid, success=True, plan=plan_resp)
        except Exception as e:
            logger.error("Bulk generate error for story %s: %s", sid, str(e))
            return BulkPlanItemResponse(story_id=sid, success=False, error=str(e))

    try:
        num_workers = min(4, max(1, len(req.story_ids)))
        with ThreadPoolExecutor(max_workers=num_workers) as executor:
            results = list(executor.map(_process_single, req.story_ids))

        successful = sum(1 for r in results if r.success)
        failed = sum(1 for r in results if not r.success)

        return BulkGenerateResponse(
            total=len(req.story_ids),
            successful=successful,
            failed=failed,
            results=results,
        )
    except Exception as e:
        logger.exception("Unexpected error in bulk_generate_plans: %s", str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Bulk plan generation failed: {str(e)}",
        ) from e



@router.get(
    "/{plan_id}",
    response_model=PlanResponse,
    responses={
        404: {"model": ErrorResponse, "description": "Plan not found"},
    },
)
def get_plan(
    plan_id: str,
    plan_store: PlanStore = Depends(get_plan_store),
    story_service: StoryService = Depends(get_story_service),
    dup_detector: DuplicateDetector = Depends(get_dup_detector),
) -> PlanResponse:
    """Retrieve saved task plan by plan_id, including live duplicate checks."""
    plan = plan_store.load_plan(plan_id.strip())
    if not plan:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Plan '{plan_id}' not found.",
        )

    # Check duplicates against live story subtasks if possible
    dup_warnings: List[DuplicateWarningSchema] = []
    try:
        story = story_service.fetch_story(story_id=plan.story_id)
        raw_duplicates = dup_detector.analyze_plan_duplicates(plan.tasks, story.subitems)
        dup_warnings = [
            DuplicateWarningSchema(
                generated_title=d.generated_title,
                existing_title=d.existing_title,
                existing_id=d.existing_id,
                match_type=d.match_type,
                similarity_score=d.similarity_score,
                recommendation=d.recommendation,
            )
            for d in raw_duplicates
        ]
    except Exception as e:
        logger.warning("Could not refresh duplicate warnings for plan %s: %s", plan_id, str(e))

    return _to_plan_response(plan, dup_warnings)


@router.put(
    "/{plan_id}",
    response_model=PlanResponse,
    responses={
        400: {"model": ErrorResponse, "description": "Invalid task data"},
        404: {"model": ErrorResponse, "description": "Plan not found"},
    },
)
def update_plan(
    plan_id: str,
    req: UpdatePlanRequest,
    plan_store: PlanStore = Depends(get_plan_store),
    story_service: StoryService = Depends(get_story_service),
    dup_detector: DuplicateDetector = Depends(get_dup_detector),
) -> PlanResponse:
    """Update editable fields of tasks in a saved plan without modifying Zoho Sprints."""
    plan = plan_store.load_plan(plan_id.strip())
    if not plan:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Plan '{plan_id}' not found.",
        )

    if not req.tasks:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Plan must contain at least one task.",
        )

    # Validate stable task IDs and convert to domain GeneratedTask instances
    prev_task_map = {t.id: t for t in plan.tasks}
    updated_tasks: List[GeneratedTask] = []
    for t_item in req.tasks:
        prev_task = prev_task_map.get(t_item.id)

        # Resolve Assignee
        assignee = None
        if t_item.assignee:
            assignee = TaskOwner(
                user_id=t_item.assignee.user_id,
                display_name=t_item.assignee.display_name,
                email=t_item.assignee.email,
            )
        elif prev_task and prev_task.assignee:
            assignee = prev_task.assignee
        elif plan.dev_owner:
            assignee = plan.dev_owner

        # Resolve QA Owner
        qa_owner = None
        if t_item.qa_owner:
            qa_owner = TaskOwner(
                user_id=t_item.qa_owner.user_id,
                display_name=t_item.qa_owner.display_name,
                email=t_item.qa_owner.email,
            )
        elif prev_task and prev_task.qa_owner:
            qa_owner = prev_task.qa_owner
        elif plan.qa_owner:
            qa_owner = plan.qa_owner

        task_inst = GeneratedTask(
            id=t_item.id,
            title=t_item.title,
            task_type=t_item.task_type,
            index=t_item.index,
            objective=t_item.objective.strip(),
            scope=ensure_numbered_list(t_item.scope, fallback="1. Implement requirements according to story specification."),
            expected_behavior=ensure_numbered_list(t_item.expected_behavior, fallback="1. System behaves as defined in objective."),
            dependencies=ensure_numbered_list(t_item.dependencies, fallback="None identified."),
            testing_considerations=ensure_numbered_list(t_item.testing_considerations, fallback="1. Verify behavior matches expected functionality.\n2. Verify edge cases and error handling."),
            acceptance_criteria=t_item.acceptance_criteria or (prev_task.acceptance_criteria if prev_task else []),
            assignee=assignee,
            qa_owner=qa_owner,
        )
        updated_tasks.append(task_inst)

    plan.tasks = updated_tasks
    if req.story_summary is not None:
        plan.story_summary = req.story_summary
    if req.status is not None:
        plan.status = req.status
    plan.updated_at = datetime.now(timezone.utc).isoformat()

    # Save updated plan to local store
    plan_store.save_plan(plan)

    # Compute duplicate warnings
    dup_warnings: List[DuplicateWarningSchema] = []
    try:
        story = story_service.fetch_story(story_id=plan.story_id)
        raw_duplicates = dup_detector.analyze_plan_duplicates(plan.tasks, story.subitems)
        dup_warnings = [
            DuplicateWarningSchema(
                generated_title=d.generated_title,
                existing_title=d.existing_title,
                existing_id=d.existing_id,
                match_type=d.match_type,
                similarity_score=d.similarity_score,
                recommendation=d.recommendation,
            )
            for d in raw_duplicates
        ]
    except Exception as e:
        logger.warning("Could not refresh duplicate warnings for plan %s: %s", plan_id, str(e))

    return _to_plan_response(plan, dup_warnings)
 
 
@router.post(
    "/{plan_id}/dry-run",
    response_model=DryRunResponse,
    responses={
        404: {"model": ErrorResponse, "description": "Plan not found"},
        500: {"model": ErrorResponse, "description": "Dry-run simulation failed"},
    },
)
def dry_run_plan(
    plan_id: str,
    plan_store: PlanStore = Depends(get_plan_store),
    task_creator: TaskCreator = Depends(get_task_creator),
) -> DryRunResponse:
    """Simulate Zoho Sprints API calls for all tasks in the plan without writing any data."""
    plan = plan_store.load_plan(plan_id.strip())
    if not plan:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Plan '{plan_id}' not found.",
        )

    try:
        operations = task_creator.dry_run(plan)
    except Exception as e:
        logger.error("Dry-run simulation failed for plan %s: %s", plan_id, str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Dry-run simulation failed: {str(e)}",
        ) from e

    op_schemas = [
        DryRunOperationSchema(
            task_title=op.task_title,
            method=op.method,
            endpoint=op.endpoint,
            payload=op.payload,
            item_type_id=str(op.payload.get("projitemtypeid") or ""),
            priority_id=str(op.payload.get("projpriorityid") or ""),
        )
        for op in operations
    ]

    return DryRunResponse(
        plan_id=plan.plan_id,
        story_id=plan.story_id,
        total_operations=len(op_schemas),
        operations=op_schemas,
    )


@router.post(
    "/{plan_id}/validate",
    response_model=PlanValidationResultSchema,
    responses={
        404: {"model": ErrorResponse, "description": "Plan not found"},
    },
)
def validate_plan(
    plan_id: str,
    plan_store: PlanStore = Depends(get_plan_store),
) -> PlanValidationResultSchema:
    """Validate plan owner inheritance and prerequisites."""
    plan = plan_store.load_plan(plan_id.strip())
    if not plan:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Plan '{plan_id}' not found.",
        )
    raw_val = OwnerValidator.validate_plan_owners(plan)
    return PlanValidationResultSchema(
        valid=raw_val.valid,
        errors=[
            ValidationIssueSchema(code=e.code, message=e.message, field=e.field)
            for e in raw_val.errors
        ],
        warnings=[
            ValidationIssueSchema(code=w.code, message=w.message, field=w.field)
            for w in raw_val.warnings
        ],
    )


def execute_single_plan_helper(
    plan_id: str,
    plan_store: PlanStore,
    task_creator: TaskCreator,
    dry_run: bool = False,
    confirm: bool = False,
) -> CreationResultResponse:
    """Core execution logic for a single plan with owner validation and state tracking."""
    if not dry_run and not confirm:
        raise ValueError("Subtask creation requires explicit confirmation. Set 'confirm': true.")

    plan = plan_store.load_plan(plan_id.strip())
    if not plan:
        raise ValueError(f"Plan '{plan_id}' not found.")

    # Owner validation check before live execution
    if not dry_run:
        val = OwnerValidator.validate_plan_owners(plan)
        if not val.valid:
            err_details = [f"[{e.code}] {e.message}" for e in val.errors]
            raise ValueError(f"Plan execution blocked by owner validation: {'; '.join(err_details)}")

    result = task_creator.execute_plan(plan, dry_run=dry_run)

    # Update plan status if live execution finished
    if not dry_run:
        if result.failed_tasks == 0:
            plan.status = "executed"
        else:
            plan.status = "partial"
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
    if result.is_dry_run:
        exec_status = "DRY_RUN"
    elif result.failed_tasks > 0 and result.created_tasks > 0:
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


@router.post(
    "/{plan_id}/execute",
    response_model=CreationResultResponse,
    responses={
        400: {"model": ErrorResponse, "description": "Confirmation required or invalid request"},
        404: {"model": ErrorResponse, "description": "Plan not found"},
        500: {"model": ErrorResponse, "description": "Execution failure"},
    },
)
def execute_plan(
    plan_id: str,
    req: ExecutePlanRequest,
    plan_store: PlanStore = Depends(get_plan_store),
    task_creator: TaskCreator = Depends(get_task_creator),
) -> CreationResultResponse:
    """Execute plan creation under parent story in Zoho Sprints with strict confirmation lock."""
    if not req.dry_run and not req.confirm:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Subtask creation requires explicit confirmation. Set 'confirm': true in the request body.",
        )

    plan = plan_store.load_plan(plan_id.strip())
    if not plan:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Plan '{plan_id}' not found.",
        )

    try:
        return execute_single_plan_helper(
            plan_id=plan_id,
            plan_store=plan_store,
            task_creator=task_creator,
            dry_run=req.dry_run,
            confirm=req.confirm,
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)) from e
    except Exception as e:
        logger.error("Execution failed for plan %s: %s", plan_id, str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Plan execution failed: {str(e)}",
        ) from e


@router.post(
    "/bulk-execute",
    response_model=BulkExecuteResponse,
    status_code=status.HTTP_200_OK,
    responses={
        400: {"model": ErrorResponse, "description": "Confirmation required or invalid request"},
    },
)
def bulk_execute_plans(
    req: BulkExecuteRequest,
    plan_store: PlanStore = Depends(get_plan_store),
    task_creator: TaskCreator = Depends(get_task_creator),
) -> BulkExecuteResponse:
    """Execute multiple plans in bulk with confirmation safety check and error isolation."""
    if not req.dry_run and not req.confirm:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Bulk subtask creation requires explicit confirmation. Set 'confirm': true in request body.",
        )

    def _execute_single(pid: str) -> BulkExecuteItemResponse:
        plan = plan_store.load_plan(pid.strip())
        story_id = plan.story_id if plan else None
        story_title = plan.story_title if plan else None

        if not plan:
            return BulkExecuteItemResponse(
                plan_id=pid,
                story_id=None,
                story_title=None,
                success=False,
                error=f"Plan '{pid}' not found.",
            )

        try:
            res = execute_single_plan_helper(
                plan_id=pid,
                plan_store=plan_store,
                task_creator=task_creator,
                dry_run=req.dry_run,
                confirm=req.confirm,
            )
            return BulkExecuteItemResponse(
                plan_id=pid,
                story_id=story_id,
                story_title=story_title,
                success=True,
                result=res,
            )
        except Exception as e:
            logger.error("Bulk execute error for plan %s: %s", pid, str(e))
            return BulkExecuteItemResponse(
                plan_id=pid,
                story_id=story_id,
                story_title=story_title,
                success=False,
                error=str(e),
            )

    try:
        num_workers = min(4, max(1, len(req.plan_ids)))
        with ThreadPoolExecutor(max_workers=num_workers) as executor:
            results = list(executor.map(_execute_single, req.plan_ids))

        successful = sum(1 for r in results if r.success)
        failed = sum(1 for r in results if not r.success)

        return BulkExecuteResponse(
            total=len(req.plan_ids),
            successful=successful,
            failed=failed,
            dry_run=req.dry_run,
            results=results,
        )
    except Exception as e:
        logger.exception("Unexpected error in bulk_execute_plans: %s", str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Bulk plan execution failed: {str(e)}",
        ) from e


