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

    # Verify description contains all 4 Zoho-compatible HTML sections in exact order
    desc = plan.fe_tasks[0].format_description()

    # 1. No Markdown headings, bold syntax, or bullets
    assert "##" not in desc
    assert "**" not in desc
    assert not any(line.strip().startswith("- ") for line in desc.splitlines())

    # 2. Four sections are present with HTML tags, Testing Considerations & Acceptance Criteria are NOT present
    assert "<p><strong>Objective:</strong>" in desc
    assert "<p><strong>Scope:</strong>" in desc
    assert "<p><strong>Expected Behavior:</strong>" in desc
    assert "<p><strong>Dependencies:</strong>" in desc
    assert "<ol>" in desc
    assert "<li>" in desc
    assert "Testing Considerations" not in desc
    assert "Acceptance Criteria" not in desc

    # 3. Sections appear in the exact required order
    obj_pos = desc.index("<strong>Objective:</strong>")
    scope_pos = desc.index("<strong>Scope:</strong>")
    exp_pos = desc.index("<strong>Expected Behavior:</strong>")
    deps_pos = desc.index("<strong>Dependencies:</strong>")
    assert obj_pos < scope_pos < exp_pos < deps_pos

    # 4. Scope and Expected Behavior use ordered lists
    assert "<li>" in desc[scope_pos:exp_pos]
    assert "<li>" in desc[exp_pos:deps_pos]



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

    # 2. Four required sections present with HTML tags, no Testing Considerations or Acceptance Criteria
    assert "<p><strong>Objective:</strong>" in desc
    assert "<p><strong>Scope:</strong>" in desc
    assert "<p><strong>Expected Behavior:</strong>" in desc
    assert "<p><strong>Dependencies:</strong>" in desc
    assert "Testing Considerations" not in desc
    assert "Acceptance Criteria" not in desc

    # 3. Strict order
    obj_idx = desc.index("<strong>Objective:</strong>")
    scope_idx = desc.index("<strong>Scope:</strong>")
    exp_idx = desc.index("<strong>Expected Behavior:</strong>")
    deps_idx = desc.index("<strong>Dependencies:</strong>")
    assert obj_idx < scope_idx < exp_idx < deps_idx

    # 4. Scope, Expected Behavior, and Dependencies use ordered lists
    scope_text = desc[scope_idx:exp_idx]
    exp_text = desc[exp_idx:deps_idx]
    deps_text = desc[deps_idx:]

    assert "<li>Implement service class</li>" in scope_text
    assert "<li>Connect repository</li>" in scope_text
    assert "<li>Handle validation exceptions</li>" in scope_text

    assert "<li>Valid data returns HTTP 200</li>" in exp_text
    assert "<li>Invalid data returns HTTP 400 with error details</li>" in exp_text

    assert "<li>Database connection pool</li>" in deps_text
    assert "<li>Configuration service</li>" in deps_text


def test_task_description_fallback_defaults_use_numbered_lists() -> None:
    """Verify fallback dependencies and scopes format with numbered lists and HTML tags."""
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
    assert "<p><strong>Objective:</strong><br>\nMinimal objective description.</p>" in desc
    assert "<p><strong>Scope:</strong></p>\n<ol>\n  <li>Implement requirements according to story specification.</li>\n</ol>" in desc
    assert "<p><strong>Expected Behavior:</strong></p>\n<ol>\n  <li>System behaves as defined in objective.</li>\n</ol>" in desc
    assert "<p><strong>Dependencies:</strong><br>\nNone identified.</p>" in desc
    assert "Testing Considerations" not in desc
    assert "Acceptance Criteria" not in desc


def test_task_description_html_escaping() -> None:
    """Verify that dynamic content with <, >, &, and quotes is safely escaped."""
    from src.services.task_models import GeneratedTask

    task = GeneratedTask(
        title="FE - XSS & Entities Test",
        task_type="FE",
        objective="Validate <script>alert('xss')</script> & 'single' and \"double\" quotes.",
        scope="Field <user_input> & condition > 10\nAnother check <= 5",
        expected_behavior="Response includes <ok> & no error",
        dependencies="API <v1> & Auth",
    )

    desc = task.format_description()

    assert "<script>" not in desc
    assert "&lt;script&gt;alert(&#x27;xss&#x27;)&lt;/script&gt; &amp; &#x27;single&#x27; and &quot;double&quot; quotes." in desc
    assert "&lt;user_input&gt; &amp; condition &gt; 10" in desc
    assert "Another check &lt;= 5" in desc
    assert "&lt;ok&gt; &amp; no error" in desc
    assert "API &lt;v1&gt; &amp; Auth" in desc


def test_is_zoho_html_formatted() -> None:
    """Verify is_zoho_html_formatted accurately detects valid Zoho HTML and rejects plain text or legacy sections."""
    from src.services.task_models import is_zoho_html_formatted, format_zoho_html_description

    valid_html = format_zoho_html_description(
        objective="Valid obj",
        scope="Scope item 1",
        expected_behavior="Expected item 1",
        dependencies="None identified",
    )
    assert is_zoho_html_formatted(valid_html) is True

    # Legacy plain text should return False
    plain_text = "Objective:\nValid obj\n\nScope:\n1. Scope item 1\n\nExpected Behavior:\n1. Expected\n\nDependencies:\nNone identified."
    assert is_zoho_html_formatted(plain_text) is False

    # HTML with Testing Considerations should return False
    with_tc = valid_html + "\n<p><strong>Testing Considerations:</strong></p>"
    assert is_zoho_html_formatted(with_tc) is False


def test_task_generator_with_string_acceptance_criteria() -> None:
    """Verify that a story with raw markdown string acceptance_criteria generates tasks without ValidationError."""
    story = StoryItem(
        id="STORY-99",
        name="Update KYC Status",
        description="Process KYC updates",
        acceptance_criteria="**\n\nScenario 1 - happy path\nGiven user submits KYC\nWhen approved\nThen status updates | Step 2 |",
        team_id="T1",
        project_id="P1",
        sprint_id="S1",
    )

    analysis = StoryAnalysisResult(
        business_objective="Process KYC updates",
        summary="KYC flow breakdown",
        requires_frontend=True,
        requires_backend=True,
        frontend_task=RawFrontendTaskDraft(
            title_suffix="KYC Form UI",
            objective="Provide KYC submission form",
            scope="Add KYC form component",
            expected_behavior="Form validates inputs",
            # acceptance_criteria not provided by LLM -> falls back to story.acceptance_criteria
        ),
        backend_tasks=[
            RawBackendTaskDraft(
                boundary="API",
                title_suffix="KYC Submission Endpoint",
                objective="Endpoint to process KYC submission",
                scope="Validate payload and persist record",
                expected_behavior="Returns 200 on success",
                # acceptance_criteria not provided by LLM -> falls back to story.acceptance_criteria
            )
        ],
    )

    generator = TaskGenerator()
    plan = generator.generate_plan(story, analysis)

    assert plan.total_task_count == 2
    for task in plan.tasks:
        assert isinstance(task.acceptance_criteria, list)
        assert len(task.acceptance_criteria) > 0
        assert not any(ac.startswith("**") for ac in task.acceptance_criteria)


