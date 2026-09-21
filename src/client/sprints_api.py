"""Zoho Sprints REST API service methods."""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from src.client.models import ItemType, PriorityType, Project, Sprint, StoryItem, Subitem, Team
from src.client.zoho_client import SprintsNotFoundError, ZohoHTTPClient
from src.config import Settings, get_settings

logger = logging.getLogger(__name__)


class SprintsAPI:
    """High-level API client for Zoho Sprints endpoints."""

    def __init__(
        self,
        settings: Optional[Settings] = None,
        http_client: Optional[ZohoHTTPClient] = None,
    ) -> None:
        self.settings = settings or get_settings()
        self.client = http_client or ZohoHTTPClient(self.settings)

    def list_teams(self) -> List[Team]:
        """Fetch all teams (workspaces) accessible to user."""
        response = self.client.request("GET", "teams/")
        logger.debug("Raw list_teams response: %s", response)
        teams_data = []

        if isinstance(response, list):
            teams_data = response
        elif isinstance(response, dict):
            teams_data = (
                response.get("portals")
                or response.get("teams")
                or response.get("teamDetails")
                or response.get("data")
                or []
            )

        teams = []
        for item in teams_data:
            t_id = str(item.get("zsoid") or item.get("teamId") or item.get("id") or "")
            t_name = str(item.get("teamName") or item.get("name") or item.get("orgName") or "Unnamed Team")
            if t_id:
                teams.append(Team(id=t_id, name=t_name, raw_data=item))
        return teams

    def list_projects(self, team_id: str) -> List[Project]:
        """Fetch all projects for a specific team."""
        response = self.client.request("GET", f"team/{team_id}/projects/", params={"action": "data"})
        projects_data = []

        if isinstance(response, list):
            projects_data = response
        elif isinstance(response, dict):
            projects_data = (
                response.get("projects")
                or response.get("projectDetails")
                or response.get("data")
                or []
            )

        projects = []
        for item in projects_data:
            p_id = str(item.get("projectId") or item.get("id") or "")
            p_name = str(item.get("projName") or item.get("projectName") or item.get("name") or "Unnamed Project")
            prefix = item.get("shortName") or item.get("prefix")
            status = str(item.get("status", "1"))
            if p_id:
                projects.append(
                    Project(
                        id=p_id,
                        name=p_name,
                        prefix=prefix,
                        status=status,
                        team_id=team_id,
                        raw_data=item,
                    )
                )
        return projects

    def list_sprints(self, team_id: str, project_id: str) -> List[Sprint]:
        """Fetch all sprints for a specific project."""
        response = self.client.request(
            "GET", f"team/{team_id}/projects/{project_id}/sprints/", params={"action": "data", "type": "all"}
        )
        sprints_data = []

        if isinstance(response, list):
            sprints_data = response
        elif isinstance(response, dict):
            sprints_data = (
                response.get("sprints")
                or response.get("sprintDetails")
                or response.get("data")
                or []
            )

        sprints = []
        for item in sprints_data:
            s_id = str(item.get("sprintId") or item.get("id") or "")
            s_name = str(item.get("sprintName") or item.get("name") or "Unnamed Sprint")
            status = str(item.get("status", ""))
            if s_id:
                sprints.append(
                    Sprint(
                        id=s_id,
                        name=s_name,
                        status=status,
                        project_id=project_id,
                        raw_data=item,
                    )
                )
        return sprints

    def get_backlog_id(self, team_id: str, project_id: str) -> Optional[str]:
        """Fetch the unique backlog ID for a project."""
        try:
            response = self.client.request("GET", f"team/{team_id}/projects/{project_id}/", params={"action": "getbacklog"})
            if isinstance(response, dict):
                return response.get("backlogId")
        except Exception as e:
            logger.debug("Failed to fetch backlog ID for project %s: %s", project_id, str(e))
        return None

    def get_item_types(self, team_id: str, project_id: str) -> List[ItemType]:
        """Fetch available item types (e.g. Story, Task, Bug) for a project."""
        response = self.client.request(
            "GET",
            f"team/{team_id}/projects/{project_id}/itemtype/",
            params={"action": "alldata"},
        )
        types_data = []
        if isinstance(response, list):
            types_data = response
        elif isinstance(response, dict):
            types_data = (
                response.get("projItemTypes")
                or response.get("itemTypes")
                or response.get("itemtypes")
                or response.get("data")
                or []
            )

        item_types = []
        for item in types_data:
            t_id = str(item.get("projItemTypeId") or item.get("itemTypeId") or item.get("id") or "")
            t_name = str(item.get("itemTypeName") or item.get("name") or "")
            is_def = bool(item.get("isDefault", False))
            if t_id:
                item_types.append(ItemType(id=t_id, name=t_name, is_default=is_def, raw_data=item))
        return item_types

    def get_priorities(self, team_id: str, project_id: str) -> List[PriorityType]:
        """Fetch priority levels for a project."""
        response = self.client.request(
            "GET",
            f"team/{team_id}/projects/{project_id}/priority/",
            params={"action": "data"},
        )
        prios_data = []
        if isinstance(response, list):
            prios_data = response
        elif isinstance(response, dict):
            prios_data = (
                response.get("projPriorities")
                or response.get("priorities")
                or response.get("priorityTypes")
                or response.get("data")
                or []
            )

        priorities = []
        for item in prios_data:
            p_id = str(item.get("projPriorityId") or item.get("priorityId") or item.get("id") or "")
            p_name = str(item.get("priorityName") or item.get("name") or "")
            is_def = bool(item.get("isDefault", False))
            if p_id:
                priorities.append(
                    PriorityType(id=p_id, name=p_name, is_default=is_def, raw_data=item)
                )
        return priorities

    def get_item(
        self, team_id: str, project_id: str, sprint_id: str, item_id: str
    ) -> StoryItem:
        """Fetch complete item/story details including existing subitems."""
        response = self.client.request(
            "GET",
            f"team/{team_id}/projects/{project_id}/sprints/{sprint_id}/item/{item_id}/",
            params={"action": "details"},
        )

        item_data = response
        user_display_names = response.get("userDisplayName") if isinstance(response, dict) else None
        if isinstance(response, dict) and "items" in response and isinstance(response["items"], list) and response["items"]:
            item_data = response["items"][0]
        elif isinstance(response, dict) and "itemDetail" in response:
            item_data = response["itemDetail"]
        elif isinstance(response, dict) and "item" in response:
            item_data = response["item"]

        if isinstance(item_data, dict) and user_display_names and "userDisplayName" not in item_data:
            item_data["userDisplayName"] = user_display_names

        retrieved_id = str(item_data.get("itemId") or item_data.get("id") or item_id)
        name = str(item_data.get("itemName") or item_data.get("name") or item_data.get("summary") or "")
        desc = str(item_data.get("description") or "")
        ac = item_data.get("acceptanceCriteria") or item_data.get("acceptance_criteria")
        actual_sprint_id = str(item_data.get("sprintId") or sprint_id)

        subitems = self._parse_subitems(item_data)
        # If no subitems in item details, attempt explicit subitem endpoint
        if not subitems:
            try:
                subitems = self.get_subitems(team_id, project_id, sprint_id, item_id)
            except Exception as e:
                logger.debug("Explicit subitem fetch returned empty or failed: %s", str(e))

        return StoryItem(
            id=retrieved_id,
            name=name,
            description=desc,
            acceptance_criteria=ac,
            team_id=team_id,
            project_id=project_id,
            sprint_id=actual_sprint_id,
            item_type_id=str(item_data.get("projItemTypeId") or item_data.get("projitemtypeid") or item_data.get("itemtypeId") or ""),
            item_type_name=item_data.get("itemtypeName"),
            priority_id=str(item_data.get("projPriorityId") or item_data.get("projpriorityid") or item_data.get("priorityId") or ""),
            priority_name=item_data.get("priorityName"),
            point=float(item_data["point"]) if item_data.get("point") is not None else None,
            status=str(item_data.get("status") or ""),
            subitems=subitems,
            raw_data=item_data,
        )

    def get_subitems(
        self, team_id: str, project_id: str, sprint_id: str, item_id: str
    ) -> List[Subitem]:
        """Fetch existing subitems for an item via the dedicated subitem endpoint."""
        response = self.client.request(
            "GET",
            f"team/{team_id}/projects/{project_id}/sprints/{sprint_id}/item/{item_id}/subitem/",
        )
        return self._parse_subitems(response)

    def create_subitem(
        self,
        team_id: str,
        project_id: str,
        sprint_id: str,
        item_id: str,
        name: str,
        item_type_id: str,
        priority_id: str,
        description: str = "",
        point: Optional[float] = None,
        custom_fields: Optional[Dict[str, Any]] = None,
        users: Optional[List[str] | str] = None,
    ) -> Subitem:
        """Create a new subitem under the specified parent item."""
        endpoint = f"team/{team_id}/projects/{project_id}/sprints/{sprint_id}/item/{item_id}/subitem/"
        data: Dict[str, Any] = {
            "name": name,
            "projitemtypeid": item_type_id,
            "projpriorityid": priority_id,
        }
        if description:
            data["description"] = description
        if point is not None:
            data["point"] = point
        if users:
            data["users"] = json.dumps(users) if isinstance(users, list) else str(users)
        if custom_fields:
            data.update(custom_fields)

        logger.info("Creating subitem '%s' under parent item %s...", name, item_id)
        response = self.client.request("POST", endpoint, data=data)

        res_data = (
            response.get("subItemDetail")
            or response.get("subitem")
            or response.get("itemDetail")
            or response
        )
        created_id = str(
            res_data.get("addedItemId")
            or res_data.get("subItemId")
            or res_data.get("itemId")
            or res_data.get("id")
            or ""
        )
        if not created_id:
            raise SprintsAPIError(
                f"Zoho Sprints subitem creation succeeded but no task ID was parsed: {response}"
            )

        return Subitem(
            id=created_id,
            name=name,
            description=description,
            parent_item_id=item_id,
            item_type_id=item_type_id,
            priority_id=priority_id,
            point=point,
            raw_data=response,
        )

    def get_project_statuses(self, team_id: str, project_id: str) -> List[Dict[str, Any]]:
        """Fetch all configured workflow item statuses for the project."""
        endpoint = f"team/{team_id}/projects/{project_id}/itemstatus/?action=data"
        try:
            response = self.client.request("GET", endpoint)
            return response.get("statuses", []) if isinstance(response, dict) else []
        except Exception as e:
            logger.warning("Could not fetch project statuses: %s", str(e))
            return []

    def update_item_status(
        self,
        team_id: str,
        project_id: str,
        sprint_id: str,
        item_id: str,
        status_id: str,
    ) -> Dict[str, Any]:
        """Update an item or subitem status (e.g., move to 'In Dev')."""
        endpoint = f"team/{team_id}/projects/{project_id}/sprints/{sprint_id}/item/{item_id}/"
        logger.info("Updating status of item %s to %s...", item_id, status_id)
        return self.client.request("POST", endpoint, data={"statusid": status_id})

    def delete_item(
        self,
        team_id: str,
        project_id: str,
        sprint_id: str,
        item_id: str,
    ) -> Dict[str, Any]:
        """Delete an item or subitem from Zoho Sprints."""
        endpoint = f"team/{team_id}/projects/{project_id}/sprints/{sprint_id}/item/{item_id}/"
        logger.info("Deleting item %s from sprint %s...", item_id, sprint_id)
        return self.client.request("DELETE", endpoint)

    def _parse_subitems(self, container: Any) -> List[Subitem]:
        """Parse subitem list from various potential response wrapper keys."""
        subitems_raw = []
        if isinstance(container, dict):
            subitems_raw = (
                container.get("subItems")
                or container.get("subitems")
                or container.get("subItemDetails")
                or container.get("data")
                or []
            )
        elif isinstance(container, list):
            subitems_raw = container

        subitems = []
        for s in subitems_raw:
            if not isinstance(s, dict):
                continue
            s_id = str(s.get("subItemId") or s.get("itemId") or s.get("id") or "")
            s_name = str(s.get("name") or s.get("summary") or "")
            if s_id and s_name:
                subitems.append(
                    Subitem(
                        id=s_id,
                        name=s_name,
                        description=str(s.get("description") or ""),
                        parent_item_id=str(s.get("parentItemId") or s.get("parentId") or ""),
                        item_type_id=str(s.get("projitemtypeid") or s.get("itemtypeId") or ""),
                        item_type_name=s.get("itemtypeName"),
                        priority_id=str(s.get("projpriorityid") or s.get("priorityId") or ""),
                        priority_name=s.get("priorityName"),
                        point=float(s["point"]) if s.get("point") is not None else None,
                        status=s.get("status"),
                        raw_data=s,
                    )
                )
        return subitems
