"""Tests for TaskGenerator adhering to strict FE/BE rules and description format."""

import pytest

from src.client.models import StoryItem
from src.services.task_generator import TaskGenerationError, TaskGenerator
from src.services.task_models import (
    RawBackendTaskDraft,
    RawFrontendTaskDraft,
    StoryAnalysisResult,
)


@pytest.fixture
def base_story() -> StoryItem:
    return StoryItem(
        id="STORY-10",
        name="Export Invoices as PDF",
        description="Users can download invoices as PDF documents",
        team_id="T1",
        project_id="P1",
        sprint_id="S1",
    )


def test_task_generator_fe_only(base_story: StoryItem) -> None:
    analysis = StoryAnalysisResult(
        business_objective="Add PDF download button to invoice view",
        summary="Frontend button with click handler to trigger download",
        requires_frontend=True,
        requires_backend=False,
        frontend_task=RawFrontendTaskDraft(
            title_suffix="Add PDF Download Button and Loading State",
            objective="Provide download button on invoice details page",
            scope="Add button component, trigger existing download API, display spinner",
            expected_behavior="User clicks button and PDF file download begins",
            dependencies="None identified",
            testing_considerations="Unit test for button click and state changes",
            acceptance_criteria=["Button shows loading state during download"],
        ),
    )

    generator = TaskGenerator()
    plan = generator.generate_plan(base_story, analysis)

    assert plan.total_task_count == 1
    assert len(plan.fe_tasks) == 1
    assert len(plan.be_tasks) == 0
    assert plan.fe_tasks[0].title == "FE - Add PDF Download Button and Loading State"
    assert plan.fe_tasks[0].task_type == "FE"

    # Verify description contains all 6 Zoho-compatible plain text sections in exact order
    desc = plan.fe_tasks[0].format_description()

    # 1. No Markdown headings, bold syntax, or bullets
    assert "##" not in desc
    assert "**" not in desc
    assert not any(line.strip().startswith("- ") for line in desc.splitlines())

    # 2. Four sections are present, Testing Considerations & Acceptance Criteria are NOT present
    assert "Objective:" in desc
    assert "Scope:" in desc
    assert "Expected Behavior:" in desc
    assert "Dependencies:" in desc
    assert "Testing Considerations" not in desc
    assert "Acceptance Criteria" not in desc

    # 3. Sections appear in the exact required order
    obj_pos = desc.index("Objective:")
    scope_pos = desc.index("Scope:")
    exp_pos = desc.index("Expected Behavior:")
    deps_pos = desc.index("Dependencies:")
    assert obj_pos < scope_pos < exp_pos < deps_pos

    # 4. Scope and Expected Behavior use numbered lists (1. )
    assert "1. " in desc[scope_pos:exp_pos]
    assert "1. " in desc[exp_pos:deps_pos]


def test_task_generator_be_only(base_story: StoryItem) -> None:
    analysis = StoryAnalysisResult(
        business_objective="Implement backend PDF generation engine",
        summary="Background worker and API to render HTML invoices to PDF",
        requires_frontend=False,
        requires_backend=True,
        backend_tasks=[
            RawBackendTaskDraft(
                boundary="API",
                title_suffix="Invoice PDF Render API Endpoint",
                objective="Create endpoint to trigger invoice PDF generation",
                scope="Accept invoice ID, authenticate caller, return download stream",
                expected_behavior="Returns PDF bytes with application/pdf Content-Type",
                dependencies="None identified",
                testing_considerations="Integration test verifying PDF response headers",
                acceptance_criteria=["Returns 200 with valid PDF binary"],
            ),
            RawBackendTaskDraft(
                boundary="Worker",
                title_suffix="Async PDF Generator Service",
                objective="Render HTML template into PDF bytes using headless engine",
                scope="Convert invoice data into HTML template and invoke renderer",
                expected_behavior="Generates well-formatted PDF document",
                dependencies="None identified",
                testing_considerations="Unit test checking rendered PDF layout",
                acceptance_criteria=["Handles invoices with up to 100 line items"],
            ),
        ],
    )

    generator = TaskGenerator()
    plan = generator.generate_plan(base_story, analysis)

    assert plan.total_task_count == 2
    assert len(plan.fe_tasks) == 0
    assert len(plan.be_tasks) == 2
    assert plan.be_tasks[0].title == "BE - 01 - Invoice PDF Render API Endpoint"
    assert plan.be_tasks[1].title == "BE - 02 - Async PDF Generator Service"


