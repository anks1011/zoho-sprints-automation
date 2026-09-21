"""Pydantic models for AI analysis, generated tasks, and task plans."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import List, Literal, Optional
from pydantic import BaseModel, Field, field_validator


class TaskOwner(BaseModel):
    """User assigned as Dev or QA owner."""

    user_id: str
    display_name: Optional[str] = None
    email: Optional[str] = None


import re


def clean_plain_text(text: Any) -> str:
    """Strip markdown formatting syntax like **bold**, *italic*, backticks, and markdown headings."""
    if not text:
        return ""
    s = str(text)
    # Remove markdown bold/italic
    s = re.sub(r"\*\*([^*]+)\*\*", r"\1", s)
    s = re.sub(r"__([^_]+)__", r"\1", s)
    s = re.sub(r"\*([^*]+)\*", r"\1", s)
    s = re.sub(r"_([^_]+)_", r"\1", s)
    s = re.sub(r"`([^`]+)`", r"\1", s)
    # Remove leading markdown headers if any
    s = re.sub(r"^#{1,6}\s*", "", s, flags=re.MULTILINE)
    return s.strip()


def ensure_numbered_list(text: Any, fallback: str = "None identified.") -> str:
    """Ensure that text or items are formatted as a sequential numbered list:
    1. First item
    2. Second item
    """
    if not text:
        return fallback

    if isinstance(text, list):
        cleaned_items: List[str] = []
        for item in text:
            cleaned_str = clean_plain_text(item)
            if not cleaned_str:
                continue
            for line in cleaned_str.splitlines():
                clean = re.sub(r"^(?:[-*+•]|\d+[.)])\s*", "", line.strip()).strip()
                if clean and clean.lower().rstrip(".") not in ("none", "none identified"):
                    cleaned_items.append(clean)
        if not cleaned_items:
            return fallback
        return "\n".join(f"{idx}. {item}" for idx, item in enumerate(cleaned_items, start=1))

    raw_text = clean_plain_text(text)
    if not raw_text:
        return fallback

    lines = [line.strip() for line in raw_text.splitlines() if line.strip()]
    if not lines:
        return fallback

    cleaned_items = []
    for line in lines:
        clean = re.sub(r"^(?:[-*+•]|\d+[.)])\s*", "", line).strip()
        if clean and clean.lower().rstrip(".") not in ("none", "none identified"):
            cleaned_items.append(clean)

    if not cleaned_items:
        return fallback

    return "\n".join(f"{idx}. {item}" for idx, item in enumerate(cleaned_items, start=1))


def ensure_bullet_points(text: Any, fallback: str = "None identified") -> str:
    """Legacy helper for backward compatibility - delegates to ensure_numbered_list."""
    return ensure_numbered_list(text, fallback=fallback)


class GeneratedTask(BaseModel):
    """Represents a generated task before creation in Zoho Sprints."""

    id: str = Field(default_factory=lambda: f"task_{uuid.uuid4().hex[:8]}", description="Stable task ID")
    title: str = Field(..., description="Task title (FE - ... or BE - 01 - ...)")
    task_type: Literal["FE", "BE"] = Field(..., description="FE or BE")
    index: Optional[int] = Field(default=None, description="Sequential index for BE tasks (1, 2, ...)")
    objective: str = Field(..., description="What this task accomplishes")
    scope: str = Field(..., description="Specific implementation responsibilities")
    expected_behavior: str = Field(..., description="Expected system behavior")
    dependencies: str = Field(default="None identified.", description="Dependencies or None identified.")
    testing_considerations: Optional[str] = Field(default="", description="Unit, integration, or UI test scenarios")
    acceptance_criteria: List[str] = Field(default_factory=list, description="List of acceptance criteria")
    assignee: Optional[TaskOwner] = Field(default=None, description="Story Dev Owner assigned to task")
    qa_owner: Optional[TaskOwner] = Field(default=None, description="Story QA Owner assigned to task")

    @field_validator("title")
    @classmethod
    def validate_title_format(cls, v: str) -> str:
        clean = v.strip()
        if clean.startswith("FE - "):
            return clean
        if clean.startswith("BE - "):
            # Check sequential pattern BE - XX - ...
            parts = clean.split(" - ", 2)
            if len(parts) >= 3 and parts[1].isdigit():
                return clean
            raise ValueError(f"Backend task title must follow 'BE - XX - <title>' format, got: '{clean}'")
        raise ValueError(f"Task title must start with 'FE - ' or 'BE - XX - ', got: '{clean}'")

    def format_description(self) -> str:
        """Format the task description using Zoho-compatible plain text and numbered lists:
        Objective:
        ...

        Scope:

        1. ...
        2. ...

        Expected Behavior:

        1. ...
        2. ...

        Dependencies:
        None identified. (or numbered list)
        """
        obj = clean_plain_text(self.objective)
        scope = ensure_numbered_list(self.scope, fallback="1. Implement requirements according to story specification.")
        exp = ensure_numbered_list(self.expected_behavior, fallback="1. System behaves as defined in objective.")

        deps_raw = clean_plain_text(self.dependencies)
        clean_deps_check = re.sub(r"^(?:[-*+•]|\d+[.)])\s*", "", deps_raw).strip()
        if not deps_raw or clean_deps_check.lower().rstrip(".") in ("none", "none identified"):
            deps_section = "Dependencies:\nNone identified."
        else:
            deps_formatted = ensure_numbered_list(self.dependencies, fallback="None identified.")
            if deps_formatted == "None identified.":
                deps_section = "Dependencies:\nNone identified."
            elif deps_formatted.startswith("1. "):
                deps_section = f"Dependencies:\n\n{deps_formatted}"
            else:
                deps_section = f"Dependencies:\n{deps_formatted}"

        return (
            f"Objective:\n{obj}\n\n"
            f"Scope:\n\n{scope}\n\n"
            f"Expected Behavior:\n\n{exp}\n\n"
            f"{deps_section}"
        )


class RawBackendTaskDraft(BaseModel):
    """Draft backend task extracted during AI analysis."""

    boundary: str = Field(default="Backend Implementation", description="Implementation boundary")
    title_suffix: str = Field(..., description="Short title describing backend work")
    objective: str = Field(..., description="What this task accomplishes")
    scope: str = Field(default="", description="Specific scope")
    expected_behavior: str = Field(default="", description="Expected system behavior")
    dependencies: str = Field(default="None identified.")
    testing_considerations: Optional[str] = Field(default="")
    acceptance_criteria: List[str] = Field(default_factory=list)

    @field_validator("expected_behavior", mode="before")
    @classmethod
    def default_expected_behavior(cls, v: Any, info: Any) -> str:
        return str(v) if v else "1. System behaves as defined in objective."

    @field_validator("scope", mode="before")
    @classmethod
    def default_scope(cls, v: Any) -> str:
        return str(v) if v else "1. Implement requirements according to story specification."


class RawFrontendTaskDraft(BaseModel):
    """Draft frontend task extracted during AI analysis."""

    title_suffix: str = Field(default="User Interface and Integration", description="Short title describing frontend work")
    objective: str = Field(default="", description="What this task accomplishes")
    scope: str = Field(default="", description="Specific scope")
    expected_behavior: str = Field(default="", description="Expected system behavior")
    dependencies: str = Field(default="None identified.")
    testing_considerations: Optional[str] = Field(default="")
    acceptance_criteria: List[str] = Field(default_factory=list)

    @classmethod
    def from_raw(cls, data: Any) -> "RawFrontendTaskDraft":
        if isinstance(data, dict):
            obj = data.get("objective") or data.get("task_description") or data.get("description") or "Implement frontend components"
            title = data.get("title_suffix") or data.get("title") or "Implement User Interface and Client Flow"
            scope = data.get("scope") or obj
            expected = data.get("expected_behavior") or obj
            return cls(
                title_suffix=title,
                objective=obj,
                scope=scope,
                expected_behavior=expected,
                dependencies=data.get("dependencies") or "None identified.",
                testing_considerations=data.get("testing_considerations") or "",
                acceptance_criteria=data.get("acceptance_criteria") or [],
            )
        return cls(title_suffix="Implement User Interface", objective=str(data), scope=str(data), expected_behavior=str(data))


class StoryAnalysisResult(BaseModel):
    """Structured output from LLM story analysis."""

    business_objective: str = Field(default="")
    summary: str = Field(default="")
    requires_frontend: bool = Field(default=False)
    requires_backend: bool = Field(default=False)
    functional_requirements: List[str] = Field(default_factory=list)
    frontend_responsibilities: List[str] = Field(default_factory=list)
    backend_responsibilities: List[str] = Field(default_factory=list)
    api_requirements: List[str] = Field(default_factory=list)
    database_requirements: List[str] = Field(default_factory=list)
    validation_requirements: List[str] = Field(default_factory=list)
    permission_requirements: List[str] = Field(default_factory=list)
    async_processing_requirements: List[str] = Field(default_factory=list)
    error_handling_requirements: List[str] = Field(default_factory=list)
    testing_considerations: List[str] = Field(default_factory=list)
    dependencies: List[str] = Field(default_factory=list)
    ambiguities: List[str] = Field(default_factory=list)
    out_of_scope: List[str] = Field(default_factory=list)
    assumptions: List[str] = Field(default_factory=list)

    frontend_task: Optional[RawFrontendTaskDraft] = None
    backend_tasks: List[RawBackendTaskDraft] = Field(default_factory=list)

    @field_validator("frontend_task", mode="before")
    @classmethod
    def parse_frontend_task(cls, v: Any) -> Optional[RawFrontendTaskDraft]:
        if v is None:
            return None
        if isinstance(v, RawFrontendTaskDraft):
            return v
        return RawFrontendTaskDraft.from_raw(v)

    @field_validator("business_objective", mode="before")
    @classmethod
    def parse_business_objective(cls, v: Any, info: Any) -> str:
        return str(v) if v else "Implement story requirements."

    @field_validator("summary", mode="before")
    @classmethod
    def parse_summary(cls, v: Any) -> str:
        return str(v) if v else "Technical implementation breakdown."


class GeneratedTaskPlan(BaseModel):
    """Complete generated task plan ready for preview and execution."""

    plan_id: str = Field(default_factory=lambda: f"plan_{uuid.uuid4().hex[:12]}")
    story_id: str
    story_title: str
    story_summary: str
    team_id: str
    project_id: str
    sprint_id: str
    assumptions: List[str] = Field(default_factory=list)
    ambiguities: List[str] = Field(default_factory=list)
    tasks: List[GeneratedTask] = Field(default_factory=list)
    dev_owner: Optional[TaskOwner] = Field(default=None, description="Inherited parent Story Dev Owner")
    qa_owner: Optional[TaskOwner] = Field(default=None, description="Inherited parent Story QA Owner")
    status: str = Field(default="draft", description="Plan status: draft, approved, completed")
    created_at: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    updated_at: Optional[str] = Field(default=None, description="ISO timestamp of last modification")

    @property
    def fe_tasks(self) -> List[GeneratedTask]:
        return [t for t in self.tasks if t.task_type == "FE"]

    @property
    def be_tasks(self) -> List[GeneratedTask]:
        return [t for t in self.tasks if t.task_type == "BE"]

    @property
    def total_task_count(self) -> int:
        return len(self.tasks)
