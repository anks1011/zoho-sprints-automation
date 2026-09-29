"""Story retrieval service with automated context discovery and parsing."""

from __future__ import annotations

import html
import json
import logging
import re
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Dict, List, Optional

from src.client.models import Project, StoryItem, Subitem
from src.client.sprints_api import SprintsAPI
from src.client.zoho_client import SprintsNotFoundError
from src.config import Settings, get_settings
from src.services.task_models import TaskOwner

logger = logging.getLogger(__name__)


@dataclass
class StoryContext:
    """Resolved context IDs for a story."""

    story_id: str
    team_id: str
    project_id: str
    sprint_id: str


class StoryServiceError(Exception):
    """Exception raised for story retrieval failures."""
    pass


def clean_html(text: str) -> str:
    """Clean HTML markup into readable text/markdown."""
    if not text:
        return ""
    # Replace line breaks and block ends with newline
    t = re.sub(r"<(?:br\s*/?|/p|/div|/tr|/h[1-6])>", "\n", text, flags=re.IGNORECASE)
    t = re.sub(r"<b>\s*", "**", t, flags=re.IGNORECASE)
    t = re.sub(r"\s*</b>", "**", t, flags=re.IGNORECASE)
    t = re.sub(r"<i>\s*", "*", t, flags=re.IGNORECASE)
    t = re.sub(r"\s*</i>", "*", t, flags=re.IGNORECASE)
    t = re.sub(r"</t[dh]>", " | ", t, flags=re.IGNORECASE)
    # Strip remaining HTML tags
    t = re.sub(r"<[^>]+>", "", t)
    # Unescape HTML entities
    t = html.unescape(t)
    # Normalize excessive newlines
    t = re.sub(r"\n{3,}", "\n\n", t)
    return t.strip()


