"""Safe Pydantic schemas for API requests and responses (zero secret leakage)."""

from __future__ import annotations

from typing import Any, Dict, List, Literal, Optional
from pydantic import BaseModel, Field, field_validator


class AuthStatusResponse(BaseModel):
    """Sanitized authentication status response for the frontend."""
    is_authenticated: bool
    has_refresh_token: bool
    is_expired: bool
    expires_at_iso: Optional[str] = None
    accounts_url: str
    message: str


class SubitemResponse(BaseModel):
    """Subtask/subitem under a parent story."""
    id: str
    name: str
    description: Optional[str] = ""
    item_type_id: Optional[str] = None
    item_type_name: Optional[str] = None
    priority_id: Optional[str] = None
    priority_name: Optional[str] = None
    status: Optional[str] = None
    point: Optional[float] = None


class StoryDetailsResponse(BaseModel):
    """Detailed story response matching StoryItem model."""
    id: str
    name: str
    description: str = ""
    acceptance_criteria: Optional[str] = None
    team_id: Optional[str] = None
    project_id: Optional[str] = None
    sprint_id: Optional[str] = None
    item_type_id: Optional[str] = None
    item_type_name: Optional[str] = None
    priority_id: Optional[str] = None
    priority_name: Optional[str] = None
    status: Optional[str] = None
    subitems: List[SubitemResponse] = Field(default_factory=list)


class GeneratePlanRequest(BaseModel):
    """Request payload to generate tasks for a story."""
    story_id: str
    team_id: Optional[str] = None
    project_id: Optional[str] = None
    sprint_id: Optional[str] = None

    @field_validator("story_id")
    @classmethod
    def validate_story_id(cls, v: str) -> str:
        clean = v.strip()
        if not clean:
            raise ValueError("Story ID cannot be empty.")
        return clean


class DuplicateWarningSchema(BaseModel):
    """Warning payload representing potential duplicate task with an existing subtask."""
    generated_title: str
    existing_title: str
    existing_id: str
    match_type: str
    similarity_score: float
    recommendation: str


class TaskOwnerSchema(BaseModel):
    """Owner representation (Dev or QA)."""
    user_id: str
    display_name: Optional[str] = None
    email: Optional[str] = None


class ValidationIssueSchema(BaseModel):
    """Validation issue item."""
    code: str
    message: str
    field: Optional[str] = None


class PlanValidationResultSchema(BaseModel):
    """Plan owner and prerequisite validation result."""
    valid: bool
    errors: List[ValidationIssueSchema] = Field(default_factory=list)
    warnings: List[ValidationIssueSchema] = Field(default_factory=list)


class GeneratedTaskSchema(BaseModel):
    """Task item within a plan response."""
    id: str
    title: str
    task_type: Literal["FE", "BE"]
    index: Optional[int] = None
    objective: str
    scope: str
    expected_behavior: str
    dependencies: str = "- None identified"
    description: Optional[str] = None
    testing_considerations: Optional[str] = ""
    acceptance_criteria: List[str] = Field(default_factory=list)
    assignee: Optional[TaskOwnerSchema] = None
    qa_owner: Optional[TaskOwnerSchema] = None

    @field_validator("acceptance_criteria", mode="before")
    @classmethod
    def normalize_acceptance_criteria(cls, v: Any) -> List[str]:
        if v is None:
            return []
        if isinstance(v, str):
            return [line.strip() for line in v.splitlines() if line.strip()]
        if isinstance(v, list):
            return [str(item).strip() for item in v if str(item).strip()]
        return []


class PlanResponse(BaseModel):
    """Response payload for a generated or loaded plan."""
    plan_id: str
    story_id: str
    story_title: str
    story_summary: str
    team_id: str
    project_id: str
    sprint_id: str
    status: str = "draft"
    assumptions: List[str] = Field(default_factory=list)
    ambiguities: List[str] = Field(default_factory=list)
    tasks: List[GeneratedTaskSchema] = Field(default_factory=list)
    dev_owner: Optional[TaskOwnerSchema] = None
    qa_owner: Optional[TaskOwnerSchema] = None
    validation: Optional[PlanValidationResultSchema] = None
    duplicate_warnings: List[DuplicateWarningSchema] = Field(default_factory=list)
    created_at: str
    updated_at: Optional[str] = None


