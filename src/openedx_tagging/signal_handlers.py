"""Signal handlers for tagging-related model updates."""

from functools import partial

from django.db import transaction
from django.db.models.signals import post_save
from django.dispatch import receiver

from openedx_tagging.models.base import Tag
from openedx_tagging.tasks import emit_content_object_associations_changed_for_tag_task


@receiver(post_save, sender=Tag)
def tag_post_save(sender, **kwargs):  # pylint: disable=unused-argument
    """
    If a tag is updated, enqueue async event emission for all associated objects.
    """
    instance = kwargs.get("instance", None)

    if kwargs.get("created", False) or instance is None:
        return

    tag_id = instance.id
    if tag_id is None:
        return

    transaction.on_commit(
        partial(
            emit_content_object_associations_changed_for_tag_task.delay,
            tag_id=tag_id
        )
    )
