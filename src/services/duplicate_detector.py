"""Normalized fuzzy duplicate detection between generated and existing tasks."""

from __future__ import annotations

import difflib
import logging
import re
from dataclasses import dataclass
from typing import List, Literal, Optional

from src.client.models import Subitem
from src.services.task_models import GeneratedTask

logger = logging.getLogger(__name__)

MatchType = Literal["DUPLICATE_EXACT", "DUPLICATE_LIKELY", "NO_OVERLAP"]


@dataclass
class DuplicateMatch:
    """Represents an overlap detected between a generated task and an existing subtask."""

    generated_title: str
    existing_title: str
    existing_id: str
    match_type: MatchType
    similarity_score: float
    recommendation: str


class DuplicateDetector:
    """Detects exact and likely duplicates using normalization and string similarity."""

    PREFIX_REGEX = re.compile(
        r"^(?:\[?(?:FE|BE)\]?\s*[-:]*\s*(?:\d{1,2}\s*[-:]*\s*)?)",
        re.IGNORECASE,
    )
    PUNCT_REGEX = re.compile(r"[^\w\s]", re.UNICODE)

    def normalize_title(self, title: str) -> str:
        """Strip prefixes, remove punctuation, collapse whitespace, and lowercase."""
        if not title:
            return ""
        # 1. Strip FE / BE prefixes
        cleaned = self.PREFIX_REGEX.sub("", title.strip())
        # 2. Lowercase
        cleaned = cleaned.lower()
        # 3. Strip punctuation
        cleaned = self.PUNCT_REGEX.sub(" ", cleaned)
        # 4. Collapse whitespace
        cleaned = " ".join(cleaned.split())
        return cleaned

    def compute_similarity(self, s1: str, s2: str) -> float:
        """Calculate SequenceMatcher similarity ratio between normalized strings."""
        norm1 = self.normalize_title(s1)
        norm2 = self.normalize_title(s2)

        if not norm1 or not norm2:
            return 0.0
        if norm1 == norm2:
            return 1.0

        # Token set check: if tokens are identical regardless of order
        tokens1 = sorted(norm1.split())
        tokens2 = sorted(norm2.split())
        if tokens1 == tokens2:
            return 0.98

        # Levenshtein-like ratio
        ratio = difflib.SequenceMatcher(None, norm1, norm2).ratio()
        return round(ratio, 3)

    def check_task(
        self,
        generated_task: GeneratedTask,
        existing_subitems: List[Subitem],
        likely_threshold: float = 0.75,
    ) -> Optional[DuplicateMatch]:
        """Check if a generated task matches any existing subitem under the story."""
        norm_gen = self.normalize_title(generated_task.title)

        best_match: Optional[DuplicateMatch] = None
        highest_score = 0.0

        for existing in existing_subitems:
            norm_ext = self.normalize_title(existing.name)
            if not norm_ext:
                continue

            # Exact normalized match
            if norm_gen == norm_ext:
                return DuplicateMatch(
                    generated_title=generated_task.title,
                    existing_title=existing.name,
                    existing_id=existing.id,
                    match_type="DUPLICATE_EXACT",
                    similarity_score=1.0,
                    recommendation="Exact duplicate detected. Review before creating.",
                )

            score = self.compute_similarity(generated_task.title, existing.name)
            if score > highest_score and score >= likely_threshold:
                highest_score = score
                best_match = DuplicateMatch(
                    generated_title=generated_task.title,
                    existing_title=existing.name,
                    existing_id=existing.id,
                    match_type="DUPLICATE_LIKELY",
                    similarity_score=score,
                    recommendation=f"High similarity ({int(score*100)}%). Review to prevent duplicate work.",
                )

        return best_match

    def analyze_plan_duplicates(
        self,
        tasks: List[GeneratedTask],
        existing_subitems: List[Subitem],
    ) -> List[DuplicateMatch]:
        """Find all duplicate matches across all generated tasks in a plan."""
        matches: List[DuplicateMatch] = []
        for task in tasks:
            match = self.check_task(task, existing_subitems)
            if match:
                matches.append(match)
        return matches
