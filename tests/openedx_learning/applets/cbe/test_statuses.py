"""
Tests for `raise_status`, the monotone write shared by the learner status tables.
"""
from datetime import datetime, timezone

import pytest

from openedx_learning.applets.cbe.statuses import raise_status
from openedx_learning.models import MasteryStatus, StudentCompetencyStatus

pytestmark = pytest.mark.django_db

FIRST = datetime(2026, 1, 1, tzinfo=timezone.utc)
SECOND = datetime(2026, 2, 1, tzinfo=timezone.utc)


def _write(user, tag, status: MasteryStatus, now: datetime) -> int:
    return raise_status(
        StudentCompetencyStatus.objects, lookup={"user_id": user.id, "tag_id": tag.id}, status=status, now=now,
    )


def test_creates_a_missing_row(user, tag) -> None:
    """A first write creates the row with created equal to modified."""
    assert _write(user, tag, MasteryStatus.PARTIALLY_ATTEMPTED, FIRST) == 1

    row = StudentCompetencyStatus.objects.get(user=user, tag=tag)
    assert row.status_id == MasteryStatus.PARTIALLY_ATTEMPTED
    assert (row.created, row.modified) == (FIRST, FIRST)


def test_raises_a_lower_stored_status(user, tag) -> None:
    """A higher status replaces a lower one and moves modified but not created."""
    _write(user, tag, MasteryStatus.PARTIALLY_ATTEMPTED, FIRST)

    assert _write(user, tag, MasteryStatus.DEMONSTRATED, SECOND) == 1

    row = StudentCompetencyStatus.objects.get(user=user, tag=tag)
    assert row.status_id == MasteryStatus.DEMONSTRATED
    assert (row.created, row.modified) == (FIRST, SECOND)


def test_never_lowers_a_stored_status(user, tag) -> None:
    """A lower status is discarded and the row is left exactly as it was."""
    _write(user, tag, MasteryStatus.DEMONSTRATED, FIRST)

    assert _write(user, tag, MasteryStatus.PARTIALLY_ATTEMPTED, SECOND) == 0

    row = StudentCompetencyStatus.objects.get(user=user, tag=tag)
    assert row.status_id == MasteryStatus.DEMONSTRATED
    assert row.modified == FIRST


def test_equal_status_changes_nothing(user, tag) -> None:
    """Writing the stored value again is a no-op, so modified keeps its old value."""
    _write(user, tag, MasteryStatus.DEMONSTRATED, FIRST)

    assert _write(user, tag, MasteryStatus.DEMONSTRATED, SECOND) == 0

    assert StudentCompetencyStatus.objects.get(user=user, tag=tag).modified == FIRST
