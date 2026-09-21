"""Story details and retrieval endpoint."""

from __future__ import annotations

import logging
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status

from src.api.schemas import ErrorResponse, StoryDetailsResponse, SubitemResponse
from src.client.zoho_client import SprintsNotFoundError
from src.config import Settings, get_settings
from src.services.story_service import StoryService, StoryServiceError

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/stories", tags=["Stories"])


def get_story_service(settings: Settings = Depends(get_settings)) -> StoryService:
    return StoryService(settings=settings)


@router.get(
    "/{story_id}",
    response_model=StoryDetailsResponse,
    responses={
        404: {"model": ErrorResponse, "description": "Story not found"},
        400: {"model": ErrorResponse, "description": "Invalid story request"},
    },
)
def get_story_details(
    story_id: str,
    team_id: Optional[str] = Query(None, description="Optional Team/Workspace ID override"),
    project_id: Optional[str] = Query(None, description="Optional Project ID override"),
    sprint_id: Optional[str] = Query(None, description="Optional Sprint ID override"),
    story_service: StoryService = Depends(get_story_service),
) -> StoryDetailsResponse:
    """Fetch parent story details, formatted description, acceptance criteria, and subtasks."""
    clean_id = story_id.strip()
    if not clean_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Story ID cannot be empty.",
        )

    try:
        story = story_service.fetch_story(
            story_id=clean_id,
            team_id=team_id,
            project_id=project_id,
            sprint_id=sprint_id,
        )
    except SprintsNotFoundError as e:
        logger.warning("Story not found: %s", str(e))
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        ) from e
    except StoryServiceError as e:
        logger.error("Story service error for %s: %s", clean_id, str(e))
        err_msg = str(e)
        if "not found" in err_msg.lower():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=err_msg,
            ) from e
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=err_msg,
        ) from e
    except Exception as e:
        logger.exception("Unexpected error retrieving story %s: %s", clean_id, str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve story '{clean_id}': {str(e)}",
        ) from e

    subitems_resp = [
        SubitemResponse(
            id=sub.id,
            name=sub.name,
            description=sub.description,
            item_type_id=sub.item_type_id,
            item_type_name=sub.item_type_name,
            priority_id=sub.priority_id,
            priority_name=sub.priority_name,
            status=sub.status,
            point=sub.point,
        )
        for sub in story.subitems
    ]

    return StoryDetailsResponse(
        id=story.id,
        name=story.name,
        description=story.description,
        acceptance_criteria=story.acceptance_criteria,
        team_id=story.team_id,
        project_id=story.project_id,
        sprint_id=story.sprint_id,
        item_type_id=story.item_type_id,
        item_type_name=story.item_type_name,
        priority_id=story.priority_id,
        priority_name=story.priority_name,
        status=story.status,
        subitems=subitems_resp,
    )