def test_task_generator_fullstack(base_story: StoryItem) -> None:
    analysis = StoryAnalysisResult(
        business_objective="Fullstack feature",
        summary="FE and BE implementation",
        requires_frontend=True,
        requires_backend=True,
        frontend_task=RawFrontendTaskDraft(
            title_suffix="Invoice PDF UI",
            objective="FE objective",
            scope="FE scope",
            expected_behavior="FE expected",
            testing_considerations="FE tests",
            acceptance_criteria=["FE AC 1"],
        ),
        backend_tasks=[
            RawBackendTaskDraft(
                boundary="API",
                title_suffix="PDF API",
                objective="BE objective",
                scope="BE scope",
                expected_behavior="BE expected",
                testing_considerations="BE tests",
                acceptance_criteria=["BE AC 1"],
            )
        ],
    )

    generator = TaskGenerator()
    plan = generator.generate_plan(base_story, analysis)

    assert plan.total_task_count == 2
    assert len(plan.fe_tasks) == 1
    assert len(plan.be_tasks) == 1
    assert plan.fe_tasks[0].title == "FE - Invoice PDF UI"
    assert plan.be_tasks[0].title == "BE - 01 - PDF API"


def test_task_generator_no_tasks_raises_error(base_story: StoryItem) -> None:
    analysis = StoryAnalysisResult(
        business_objective="No work",
        summary="No tasks",
        requires_frontend=False,
        requires_backend=False,
    )
    generator = TaskGenerator()
    with pytest.raises(TaskGenerationError):
        generator.generate_plan(base_story, analysis)


def test_task_description_zoho_compatible_format() -> None:
    """Verify that every generated task description strictly conforms to the 6 plain-text sections with numbered lists."""
    from src.services.task_models import GeneratedTask

    task = GeneratedTask(
        title="BE - 01 - Sample Service Implementation",
        task_type="BE",
        index=1,
        objective="Provide sample backend logic for data processing.",
        scope="Implement service class\nConnect repository\nHandle validation exceptions",
        expected_behavior="Valid data returns HTTP 200\nInvalid data returns HTTP 400 with error details",
        dependencies="Database connection pool\nConfiguration service",
        testing_considerations="Unit test for service logic\nIntegration test with repository",
        acceptance_criteria=["Valid data returns HTTP 200", "Invalid data returns structured error"],
    )

    desc = task.format_description()

    # 1. No Markdown headings, bold, or bullet points
    assert "##" not in desc
    assert "**" not in desc
    assert not any(line.strip().startswith("- ") for line in desc.splitlines())

    # 2. Four required sections present with plain-text labels, no Testing Considerations or Acceptance Criteria
    assert "Objective:" in desc
    assert "Scope:" in desc
    assert "Expected Behavior:" in desc
    assert "Dependencies:" in desc
    assert "Testing Considerations" not in desc
    assert "Acceptance Criteria" not in desc

    # 3. Strict order
    obj_idx = desc.index("Objective:")
    scope_idx = desc.index("Scope:")
    exp_idx = desc.index("Expected Behavior:")
    deps_idx = desc.index("Dependencies:")
    assert obj_idx < scope_idx < exp_idx < deps_idx

    # 4. Scope and Expected Behavior use numbered lists
    scope_text = desc[scope_idx:exp_idx]
    exp_text = desc[exp_idx:deps_idx]

    assert "1. Implement service class" in scope_text
    assert "2. Connect repository" in scope_text
    assert "3. Handle validation exceptions" in scope_text

    assert "1. Valid data returns HTTP 200" in exp_text
    assert "2. Invalid data returns HTTP 400 with error details" in exp_text


def test_task_description_fallback_defaults_use_numbered_lists() -> None:
    """Verify fallback dependencies and scopes format with numbered lists and plain-text headers."""
    from src.services.task_models import GeneratedTask

    task = GeneratedTask(
        title="FE - Minimal UI",
        task_type="FE",
        objective="Minimal objective description.",
        scope="",
        expected_behavior="",
        dependencies="None identified",
    )

    desc = task.format_description()

    assert "##" not in desc
    assert "**" not in desc
    assert "Objective:\nMinimal objective description." in desc
    assert "Scope:\n\n1. Implement requirements according to story specification." in desc
    assert "Expected Behavior:\n\n1. System behaves as defined in objective." in desc
    assert "Dependencies:\nNone identified." in desc
    assert "Testing Considerations" not in desc
    assert "Acceptance Criteria" not in desc
