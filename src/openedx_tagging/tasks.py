"""Celery tasks for openedx_tagging."""

import logging

from celery import shared_task  # type: ignore[import]
from openedx_events.content_authoring.data import ContentObjectChangedData  # type: ignore[import-untyped]
from openedx_events.content_authoring.signals import CONTENT_OBJECT_ASSOCIATIONS_CHANGED  # type: ignore[import-untyped]

from openedx_tagging.models.base import ObjectTag, Tag

logger = logging.getLogger(__name__)


def _emit_content_object_associations_changed_for_tag(tag: Tag) -> int:
    """
    Emit CONTENT_OBJECT_ASSOCIATIONS_CHANGED events for each content object linked to this tag
    via the ObjectTag assciations. This is used to trigger downstream updates
    like search index refreshes in Meilisearch.
    """
    object_ids = ObjectTag.objects.filter(tag=tag).values_list("object_id", flat=True)
    emitted_events = 0

    for object_id in object_ids.iterator():
        # .. event_implemented_name: CONTENT_OBJECT_ASSOCIATIONS_CHANGED
        # .. event_type: org.openedx.content_authoring.content.object.associations.changed.v1
        CONTENT_OBJECT_ASSOCIATIONS_CHANGED.send_event(
            content_object=ContentObjectChangedData(
                object_id=object_id,
                changes=["tags"],
            ),
        )
        emitted_events += 1

    logger.info(
        "Tag with id %s was updated. Emitted CONTENT_OBJECT_ASSOCIATIONS_CHANGED events for %s associated objects.",
        tag.id,
        emitted_events,
    )
    return emitted_events


@shared_task
def emit_content_object_associations_changed_for_tag_task(tag_id: int) -> int:
    """
    When a tag is updated, emit a CONTENT_OBJECT_ASSOCIATIONS_CHANGED event for every ObjectTag linked to that tag.
    Each ObjectTag represents an association between the tag and an Open edX object.
    Because downstream systems (for example, search indexes such as Meilisearch) index object-tag relationships,
    they must be notified so they can refresh the object's association data.
    """
    try:
        tag = Tag.objects.get(pk=tag_id)
    except Tag.DoesNotExist:
        logger.warning(
            "Skipping CONTENT_OBJECT_ASSOCIATIONS_CHANGED emission because tag id %s does not exist.",
            tag_id,
        )
        return 0

    return _emit_content_object_associations_changed_for_tag(tag)
