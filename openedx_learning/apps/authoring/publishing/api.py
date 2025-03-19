"""
Publishing API (warning: UNSTABLE, in progress API)

Please look at the models.py file for more information about the kinds of data
are stored in this app.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import TypeVar

from django.core.exceptions import ObjectDoesNotExist, ValidationError
from django.db.models import F, Q, QuerySet
from django.db.transaction import atomic

from .models import (
    Container,
    ContainerVersion,
    Draft,
    EntityList,
    EntityListRow,
    LearningPackage,
    PublishableContentModelRegistry,
    PublishableEntity,
    PublishableEntityMixin,
    PublishableEntityVersion,
    PublishableEntityVersionMixin,
    Published,
    PublishLog,
    PublishLogRecord,
)

# A few of the APIs in this file are generic and can be used for Containers in
# general, or e.g. Units (subclass of Container) in particular. These type
# variables are used to provide correct typing for those generic API methods.
ContainerModel = TypeVar('ContainerModel', bound=Container)
ContainerVersionModel = TypeVar('ContainerVersionModel', bound=ContainerVersion)

# The public API that will be re-exported by openedx_learning.apps.authoring.api
# is listed in the __all__ entries below. Internal helper functions that are
# private to this module should start with an underscore. If a function does not
# start with an underscore AND it is not in __all__, that function is considered
# to be callable only by other apps in the authoring package.
__all__ = [
    "get_learning_package",
    "get_learning_package_by_key",
    "create_learning_package",
    "update_learning_package",
    "learning_package_exists",
    "create_publishable_entity",
    "create_publishable_entity_version",
    "get_publishable_entity",
    "get_publishable_entity_by_key",
    "get_last_publish",
    "get_all_drafts",
    "get_entities_with_unpublished_changes",
    "get_entities_with_unpublished_deletes",
    "publish_all_drafts",
    "publish_from_drafts",
    "get_draft_version",
    "get_published_version",
    "set_draft_version",
    "soft_delete_draft",
    "reset_drafts_to_published",
    "register_content_models",
    "filter_publishable_entities",
    # 🛑 UNSTABLE: All APIs related to containers are unstable until we've figured
    #              out our approach to dynamic content (randomized, A/B tests, etc.)
    "create_container",
    "create_container_version",
    "create_next_container_version",
    "get_container",
    "get_container_by_key",
    "get_containers",
    "ContainerEntityListEntry",
    "get_entities_in_container",
    "contains_unpublished_changes",
    "get_containers_with_entity",
]


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


def learning_package_exists(key: str) -> bool:
    """
    Check whether a LearningPackage with a particular key exists.
    """
    return LearningPackage.objects.filter(key=key).exists()


def create_publishable_entity(
    learning_package_id: int,
    /,
    key: str,
    created: datetime,
    # User ID who created this
    created_by: int | None,
    *,
    can_stand_alone: bool = True,
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
        can_stand_alone=can_stand_alone,
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


def get_entities_with_unpublished_changes(
    learning_package_id: int,
    /,
    include_deleted_drafts: bool = False
) -> QuerySet[PublishableEntity]:
    """
    Fetch entities that have unpublished changes.

    By default, this excludes soft-deleted drafts but can be included using include_deleted_drafts option.
    """
    entities_qs = (
        PublishableEntity.objects
        .filter(learning_package_id=learning_package_id)
        .exclude(draft__version=F('published__version'))
    )

    if include_deleted_drafts:
        # This means that we should also return PublishableEntities where the draft
        # has been soft-deleted, but that deletion has not been published yet. Just
        # excluding records where the Draft and Published versions don't match won't
        # be enough here, because that will return soft-deletes that have already
        # been published (since NULL != NULL in SQL).
        #
        # So we explicitly exclude already-published soft-deletes:
        return entities_qs.exclude(
            Q(draft__version__isnull=True) & Q(published__version__isnull=True)
        )

    # Simple case: exclude all entities that have been soft-deleted.
    return entities_qs.exclude(draft__version__isnull=True)


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
    draft_qset = (
        Draft.objects.select_related("entity__published")
        .filter(entity__learning_package_id=learning_package_id)

        # Exclude entities where the Published version already matches the
        # Draft version.
        .exclude(entity__published__version_id=F("version_id"))

        # Account for soft-deletes:
        # NULL != NULL in SQL, so simply excluding entities where the Draft
        # and Published versions match will not catch the case where a
        # soft-delete has been published (i.e. both the Draft and Published
        # versions are NULL). We need to explicitly check for that case
        # instead, or else we will re-publish the same soft-deletes over
        # and over again.
        .exclude(Q(version__isnull=True) & Q(entity__published__version__isnull=True))
    )
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
        # If the drafts include any containers, we need to auto-publish their descendants:
        # TODO: this only handles one level deep and would need to be updated to support sections > subsections > units

        # Get the IDs of the ContainerVersion for any Containers whose drafts are slated to be published.
        container_version_ids = (
            Container.objects.filter(publishable_entity__draft__in=draft_qset)
            .values_list("publishable_entity__draft__version__containerversion__pk", flat=True)
        )
        if container_version_ids:
            # We are publishing at least one container. Check if it has any child components that aren't already slated
            # to be published.
            unpublished_draft_children = EntityListRow.objects.filter(
                entity_list__container_versions__pk__in=container_version_ids,
                entity_version=None,  # Unpinned entities only
            ).exclude(
                entity__draft__version=F("entity__published__version")  # Exclude already published things
            ).values_list("entity__draft__pk", flat=True)
            if unpublished_draft_children:
                # Force these additional child components to be published at the same time by adding them to the qset:
                draft_qset = Draft.objects.filter(
                    Q(pk__in=draft_qset.values_list("pk", flat=True)) |
                    Q(pk__in=unpublished_draft_children)
                )

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
    the publishable_entity.py module for more details.

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


def filter_publishable_entities(
    entities: QuerySet[PublishableEntity],
    has_draft=None,
    has_published=None
) -> QuerySet[PublishableEntity]:
    """
    Filter an entities query set.

    has_draft: You can filter by entities that has a draft or not.
    has_published: You can filter by entities that has a published version or not.
    """
    if has_draft is not None:
        entities = entities.filter(draft__version__isnull=not has_draft)
    if has_published is not None:
        entities = entities.filter(published__version__isnull=not has_published)

    return entities


def get_published_version_as_of(entity_id: int, publish_log_id: int) -> PublishableEntityVersion | None:
    """
    Get the published version of the given entity, at a specific snapshot in the
    history of this Learning Package, given by the PublishLog ID.

    This is a semi-private function, only available to other apps in the
    authoring package.
    """
    record = PublishLogRecord.objects.filter(
        entity_id=entity_id,
        publish_log_id__lte=publish_log_id,
    ).order_by('-publish_log_id').first()
    return record.new_version if record else None


def create_container(
    learning_package_id: int,
    key: str,
    created: datetime,
    created_by: int | None,
    *,
    can_stand_alone: bool = True,
    # The types on the following line are correct, but mypy will complain - https://github.com/python/mypy/issues/3737
    container_cls: type[ContainerModel] = Container,  # type: ignore[assignment]
) -> ContainerModel:
    """
    [ 🛑 UNSTABLE ]
    Create a new container.

    Args:
        learning_package_id: The ID of the learning package that contains the container.
        key: The key of the container.
        created: The date and time the container was created.
        created_by: The ID of the user who created the container
        can_stand_alone: Set to False when created as part of containers
        container_cls: The subclass of Container to use, if applicable

    Returns:
        The newly created container.
    """
    assert issubclass(container_cls, Container)
    with atomic():
        publishable_entity = create_publishable_entity(
            learning_package_id,
            key,
            created,
            created_by,
            can_stand_alone=can_stand_alone,
        )
        container = container_cls.objects.create(
            publishable_entity=publishable_entity,
        )
    return container


def create_entity_list() -> EntityList:
    """
    [ 🛑 UNSTABLE ]
    Create a new entity list. This is an structure that holds a list of entities
    that will be referenced by the container.

    Returns:
        The newly created entity list.
    """
    return EntityList.objects.create()


def create_entity_list_with_rows(
    entity_pks: list[int],
    entity_version_pks: list[int | None],
    *,
    learning_package_id: int | None,
) -> EntityList:
    """
    [ 🛑 UNSTABLE ]
    Create new entity list rows for an entity list.

    Args:
        entity_pks: The IDs of the publishable entities that the entity list rows reference.
        entity_version_pks: The IDs of the versions of the entities
            (PublishableEntityVersion) that the entity list rows reference, or
            Nones for "unpinned" (default).
        learning_package_id: Optional. Verify that all the entities are from
            the specified learning package.

    Returns:
        The newly created entity list.
    """
    # Do a quick check that the given entities are in the right learning package:
    if learning_package_id:
        if PublishableEntity.objects.filter(
            pk__in=entity_pks,
        ).exclude(
            learning_package_id=learning_package_id,
        ).exists():
            raise ValidationError("Container entities must be from the same learning package.")

    order_nums = range(len(entity_pks))
    with atomic(savepoint=False):

        entity_list = create_entity_list()
        EntityListRow.objects.bulk_create(
            [
                EntityListRow(
                    entity_list=entity_list,
                    entity_id=entity_pk,
                    order_num=order_num,
                    entity_version_id=entity_version_pk,
                )
                for order_num, entity_pk, entity_version_pk in zip(
                    order_nums, entity_pks, entity_version_pks
                )
            ]
        )
    return entity_list


def _create_container_version(
    container: Container,
    version_num: int,
    *,
    title: str,
    entity_list: EntityList,
    created: datetime,
    created_by: int | None,
    container_version_cls: type[ContainerVersionModel] = ContainerVersion,  # type: ignore[assignment]
) -> ContainerVersionModel:
    """
    Private internal method for logic shared by create_container_version() and
    create_next_container_version().
    """
    assert issubclass(container_version_cls, ContainerVersion)
    with atomic(savepoint=False):  # Make sure this will happen atomically but we don't need to create a new savepoint.
        publishable_entity_version = create_publishable_entity_version(
            container.publishable_entity_id,
            version_num=version_num,
            title=title,
            created=created,
            created_by=created_by,
        )
        container_version = container_version_cls.objects.create(
            publishable_entity_version=publishable_entity_version,
            container_id=container.pk,
            entity_list=entity_list,
        )

    return container_version


def create_container_version(
    container_id: int,
    version_num: int,
    *,
    title: str,
    publishable_entities_pks: list[int],
    entity_version_pks: list[int | None] | None,
    created: datetime,
    created_by: int | None,
    container_version_cls: type[ContainerVersionModel] = ContainerVersion,  # type: ignore[assignment]
) -> ContainerVersionModel:
    """
    [ 🛑 UNSTABLE ]
    Create a new container version.

    Args:
        container_id: The ID of the container that the version belongs to.
        version_num: The version number of the container.
        title: The title of the container.
        publishable_entities_pks: The IDs of the members of the container.
        entity_version_pks: The IDs of the versions to pin to, if pinning is desired.
        created: The date and time the container version was created.
        created_by: The ID of the user who created the container version.
        container_version_cls: The subclass of ContainerVersion to use, if applicable.

    Returns:
        The newly created container version.
    """
    assert title is not None
    assert publishable_entities_pks is not None

    with atomic(savepoint=False):
        container = Container.objects.select_related("publishable_entity").get(pk=container_id)
        entity = container.publishable_entity
        if entity_version_pks is None:
            entity_version_pks = [None] * len(publishable_entities_pks)
        entity_list = create_entity_list_with_rows(
            entity_pks=publishable_entities_pks,
            entity_version_pks=entity_version_pks,
            learning_package_id=entity.learning_package_id,
        )
        container_version = _create_container_version(
            container,
            version_num,
            title=title,
            entity_list=entity_list,
            created=created,
            created_by=created_by,
            container_version_cls=container_version_cls,
        )

    return container_version


def create_next_container_version(
    container_pk: int,
    *,
    title: str | None,
    publishable_entities_pks: list[int] | None,
    entity_version_pks: list[int | None] | None,
    created: datetime,
    created_by: int | None,
    container_version_cls: type[ContainerVersionModel] = ContainerVersion,  # type: ignore[assignment]
) -> ContainerVersionModel:
    """
    [ 🛑 UNSTABLE ]
    Create the next version of a container. A new version of the container is created
    only when its metadata changes:

    * Something was added to the Container.
    * We re-ordered the rows in the container.
    * Something was removed from the container.
    * The Container's metadata changed, e.g. the title.
    * We pin to different versions of the Container.

    Args:
        container_pk: The ID of the container to create the next version of.
        title: The title of the container. None to keep the current title.
        publishable_entities_pks: The IDs of the members current members of the container. Or None for no change.
        entity_version_pks: The IDs of the versions to pin to, if pinning is desired.
        created: The date and time the container version was created.
        created_by: The ID of the user who created the container version.
        container_version_cls: The subclass of ContainerVersion to use, if applicable.

    Returns:
        The newly created container version.
    """
    assert issubclass(container_version_cls, ContainerVersion)
    with atomic():
        container = Container.objects.select_related("publishable_entity").get(pk=container_pk)
        entity = container.publishable_entity
        last_version = container.versioning.latest
        assert last_version is not None
        next_version_num = last_version.version_num + 1
        if publishable_entities_pks is None:
            # We're only changing metadata. Keep the same entity list.
            next_entity_list = last_version.entity_list
        else:
            if entity_version_pks is None:
                entity_version_pks = [None] * len(publishable_entities_pks)
            next_entity_list = create_entity_list_with_rows(
                entity_pks=publishable_entities_pks,
                entity_version_pks=entity_version_pks,
                learning_package_id=entity.learning_package_id,
            )
        next_container_version = _create_container_version(
            container,
            next_version_num,
            title=title if title is not None else last_version.title,
            entity_list=next_entity_list,
            created=created,
            created_by=created_by,
            container_version_cls=container_version_cls,
        )

    return next_container_version


def get_container(pk: int) -> Container:
    """
    [ 🛑 UNSTABLE ]
    Get a container by its primary key.

    Args:
        pk: The primary key of the container.

    Returns:
        The container with the given primary key.
    """
    return Container.objects.get(pk=pk)


def get_container_by_key(learning_package_id: int, /, key: str) -> Container:
    """
    [ 🛑 UNSTABLE ]
    Get a container by its learning package and primary key.

    Args:
        learning_package_id: The ID of the learning package that contains the container.
        key: The primary key of the container.

    Returns:
        The container with the given primary key.
    """
    return Container.objects.get(
        publishable_entity__learning_package_id=learning_package_id,
        publishable_entity__key=key,
    )


def get_containers(
    learning_package_id: int,
    container_cls: type[ContainerModel] = Container,  # type: ignore[assignment]
) -> QuerySet[ContainerModel]:
    """
    [ 🛑 UNSTABLE ]
    Get all containers in the given learning package.

    Args:
        learning_package_id: The primary key of the learning package
        container_cls: The subclass of Container to use, if applicable

    Returns:
        A queryset containing the container associated with the given learning package.
    """
    assert issubclass(container_cls, Container)
    return container_cls.objects.filter(publishable_entity__learning_package=learning_package_id)


@dataclass(frozen=True)
class ContainerEntityListEntry:
    """
    [ 🛑 UNSTABLE ]
    Data about a single entity in a container, e.g. a component in a unit.
    """
    entity_version: PublishableEntityVersion
    pinned: bool

    @property
    def entity(self):
        return self.entity_version.entity


def get_entities_in_container(
    container: Container,
    *,
    published: bool,
) -> list[ContainerEntityListEntry]:
    """
    [ 🛑 UNSTABLE ]
    Get the list of entities and their versions in the current draft or
    published version of the given container.

    Args:
        container: The Container, e.g. returned by `get_container()`
        published: `True` if we want the published version of the container, or
            `False` for the draft version.
    """
    assert isinstance(container, Container)
    container_version = container.versioning.published if published else container.versioning.draft
    if container_version is None:
        raise ContainerVersion.DoesNotExist  # This container has not been published yet, or has been deleted.
    assert isinstance(container_version, ContainerVersion)
    entity_list = []
    for row in container_version.entity_list.entitylistrow_set.order_by("order_num"):
        entity_version = row.entity_version  # This will be set if pinned
        if not entity_version:  # If this entity is "unpinned", use the latest published/draft version:
            entity_version = row.entity.published.version if published else row.entity.draft.version
        if entity_version is not None:  # As long as this hasn't been soft-deleted:
            entity_list.append(ContainerEntityListEntry(
                entity_version=entity_version,
                pinned=row.entity_version is not None,
            ))
        # else we could indicate somehow a deleted item was here, e.g. by returning a ContainerEntityListEntry with
        # deleted=True, but we don't have a use case for that yet.
    return entity_list


def contains_unpublished_changes(container_id: int) -> bool:
    """
    [ 🛑 UNSTABLE ]
    Check recursively if a container has any unpublished changes.

    Note: unlike this method, the similar-sounding
    `container.versioning.has_unpublished_changes` property only reports
    if the container itself has unpublished changes, not
    if its contents do. So if you change a title or add a new child component,
    `has_unpublished_changes` will be `True`, but if you merely edit a component
    that's in the container, it will be `False`. This method will return `True`
    in either case.
    """
    # This is similar to 'get_container(container.container_id)' but pre-loads more data.
    container = Container.objects.select_related(
        "publishable_entity__draft__version__containerversion__entity_list",
    ).get(pk=container_id)

    if container.versioning.has_unpublished_changes:
        return True

    # We only care about children that are un-pinned, since published changes to pinned children don't matter
    entity_list = container.versioning.draft.entity_list

    # This is a naive and inefficient implementation but should be correct.
    # TODO: Once we have expanded the containers system to support multiple levels (not just Units and Components but
    # also subsections and sections) and we have an expanded test suite for correctness, then we can optimize.
    # We will likely change to a tracking-based approach rather than a "scan for changes" based approach.
    for row in entity_list.entitylistrow_set.filter(entity_version=None).select_related(
        "entity__container",
        "entity__draft__version",
        "entity__published__version",
    ):
        try:
            child_container = row.entity.container
        except Container.DoesNotExist:
            child_container = None
        if child_container:
            # This is itself a container - check recursively:
            if contains_unpublished_changes(child_container.pk):
                return True
        else:
            # This is not a container:
            draft_pk = row.entity.draft.version_id if row.entity.draft else None
            published_pk = row.entity.published.version_id if hasattr(row.entity, "published") else None
            if draft_pk != published_pk:
                return True
    return False


def get_containers_with_entity(
    publishable_entity_pk: int,
    *,
    ignore_pinned=False,
) -> QuerySet[Container]:
    """
    [ 🛑 UNSTABLE ]
    Find all draft containers that directly contain the given entity.

    They will always be from the same learning package; cross-package containers
    are not allowed.

    Args:
        publishable_entity_pk: The ID of the PublishableEntity to search for.
        ignore_pinned: if true, ignore any pinned references to the entity.
    """
    if ignore_pinned:
        qs = Container.objects.filter(
            # Note: these two conditions must be in the same filter() call, or the query won't be correct.
            publishable_entity__draft__version__containerversion__entity_list__entitylistrow__entity_id=publishable_entity_pk,  # pylint: disable=line-too-long # noqa: E501
            publishable_entity__draft__version__containerversion__entity_list__entitylistrow__entity_version_id=None,  # pylint: disable=line-too-long # noqa: E501
        ).order_by("pk")  # Ordering is mostly for consistent test cases.
    else:
        qs = Container.objects.filter(
            publishable_entity__draft__version__containerversion__entity_list__entitylistrow__entity_id=publishable_entity_pk,  # pylint: disable=line-too-long # noqa: E501
        ).order_by("pk")  # Ordering is mostly for consistent test cases.
    # Could alternately do this query in two steps. Not sure which is more efficient; depends on how the DB plans it.
    # # Find all the EntityLists that contain the given entity:
    # lists = EntityList.objects.filter(entitylistrow__entity_id=publishable_entity_pk).values_list('pk', flat=True)
    # qs = Container.objects.filter(
    #     publishable_entity__draft__version__containerversion__entity_list__in=lists
    # )
    return qs
