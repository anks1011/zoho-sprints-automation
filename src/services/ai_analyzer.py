"""AI Story Analyzer using OpenAI-compatible structured LLM invocations."""

from __future__ import annotations

import json
import logging
from typing import Any, Dict, List, Optional

from openai import OpenAI

from src.client.models import StoryItem
from src.config import Settings, get_settings
from src.services.task_models import StoryAnalysisResult

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are a senior software architect, principal API engineer, and tech lead.
Your job is to analyze a user story from Zoho Sprints and produce a comprehensive, realistic technical breakdown.

STRICT CONSTRAINTS & ARCHITECTURAL GUIDELINES:
1. The Story Description and Acceptance Criteria are your ABSOLUTE SOURCE OF TRUTH.
2. DO NOT invent requirements, architecture, or tech stacks not supported or implied by the story description.
3. Deep FE/BE Requirement Analysis:
   - Carefully evaluate whether frontend work, backend work, or both are required to deliver the story end-to-end.
   - Do NOT assume a feature is frontend-only simply because user interactions, browser downloads, or UI buttons are described.
   - In particular, for template generation, import/export, dynamic layouts, or data wizards (even when files are downloaded or triggered client-side in the browser):
     Analyze whether the backend must support:
     * Template schema and column generation: Querying configured layout fields, filtering by user permissions / field-permission matrix, resolving column order.
     * Mode handling: In Update mode, determining and placing the designated unique identifier / match field as the first column.
     * Conditional and complex columns: Identifying attachment-type fields based on inclusion toggles; dynamically expanding multi-row/multi-column table sections on the layout into flattened grid columns (e.g., section and cell coordinates).
     * Layout configuration validation: Verifying whether layout prerequisites are satisfied (e.g. verifying table sections have mandatory 'Max rows' configured) and returning structured validation refusals / error codes.
     * API contract and error handling: Defining pre-flight validation endpoints or schema metadata endpoints with structured status codes and explanatory error messages.
   - If backend changes, API endpoints, schema resolution, or layout validation are required to support the story, you MUST set requires_backend=true and generate justified BE tasks.
   - Do NOT force a BE task if the existing backend already supports all required functionality and the story is genuinely purely UI/styling.
4. Task Granularity Rules:
   - If frontend work is required:
     * Generate EXACTLY ONE frontend task draft (`frontend_task`) combining all UI components, state management, form validation, user interactions, loading states, tooltips/disabled states, and error handling.
   - If backend work is required:
     * Generate justified, sequential backend task drafts (`backend_tasks`) broken down cleanly by technical domain / responsibility (e.g. BE - 01 for Template Schema and Column Resolution API, BE - 02 for Layout Configuration and Table-Section Validation Service).
     * Do not create artificial tasks just to inflate task counts, but do not lump disparate backend responsibilities into a single oversized task when distinct architectural boundaries exist.
5. Task Content Structure & Formatting (MANDATORY):
   - Zoho Sprints displays task descriptions in an HTML container and does not parse Markdown.
   - STRICT FORMATTING RULES:
     * DO NOT use Markdown headings such as '## Objective'. Use plain-text labels ending in a colon (e.g. 'Objective:').
     * DO NOT use Markdown bold syntax such as '**text**'.
     * DO NOT use Markdown bullet syntax ('- ', '* ').
     * Use sequential NUMBERED LISTS ('1. ', '2. ') for all list sections.
     * Preserve double line breaks between sections.
   - For every task (FE and each BE), provide complete, detailed contents strictly adhering to these 4 sections in order:
     * title_suffix: Clear, professional title describing the work.
     * objective: A clear and concise description of what this task accomplishes and why it is required (as a concise paragraph).
     * scope: Specific implementation responsibilities and components affected. MUST use a numbered list ('1. ...\n2. ...').
     * expected_behavior: Clear description of expected system behavior under normal and failure/edge conditions. MUST use a numbered list ('1. ...\n2. ...').
     * dependencies: Required services, configurations, permissions, APIs, or other dependencies. Use 'None identified.' or a numbered list.
   - DO NOT include or generate any 'Testing Considerations' section.
   - DO NOT include or generate any 'Acceptance Criteria' section.
   - Keep content specific to the task. Do NOT generate scope or expected behavior as plain paragraphs; format them as numbered lists.
