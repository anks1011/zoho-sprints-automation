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

    # Verify description contains all 6 sections
    desc = plan.fe_tasks[0].format_description()
    assert "Objective:" in desc
    assert "Scope:" in desc
    assert "Expected behavior:" in desc
    assert "Dependencies:" in desc
    assert "Testing considerations:" in desc
    assert "Acceptance criteria:" in desc


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
