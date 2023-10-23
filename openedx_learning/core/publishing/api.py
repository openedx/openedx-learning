"""
Publishing API (warning: UNSTABLE, in progress API)

Please look at the models.py file for more information about the kinds of data
are stored in this app.
"""
from __future__ import annotations

from datetime import datetime, timezone

from django.core.exceptions import ObjectDoesNotExist
from django.db.models import F, QuerySet
from django.db.transaction import atomic

from .model_mixins import PublishableContentModelRegistry, PublishableEntityMixin, PublishableEntityVersionMixin
from .models import (
    Draft,
    LearningPackage,
    PublishableEntity,
    PublishableEntityVersion,
    Published,
    PublishLog,
    PublishLogRecord,
)


def create_learning_package(
    key: str, title: str, created: datetime | None = None
) -> LearningPackage:
    """
    Create a new LearningPackage.

    The ``key`` must be unique.

    Errors that can be raised:

    * django.core.exceptions.ValidationError
    """
    if not created:
        created = datetime.now(tz=timezone.utc)

    package = LearningPackage(
        key=key,
        title=title,
        created=created,
        updated=created,
    )
    package.full_clean()
    package.save()

    return package


def create_publishable_entity(
    learning_package_id: int,
    key: str,
    created: datetime,
    # User ID who created this
    created_by: int | None,
) -> PublishableEntity:
    """
    Create a PublishableEntity.

    You'd typically want to call this right before creating your own content
    model that points to it.
    """
    return PublishableEntity.objects.create(
        learning_package_id=learning_package_id,
        key=key,
        created=created,
        created_by_id=created_by,
    )


def create_publishable_entity_version(
    entity_id: int,
    version_num: int,
    title: str,
    created: datetime,
    created_by: int | None,
) -> PublishableEntityVersion:
    """
    Create a PublishableEntityVersion.

    You'd typically want to call this right before creating your own content
    version model that points to it.
    """
    with atomic():
        version = PublishableEntityVersion.objects.create(
            entity_id=entity_id,
            version_num=version_num,
            title=title,
            created=created,
            created_by_id=created_by,
        )
        Draft.objects.update_or_create(
            entity_id=entity_id,
            defaults={"version": version},
        )
    return version


def learning_package_exists(key: str) -> bool:
    """
    Check whether a LearningPackage with a particular key exists.
    """
    return LearningPackage.objects.filter(key=key).exists()


def publish_all_drafts(
    learning_package_id: int,
    message="",
    published_at: datetime | None = None,
    published_by: int | None = None
):
    """
    Publish everything that is a Draft and is not already published.
    """
    draft_qset = (
        Draft.objects.select_related("entity__published")
        .filter(entity__learning_package_id=learning_package_id)
        .exclude(entity__published__version_id=F("version_id"))
    )
    return publish_from_drafts(
        learning_package_id, draft_qset, message, published_at, published_by
    )


def publish_from_drafts(
    learning_package_id: int,  # LearningPackage.id
    draft_qset: QuerySet,
    message: str = "",
    published_at: datetime | None = None,
    published_by: int | None = None,  # User.id
) -> PublishLog:
    """
    Publish the rows in the ``draft_model_qsets`` args passed in.
    """
    if published_at is None:
        published_at = datetime.now(tz=timezone.utc)

    with atomic():
        # One PublishLog for this entire publish operation.
        publish_log = PublishLog(
            learning_package_id=learning_package_id,
            message=message,
            published_at=published_at,
            published_by_id=published_by,
        )
        publish_log.full_clean()
        publish_log.save(force_insert=True)

        for draft in draft_qset.select_related("entity__published__version"):
            try:
                old_version = draft.entity.published.version
            except ObjectDoesNotExist:
                # This means there is no published version yet.
                old_version = None

            # Create a record describing publishing this particular Publishable
            # (useful for auditing and reverting).
            publish_log_record = PublishLogRecord(
                publish_log=publish_log,
                entity=draft.entity,
                old_version=old_version,
                new_version=draft.version,
            )
            publish_log_record.full_clean()
            publish_log_record.save(force_insert=True)

            # Update the lookup we use to fetch the published versions
            Published.objects.update_or_create(
                entity=draft.entity,
                defaults={
                    "version": draft.version,
                    "publish_log_record": publish_log_record,
                },
            )

    return publish_log


def get_draft_version(publishable_entity_id: int) -> PublishableEntityVersion | None:
    """
    Return current draft PublishableEntityVersion for this PublishableEntity.

    This function will return None if there is no current draft.
    """
    try:
        draft = Draft.objects.select_related("version").get(
            entity_id=publishable_entity_id
        )
    except Draft.DoesNotExist:
        # No draft was ever created.
        return None

    # draft.version could be None if it was set that way by set_draft_version.
    # Setting the Draft.version to None is how we show that we've "deleted" the
    # content in Studio.
    return draft.version


def set_draft_version(publishable_entity_id: int, publishable_entity_version_pk: int | None) -> None:
    """
    Modify the Draft of a PublishableEntity to be a PublishableEntityVersion.

    This would most commonly be used to set the Draft to point to a newly
    created PublishableEntityVersion that was created in Studio (because someone
    edited some content). Setting a Draft's version to None is like deleting it
    from Studio's editing point of view. We don't actually delete the Draft row
    because we'll need that for publishing purposes (i.e. to delete content from
    the published branch).
    """
    draft = Draft.objects.get(entity_id=publishable_entity_id)
    draft.version_id = publishable_entity_version_pk
    draft.save()


def register_content_models(
    content_model_cls: type[PublishableEntityMixin],
    content_version_model_cls: type[PublishableEntityVersionMixin],
):
    """
    Register what content model maps to what content version model.

    This is so that we can provide convenience links between content models and
    content version models *through* the publishing apps, so that you can do
    things like finding the draft version of a content model more easily. See
    the model_mixins.py module for more details.

    This should only be imported and run from the your app's AppConfig.ready()
    method. For example, in the components app, this looks like:

        def ready(self):
            from ..publishing.api import register_content_models
            from .models import Component, ComponentVersion

            register_content_models(Component, ComponentVersion)

    There may be a more clever way to introspect this information from the model
    metadata, but this is simple and explicit.
    """
    return PublishableContentModelRegistry.register(
        content_model_cls, content_version_model_cls
    )