6. If the story description is short, ambiguous, or missing crucial specifications, explicitly list the ambiguities in the `ambiguities` array.
7. Output MUST be valid JSON adhering strictly to the provided schema.
"""


class AIAnalyzerError(Exception):
    """Exception raised for AI analysis failures."""
    pass


class AIStoryAnalyzer:
    """Analyzes user stories using an OpenAI-compatible LLM client."""

    def __init__(
        self,
        settings: Optional[Settings] = None,
        openai_client: Optional[OpenAI] = None,
    ) -> None:
        self.settings = settings or get_settings()
        self._client = openai_client

    @property
    def client(self) -> OpenAI:
        if self._client is None:
            if not self.settings.openai_api_key:
                raise AIAnalyzerError(
                    "OPENAI_API_KEY is not configured. Please set it in your environment or .env file."
                )
            self._client = OpenAI(
                api_key=self.settings.openai_api_key,
                base_url=self.settings.openai_base_url,
            )
        return self._client

    def analyze_story(self, story: StoryItem) -> StoryAnalysisResult:
        """Analyze a StoryItem and return structured analysis result."""
        # Sanity check for empty description
        clean_desc = story.description.strip()
        clean_title = story.name.strip()
        if not clean_title:
            raise AIAnalyzerError("Story title is empty. Cannot analyze story.")

        existing_subtask_names = [s.name for s in story.subitems]

        prompt_payload = {
            "story_id": story.id,
            "story_title": clean_title,
            "story_description": clean_desc if clean_desc else "NO DESCRIPTION PROVIDED",
            "acceptance_criteria": story.acceptance_criteria or "None specified",
            "existing_subtasks": existing_subtask_names,
            "project_metadata": {
                "team_id": story.team_id,
                "project_id": story.project_id,
                "sprint_id": story.sprint_id,
                "item_type": story.item_type_name,
                "priority": story.priority_name,
            },
        }

        user_content = (
            f"Analyze the following user story and produce structured technical requirements:\n\n"
            f"```json\n{json.dumps(prompt_payload, indent=2)}\n```\n\n"
            f"Requirements:\n"
            f"1. Perform deep FE and BE architectural analysis. Evaluate if backend implementation is needed for template schema & column generation, Create/Update mode unique field selection, attachment & table-section columns, layout configuration validation, and API contracts/error handling.\n"
            f"2. If frontend work is needed, generate exactly ONE frontend task draft.\n"
            f"3. If backend work is needed, generate justified, sequential backend task drafts. Do not force backend tasks if the existing backend already supports everything.\n"
            f"4. For each task, explain clearly in the objective and scope why the task is required.\n\n"
            f"Return JSON strictly adhering to this structure:\n"
            f"{{\n"
            f'  "business_objective": "string",\n'
            f'  "summary": "string",\n'
            f'  "requires_frontend": true/false,\n'
            f'  "requires_backend": true/false,\n'
            f'  "functional_requirements": ["string"],\n'
            f'  "frontend_responsibilities": ["string"],\n'
            f'  "backend_responsibilities": ["string"],\n'
            f'  "dependencies": ["string"],\n'
            f'  "ambiguities": ["string"],\n'
            f'  "assumptions": ["string"],\n'
            f'  "frontend_task": {{\n'
            f'    "title_suffix": "string (clear title describing UI work)",\n'
            f'    "objective": "string (concise paragraph)",\n'
            f'    "scope": "1. First scope item\\n2. Second scope item",\n'
            f'    "expected_behavior": "1. First behavior\\n2. Second behavior",\n'
            f'    "dependencies": "None identified. or 1. Service dependency"\n'
            f'  }} or null,\n'
            f'  "backend_tasks": [\n'
            f'    {{\n'
            f'      "boundary": "API/DB/Logic/Worker",\n'
            f'      "title_suffix": "string (clear title describing backend work)",\n'
            f'      "objective": "string (concise paragraph)",\n'
            f'      "scope": "1. First scope item\\n2. Second scope item",\n'
            f'      "expected_behavior": "1. First behavior\\n2. Second behavior",\n'
            f'      "dependencies": "None identified. or 1. Service dependency"\n'
            f'    }}\n'
            f'  ]\n'
            f"}}"
        )

        logger.info("Invoking AI model '%s' for story '%s'...", self.settings.openai_model, story.id)

        try:
            response = self.client.chat.completions.create(
                model=self.settings.openai_model,
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": user_content},
                ],
                response_format={"type": "json_object"},
                temperature=0.2,
            )
        except Exception as e:
            raise AIAnalyzerError(f"OpenAI API call failed: {str(e)}") from e

        content = response.choices[0].message.content
        if not content:
            raise AIAnalyzerError("Received empty response from OpenAI model.")

        try:
            data = json.loads(content)
            # If model wrapped in a top-level key like "analysis" or "result"
            if "analysis" in data and isinstance(data["analysis"], dict):
                data = data["analysis"]
            result = StoryAnalysisResult.model_validate(data)
        except Exception as e:
            logger.error("Failed to validate AI response JSON: %s\nRaw content: %s", str(e), content)
            raise AIAnalyzerError(f"Invalid AI analysis output format: {str(e)}") from e

        # Check if description was empty/short and flag ambiguity if not already done
        if len(clean_desc) < 20 and not result.ambiguities:
            result.ambiguities.append(
                "Story description is very brief or missing details. Requirements may be underspecified."
            )

        return result
