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

from django.db import transaction
from django.db.models import F, QuerySet
from django.utils.translation import gettext as _

from .models import ObjectTag, Tag, Taxonomy

# Export this as part of the API
TagDoesNotExist = Tag.DoesNotExist


def create_taxonomy(
    name: str,
    description: str | None = None,
    enabled=True,
    allow_multiple=True,
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
        allow_multiple=allow_multiple,
        allow_free_text=allow_free_text,
    )
    if taxonomy_class:
        taxonomy.taxonomy_class = taxonomy_class
    taxonomy.save()
    return taxonomy.cast()


def get_taxonomy(taxonomy_id: int) -> Taxonomy | None:
    """
    Returns a Taxonomy cast to the appropriate subclass which has the given ID.
    """
    taxonomy = Taxonomy.objects.filter(pk=taxonomy_id).first()
    return taxonomy.cast() if taxonomy else None


def get_taxonomies(enabled=True) -> QuerySet[Taxonomy]:
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


def get_root_tags(taxonomy: Taxonomy) -> list[Tag]:
    """
    Returns a list of the root tags for the given taxonomy.

    Note that if the taxonomy allows free-text tags, then the returned list will be empty.
    """
    return list(taxonomy.cast().get_filtered_tags())


def search_tags(taxonomy: Taxonomy, search_term: str) -> list[Tag]:
    """
    Returns a list of all tags that contains `search_term` of the given taxonomy.

    Note that if the taxonomy allows free-text tags, then the returned list will be empty.
    """
    return list(
        taxonomy.cast().get_filtered_tags(
            search_term=search_term,
            search_in_all=True,
        )
    )


def get_children_tags(
    taxonomy: Taxonomy,
    parent_tag_id: int,
    search_term: str | None = None,
) -> list[Tag]:
    """
    Returns a list of children tags for the given parent tag.

    Note that if the taxonomy allows free-text tags, then the returned list will be empty.
    """
    return list(
        taxonomy.cast().get_filtered_tags(
            parent_tag_id=parent_tag_id,
            search_term=search_term,
        )
    )


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
    object_id: str,
    taxonomy_id: int | None = None,
    object_tag_class: type[ObjectTag] = ObjectTag
) -> QuerySet[ObjectTag]:
    """
    Returns a Queryset of object tags for a given object.

    Pass taxonomy_id to limit the returned object_tags to a specific taxonomy.
    """
    filters = {"taxonomy_id": taxonomy_id} if taxonomy_id else {}
    tags = (
        object_tag_class.objects.filter(object_id=object_id, **filters)
        .select_related("tag", "taxonomy")
        .order_by("id")
    )
    return tags


def delete_object_tags(object_id: str):
    """
    Delete all ObjectTag entries for a given object.
    """
    tags = ObjectTag.objects.filter(object_id=object_id)

    tags.delete()


