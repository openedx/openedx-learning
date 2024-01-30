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


def get_learning_package(learning_package_id: int, /) -> LearningPackage:
    """
    Get LearningPackage by ID.
    """
    return LearningPackage.objects.get(id=learning_package_id)


def get_learning_package_by_key(key: str) -> LearningPackage:
    """
    Get LearningPackage by key.

    Can throw a NotFoundError
    """
    return LearningPackage.objects.get(key=key)


def create_learning_package(
    key: str, title: str, description: str = "", created: datetime | None = None
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
        description=description,
        created=created,
        updated=created,
    )
    package.full_clean()
    package.save()

    return package


def update_learning_package(
    learning_package_id: int,
    /,
    key: str | None = None,
    title: str | None = None,
    description: str | None = None,
    updated: datetime | None = None,
) -> LearningPackage:
    """
    Make an update to LearningPackage metadata.

    Note that LearningPackage itself is not versioned (only stuff inside it is).
    """
    lp = LearningPackage.objects.get(id=learning_package_id)

    # If no changes were requested, there's nothing to update, so just return
    # the LearningPackage as-is.
    if all(field is None for field in [key, title, description, updated]):
        return lp

    if key is not None:
        lp.key = key
    if title is not None:
        lp.title = title
    if description is not None:
        lp.description = description

    # updated is a bit different–we auto-generate it if it's not explicitly
    # passed in.
    if updated is None:
        updated = datetime.now(tz=timezone.utc)
    lp.updated = updated

    lp.save()
    return lp


def create_publishable_entity(
    learning_package_id: int,
    /,
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
    /,
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


def get_publishable_entity(publishable_entity_id: int, /) -> PublishableEntity:
    return PublishableEntity.objects.get(id=publishable_entity_id)


def get_publishable_entity_by_key(learning_package_id, /, key) -> PublishableEntity:
    return PublishableEntity.objects.get(
        learning_package_id=learning_package_id,
        key=key,
    )


def learning_package_exists(key: str) -> bool:
    """
    Check whether a LearningPackage with a particular key exists.
    """
    return LearningPackage.objects.filter(key=key).exists()


def get_last_publish(learning_package_id: int, /) -> PublishLog | None:
    return PublishLog.objects \
                     .filter(learning_package_id=learning_package_id) \
                     .order_by('-id') \
                     .first()


def get_all_drafts(learning_package_id: int, /) -> QuerySet[Draft]:
    return Draft.objects.filter(
        entity__learning_package_id=learning_package_id,
        version__isnull=False,
    )


def get_entities_with_unpublished_changes(learning_package_id: int, /) -> QuerySet[PublishableEntity]:
    return PublishableEntity.objects \
                            .filter(learning_package_id=learning_package_id) \
                            .exclude(draft__version=F('published__version'))


def get_entities_with_unpublished_deletes(learning_package_id: int, /) -> QuerySet[PublishableEntity]:
    """
    Something will become "deleted" if it has a null Draft version but a
    not-null Published version. (If both are null, it means it's already been
    deleted in a previous publish, or it was never published.)
    """
    return PublishableEntity.objects \
                            .filter(
                                learning_package_id=learning_package_id,
                                draft__version__isnull=True,
                            ).exclude(published__version__isnull=True)


def publish_all_drafts(
    learning_package_id: int,
    /,
    message="",
    published_at: datetime | None = None,
    published_by: int | None = None
) -> PublishLog:
    """
    Publish everything that is a Draft and is not already published.
    """
    draft_qset = Draft.objects \
                      .select_related("entity__published") \
                      .filter(entity__learning_package_id=learning_package_id) \
                      .exclude(entity__published__version_id=F("version_id"))
    return publish_from_drafts(
        learning_package_id, draft_qset, message, published_at, published_by
    )


def publish_from_drafts(
    learning_package_id: int,  # LearningPackage.id
    /,
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


def get_draft_version(publishable_entity_id: int, /) -> PublishableEntityVersion | None:
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


def get_published_version(publishable_entity_id: int, /) -> PublishableEntityVersion | None:
    """
    Return current published PublishableEntityVersion for this PublishableEntity.

    This function will return None if there is no current published version.
    """
    try:
        published = Published.objects.select_related("version").get(
            entity_id=publishable_entity_id
        )
    except Published.DoesNotExist:
        return None

    # published.version could be None if something was published at one point,
    # had its draft soft deleted, and then was published again.
    return published.version


def set_draft_version(
    publishable_entity_id: int,
    publishable_entity_version_pk: int | None,
    /,
) -> None:
    """
    Modify the Draft of a PublishableEntity to be a PublishableEntityVersion.

    This would most commonly be used to set the Draft to point to a newly
    created PublishableEntityVersion that was created in Studio (because someone
    edited some content). Setting a Draft's version to None is like deleting it
    from Studio's editing point of view (see ``soft_delete_draft`` for more
    details).
    """
    draft = Draft.objects.get(entity_id=publishable_entity_id)
    draft.version_id = publishable_entity_version_pk
    draft.save()


def soft_delete_draft(publishable_entity_id: int, /) -> None:
    """
    Sets the Draft version to None.

    This "deletes" the ``PublishableEntity`` from the point of an authoring
    environment like Studio, but doesn't immediately remove the ``Published``
    version. No version data is actually deleted, so restoring is just a matter
    of pointing the Draft back to the most recent ``PublishableEntityVersion``
    for a given ``PublishableEntity``.
    """
    return set_draft_version(publishable_entity_id, None)


def reset_drafts_to_published(learning_package_id: int, /) -> None:
    """
    Reset all Drafts to point to the most recently Published versions.

    This is a way to say "discard my unpublished changes" at the level of an
    entire LearningPackage. Note that the ``PublishableEntityVersions`` that
    were created in the mean time are not deleted.

    Let's look at the example of a PublishableEntity where Draft and Published
    both point to version 4.

    * The PublishableEntity is then edited multiple times, creating a new
      version with every save. Each new save also updates the the Draft to point
      to it. After three such saves, Draft points at version 7.
    * No new publishes have happened, so Published still points to version 4.
    * ``reset_drafts_to_published`` is called. Draft now points to version 4 to
      match Published.
    * The PublishableEntity is edited again. This creates version 8, and Draft
      now points to this new version.

    So in the above example, versions 5-7 aren't discarded from the history, and
    it's important that the code creating the "next" version_num looks at the
    latest version created for a PublishableEntity (its ``latest`` attribute),
    rather than basing it off of the version that Draft points to.

    Also, there is no current immutable record for when a reset happens. It's
    not like a publish that leaves an entry in the ``PublishLog``.
    """
    # These are all the drafts that are different from the published versions.
    draft_qset = Draft.objects \
                      .select_related("entity__published") \
                      .filter(entity__learning_package_id=learning_package_id) \
                      .exclude(entity__published__version_id=F("version_id"))

    # Note: We can't do an .update with a F() on a joined field in the ORM, so
    # we have to loop through the drafts individually to reset them. We can
    # rework this into a bulk update or custom SQL if it becomes a performance
    # issue.
    with atomic():
        for draft in draft_qset:
            if hasattr(draft.entity, 'published'):
                draft.version_id = draft.entity.published.version_id
            else:
                draft.version = None
            draft.save()


def register_content_models(
    content_model_cls: type[PublishableEntityMixin],
    content_version_model_cls: type[PublishableEntityVersionMixin],
) -> PublishableContentModelRegistry:
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
