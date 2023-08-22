""""
Tagging API

Anyone using the openedx_tagging app should use these APIs instead of creating
or modifying the models directly, since there might be other related model
changes that you may not know about.

No permissions/rules are enforced by these methods -- these must be enforced in the views.

Please look at the models.py file for more information about the kinds of data
are stored in this app.
"""
from __future__ import annotations
from typing import Iterator

from django.db.models import QuerySet
from django.utils.translation import gettext_lazy as _

from .models import ObjectTag, Tag, Taxonomy


def create_taxonomy(
    name: str,
    description: str | None = None,
    enabled=True,
    required=False,
    allow_multiple=False,
    allow_free_text=False,
    taxonomy_class: type[Taxonomy] | None = None,
) -> Taxonomy:
    """
    Creates, saves, and returns a new Taxonomy with the given attributes.
    """
    taxonomy = Taxonomy(
        name=name,
        description=description or "",
        enabled=enabled,
        required=required,
        allow_multiple=allow_multiple,
        allow_free_text=allow_free_text,
    )
    if taxonomy_class:
        taxonomy.taxonomy_class = taxonomy_class
    taxonomy.save()
    return taxonomy.cast()


def get_taxonomy(id: int) -> Taxonomy | None:
    """
    Returns a Taxonomy cast to the appropriate subclass which has the given ID.
    """
    taxonomy = Taxonomy.objects.filter(id=id).first()
    return taxonomy.cast() if taxonomy else None


def get_taxonomies(enabled=True) -> QuerySet:
    """
    Returns a queryset containing the enabled taxonomies, sorted by name.

    We return a QuerySet here for ease of use with Django Rest Framework and other query-based use cases.
    So be sure to use `Taxonomy.cast()` to cast these instances to the appropriate subclass before use.

    If you want the disabled taxonomies, pass enabled=False.
    If you want all taxonomies (both enabled and disabled), pass enabled=None.
    """
    queryset = Taxonomy.objects.order_by("name", "id")
    if enabled is None:
        return queryset.all()
    return queryset.filter(enabled=enabled)


def get_tags(taxonomy: Taxonomy) -> list[Tag]:
    """
    Returns a list of predefined tags for the given taxonomy.

    Note that if the taxonomy allows free-text tags, then the returned list will be empty.
    """
    return taxonomy.cast().get_tags()


def resync_object_tags(object_tags: QuerySet | None = None) -> int:
    """
    Reconciles ObjectTag entries with any changes made to their associated taxonomies and tags.

    By default, we iterate over all ObjectTags. Pass a filtered ObjectTags queryset to limit which tags are resynced.
    """
    if not object_tags:
        object_tags = ObjectTag.objects.select_related("tag", "taxonomy")

    num_changed = 0
    for object_tag in object_tags:
        changed = object_tag.resync()
        if changed:
            object_tag.save()
            num_changed += 1
    return num_changed


def get_object_tags(
    object_id: str, taxonomy: Taxonomy | None = None, valid_only=True
) -> Iterator[ObjectTag]:
    """
    Generates a list of object tags for a given object.

    Pass taxonomy to limit the returned object_tags to a specific taxonomy.

    Pass valid_only=False when displaying tags to content authors, so they can see invalid tags too.
    Invalid tags will (probably) be hidden from learners.
    """
    ObjectTagClass = ObjectTag
    if taxonomy:
        ObjectTagClass = taxonomy.object_tag_class
    tags = (
        ObjectTagClass.objects.filter(
            object_id=object_id,
        )
        .select_related("tag", "taxonomy")
        .order_by("id")
    )
    if taxonomy:
        tags = tags.filter(taxonomy=taxonomy)

    for object_tag in tags:
        if not valid_only or object_tag.is_valid():
            yield object_tag


def tag_object(
    taxonomy: Taxonomy,
    tags: list[str],
    object_id: str,
) -> list[ObjectTag]:
    """
    Replaces the existing ObjectTag entries for the given taxonomy + object_id with the given list of tags.

    If taxonomy.allows_free_text, then the list should be a list of tag values.
    Otherwise, it should be a list of existing Tag IDs.

    Raised ValueError if the proposed tags are invalid for this taxonomy.
    Preserves existing (valid) tags, adds new (valid) tags, and removes omitted (or invalid) tags.
    """
    return taxonomy.cast().tag_object(tags, object_id)


def autocomplete_tags(
    taxonomy: Taxonomy,
    search: str,
    object_id: str | None= None,
    object_tags_only=True,
) -> QuerySet:
    """
    Provides auto-complete suggestions by matching the `search` string against existing
    ObjectTags linked to the given taxonomy. A case-insensitive search is used in order
    to return the highest number of relevant tags.

    If `object_id` is provided, then object tag values already linked to this object
    are omitted from the returned suggestions. (ObjectTag values must be unique for a
    given object + taxonomy, and so omitting these suggestions helps users avoid
    duplication errors.).

    Returns a QuerySet of dictionaries containing distinct `value` (string) and
    `tag` (numeric ID) values, sorted alphabetically by `value`.
    The `value` is what should be shown as a suggestion to users,
    and if it's a free-text taxonomy, `tag` will be `None`:  we include the `tag` ID
    in anticipation of the second use case listed below.

    Use cases:
    * This method is useful for reducing tag variation in free-text taxonomies by showing
      users tags that are similar to what they're typing. E.g., if the `search` string "dn"
      shows that other objects have been tagged with "DNA", "DNA electrophoresis", and "DNA fingerprinting",
      this encourages users to use those existing tags if relevant, instead of creating new ones that
      look similar (e.g. "dna finger-printing").
    * It could also be used to assist tagging for closed taxonomies with a list of possible tags which is too
      large to return all at once, e.g. a user model taxonomy that dynamically creates tags on request for any
      registered user in the database. (Note that this is not implemented yet, but may be as part of a future change.)
    """
    if not object_tags_only:
        raise NotImplementedError(
            _(
                "Using this would return a query set of tags instead of object tags."
                "For now we recommend fetching all of the taxonomy's tags "
                "using get_tags() and filtering them on the frontend."
            )
        )
    return taxonomy.cast().autocomplete_tags(search, object_id)