class UpdateTaskItem(BaseModel):
    """Editable task item payload for PUT /api/v1/plans/{plan_id}."""
    id: str
    title: str
    task_type: Literal["FE", "BE"]
    index: Optional[int] = None
    objective: str
    scope: str
    expected_behavior: str
    dependencies: str = "None identified"
    testing_considerations: Optional[str] = ""
    acceptance_criteria: List[str] = Field(default_factory=list)
    assignee: Optional[TaskOwnerSchema] = None
    qa_owner: Optional[TaskOwnerSchema] = None

    @field_validator("acceptance_criteria", mode="before")
    @classmethod
    def normalize_acceptance_criteria(cls, v: Any) -> List[str]:
        if v is None:
            return []
        if isinstance(v, str):
            return [line.strip() for line in v.splitlines() if line.strip()]
        if isinstance(v, list):
            return [str(item).strip() for item in v if str(item).strip()]
        return []

    @field_validator("title")
    @classmethod
    def validate_title(cls, v: str) -> str:
        clean = v.strip()
        if not clean:
            raise ValueError("Task title is required.")
        if not (clean.startswith("FE - ") or clean.startswith("BE - ")):
            raise ValueError("Task title must start with 'FE - ' or 'BE - '")
        return clean

    @field_validator("objective", "scope", "expected_behavior")
    @classmethod
    def validate_non_empty_sections(cls, v: str, info: Any) -> str:
        clean = v.strip()
        if not clean:
            raise ValueError(f"Task section '{info.field_name}' cannot be empty.")
        return clean


class UpdatePlanRequest(BaseModel):
    """Payload to update an existing plan."""
    tasks: List[UpdateTaskItem]
    story_summary: Optional[str] = None
    status: Optional[str] = None


class ErrorResponse(BaseModel):
    """Standard error response."""
    detail: str
    error_code: Optional[str] = None


class DryRunOperationSchema(BaseModel):
    """Simulated Zoho Sprints API operation."""
    task_title: str
    method: str
    endpoint: str
    payload: Dict[str, Any]
    item_type_id: Optional[str] = None
    priority_id: Optional[str] = None


class DryRunResponse(BaseModel):
    """Response containing simulated dry-run API operations."""
    plan_id: str
    story_id: str
    total_operations: int
    operations: List[DryRunOperationSchema]


class ExecutePlanRequest(BaseModel):
    """Request payload to execute a plan."""
    confirm: bool = False
    dry_run: bool = False


class TaskExecutionStateSchema(BaseModel):
    """Execution status for an individual task."""
    title: str
    task_type: Literal["FE", "BE"]
    status: Literal["PENDING", "CREATED", "FAILED", "SKIPPED"]
    zoho_task_id: Optional[str] = None
    zoho_task_url: Optional[str] = None
    error_message: Optional[str] = None
    attempted_at: Optional[str] = None


class CreationResultResponse(BaseModel):
    """Result of plan execution."""
    execution_id: str
    plan_id: Optional[str] = None
    story_id: Optional[str] = None
    total_tasks: int
    created_tasks: int
    skipped_tasks: int
    failed_tasks: int
    status: str
    tasks: List[TaskExecutionStateSchema]
    is_dry_run: bool = False


class ExecutionRecordResponse(BaseModel):
    """Saved execution record for history and resume tracking."""
    execution_id: str
    plan_id: str
    story_id: str
    team_id: str
    project_id: str
    sprint_id: str
    status: str
    tasks: List[TaskExecutionStateSchema]
    created_count: int
    failed_count: int
    pending_count: int
    created_at: str
    updated_at: str


# =========================================================================
# Bulk Operations Schemas
# =========================================================================

