"""Validation service for parent story and task owner inheritance and integrity."""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

from src.services.task_models import GeneratedTaskPlan, TaskOwner

logger = logging.getLogger(__name__)


class ValidationIssue(BaseModel):
    """Validation error or warning."""

    code: str
    message: str
    field: Optional[str] = None


class PlanValidationResult(BaseModel):
    """Structured result of plan and owner validation."""

    valid: bool
    errors: List[ValidationIssue] = Field(default_factory=list)
    warnings: List[ValidationIssue] = Field(default_factory=list)


class OwnerValidator:
    """Validates that parent story Dev and QA owners are present, valid, and properly inherited."""

    @staticmethod
    def validate_plan_owners(
        plan: GeneratedTaskPlan,
        valid_project_user_ids: Optional[set[str]] = None,
    ) -> PlanValidationResult:
        """Validate inherited owners. Missing owners are treated as non-blocking warnings."""
        errors: List[ValidationIssue] = []
        warnings: List[ValidationIssue] = []

        # 1. Check Story Dev Owner (Optional)
        if not plan.dev_owner or not plan.dev_owner.user_id or not plan.dev_owner.user_id.strip():
            warnings.append(
                ValidationIssue(
                    code="STORY_DEV_OWNER_NOT_ASSIGNED",
                    message="The parent Story does not have an assigned Dev Owner. Tasks will be created unassigned.",
                    field="dev_owner",
                )
            )
        elif valid_project_user_ids and plan.dev_owner.user_id not in valid_project_user_ids:
            errors.append(
                ValidationIssue(
                    code="INVALID_DEV_OWNER_ID",
                    message=f"Story Dev Owner ID '{plan.dev_owner.user_id}' is not an active user in this Zoho project.",
                    field="dev_owner",
                )
            )

        # 2. Check Story QA Owner (Optional)
        if not plan.qa_owner or not plan.qa_owner.user_id or not plan.qa_owner.user_id.strip():
            warnings.append(
                ValidationIssue(
                    code="STORY_QA_OWNER_NOT_ASSIGNED",
                    message="The parent Story does not have a QA Owner. Tasks will be created without a QA Owner.",
                    field="qa_owner",
                )
            )
        elif valid_project_user_ids and plan.qa_owner.user_id not in valid_project_user_ids:
            errors.append(
                ValidationIssue(
                    code="INVALID_QA_OWNER_ID",
                    message=f"Story QA Owner ID '{plan.qa_owner.user_id}' is not an active user in this Zoho project.",
                    field="qa_owner",
                )
            )

        # 3. Check Task-Level Owners
        for task in plan.tasks:
            # Assignee check
            if not task.assignee or not task.assignee.user_id or not task.assignee.user_id.strip():
                if plan.dev_owner and plan.dev_owner.user_id:
                    # Auto-sync if plan has dev_owner
                    task.assignee = plan.dev_owner
            elif plan.dev_owner and task.assignee.user_id != plan.dev_owner.user_id:
                warnings.append(
                    ValidationIssue(
                        code="TASK_ASSIGNEE_OVERRIDDEN",
                        message=f"Task '{task.title}' Assignee '{task.assignee.user_id}' differs from Story Dev Owner '{plan.dev_owner.user_id}'.",
                        field=f"tasks.{task.id}.assignee",
                    )
                )

            # QA Owner check
            if not task.qa_owner or not task.qa_owner.user_id or not task.qa_owner.user_id.strip():
                if plan.qa_owner and plan.qa_owner.user_id:
                    # Auto-sync if plan has qa_owner
                    task.qa_owner = plan.qa_owner
            elif plan.qa_owner and task.qa_owner.user_id != plan.qa_owner.user_id:
                warnings.append(
                    ValidationIssue(
                        code="TASK_QA_OWNER_OVERRIDDEN",
                        message=f"Task '{task.title}' QA Owner '{task.qa_owner.user_id}' differs from Story QA Owner '{plan.qa_owner.user_id}'.",
                        field=f"tasks.{task.id}.qa_owner",
                    )
                )

        is_valid = len(errors) == 0
        return PlanValidationResult(valid=is_valid, errors=errors, warnings=warnings)
