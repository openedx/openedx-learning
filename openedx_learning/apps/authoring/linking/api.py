"""
Linking API (warning: UNSTABLE, in progress API)

Please look at the models.py file for more information about the kinds of data
are stored in this app.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from django.db.models import QuerySet

from ..components.models import Component
from .models import LearningContextLinksStatus, LearningContextLinksStatusChoices, PublishableEntityLink

__all__ = [
    'delete_entity_link',
    'get_entity_links',
    'get_entity_links_by_downstream',
    'get_or_create_learning_context_link_status',
    'update_or_create_entity_link',
    'update_learning_context_link_status',
]


def get_or_create_learning_context_link_status(
    context_key: str, created: datetime | None = None
) -> LearningContextLinksStatus:
    """
    Get or create course link status row from LearningContextLinksStatus table for given course key.

    Args:
        context_key: Learning context or Course key

    Returns:
        LearningContextLinksStatus object
    """
    if not created:
        created = datetime.now(tz=timezone.utc)
    status, _ = LearningContextLinksStatus.objects.get_or_create(
        context_key=context_key,
        defaults={
            'status': LearningContextLinksStatusChoices.PENDING,
            'created': created,
            'updated': created,
        },
    )
    return status


def update_learning_context_link_status(
    context_key: str,
    status: LearningContextLinksStatusChoices,
    updated: datetime | None = None
) -> None:
    """
    Updates entity links processing status of given learning context.
    """
    if not updated:
        updated = datetime.now(tz=timezone.utc)
    LearningContextLinksStatus.objects.filter(context_key=context_key).update(
        status=status,
        updated=updated,
    )


def get_entity_links(filters: dict[str, Any]) -> QuerySet[PublishableEntityLink]:
    """
    Get entity links based on passed filters.
    """
    return PublishableEntityLink.objects.filter(**filters)


def update_or_create_entity_link(
    upstream_block: Component | None,
    /,
    upstream_usage_key: str,
    upstream_context_key: str,
    downstream_usage_key: str,
    downstream_context_key: str,
    downstream_context_title: str,
    version_synced: int,
    version_declined: int | None = None,
    created: datetime | None = None,
) -> PublishableEntityLink:
    """
    Update or create entity link. This will only update `updated` field if something has changed.
    """
    if not created:
        created = datetime.now(tz=timezone.utc)
    new_values = {
        'upstream_usage_key': upstream_usage_key,
        'upstream_context_key': upstream_context_key,
        'downstream_usage_key': downstream_usage_key,
        'downstream_context_key': downstream_context_key,
        'downstream_context_title': downstream_context_title,
        'version_synced': version_synced,
        'version_declined': version_declined,
    }
    if upstream_block:
        new_values.update(
            {
                'upstream_block': upstream_block.publishable_entity,
            }
        )
    try:
        link = PublishableEntityLink.objects.get(downstream_usage_key=downstream_usage_key)
        has_changes = False
        for key, value in new_values.items():
            prev = getattr(link, key)
            # None != None is True, so we need to check for it specially
            if prev != value and ~(prev is None and value is None):
                has_changes = True
                setattr(link, key, value)
        if has_changes:
            link.updated = created
            link.save()
    except PublishableEntityLink.DoesNotExist:
        link = PublishableEntityLink(**new_values)
        link.created = created
        link.updated = created
        link.save()
    return link


def delete_entity_link(downstream_usage_key: str):
    """Detele upstream->downstream entity link from database"""
    PublishableEntityLink.objects.filter(downstream_usage_key=downstream_usage_key).delete()


def get_entity_links_by_downstream(downstream_context_key: str) -> QuerySet[PublishableEntityLink]:
    """
    Filter publishable entity links by given downstream_context_key.
    Returns latest published version number of upstream_block as well.
    """
    return PublishableEntityLink.objects.filter(
        downstream_context_key=downstream_context_key
    ).select_related(
        "upstream_block__published__version",
        "upstream_block__learning_package"
    )
