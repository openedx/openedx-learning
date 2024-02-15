"""
Components API (warning: UNSTABLE, in progress API)

These functions are often going to be simple-looking write operations, but there
is bookkeeping logic needed across multiple models to keep state consistent. You
can read from the models directly for various queries if necessary–we do this in
the Django Admin for instance. But you should NEVER mutate this app's models
directly, since there might be other related models that you may not know about.

Please look at the models.py file for more information about the kinds of data
are stored in this app.
"""
from __future__ import annotations

from datetime import datetime
from pathlib import Path

from django.db.models import Q, QuerySet
from django.db.transaction import atomic

from ..publishing import api as publishing_api
from .models import Component, ComponentType, ComponentVersion, ComponentVersionContent


def get_or_create_component_type(namespace: str, name: str) -> ComponentType:
    """
    Get the ID of a ComponentType, and create if missing.

    Caching Warning: Be careful about putting any caching decorator around this
    function (e.g. ``lru_cache``). It's possible that incorrect cache values
    could leak out in the event of a rollback–e.g. new types are introduced in
    a large import transaction which later fails. You can safely cache the
    results that come back from this function with a local dict in your import
    process instead.#
    """
    component_type, _created = ComponentType.objects.get_or_create(
        namespace=namespace,
        name=name,
    )
    return component_type


def create_component(
    learning_package_id: int,
    /,
    component_type: ComponentType,
    local_key: str,
    created: datetime,
    created_by: int | None,
) -> Component:
    """
    Create a new Component (an entity like a Problem or Video)
    """
    key = f"{component_type.namespace}:{component_type.name}:{local_key}"
    with atomic():
        publishable_entity = publishing_api.create_publishable_entity(
            learning_package_id, key, created, created_by
        )
        component = Component.objects.create(
            publishable_entity=publishable_entity,
            learning_package_id=learning_package_id,
            component_type=component_type,
            local_key=local_key,
        )
    return component


def create_component_version(
    component_pk: int,
    /,
    version_num: int,
    title: str,
    created: datetime,
    created_by: int | None,
) -> ComponentVersion:
    """
    Create a new ComponentVersion
    """
    with atomic():
        publishable_entity_version = publishing_api.create_publishable_entity_version(
            component_pk,
            version_num=version_num,
            title=title,
            created=created,
            created_by=created_by,
        )
        component_version = ComponentVersion.objects.create(
            publishable_entity_version=publishable_entity_version,
            component_id=component_pk,
        )
    return component_version


def create_next_version(
    component_pk: int,
    /,
    title: str,
    content_to_replace: dict[str, int | None],
    created: datetime,
    created_by: int | None = None,
) -> ComponentVersion:
    """
    Create a new ComponentVersion based on the most recent version.

    A very common pattern for making a new ComponentVersion is going to be "make
    it just like the last version, except changing these one or two things".
    Before calling this, you should create any new contents via the contents
    API, since ``content_to_replace`` needs Content IDs for the values.

    The ``content_to_replace`` dict is a mapping of strings representing the
    local path/key for a file, to ``Content.id`` values. Using a `None` for
    a value in this dict means to delete that key in the next version.

    It is okay to mark entries for deletion that don't exist. For instance, if a
    version has ``a.txt`` and ``b.txt``, sending a ``content_to_replace`` value
    of ``{"a.txt": None, "c.txt": None}`` will remove ``a.txt`` from the next
    version, leave ``b.txt`` alone, and will not error–even though there is no
    ``c.txt`` in the previous version. This is to make it a little more
    convenient to remove paths (e.g. due to deprecation) without having to
    always check for its existence first.

    TODO: Have to add learning_downloadable info to this when it comes time to
          support static asset download.
    """
    # This needs to grab the highest version_num for this Publishable Entity.
    # This will often be the Draft version, but not always. For instance, if
    # an entity was soft-deleted, the draft would be None, but the version_num
    # should pick up from the last edited version. Likewise, a Draft might get
    # reverted to an earlier version, but we want the latest version_num when
    # creating the next version.
    component = Component.objects.get(pk=component_pk)
    last_version = component.versioning.latest
    if last_version is None:
        next_version_num = 1
    else:
        next_version_num = last_version.version_num + 1

    with atomic():
        publishable_entity_version = publishing_api.create_publishable_entity_version(
            component_pk,
            version_num=next_version_num,
            title=title,
            created=created,
            created_by=created_by,
        )
        component_version = ComponentVersion.objects.create(
            publishable_entity_version=publishable_entity_version,
            component_id=component_pk,
        )
        # First copy the new stuff over...
        for key, content_pk in content_to_replace.items():
            # If the content_pk is None, it means we want to remove the
            # content represented by our key from the next version. Otherwise,
            # we add our key->content_pk mapping to the next version.
            if content_pk is not None:
                ComponentVersionContent.objects.create(
                    content_id=content_pk,
                    component_version=component_version,
                    key=key,
                    learner_downloadable=False,
                )
        # Now copy any old associations that existed, as long as they aren't
        # in conflict with the new stuff or marked for deletion.
        last_version_content_mapping = ComponentVersionContent.objects \
                                                              .filter(component_version=last_version)
        for cvrc in last_version_content_mapping:
            if cvrc.key not in content_to_replace:
                ComponentVersionContent.objects.create(
                    content_id=cvrc.content_id,
                    component_version=component_version,
                    key=cvrc.key,
                    learner_downloadable=cvrc.learner_downloadable,
                )

        return component_version


