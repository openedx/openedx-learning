"""
Django signal handlers for the publishing applet.
"""

from functools import partial

from django.db import transaction
from django.db.models.signals import post_delete
from django.dispatch import receiver

from .models.learning_package import LearningPackage
from .signals import LEARNING_PACKAGE_DELETED, LearningPackageEventData


@receiver(post_delete, sender=LearningPackage)
def emit_learning_package_deleted(sender, instance, **kwargs):  # pylint: disable=unused-argument
    """
    Emit ``LEARNING_PACKAGE_DELETED`` after a ``LearningPackage`` is deleted.

    This fires for any deletion: single-object ``.delete()``, bulk
    ``QuerySet.delete()`` (Django calls ``post_delete`` once per row), or
    deletions performed via the Django admin. There is currently no official API
    for deleting Learning Packages, but you can orphan them by deleting any
    references to them such as ``ContentLibrary`` instances in openedx-platform.

    The event is deferred via ``transaction.on_commit`` so that it is only
    emitted once the enclosing database transaction has been committed. If
    the transaction is rolled back, the row still exists and no event fires.

    Note: by the time this handler runs, the ``LearningPackage`` row has
    already been removed from the database (Django preserves ``instance.pk``
    on the in-memory object, but the DB row is gone). We capture ``id`` and
    ``title`` at handler-invocation time so that the event payload remains
    correct even though the underlying record is no longer retrievable.
    """
    transaction.on_commit(
        partial(
            LEARNING_PACKAGE_DELETED.send_event,
            learning_package=LearningPackageEventData(id=instance.id, title=instance.title),
        )
    )