class StoryService:
    """Handles fetching stories, discovering context IDs, and parsing acceptance criteria."""

    def __init__(
        self,
        settings: Optional[Settings] = None,
        sprints_api: Optional[SprintsAPI] = None,
    ) -> None:
        self.settings = settings or get_settings()
        self.api = sprints_api or SprintsAPI(self.settings)
        self.cache_file = self.settings.cache_dir / "context_cache.json"

    def fetch_story(
        self,
        story_id: str,
        team_id: Optional[str] = None,
        project_id: Optional[str] = None,
        sprint_id: Optional[str] = None,
    ) -> StoryItem:
        """Fetch parent story details and subtasks, auto-resolving team, project, and sprint."""
        clean_story_id = story_id.strip()
        if not clean_story_id:
            raise StoryServiceError("Story ID cannot be empty.")

        context = self.resolve_context(
            story_id=clean_story_id,
            team_id=team_id,
            project_id=project_id,
            sprint_id=sprint_id,
        )

        try:
            story = self.api.get_item(
                team_id=context.team_id,
                project_id=context.project_id,
                sprint_id=context.sprint_id,
                item_id=clean_story_id,
            )
        except SprintsNotFoundError as e:
            raise StoryServiceError(
                f"Story '{clean_story_id}' not found in team '{context.team_id}', "
                f"project '{context.project_id}', sprint '{context.sprint_id}'."
            ) from e
        except Exception as e:
            raise StoryServiceError(f"Failed to retrieve story '{clean_story_id}': {str(e)}") from e

        # Clean HTML from description
        story.description = clean_html(story.description)

        # Extract acceptance criteria from description if not present in explicit field
        if story.acceptance_criteria:
            story.acceptance_criteria = clean_html(story.acceptance_criteria)
        elif story.description:
            parsed_ac = self.extract_acceptance_criteria(story.description)
            if parsed_ac:
                story.acceptance_criteria = clean_html(parsed_ac)

        # Save resolved context to local cache for instant future reuse
        self._save_cached_context(clean_story_id, context)
        return story

    def resolve_context(
        self,
        story_id: str,
        team_id: Optional[str] = None,
        project_id: Optional[str] = None,
        sprint_id: Optional[str] = None,
    ) -> StoryContext:
        """Resolve team_id, project_id, and sprint_id using CLI args, config, cache, or auto-discovery."""
        # 1. Check CLI args or Settings defaults
        final_team = team_id or self.settings.zoho_team_id
        final_project = project_id or self.settings.zoho_project_id
        final_sprint = sprint_id or self.settings.zoho_sprint_id

        # 2. Check local cache if any component is missing
        if not (final_team and final_project and final_sprint):
            cached = self._load_cached_context(story_id)
            if cached:
                final_team = final_team or cached.team_id
                final_project = final_project or cached.project_id
                final_sprint = final_sprint or cached.sprint_id

        # 3. Discover Team if missing
        if not final_team:
            teams = self.api.list_teams()
            if not teams:
                raise StoryServiceError(
                    "No Zoho Sprints teams/workspaces found for this user account."
                )
            if len(teams) == 1:
                final_team = teams[0].id
                logger.info("Auto-selected single team: %s (%s)", teams[0].name, final_team)
            else:
                team_list = ", ".join(f"{t.name} (ID: {t.id})" for t in teams)
                raise StoryServiceError(
                    f"Multiple teams found: [{team_list}]. Please specify --team-id or configure ZOHO_TEAM_ID."
                )

        # 4. If project or sprint is missing, auto-discover by searching projects and backlogs
        if not (final_project and final_sprint):
            projects = (
                [Project(id=final_project, name=final_project)]
                if final_project
                else self.api.list_projects(final_team)
            )

            logger.info("Searching for story %s across %d project(s)...", story_id, len(projects))
            located_project_id = None
            located_sprint_id = None

            for p in projects:
                # 1. Check project backlog
                backlog_id = self.api.get_backlog_id(final_team, p.id)
                if backlog_id:
                    try:
                        self.api.get_item(final_team, p.id, backlog_id, story_id)
                        located_project_id = p.id
                        located_sprint_id = backlog_id
                        logger.info("Story %s located in project '%s' backlog (%s)", story_id, p.name, backlog_id)
                        break
                    except Exception:
                        pass

                # 2. Check project sprints
                try:
                    sprints = self.api.list_sprints(final_team, p.id)
                    for sp in sprints:
                        try:
                            self.api.get_item(final_team, p.id, sp.id, story_id)
                            located_project_id = p.id
                            located_sprint_id = sp.id
                            logger.info("Story %s located in project '%s' sprint '%s' (%s)", story_id, p.name, sp.name, sp.id)
                            break
                        except Exception:
                            continue
                    if located_project_id:
                        break
                except Exception:
                    continue

            if located_project_id and located_sprint_id:
                final_project = located_project_id
                final_sprint = located_sprint_id
            else:
                if not final_project:
                    project_list = ", ".join(f"{p.name} (ID: {p.id})" for p in projects[:5])
                    raise StoryServiceError(
                        f"Could not automatically locate story '{story_id}' in candidate projects: [{project_list}]. "
                        f"Please specify --project-id or configure ZOHO_PROJECT_ID."
                    )
                elif not final_sprint:
                    raise StoryServiceError(
                        f"Could not locate story '{story_id}' in project '{final_project}'. "
                        f"Please specify --sprint-id."
                    )

        return StoryContext(
            story_id=story_id,
            team_id=str(final_team),
            project_id=str(final_project),
            sprint_id=str(final_sprint),
        )

    def extract_acceptance_criteria(self, text: str) -> Optional[str]:
        """Extract Acceptance Criteria section from markdown or text if present."""
        if not text:
            return None
        pattern = re.compile(
            r"(?:\*{1,2}\s*)?(?:###?\s*)?Acceptance Criteria\s*(?::|\*{1,2}:?|\b)(.*?)(?:###|\Z)",
            re.IGNORECASE | re.DOTALL,
        )
        match = pattern.search(text)
        if match:
            extracted = match.group(1).strip()
            extracted = re.sub(r"^\s*[*_~:]+\s*", "", extracted).strip()
            return extracted if extracted else None
        return None

    def get_project_users(self, team_id: str, project_id: str) -> Dict[str, Dict[str, Any]]:
        """Fetch project users mapping user_id -> user dict with displayName and emailId."""
        try:
            res = self.api.client.request(
                "GET",
                f"team/{team_id}/projects/{project_id}/users/",
                params={"action": "data", "index": 1, "range": 100},
            )
            users_list = res.get("users", []) if isinstance(res, dict) else []
            return {str(u.get("userId") or u.get("id")): u for u in users_list if u.get("userId") or u.get("id")}
        except Exception as e:
            logger.debug("Failed to fetch project users: %s", str(e))
            return {}

    def extract_story_owners(
        self,
        story: StoryItem,
        project_users: Optional[Dict[str, Dict[str, Any]]] = None,
    ) -> tuple[Optional[TaskOwner], Optional[TaskOwner]]:
        """Extract Dev Owner (Task Assignee) and QA Owner from parent story.

        Mapping:
          Parent Story Dev Owner (UDF_USERPKL3 or ownerId) -> Task Assignee
          Parent Story QA Owner (UDF_USERPKL2) -> Task QA Owner
        """
        raw = story.raw_data or {}
        user_names = raw.get("userDisplayName") or {}

        # 1. Dev Owner
        dev_id = None
        if raw.get("UDF_USERPKL3") and str(raw["UDF_USERPKL3"]).strip() not in ("", "-1", -1):
            dev_id = str(raw["UDF_USERPKL3"]).strip()
        elif raw.get("ownerId"):
            owners = raw["ownerId"] if isinstance(raw["ownerId"], list) else [raw["ownerId"]]
            if owners and str(owners[0]).strip() not in ("", "-1", -1):
                dev_id = str(owners[0]).strip()

        dev_owner = None
        if dev_id:
            name = user_names.get(dev_id)
            email = None
            if project_users and dev_id in project_users:
                u = project_users[dev_id]
                name = name or u.get("displayName")
                email = u.get("emailId")
            dev_owner = TaskOwner(user_id=dev_id, display_name=name, email=email)

        # 2. QA Owner
        qa_id = None
        if raw.get("UDF_USERPKL2") and str(raw["UDF_USERPKL2"]).strip() not in ("", "-1", -1):
            qa_id = str(raw["UDF_USERPKL2"]).strip()

        qa_owner = None
        if qa_id:
            name = user_names.get(qa_id)
            email = None
            if project_users and qa_id in project_users:
                u = project_users[qa_id]
                name = name or u.get("displayName")
                email = u.get("emailId")
            qa_owner = TaskOwner(user_id=qa_id, display_name=name, email=email)

        return dev_owner, qa_owner

    def get_sprint_stories_for_story(
        self,
        story_id: str,
        filter_dev_owner: bool = True,
        developer_owner_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Given a Story ID, identify its sprint, fetch all stories in that sprint,
        and filter where the current user/developer is the Developer Owner."""
        clean_story_id = story_id.strip()
        if not clean_story_id:
            raise StoryServiceError("Story ID cannot be empty.")

        # 1. Fetch input story to resolve context and dev owner
        input_story = self.fetch_story(clean_story_id)
        team_id = input_story.team_id
        project_id = input_story.project_id
        sprint_id = input_story.sprint_id

        # 2. Get project users mapping
        project_users = self.get_project_users(team_id, project_id)

        # 3. Resolve Developer Owner
        target_dev_id = developer_owner_id
        target_dev_name = None
        if not target_dev_id:
            dev_owner, _ = self.extract_story_owners(input_story, project_users)
            if dev_owner:
                target_dev_id = dev_owner.user_id
                target_dev_name = dev_owner.display_name

        if target_dev_id and not target_dev_name:
            user_info = project_users.get(target_dev_id)
            if user_info:
                target_dev_name = user_info.get("displayName")

        # 4. Fetch sprint details if available
        sprint_name = None
        try:
            sprints = self.api.list_sprints(team_id, project_id)
            for s in sprints:
                if str(s.id) == str(sprint_id):
                    sprint_name = s.name
                    break
        except Exception:
            pass

        # 5. Fetch all items in sprint
        raw_items = self.api.list_sprint_items(team_id, project_id, sprint_id)

        # 6. Parse and filter items
        all_stories = []
        for it in raw_items:
            # Skip subtasks / subitems (parentItemId is set)
            parent_id = str(it.get("parentItemId") or it.get("parentId") or "")
            if parent_id and parent_id != "-1":
                continue

            it_id = str(it.get("itemId") or it.get("id") or "")
            if not it_id:
                continue

            it_name = str(it.get("itemName") or it.get("name") or it.get("summary") or "Untitled Story")
            it_type_id = str(it.get("projItemTypeId") or it.get("projitemtypeid") or it.get("itemtypeId") or "")
            it_type_name = str(it.get("itemtypeName") or "")

            # Resolve dev owner for this item
            raw_dev_id = str(it.get("UDF_USERPKL3") or "").strip()
            if not raw_dev_id or raw_dev_id in ("-1", "0"):
                owners = it.get("ownerId")
                if owners:
                    owner_list = owners if isinstance(owners, list) else [owners]
                    if owner_list and str(owner_list[0]).strip() not in ("", "-1", -1):
                        raw_dev_id = str(owner_list[0]).strip()

            it_dev_name = None
            user_display_map = it.get("userDisplayName") or {}
            if raw_dev_id and raw_dev_id not in ("", "-1", "0"):
                it_dev_name = user_display_map.get(raw_dev_id)
                if not it_dev_name and raw_dev_id in project_users:
                    it_dev_name = project_users[raw_dev_id].get("displayName")

            # Resolve qa owner
            raw_qa_id = str(it.get("UDF_USERPKL2") or "").strip()
            it_qa_name = None
            if raw_qa_id and raw_qa_id not in ("", "-1", "0"):
                it_qa_name = user_display_map.get(raw_qa_id)
                if not it_qa_name and raw_qa_id in project_users:
                    it_qa_name = project_users[raw_qa_id].get("displayName")

            # Check if matching dev owner filter
            is_match = True
            if filter_dev_owner and target_dev_id:
                is_match = (str(raw_dev_id) == str(target_dev_id))

            story_record = {
                "story_id": it_id,
                "name": it_name,
                "item_type_id": it_type_id,
                "item_type_name": it_type_name,
                "priority_id": str(it.get("projPriorityId") or it.get("priorityId") or ""),
                "priority_name": it.get("priorityName"),
                "status": str(it.get("status") or ""),
                "point": float(it["point"]) if it.get("point") is not None else None,
                "dev_owner_id": raw_dev_id if raw_dev_id not in ("", "-1", "0") else None,
                "dev_owner_name": it_dev_name,
                "qa_owner_id": raw_qa_id if raw_qa_id not in ("", "-1", "0") else None,
                "qa_owner_name": it_qa_name,
                "is_current_story": (it_id == clean_story_id),
            }

            if is_match:
                all_stories.append(story_record)

        return {
            "input_story_id": clean_story_id,
            "team_id": str(team_id),
            "project_id": str(project_id),
            "sprint_id": str(sprint_id),
            "sprint_name": sprint_name or f"Sprint {sprint_id}",
            "current_user_dev_id": target_dev_id,
            "current_user_dev_name": target_dev_name,
            "filter_applied": filter_dev_owner and bool(target_dev_id),
            "total_sprint_stories": len(raw_items),
            "matched_stories_count": len(all_stories),
            "stories": all_stories,
        }

    def _load_cached_context(self, story_id: str) -> Optional[StoryContext]:
        if not self.cache_file.exists():
            return None
        try:
            with open(self.cache_file, "r", encoding="utf-8") as f:
                cache = json.load(f)
            data = cache.get(story_id)
            if data:
                return StoryContext(**data)
        except Exception:
            pass
        return None

    def _save_cached_context(self, story_id: str, context: StoryContext) -> None:
        try:
            self.settings.ensure_runtime_dirs()
            cache = {}
            if self.cache_file.exists():
                try:
                    with open(self.cache_file, "r", encoding="utf-8") as f:
                        cache = json.load(f)
                except Exception:
                    cache = {}
            cache[story_id] = asdict(context)
            with open(self.cache_file, "w", encoding="utf-8") as f:
                json.dump(cache, f, indent=2)
        except Exception as e:
            logger.debug("Failed to write to context cache: %s", str(e))