# TODO: a function called "tag_object" should take "object_id" as its first parameter, not taxonomy
def tag_object(
    taxonomy: Taxonomy,
    tags: list[str],
    object_id: str,
    object_tag_class: type[ObjectTag] = ObjectTag,
) -> None:
    """
    Replaces the existing ObjectTag entries for the given taxonomy + object_id
    with the given list of tags.

    tags: A list of the values of the tags from this taxonomy to apply.

    object_tag_class: Optional. Use a proxy subclass of ObjectTag for additional
        validation. (e.g. only allow tagging certain types of objects.)

    Raised Tag.DoesNotExist if the proposed tags are invalid for this taxonomy.
    Preserves existing (valid) tags, adds new (valid) tags, and removes omitted
    (or invalid) tags.
    """

    def _check_new_tag_count(new_tag_count: int) -> None:
        """
        Checks if the new count of tags for the object is equal or less than 100
        """
        # Exclude self.id to avoid counting the tags that are going to be updated
        current_count = ObjectTag.objects.filter(object_id=object_id).exclude(taxonomy_id=taxonomy.id).count()

        if current_count + new_tag_count > 100:
            raise ValueError(
                _("Cannot add more than 100 tags to ({object_id}).").format(object_id=object_id)
            )

    if not isinstance(tags, list):
        raise ValueError(_("Tags must be a list, not {type}.").format(type=type(tags).__name__))

    ObjectTagClass = object_tag_class
    taxonomy = taxonomy.cast()  # Make sure we're using the right subclass. This is a no-op if we are already.
    tags = list(dict.fromkeys(tags))  # Remove duplicates preserving order

    _check_new_tag_count(len(tags))

    if not taxonomy.allow_multiple and len(tags) > 1:
        raise ValueError(_("Taxonomy ({name}) only allows one tag per object.").format(name=taxonomy.name))

    current_tags = list(
        ObjectTagClass.objects.filter(taxonomy=taxonomy, object_id=object_id)
    )
    updated_tags = []
    if taxonomy.allow_free_text:
        for tag_value in tags:
            object_tag_index = next((i for (i, t) in enumerate(current_tags) if t.value == tag_value), -1)
            if object_tag_index >= 0:
                # This tag is already applied.
                object_tag = current_tags.pop(object_tag_index)
            else:
                object_tag = ObjectTagClass(taxonomy=taxonomy, object_id=object_id, _value=tag_value)
                updated_tags.append(object_tag)
    else:
        # Handle closed taxonomies:
        for tag_value in tags:
            tag = taxonomy.tag_for_value(tag_value)  # Will raise Tag.DoesNotExist if the value is invalid.
            object_tag_index = next((i for (i, t) in enumerate(current_tags) if t.tag_id == tag.id), -1)
            if object_tag_index >= 0:
                # This tag is already applied.
                object_tag = current_tags.pop(object_tag_index)
                if object_tag._value != tag.value:  # pylint: disable=protected-access
                    # The ObjectTag's cached '_value' is out of sync with the Tag, so update it:
                    object_tag._value = tag.value  # pylint: disable=protected-access
                    updated_tags.append(object_tag)
            else:
                # We are newly applying this tag:
                object_tag = ObjectTagClass(taxonomy=taxonomy, object_id=object_id, tag=tag)
                updated_tags.append(object_tag)

    # Save all updated tags at once to avoid partial updates
    with transaction.atomic():
        # delete any omitted existing tags. We do this first to reduce chances of UNIQUE constraint edge cases
        for old_tag in current_tags:
            old_tag.delete()
        # add the new tags:
        for object_tag in updated_tags:
            object_tag.full_clean()  # Run validation
            object_tag.save()


# TODO: return tags from closed taxonomies as well as the count of how many times each is used.
def autocomplete_tags(
    taxonomy: Taxonomy,
    search: str,
    object_id: str | None = None,
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
    # Fetch tags that the object already has to exclude them from the result
    excluded_tags: list[str] = []
    if object_id:
        excluded_tags = list(
            taxonomy.objecttag_set.filter(object_id=object_id).values_list(
                "_value", flat=True
            )
        )
    return (
        # Fetch object tags from this taxonomy whose value contains the search
        taxonomy.objecttag_set.filter(_value__icontains=search)
        # omit any tags whose values match the tags on the given object
        .exclude(_value__in=excluded_tags)
        # alphabetical ordering
        .order_by("_value")
        # Alias the `_value` field to `value` to make it nicer for users
        .annotate(value=F("_value"))
        # obtain tag values
        .values("value", "tag_id")
        # remove repeats
        .distinct()
    )


def add_tag_to_taxonomy(
    taxonomy: Taxonomy,
    tag: str,
    parent_tag_value: str | None = None,
    external_id: str | None = None
) -> Tag:
    """
    Adds a new Tag to provided Taxonomy. If a Tag already exists in the
    Taxonomy, an exception is raised, otherwise the newly created
    Tag is returned
    """
    taxonomy = taxonomy.cast()
    new_tag = taxonomy.add_tag(tag, parent_tag_value, external_id)

    # Resync all related ObjectTags after creating new Tag to
    # to ensure any existing ObjectTags with the same value will
    # be linked to the new Tag
    object_tags = taxonomy.objecttag_set.all()
    resync_object_tags(object_tags)

    return new_tag


def update_tag_in_taxonomy(taxonomy: Taxonomy, tag: str, new_value: str):
    """
    Update a Tag that belongs to a Taxonomy. The related ObjectTags are
    updated accordingly.

    Currently only supports updating the Tag value.
    """
    taxonomy = taxonomy.cast()
    updated_tag = taxonomy.update_tag(tag, new_value)

    # Resync all related ObjectTags to update to the new Tag value
    object_tags = taxonomy.objecttag_set.all()
    resync_object_tags(object_tags)

    return updated_tag


def delete_tags_from_taxonomy(
    taxonomy: Taxonomy,
    tags: list[str],
    with_subtags: bool
):
    """
    Delete Tags that belong to a Taxonomy. If any of the Tags have children and
    the `with_subtags` is not set to `True` it will fail, otherwise
    the sub-tags will be deleted as well.
    """
    taxonomy = taxonomy.cast()
    taxonomy.delete_tags(tags, with_subtags)
