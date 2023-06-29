""""
Tagging API

Anyone using the openedx_tagging app should use these APIs instead of creating
or modifying the models directly, since there might be other related model
changes that you may not know about.

No permissions/rules are enforced by these methods -- these must be enforced in the views.

Please look at the models.py file for more information about the kinds of data
are stored in this app.
"""
from typing import Iterator, List, Type, Union

from django.db.models import QuerySet
from django.utils.translation import gettext_lazy as _

from .models import ObjectTag, Tag, Taxonomy, TagResult

def create_taxonomy(
    name: str,
    description: str = None,
    enabled=True,
    required=False,
    allow_multiple=False,
    allow_free_text=False,
    taxonomy_class: Type = None,
) -> Taxonomy:
    """
    Creates, saves, and returns a new Taxonomy with the given attributes.
    """
    taxonomy = Taxonomy(
        name=name,
        description=description,
        enabled=enabled,
        required=required,
        allow_multiple=allow_multiple,
        allow_free_text=allow_free_text,
    )
    if taxonomy_class:
        taxonomy.taxonomy_class = taxonomy_class
    taxonomy.save()
    return taxonomy.cast()


def get_taxonomy(id: int) -> Union[Taxonomy, None]:
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


def get_tags(taxonomy: Taxonomy) -> List[Tag]:
    """
    Returns a list of predefined tags for the given taxonomy.

    Note that if the taxonomy allows free-text tags, then the returned list will be empty.
    """
    return taxonomy.cast().get_tags()


def resync_object_tags(object_tags: QuerySet = None) -> int:
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
    object_id: str, taxonomy: Taxonomy = None, valid_only=True
) -> Iterator[ObjectTag]:
    """
    Generates a list of object tags for a given object.

    Pass taxonomy to limit the returned object_tags to a specific taxonomy.

    Pass valid_only=False when displaying tags to content authors, so they can see invalid tags too.
    Invalid tags will (probably) be hidden from learners.
    """
    ObjectTagClass = taxonomy.object_tag_class if taxonomy else ObjectTag
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
    tags: List,
    object_id: str,
) -> List[ObjectTag]:
    """
    Replaces the existing ObjectTag entries for the given taxonomy + object_id with the given list of tags.

    If taxonomy.allows_free_text, then the list should be a list of tag values.
    Otherwise, it should be a list of existing Tag IDs.

    Raised ValueError if the proposed tags are invalid for this taxonomy.
    Preserves existing (valid) tags, adds new (valid) tags, and removes omitted (or invalid) tags.
    """
    return taxonomy.cast().tag_object(tags, object_id)


def autocomplete_tags(taxonomy: Taxonomy, prefix: str, object_id: str= None, count=10) -> List[TagResult]:
    """
    Returns the first `count` tag values in the given Taxonomy with names 
    that begin with the given prefix string. The result is returned in alphabetical

    Closed taxonomies return tag values that exist in the taxonomy. Also excludes all Tags that the
    `object_id` already has. 

    Free-text taxonomies return only tag values that are currently in use on (another) object. Also excludes
    the tags used by `object_id`.
    """
    result = []

    # Fetch tags that the object already has to exclude them from the result
    excluded_tags = ObjectTag.objects.filter(object_id=object_id, taxonomy=taxonomy)
    if taxonomy.allow_free_text:
        # Free-text taxonomy

        # Obtain the value of the excluded tags
        excluded_tags = excluded_tags.values_list('_value', flat=True)
        result = (
            # Fetch object tags from this taxonomy whose value starts with the given prefix
            ObjectTag.objects.filter(taxonomy=taxonomy, _value__istartswith=prefix)
            # omit any free-text tags whose values match the tags on the given object
            .exclude(_value__in=excluded_tags)
            # alphabetical ordering
            .order_by('_value')
            # obtain the values of the tags
            .values_list('_value', flat=True)
            # remove repeats
            .distinct()
            # get only first `count` values
            [:count]
        )
        # Build tag results
        result = [TagResult(id=None, value=value) for value in result]
    else:
        # Closed taxonomy
        
        # Obtain the id of the excluded tags
        excluded_tags = excluded_tags.filter(tag__isnull=False).values_list('tag__id', flat=True)
        result = (
            # Fetch tags from this taxonomy whose value starts with the given prefix
            Tag.objects.filter(taxonomy=taxonomy, value__istartswith=prefix)
            # omit any tags applied to the given object
            .exclude(id__in=excluded_tags)
            # alphabetical ordering
            .order_by('value')
            # obtain only id and values of the tags
            .values('id', 'value')
            # get only first `count` values
            [:count]
        )

        # Build tag results
        result = [TagResult(id=item['id'], value=item['value']) for item in result]
    return result
