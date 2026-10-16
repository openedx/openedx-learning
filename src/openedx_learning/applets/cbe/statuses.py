"""
The monotone write the rollup uses for the group and competency status tables.
"""
from __future__ import annotations

from datetime import datetime
from typing import TypeVar

from django.db import models

from .models import MasteryStatus

__all__ = ["raise_status"]

_ModelT = TypeVar("_ModelT", bound=models.Model)


def raise_status(
    manager: models.Manager[_ModelT], *, lookup: dict[str, int], status: MasteryStatus, now: datetime,
) -> int:
    """
    Create or raise the learner status row identified by ``lookup``; never lowers a stored status.

    Returns 1 if a row was created or raised, 0 if the stored status was already at least ``status``.
    """
    row, created = manager.get_or_create(**lookup, defaults={"status_id": status, "created": now, "modified": now})
    if created:
        return 1
    # A single conditional UPDATE, never read-then-write: a stale read can only compute a value that is too low.
    return manager.filter(pk=row.pk, status_id__lt=status).update(status_id=status, modified=now)
