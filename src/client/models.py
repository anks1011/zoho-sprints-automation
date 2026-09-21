"""Pydantic data models for Zoho Sprints entities."""

from __future__ import annotations

from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class Team(BaseModel):
    """Zoho Sprints Team / Workspace."""

    id: str
    name: str
    raw_data: Dict[str, Any] = Field(default_factory=dict, repr=False)


class Project(BaseModel):
    """Zoho Sprints Project."""

    id: str
    name: str
    prefix: Optional[str] = None
    status: Optional[str] = None
    team_id: Optional[str] = None
    raw_data: Dict[str, Any] = Field(default_factory=dict, repr=False)


class Sprint(BaseModel):
    """Zoho Sprints Sprint."""

    id: str
    name: str
    status: Optional[str] = None
    project_id: Optional[str] = None
    raw_data: Dict[str, Any] = Field(default_factory=dict, repr=False)


class ItemType(BaseModel):
    """Item Type in a project (e.g. Story, Task, Bug)."""

    id: str
    name: str
    is_default: bool = False
    raw_data: Dict[str, Any] = Field(default_factory=dict, repr=False)


class PriorityType(BaseModel):
    """Priority Type in a project (e.g. Low, Medium, High, None)."""

    id: str
    name: str
    is_default: bool = False
    raw_data: Dict[str, Any] = Field(default_factory=dict, repr=False)


class Subitem(BaseModel):
    """Zoho Sprints Subitem / Task."""

    id: str
    name: str
    description: Optional[str] = ""
    parent_item_id: Optional[str] = None
    item_type_id: Optional[str] = None
    item_type_name: Optional[str] = None
    priority_id: Optional[str] = None
    priority_name: Optional[str] = None
    point: Optional[float] = None
    status: Optional[str] = None
    raw_data: Dict[str, Any] = Field(default_factory=dict, repr=False)


class StoryItem(BaseModel):
    """Zoho Sprints parent Story / Item."""

    id: str
    name: str
    description: str = ""
    acceptance_criteria: Optional[str] = None
    team_id: str
    project_id: str
    sprint_id: str
    item_type_id: Optional[str] = None
    item_type_name: Optional[str] = None
    priority_id: Optional[str] = None
    priority_name: Optional[str] = None
    point: Optional[float] = None
    status: Optional[str] = None
    subitems: List[Subitem] = Field(default_factory=list)
    raw_data: Dict[str, Any] = Field(default_factory=dict, repr=False)