def create_component_and_version(
    learning_package_id: int,
    /,
    component_type: ComponentType,
    local_key: str,
    title: str,
    created: datetime,
    created_by: int | None = None,
) -> tuple[Component, ComponentVersion]:
    """
    Create a Component and associated ComponentVersion atomically
    """
    with atomic():
        component = create_component(
            learning_package_id, component_type, local_key, created, created_by
        )
        component_version = create_component_version(
            component.pk,
            version_num=1,
            title=title,
            created=created,
            created_by=created_by,
        )
        return (component, component_version)


def get_component(component_pk: int, /) -> Component:
    """
    Get Component by its primary key.

    This is the same as the PublishableEntity's ID primary key.
    """
    return Component.with_publishing_relations.get(pk=component_pk)


def get_component_by_key(
    learning_package_id: int,
    /,
    namespace: str,
    type_name: str,
    local_key: str,
) -> Component:
    """
    Get a Component by its unique (namespace, type, local_key) tuple.
    """
    return Component.with_publishing_relations \
                    .get(
                        learning_package_id=learning_package_id,
                        component_type__namespace=namespace,
                        component_type__name=type_name,
                        local_key=local_key,
                    )


def component_exists_by_key(
    learning_package_id: int,
    /,
    namespace: str,
    type_name: str,
    local_key: str
) -> bool:
    """
    Return True/False for whether a Component exists.

    Note that a Component still exists even if it's been soft-deleted (there's
    no current Draft version for it), or if it's been unpublished.
    """
    try:
        _component = Component.objects.only('pk', 'component_type').get(
            learning_package_id=learning_package_id,
            component_type__namespace=namespace,
            component_type__name=type_name,
            local_key=local_key,
        )
        return True
    except Component.DoesNotExist:
        return False


def get_components(
    learning_package_id: int,
    /,
    draft: bool | None = None,
    published: bool | None = None,
    namespace: str | None = None,
    type_names: list[str] | None = None,
    draft_title: str | None = None,
    published_title: str | None = None,
) -> QuerySet[Component]:
    """
    Fetch a QuerySet of Components for a LearningPackage using various filters.

    This method will pre-load all the relations that we need in order to get
    info from the Component's draft and published versions, since we'll be
    referencing these a lot.
    """
    qset = Component.with_publishing_relations \
                    .filter(learning_package_id=learning_package_id) \
                    .order_by('pk')

    if draft is not None:
        qset = qset.filter(publishable_entity__draft__version__isnull=not draft)
    if published is not None:
        qset = qset.filter(publishable_entity__published__version__isnull=not published)
    if namespace is not None:
        qset = qset.filter(component_type__namespace=namespace)
    if type_names is not None:
        qset = qset.filter(component_type__name__in=type_names)
    if draft_title is not None:
        qset = qset.filter(
            Q(publishable_entity__draft__version__title__icontains=draft_title) |
            Q(local_key__icontains=draft_title)
        )
    if published_title is not None:
        qset = qset.filter(
            Q(publishable_entity__published__version__title__icontains=published_title) |
            Q(local_key__icontains=published_title)
        )

    return qset


def look_up_component_version_content(
    learning_package_key: str,
    component_key: str,
    version_num: int,
    key: Path,
) -> ComponentVersionContent:
    """
    Look up ComponentVersionContent by human readable keys.

    Can raise a django.core.exceptions.ObjectDoesNotExist error if there is no
    matching ComponentVersionContent.
    """
    queries = (
        Q(component_version__component__learning_package__key=learning_package_key)
        & Q(component_version__component__publishable_entity__key=component_key)
        & Q(component_version__publishable_entity_version__version_num=version_num)
        & Q(key=key)
    )
    return ComponentVersionContent.objects \
                                  .select_related(
                                      "content",
                                      "content__media_type",
                                      "component_version",
                                      "component_version__component",
                                      "component_version__component__learning_package",
                                  ).get(queries)


def create_component_version_content(
    component_version_id: int,
    content_id: int,
    /,
    key: str,
    learner_downloadable=False,
) -> ComponentVersionContent:
    """
    Add a Content to the given ComponentVersion
    """
    cvrc, _created = ComponentVersionContent.objects.get_or_create(
        component_version_id=component_version_id,
        content_id=content_id,
        key=key,
        learner_downloadable=learner_downloadable,
    )
    return cvrc
