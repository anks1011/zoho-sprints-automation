"""Local persistence for generated task plans."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import List, Optional

from src.config import Settings, get_settings
from src.services.task_models import GeneratedTaskPlan

logger = logging.getLogger(__name__)


class PlanStore:
    """Handles saving, loading, and listing locally generated task plans."""

    def __init__(self, settings: Optional[Settings] = None) -> None:
        self.settings = settings or get_settings()

    def save_plan(self, plan: GeneratedTaskPlan) -> Path:
        """Save task plan as JSON to the plans directory and update latest pointer."""
        self.settings.ensure_runtime_dirs()

        plan_file = self.settings.plans_dir / f"{plan.plan_id}.json"
        with open(plan_file, "w", encoding="utf-8") as f:
            f.write(plan.model_dump_json(indent=2))

        # Update latest pointer for this story_id
        latest_file = self.settings.plans_dir / f"latest_{plan.story_id}.json"
        with open(latest_file, "w", encoding="utf-8") as f:
            f.write(plan.model_dump_json(indent=2))

        logger.debug("Saved task plan %s to %s", plan.plan_id, plan_file)
        return plan_file

    def load_plan(self, plan_id: str) -> Optional[GeneratedTaskPlan]:
        """Load plan by its unique plan_id."""
        plan_file = self.settings.plans_dir / f"{plan_id}.json"
        if not plan_file.exists():
            return None
        try:
            with open(plan_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            return GeneratedTaskPlan.model_validate(data)
        except Exception as e:
            logger.error("Failed to load plan %s: %s", plan_id, str(e))
            return None

    def load_latest_for_story(self, story_id: str) -> Optional[GeneratedTaskPlan]:
        """Load the most recent plan generated for a story_id."""
        latest_file = self.settings.plans_dir / f"latest_{story_id}.json"
        if not latest_file.exists():
            return None
        try:
            with open(latest_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            return GeneratedTaskPlan.model_validate(data)
        except Exception as e:
            logger.error("Failed to load latest plan for story %s: %s", story_id, str(e))
            return None

    def list_plans(self) -> List[str]:
        """Return list of all plan IDs stored."""
        if not self.settings.plans_dir.exists():
            return []
        return [
            p.stem
            for p in self.settings.plans_dir.glob("plan_*.json")
            if not p.name.startswith("latest_")
        ]
