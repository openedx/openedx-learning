""""
Tagging API

Anyone using the openedx_tagging app should use these APIs instead of creating
or modifying the models directly, since there might be other related model
changes that you may not know about.

No permissions/rules are enforced by these methods -- these must be enforced in the views.

Please look at the models.py file for more information about the kinds of data
are stored in this app.
"""
from typing import List, Type

from django.db.models import QuerySet
from django.utils.translation import gettext_lazy as _

from .models import ObjectTag, Tag, Taxonomy


def create_taxonomy(
    name,
    description=None,
    enabled=True,
    required=False,
    allow_multiple=False,
    allow_free_text=False,
) -> Taxonomy:
    """
    Creates, saves, and returns a new Taxonomy with the given attributes.
    """
    return Taxonomy.objects.create(
        name=name,
        description=description,
        enabled=enabled,
        required=required,
        allow_multiple=allow_multiple,
        allow_free_text=allow_free_text,
    )


def get_taxonomies(enabled=True) -> QuerySet:
    """
    Returns a queryset containing the enabled taxonomies, sorted by name.
    If you want the disabled taxonomies, pass enabled=False.
    If you want all taxonomies (both enabled and disabled), pass enabled=None.
    """
    queryset = Taxonomy.objects.order_by("name", "id")
    if enabled is None:
        return queryset.all()
    return queryset.filter(enabled=enabled)


def get_tags(taxonomy: Taxonomy) -> List[Tag]:
    """
    Returns a list of predefined tags for the given taxonomy.

    Note that if the taxonomy allows free-text tags, then the returned list will be empty.
    """
    return taxonomy.get_tags()


def resync_object_tags(object_tags: QuerySet = None) -> int:
    """
    Reconciles ObjectTag entries with any changes made to their associated taxonomies and tags.

    By default, we iterate over all ObjectTags. Pass a filtered ObjectTags queryset to limit which tags are resynced.
    """
    if not object_tags:
        object_tags = ObjectTag.objects.all()

    num_changed = 0
    for object_tag in object_tags:
        changed = object_tag.resync()
        if changed:
            object_tag.save()
            num_changed += 1
    return num_changed


def get_object_tags(
    taxonomy: Taxonomy, object_id: str, object_type: str, valid_only=True
) -> List[ObjectTag]:
    """
    Returns a list of tags for a given taxonomy + content.

    Pass valid_only=False when displaying tags to content authors, so they can see invalid tags too.
    Invalid tags will likely be hidden from learners.
    """
    tags = ObjectTag.objects.filter(
        taxonomy=taxonomy, object_id=object_id, object_type=object_type
    ).order_by("id")
    return [tag for tag in tags if not valid_only or taxonomy.validate_object_tag(tag)]


def tag_object(
    taxonomy: Taxonomy, tags: List, object_id: str, object_type: str
) -> List[ObjectTag]:
    """
    Replaces the existing ObjectTag entries for the given taxonomy + object_id with the given list of tags.

    If taxonomy.allows_free_text, then the list should be a list of tag values.
    Otherwise, it should be a list of existing Tag IDs.

    Raised ValueError if the proposed tags are invalid for this taxonomy.
    Preserves existing (valid) tags, adds new (valid) tags, and removes omitted (or invalid) tags.
    """

    return taxonomy.tag_object(tags, object_id, object_type)
