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


def ensure_bullet_points(text: Any, fallback: str = "None identified") -> str:
    """Ensure that text is formatted as markdown bullet points, each starting with '- '."""
    if not text:
        return f"- {fallback}"

    if isinstance(text, list):
        items = [str(item).strip() for item in text if str(item).strip()]
        if not items:
            return f"- {fallback}"
        return "\n".join(f"- {item.lstrip('- *•+').strip()}" for item in items if item.lstrip("- *•+").strip())

    clean_text = str(text).strip()
    if not clean_text:
        return f"- {fallback}"

    lines = [line.strip() for line in clean_text.splitlines() if line.strip()]
    if not lines:
        return f"- {fallback}"

    bulleted_lines: List[str] = []
    for line in lines:
        if line.startswith(("- ", "* ", "+ ", "• ")):
            clean_item = line[2:].strip()
        elif line.startswith(("-", "*", "+", "•")):
            clean_item = line[1:].strip()
        else:
            clean_item = line

        if clean_item:
            bulleted_lines.append(f"- {clean_item}")

    if not bulleted_lines:
        return f"- {fallback}"

    return "\n".join(bulleted_lines)


class GeneratedTask(BaseModel):
    """Represents a generated task before creation in Zoho Sprints."""

    id: str = Field(default_factory=lambda: f"task_{uuid.uuid4().hex[:8]}", description="Stable task ID")
    title: str = Field(..., description="Task title (FE - ... or BE - 01 - ...)")
    task_type: Literal["FE", "BE"] = Field(..., description="FE or BE")
    index: Optional[int] = Field(default=None, description="Sequential index for BE tasks (1, 2, ...)")
    objective: str = Field(..., description="What this task accomplishes")
    scope: str = Field(..., description="Specific implementation responsibilities")
    expected_behavior: str = Field(..., description="Expected system behavior")
    dependencies: str = Field(default="None identified", description="Dependencies or None identified")
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
        """Format the task description using exact four Markdown sections in order:
        ## Objective
        ## Scope
        ## Expected Behavior
        ## Dependencies
        """
        obj = self.objective.strip()
        scope = ensure_bullet_points(self.scope, fallback="Implement requirements according to story specification.")
        exp = ensure_bullet_points(self.expected_behavior, fallback="System behaves as defined in objective.")
        deps = ensure_bullet_points(self.dependencies, fallback="None identified")

        return (
            f"## Objective\n{obj}\n\n"
            f"## Scope\n{scope}\n\n"
            f"## Expected Behavior\n{exp}\n\n"
            f"## Dependencies\n{deps}"
        )


class RawBackendTaskDraft(BaseModel):
    """Draft backend task extracted during AI analysis."""

    boundary: str = Field(default="Backend Implementation", description="Implementation boundary")
    title_suffix: str = Field(..., description="Short title describing backend work")
    objective: str = Field(..., description="What this task accomplishes")
    scope: str = Field(default="", description="Specific scope")
    expected_behavior: str = Field(default="", description="Expected system behavior")
    dependencies: str = Field(default="- None identified")
    testing_considerations: Optional[str] = Field(default="")
    acceptance_criteria: List[str] = Field(default_factory=list)

    @field_validator("expected_behavior", mode="before")
    @classmethod
    def default_expected_behavior(cls, v: Any, info: Any) -> str:
        return str(v) if v else "- System behaves as defined in objective."

    @field_validator("scope", mode="before")
    @classmethod
    def default_scope(cls, v: Any) -> str:
        return str(v) if v else "- Implement requirements according to story specification."


class RawFrontendTaskDraft(BaseModel):
    """Draft frontend task extracted during AI analysis."""

    title_suffix: str = Field(default="User Interface and Integration", description="Short title describing frontend work")
    objective: str = Field(default="", description="What this task accomplishes")
    scope: str = Field(default="", description="Specific scope")
    expected_behavior: str = Field(default="", description="Expected system behavior")
    dependencies: str = Field(default="- None identified")
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
                dependencies=data.get("dependencies") or "- None identified",
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
