""""
Tagging API

Anyone using the openedx_tagging app should use these APIs instead of creating
or modifying the models directly, since there might be other related model
changes that you may not know about.

No permissions/rules are enforced by these methods -- these must be enforced in the views.

Please look at the models.py file for more information about the kinds of data
are stored in this app.
"""
import csv
import json
from enum import Enum
from io import StringIO, BytesIO, TextIOWrapper
from typing import List, Type

from django.db import transaction
from django.db.models import QuerySet
from django.core.exceptions import ObjectDoesNotExist
from django.utils.translation import gettext_lazy as _

from .models import ObjectTag, Tag, Taxonomy

csv_fields = ['id', 'name', 'parent_id', 'parent_name']

class TaxonomyDataFormat(Enum):
    """
    Formats used to export and import Taxonomies
    """
    CSV = 'CSV'
    JSON = 'JSON'


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


def import_tags(taxonomy: Taxonomy, tags: BytesIO, format: TaxonomyDataFormat, replace=False):
    """
    Imports the hierarchical tags from the given blob into the Taxonomy.
    The blob can be CSV or JSON format.

    If replace, then removes any existing child Tags linked to this taxonomy before performing the import.
    """

    # Validations
    if taxonomy.allow_free_text:
        raise ValueError(
            _(
                f"Invalid taxonomy ({taxonomy.id}): You cannot import into a free-form taxonomy."
            )
        )

    # Read file and build the tags data to be uploaded
    try:
        tags_data = {}
        tags.seek(0)
        if format == TaxonomyDataFormat.CSV:        
            text_tags = TextIOWrapper(tags, encoding='utf-8')
            csv_reader = csv.DictReader(text_tags)
            header_fields = csv_reader.fieldnames
            if csv_fields != header_fields:
                raise ValueError(
                    _(
                        f"Invalid CSV header: {header_fields}. Must be: {csv_fields}."
                    )
                )
            tags_data = list(csv_reader)
        elif format == TaxonomyDataFormat.JSON:
            tags_data = json.load(tags)
            if 'tags' not in tags_data:
                raise ValueError(
                    _(
                        f"Invalid JSON format: Missing 'tags' list."
                    )
                )
            tags_data = tags_data.get('tags')
        else:
            raise ValueError(
                _(
                    f"Invalid format: {format}"
                )
            )
    except ValueError as e:
        raise e
    finally:
        tags.close()


    updated_tags = []

    def create_update_tag(tag):
        """
        Function to create a new Tag or update an existing one.

        This function keeps a creation/update history with `updated_tags`,
        a same tag can't be created/updated in a same taxonomy import.
        Also, recursively, creates the parents of the `tag`.

        Returns the created/updated Tag.
        Raise KeyError if 'id' or 'name' don't exist on `tag`
        """

        tag_id = tag['id']
        tag_name = tag['name']
        tag_parent_id = tag.get('parent_id')
        tag_parent_name = tag.get('parent_name')

        # Check if the tag has not already been created or updated
        if tag_id not in updated_tags:
            try:
                # Update tag
                tag_instance = taxonomy.tag_set.get(external_id=tag_id)
                tag_instance.value = tag_name

                if tag_instance.parent and (not tag_parent_id or not tag_parent_name):
                    # if there is no parent in the data import
                    tag_instance.parent = None
                updated_tags.append(tag_id)
            except Tag.DoesNotExist:
                # Create tag
                tag_instance = Tag(
                    taxonomy=taxonomy,
                    value=tag_name,
                    external_id=tag_id,    
                )
                updated_tags.append(tag_id)

            if tag_parent_id and tag_parent_name:
                # Parent creation/update
                parent = create_update_tag({'id': tag_parent_id, 'name': tag_parent_name})
                tag_instance.parent = parent

            tag_instance.save()
            return tag_instance
        else:
            # Returns the created/updated tag from history
            return taxonomy.tag_set.get(external_id=tag_id)

    # Create and update tags
    with transaction.atomic():
        for tag in tags_data:
            try:
                create_update_tag(tag)
            except KeyError as e:
                key = e.args[0]
                raise ValueError(
                    _(
                        f"Invalid JSON format: Missing '{key}' on a tag ({tag})"
                    )
                )
            
        # If replace, delete all not updated tags (Not present in the file)
        if replace:
            taxonomy.tag_set.exclude(external_id__in=updated_tags).delete()

        resync_object_tags(ObjectTag.objects.filter(taxonomy=taxonomy))

def export_tags(taxonomy: Taxonomy, format: TaxonomyDataFormat) -> str: 
    """
    Creates a blob string describing all the tags in the given Taxonomy.
    The output format can be CSV or JSON.
    """

    # Validations
    if taxonomy.allow_free_text:
        raise ValueError(
            _(
                f"Invalid taxonomy ({taxonomy.id}): You cannot import into a free-form taxonomy."
            )
        )
    if format not in TaxonomyDataFormat.__members__.values():
        raise ValueError(
            _(
                f"Invalid format: {format}"
            )
        )

    # Build tags in a dictionary format
    tags = get_tags(taxonomy)
    result = []
    for tag in tags:
        result_tag = {
            'id': tag.external_id or tag.id,
            'name': tag.value,
        }
        if tag.parent:
            result_tag['parent_id'] = tag.parent.external_id or tag.parent.id
            result_tag['parent_name'] = tag.parent.value
        result.append(result_tag)

    # Convert dictonary into the output format
    if format == TaxonomyDataFormat.CSV:
        with StringIO() as csv_buffer:
            csv_writer = csv.DictWriter(csv_buffer, fieldnames=csv_fields)
            csv_writer.writeheader()
        
            for tag in result:
                csv_writer.writerow(tag)
        
            csv_string = csv_buffer.getvalue()
            return csv_string
    else:
        # TaxonomyDataFormat.JSON
        # Verification is made at the beginning before bringing and assembling tags data.
        json_result = {
            'name': taxonomy.name,
            'description': taxonomy.description,
            'tags': result
        }
        return json.dumps(json_result)
