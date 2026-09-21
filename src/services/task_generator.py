"""Task synthesis and validation service adhering to strict FE/BE rules."""

from __future__ import annotations

import logging
from typing import List

from src.client.models import StoryItem
from src.services.task_models import (
    GeneratedTask,
    GeneratedTaskPlan,
    StoryAnalysisResult,
    TaskOwner,
)

logger = logging.getLogger(__name__)


class TaskGenerationError(Exception):
    """Exception raised for task generation or validation issues."""
    pass


class TaskGenerator:
    """Transforms AI analysis into validated FE and BE tasks matching strict formatting rules."""

    def generate_plan(
        self,
        story: StoryItem,
        analysis: StoryAnalysisResult,
        dev_owner: Optional[TaskOwner] = None,
        qa_owner: Optional[TaskOwner] = None,
    ) -> GeneratedTaskPlan:
        """Synthesize a complete GeneratedTaskPlan from a StoryItem and StoryAnalysisResult."""
        raw = story.raw_data or {}
        user_names = raw.get("userDisplayName") or {}

        # Resolve Dev Owner from story if not passed
        if dev_owner is None:
            dev_id = None
            if raw.get("UDF_USERPKL3") and str(raw["UDF_USERPKL3"]).strip() not in ("", "-1", -1):
                dev_id = str(raw["UDF_USERPKL3"]).strip()
            elif raw.get("ownerId"):
                owners = raw["ownerId"] if isinstance(raw["ownerId"], list) else [raw["ownerId"]]
                if owners and str(owners[0]).strip() not in ("", "-1", -1):
                    dev_id = str(owners[0]).strip()
            if dev_id:
                dev_owner = TaskOwner(user_id=dev_id, display_name=user_names.get(dev_id))

        # Resolve QA Owner from story if not passed
        if qa_owner is None:
            qa_id = None
            if raw.get("UDF_USERPKL2") and str(raw["UDF_USERPKL2"]).strip() not in ("", "-1", -1):
                qa_id = str(raw["UDF_USERPKL2"]).strip()
            if qa_id:
                qa_owner = TaskOwner(user_id=qa_id, display_name=user_names.get(qa_id))

        tasks: List[GeneratedTask] = []

        # 1. Synthesize FE Task if required
        if analysis.requires_frontend and analysis.frontend_task:
            fe_raw = analysis.frontend_task
            fe_title = fe_raw.title_suffix.strip()
            # Strip redundant FE prefixes if model included them
            if fe_title.upper().startswith("FE - "):
                fe_title = fe_title[5:].strip()
            elif fe_title.upper().startswith("FE:"):
                fe_title = fe_title[3:].strip()

            final_fe_title = f"FE - {fe_title}"

            fe_task = GeneratedTask(
                title=final_fe_title,
                task_type="FE",
                index=None,
                objective=fe_raw.objective,
                scope=fe_raw.scope,
                expected_behavior=fe_raw.expected_behavior,
                dependencies=fe_raw.dependencies or "None identified",
                testing_considerations=fe_raw.testing_considerations,
                acceptance_criteria=fe_raw.acceptance_criteria,
                assignee=dev_owner,
                qa_owner=qa_owner,
            )
            tasks.append(fe_task)
        elif analysis.requires_frontend and not analysis.frontend_task:
            # If flagged as requiring frontend but draft task was omitted, synthesize from responsibilities
            if analysis.frontend_responsibilities:
                fe_task = GeneratedTask(
                    title=f"FE - Implement {story.name} UI and Client Integration",
                    task_type="FE",
                    index=None,
                    objective=f"Implement frontend user interface, state management, and API integration for {story.name}.",
                    scope="\n".join(f"- {r}" for r in analysis.frontend_responsibilities),
                    expected_behavior=f"User can interact with the {story.name} interface with proper validation, loading states, and error handling.",
                    dependencies="None identified",
                    testing_considerations="Unit tests for UI components and form validation; E2E user flow tests.",
                    acceptance_criteria=[
                        "UI matches design and validation specifications",
                        "Form submissions and API error handling operate correctly",
                    ],
                    assignee=dev_owner,
                    qa_owner=qa_owner,
                )
                tasks.append(fe_task)

        # 2. Synthesize BE Tasks if required
        if analysis.requires_backend and analysis.backend_tasks:
            for idx, be_raw in enumerate(analysis.backend_tasks, start=1):
                be_title = be_raw.title_suffix.strip()
                # Strip redundant BE prefixes if model included them
                if be_title.upper().startswith("BE - "):
                    # strip 'BE - XX - ' or 'BE - '
                    parts = be_title.split(" - ")
                    if len(parts) >= 3 and parts[1].isdigit():
                        be_title = parts[2].strip()
                    else:
                        be_title = be_title[5:].strip()

                formatted_be_title = f"BE - {idx:02d} - {be_title}"

                be_task = GeneratedTask(
                    title=formatted_be_title,
                    task_type="BE",
                    index=idx,
                    objective=be_raw.objective,
                    scope=be_raw.scope,
                    expected_behavior=be_raw.expected_behavior,
                    dependencies=be_raw.dependencies or "None identified",
                    testing_considerations=be_raw.testing_considerations,
                    acceptance_criteria=be_raw.acceptance_criteria,
                    assignee=dev_owner,
                    qa_owner=qa_owner,
                )
                tasks.append(be_task)
        elif analysis.requires_backend and not analysis.backend_tasks:
            # Fallback synthesis if backend was flagged but drafts list was empty
            if analysis.backend_responsibilities:
                be_task = GeneratedTask(
                    title=f"BE - 01 - Implement {story.name} Backend Logic and APIs",
                    task_type="BE",
                    index=1,
                    objective=f"Implement backend services, validation, and APIs for {story.name}.",
                    scope="\n".join(f"- {r}" for r in analysis.backend_responsibilities),
                    expected_behavior=f"Backend endpoints process requests for {story.name} according to business rules.",
                    dependencies="None identified",
                    testing_considerations="Unit and integration tests for API endpoints and database operations.",
                    acceptance_criteria=[
                        "API endpoints validate input and return appropriate status codes",
                        "Database transactions and business logic execute correctly",
                    ],
                    assignee=dev_owner,
                    qa_owner=qa_owner,
                )
                tasks.append(be_task)

        # Validate that at least one task was produced if story has content
        if not tasks:
            raise TaskGenerationError(
                "No frontend or backend tasks were identified for this story. "
                "Please verify that the story description contains actionable implementation requirements."
            )

        # Construct and return the full plan
        return GeneratedTaskPlan(
            story_id=story.id,
            story_title=story.name,
            story_summary=analysis.summary,
            team_id=story.team_id,
            project_id=story.project_id,
            sprint_id=story.sprint_id,
            assumptions=analysis.assumptions,
            ambiguities=analysis.ambiguities,
            tasks=tasks,
            dev_owner=dev_owner,
            qa_owner=qa_owner,
        )