class BulkGenerateRequest(BaseModel):
    """Request payload to generate plans for multiple story IDs."""
    story_ids: List[str]
    team_id: Optional[str] = None
    project_id: Optional[str] = None
    sprint_id: Optional[str] = None

    @field_validator("story_ids")
    @classmethod
    def validate_story_ids(cls, v: List[str]) -> List[str]:
        cleaned = [s.strip() for s in v if s and s.strip()]
        if not cleaned:
            raise ValueError("Story IDs list cannot be empty.")
        seen = set()
        deduped = []
        for s in cleaned:
            if s not in seen:
                seen.add(s)
                deduped.append(s)
        return deduped


class BulkPlanItemResponse(BaseModel):
    """Result of generating a plan for an individual story in a bulk batch."""
    story_id: str
    success: bool
    error: Optional[str] = None
    plan: Optional[PlanResponse] = None


class BulkGenerateResponse(BaseModel):
    """Response payload for bulk plan generation."""
    total: int
    successful: int
    failed: int
    results: List[BulkPlanItemResponse]


class BulkExecuteRequest(BaseModel):
    """Request payload to execute multiple plans in bulk."""
    plan_ids: List[str]
    confirm: bool = False
    dry_run: bool = False

    @field_validator("plan_ids")
    @classmethod
    def validate_plan_ids(cls, v: List[str]) -> List[str]:
        cleaned = [p.strip() for p in v if p and p.strip()]
        if not cleaned:
            raise ValueError("Plan IDs list cannot be empty.")
        seen = set()
        deduped = []
        for p in cleaned:
            if p not in seen:
                seen.add(p)
                deduped.append(p)
        return deduped


class BulkExecuteItemResponse(BaseModel):
    """Result of executing an individual plan in a bulk batch."""
    plan_id: str
    story_id: Optional[str] = None
    story_title: Optional[str] = None
    success: bool
    error: Optional[str] = None
    result: Optional[CreationResultResponse] = None


class BulkExecuteResponse(BaseModel):
    """Response payload for bulk plan execution."""
    total: int
    successful: int
    failed: int
    dry_run: bool
    results: List[BulkExecuteItemResponse]


# =========================================================================
# Sprint Stories Discovery Schemas
# =========================================================================

class SprintStoryItemSchema(BaseModel):
    """Individual story summary in a sprint."""
    story_id: str
    name: str
    item_type_id: Optional[str] = None
    item_type_name: Optional[str] = None
    priority_id: Optional[str] = None
    priority_name: Optional[str] = None
    status: Optional[str] = None
    point: Optional[float] = None
    dev_owner_id: Optional[str] = None
    dev_owner_name: Optional[str] = None
    qa_owner_id: Optional[str] = None
    qa_owner_name: Optional[str] = None
    is_current_story: bool = False
    existing_tasks_count: Optional[int] = 0
    has_existing_tasks: Optional[bool] = False


class SprintStoriesResponse(BaseModel):
    """Stories in the same sprint as the input story, optionally filtered by Dev Owner."""
    input_story_id: str
    team_id: str
    project_id: str
    sprint_id: str
    sprint_name: Optional[str] = None
    current_user_dev_id: Optional[str] = None
    current_user_dev_name: Optional[str] = None
    filter_applied: bool = True
    total_sprint_stories: int
    matched_stories_count: int
    stories: List[SprintStoryItemSchema]


# =========================================================================
# Dashboard Metrics Schema
# =========================================================================

class DashboardMetricsResponse(BaseModel):
    """Real numeric KPI metrics calculated from persisted executions and sprint context."""
    stories_processed_today: int = Field(alias="storiesProcessedToday", default=0)
    tasks_created_today: int = Field(alias="tasksCreatedToday", default=0)
    stories_processed: int = Field(alias="storiesProcessed", default=0)
    tasks_created: int = Field(alias="tasksCreated", default=0)
    stories_assigned_to_me: int = Field(alias="storiesAssignedToMe", default=0)
    failed_today: int = Field(alias="failedToday", default=0)

    model_config = {
        "populate_by_name": True,
        "serialize_by_alias": True,
    }




