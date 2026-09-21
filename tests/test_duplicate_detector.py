"""Tests for DuplicateDetector normalized and fuzzy matching."""

import pytest

from src.client.models import Subitem
from src.services.duplicate_detector import DuplicateDetector
from src.services.task_models import GeneratedTask


@pytest.fixture
def detector() -> DuplicateDetector:
    return DuplicateDetector()


def test_normalize_title(detector: DuplicateDetector) -> None:
    assert detector.normalize_title("FE - User Signup Form") == "user signup form"
    assert detector.normalize_title("BE - 01 - User Signup API Endpoint") == "user signup api endpoint"
    assert detector.normalize_title("  [FE]:  Design   UI  !! ") == "design ui"
    assert detector.normalize_title("BE: Database Migrations") == "database migrations"


def test_exact_duplicate_detection(detector: DuplicateDetector) -> None:
    existing = [
        Subitem(id="SUB-1", name="FE - User Authentication Flow"),
        Subitem(id="SUB-2", name="BE - 01 - Auth Token Endpoints"),
    ]

    task_match = GeneratedTask(
        title="FE - User Authentication Flow",
        task_type="FE",
        objective="Obj",
        scope="Scope",
        expected_behavior="Expected",
        testing_considerations="Tests",
    )

    match = detector.check_task(task_match, existing)
    assert match is not None
    assert match.match_type == "DUPLICATE_EXACT"
    assert match.existing_id == "SUB-1"
    assert match.similarity_score == 1.0


def test_likely_duplicate_fuzzy_detection(detector: DuplicateDetector) -> None:
    existing = [
        Subitem(id="SUB-20", name="BE - 01 - Setup PostgreSQL Database Schema"),
    ]

    task_likely = GeneratedTask(
        title="BE - 02 - Setup Postgres Database Schema",
        task_type="BE",
        index=2,
        objective="Obj",
        scope="Scope",
        expected_behavior="Expected",
        testing_considerations="Tests",
    )

    match = detector.check_task(task_likely, existing)
    assert match is not None
    assert match.match_type in ("DUPLICATE_EXACT", "DUPLICATE_LIKELY")
    assert match.existing_id == "SUB-20"
    assert match.similarity_score >= 0.75


def test_no_overlap_detected(detector: DuplicateDetector) -> None:
    existing = [
        Subitem(id="SUB-30", name="FE - Profile Settings UI"),
    ]

    task_different = GeneratedTask(
        title="BE - 01 - Billing Stripe Webhook",
        task_type="BE",
        index=1,
        objective="Obj",
        scope="Scope",
        expected_behavior="Expected",
        testing_considerations="Tests",
    )

    match = detector.check_task(task_different, existing)
    assert match is None
