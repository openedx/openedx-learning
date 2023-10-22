"""
Tagging app base data models
"""
from __future__ import annotations

import logging
from typing import List

from django.core.exceptions import ValidationError
from django.db import models
from django.utils.module_loading import import_string
from django.utils.translation import gettext_lazy as _
from typing_extensions import Self  # Until we upgrade to python 3.11

from openedx_learning.lib.fields import MultiCollationTextField, case_insensitive_char_field, case_sensitive_char_field

log = logging.getLogger(__name__)


# Maximum depth allowed for a hierarchical taxonomy's tree of tags.
TAXONOMY_MAX_DEPTH = 3

# Ancestry of a given tag; the Tag.value fields of a given tag and its parents, starting from the root.
# Will contain 0...TAXONOMY_MAX_DEPTH elements.
Lineage = List[str]


class Tag(models.Model):
    """
    Represents a single value in a list or tree of values which can be applied to a particular Open edX object.

    Open edX tags are "name:value" pairs which can be applied to objects like content libraries, units, or people.
    Tag.taxonomy.name provides the "name" and the Tag.value provides the "value".
    (And an ObjectTag links a Tag with an object.)
    """

    id = models.BigAutoField(primary_key=True)
    taxonomy = models.ForeignKey(
        "Taxonomy",
        null=True,
        default=None,
        on_delete=models.CASCADE,
        help_text=_("Namespace and rules for using a given set of tags."),
    )
    parent = models.ForeignKey(
        "self",
        null=True,
        default=None,
        on_delete=models.CASCADE,
        related_name="children",
        help_text=_(
            "Tag that lives one level up from the current tag, forming a hierarchy."
        ),
    )
    value = case_insensitive_char_field(
        max_length=500,
        help_text=_(
            "Content of a given tag, occupying the 'value' part of the key:value pair."
        ),
    )
    external_id = case_insensitive_char_field(
        max_length=255,
        null=True,  # To allow multiple values with our UNIQUE constraint, we need to use NULL values here instead of ""
        blank=True,
        help_text=_(
            "Used to link an Open edX Tag with a tag in an externally-defined taxonomy."
        ),
    )

    class Meta:
        indexes = [
            models.Index(fields=["taxonomy", "value"]),
            models.Index(fields=["taxonomy", "external_id"]),
        ]
        unique_together = [
            ["taxonomy", "external_id"],
            ["taxonomy", "value"],
        ]

    def __repr__(self):
        """
        Developer-facing representation of a Tag.
        """
        return str(self)

    def __str__(self):
        """
        User-facing string representation of a Tag.
        """
        return f"<{self.__class__.__name__}> ({self.id}) {self.value}"

    def get_lineage(self) -> Lineage:
        """
        Queries and returns the lineage of the current tag as a list of Tag.value strings.

        The root Tag.value is first, followed by its child.value, and on down to self.value.

        Performance note: may perform as many as TAXONOMY_MAX_DEPTH select queries.
        """
        lineage: Lineage = []
        tag: Tag | None = self
        depth = TAXONOMY_MAX_DEPTH
        while tag and depth > 0:
            lineage.insert(0, tag.value)
            tag = tag.parent
            depth -= 1
        return lineage


class Taxonomy(models.Model):
    """
    Represents a namespace and rules for a group of tags.
    """

    id = models.BigAutoField(primary_key=True)
    name = case_insensitive_char_field(
        null=False,
        max_length=255,
        db_index=True,
        help_text=_(
            "User-facing label used when applying tags from this taxonomy to Open edX objects."
        ),
    )
    description = MultiCollationTextField(
        blank=True,
        help_text=_(
            "Provides extra information for the user when applying tags from this taxonomy to an object."
        ),
    )
    enabled = models.BooleanField(
        default=True,
        help_text=_("Only enabled taxonomies will be shown to authors."),
    )
    allow_multiple = models.BooleanField(
        default=True,
        help_text=_(
            "Indicates that multiple tags from this taxonomy may be added to an object."
        ),
    )
    allow_free_text = models.BooleanField(
        default=False,
        help_text=_(
            "Indicates that tags in this taxonomy need not be predefined; authors may enter their own tag values."
        ),
    )
    visible_to_authors = models.BooleanField(
        default=True,
        editable=False,
        help_text=_(
            "Indicates whether this taxonomy should be visible to object authors."
        ),
    )
    _taxonomy_class = models.CharField(
        null=True,
        max_length=255,
        help_text=_(
            "Taxonomy subclass used to instantiate this instance; must be a fully-qualified module and class name."
            " If the module/class cannot be imported, an error is logged and the base Taxonomy class is used instead."
        ),
    )

    class Meta:
        verbose_name_plural = "Taxonomies"

    def __repr__(self):
        """
        Developer-facing representation of a Taxonomy.
        """
        return str(self)

    def __str__(self):
        """
        User-facing string representation of a Taxonomy.
        """
        try:
            if self._taxonomy_class:
                return f"<{self.taxonomy_class.__name__}> ({self.id}) {self.name}"
        except ImportError:
            # Log error and continue
            log.exception(
                f"Unable to import taxonomy_class for {self.id}: {self._taxonomy_class}"
            )
        return f"<{self.__class__.__name__}> ({self.id}) {self.name}"

    @property
    def taxonomy_class(self) -> type[Taxonomy] | None:
        """
        Returns the Taxonomy subclass associated with this instance, or None if none supplied.

        May raise ImportError if a custom taxonomy_class cannot be imported.
        """
        if self._taxonomy_class:
            return import_string(self._taxonomy_class)
        return None

    @taxonomy_class.setter
    def taxonomy_class(self, taxonomy_class: type[Taxonomy] | None):
        """
        Assigns the given taxonomy_class's module path.class to the field.

        Must be a subclass of Taxonomy, or raises a ValueError.
        """
        if taxonomy_class:
            if not issubclass(taxonomy_class, Taxonomy):
                raise ValueError(
                    f"Unable to assign taxonomy_class for {self}: {taxonomy_class} must be a subclass of Taxonomy"
                )

            # ref: https://stackoverflow.com/a/2020083
            self._taxonomy_class = ".".join(
                [taxonomy_class.__module__, taxonomy_class.__qualname__]
            )
        else:
            self._taxonomy_class = None

    @property
    def system_defined(self) -> bool:
        """
        Indicates that tags and metadata for this taxonomy are maintained by the system;
        taxonomy admins will not be permitted to modify them.
        """
        return False

    def cast(self):
        """
        Returns the current Taxonomy instance cast into its taxonomy_class.

        If no taxonomy_class is set, or if we're unable to import it, then just returns self.
        """
        try:
            TaxonomyClass = self.taxonomy_class
            if TaxonomyClass and not isinstance(self, TaxonomyClass):
                return TaxonomyClass().copy(self)
        except ImportError:
            # Log error and continue
            log.exception(
                f"Unable to import taxonomy_class for {self}: {self._taxonomy_class}"
            )

        return self

    def check_casted(self):
        """
        Double-check that this taxonomy has been cast() to a subclass if needed.
        """
        if self.cast() is not self:
            raise TypeError("Taxonomy was used incorrectly - without .cast()")

    def copy(self, taxonomy: Taxonomy) -> Taxonomy:
        """
        Copy the fields from the given Taxonomy into the current instance.
        """
        self.id = taxonomy.id
        self.name = taxonomy.name
        self.description = taxonomy.description
        self.enabled = taxonomy.enabled
        self.allow_multiple = taxonomy.allow_multiple
        self.allow_free_text = taxonomy.allow_free_text
        self.visible_to_authors = taxonomy.visible_to_authors
        self._taxonomy_class = taxonomy._taxonomy_class  # pylint: disable=protected-access
        return self

    def get_tags(
        self,
        tag_set: models.QuerySet[Tag] | None = None,
    ) -> list[Tag]:
        """
        Returns a list of all Tags in the current taxonomy, from the root(s)
        down to TAXONOMY_MAX_DEPTH tags, in tree order.

        Use `tag_set` to do an initial filtering of the tags.

        Annotates each returned Tag with its ``depth`` in the tree (starting at
        0).

        Performance note: may perform as many as TAXONOMY_MAX_DEPTH select
        queries.
        """
        tags: list[Tag] = []
        if self.allow_free_text:
            return tags

        if tag_set is None:
            tag_set = self.tag_set.all()

        parents = None

        for depth in range(TAXONOMY_MAX_DEPTH):
            filtered_tags = tag_set.prefetch_related("parent")
            if parents is None:
                filtered_tags = filtered_tags.filter(parent=None)
            else:
                filtered_tags = filtered_tags.filter(parent__in=parents)
            next_parents = list(
                filtered_tags.annotate(
                    annotated_field=models.Value(
                        depth, output_field=models.IntegerField()
                    )
                )
                .order_by("parent__value", "value", "id")
                .all()
            )
            tags.extend(next_parents)
            parents = next_parents
            if not parents:
                break
        return tags

    def get_filtered_tags(
        self,
        tag_set: models.QuerySet[Tag] | None = None,
        parent_tag_id: int | None = None,
        search_term: str | None = None,
        search_in_all: bool = False,
    ) -> models.QuerySet[Tag]:
        """
        Returns a filtered QuerySet of tags.
        By default returns the root tags of the given taxonomy

        Use `parent_tag_id` to return the children of a tag.

        Use `search_term` to filter the results by values that contains `search_term`.

        Set `search_in_all` to True to make the search in all tags on the given taxonomy.

        Note: This is mostly an 'internal' API and generally code outside of openedx_tagging
        should use the APIs in openedx_tagging.api which in turn use this.
        """
        if tag_set is None:
            tag_set = self.tag_set.all()

        if self.allow_free_text:
            return tag_set.none()

        if not search_in_all:
            # If not search in all taxonomy, then apply parent filter.
            tag_set = tag_set.filter(parent=parent_tag_id)

        if search_term:
            # Apply search filter
            tag_set = tag_set.filter(value__icontains=search_term)

        return tag_set.order_by("value", "id")

    def add_tag(
        self,
        tag_value: str,
        parent_tag_value: str | None = None,
        external_id: str | None = None
    ) -> Tag:
        """
        Add new Tag to Taxonomy. If an existing Tag with the `tag_value` already
        exists in the Taxonomy, an exception is raised, otherwise the newly
        created Tag is returned
        """
        self.check_casted()

        if self.allow_free_text:
            raise ValueError(
                "add_tag() doesn't work for free text taxonomies. They don't use Tag instances."
            )

        if self.system_defined:
            raise ValueError(
                "add_tag() doesn't work for system defined taxonomies. They cannot be modified."
            )

        if self.tag_set.filter(value__iexact=tag_value).exists():
            raise ValueError(f"Tag with value '{tag_value}' already exists for taxonomy.")

        parent = None
        if parent_tag_value:
            # Get parent tag from taxonomy, raises Tag.DoesNotExist if doesn't
            # belong to taxonomy
            parent = self.tag_set.get(value__iexact=parent_tag_value)

        tag = Tag.objects.create(
            taxonomy=self, value=tag_value, parent=parent, external_id=external_id
        )

        return tag

    def update_tag(self, tag: str, new_value: str) -> Tag:
        """
        Update an existing Tag in Taxonomy and return it. Currently only
        supports updating the Tag's value.
        """
        self.check_casted()

        if self.allow_free_text:
            raise ValueError(
                "update_tag() doesn't work for free text taxonomies. They don't use Tag instances."
            )

        if self.system_defined:
            raise ValueError(
                "update_tag() doesn't work for system defined taxonomies. They cannot be modified."
            )

        # Update Tag instance with new value, raises Tag.DoesNotExist if
        # tag doesn't belong to taxonomy
        tag_to_update = self.tag_set.get(value__iexact=tag)
        tag_to_update.value = new_value
        tag_to_update.save()
        return tag_to_update

    def delete_tags(self, tags: List[str], with_subtags: bool = False):
        """
        Delete the Taxonomy Tags provided. If any of them have children and
        the `with_subtags` is not set to `True` it will fail, otherwise
        the sub-tags will be deleted as well.
        """
        self.check_casted()

        if self.allow_free_text:
            raise ValueError(
                "delete_tags() doesn't work for free text taxonomies. They don't use Tag instances."
            )

        if self.system_defined:
            raise ValueError(
                "delete_tags() doesn't work for system defined taxonomies. They cannot be modified."
            )

        tags_to_delete = self.tag_set.filter(value__in=tags)

        if tags_to_delete.count() != len(tags):
            # If they do not match that means there is one or more Tag ID(s)
            # provided that do not belong to this Taxonomy
            raise ValueError("Invalid tag id provided or tag id does not belong to taxonomy")

        # Check if any Tag contains subtags (children)
        contains_children = tags_to_delete.filter(children__isnull=False).distinct().exists()

        if contains_children and not with_subtags:
            raise ValueError(
                "Tag(s) contain children, `with_subtags` must be `True` for "
                "all Tags and their subtags (children) to be deleted."
            )

        # Delete the Tags with their subtags if any
        tags_to_delete.delete()

    def validate_value(self, value: str) -> bool:
        """
        Check if 'value' is part of this Taxonomy.
        A 'Tag' object may not exist for the value (e.g. if this is a free text
        taxonomy, then any value is allowed but no Tags are created; if this is
        a user taxonomy, Tag entries may only get created as needed.), but if
        this returns True then the value conceptually exists in this taxonomy
        and can be used to tag objects.
        """
        self.check_casted()
        if self.allow_free_text:
            return value != "" and isinstance(value, str)
        return self.tag_set.filter(value__iexact=value).exists()

    def tag_for_value(self, value: str) -> Tag:
        """
        Get the Tag object for the given value.
        Some Taxonomies may auto-create the Tag at this point, e.g. a User
        Taxonomy will create User Tags "just in time".

        Will raise Tag.DoesNotExist if the value is not valid for this taxonomy.
        """
        self.check_casted()
        if self.allow_free_text:
            raise ValueError("tag_for_value() doesn't work for free text taxonomies. They don't use Tag instances.")
        return self.tag_set.get(value__iexact=value)

    def validate_external_id(self, external_id: str) -> bool:
        """
        Check if 'external_id' is part of this Taxonomy.
        """
        self.check_casted()
        if self.allow_free_text:
            return False  # Free text taxonomies don't use 'external_id' on their tags
        return self.tag_set.filter(external_id__iexact=external_id).exists()

    def tag_for_external_id(self, external_id: str) -> Tag:
        """
        Get the Tag object for the given external_id.
        Some Taxonomies may auto-create the Tag at this point, e.g. a User
        Taxonomy will create User Tags "just in time".

        Will raise Tag.DoesNotExist if the tag is not valid for this taxonomy.
        """
        self.check_casted()
        if self.allow_free_text:
            raise ValueError("tag_for_external_id() doesn't work for free text taxonomies.")
        return self.tag_set.get(external_id__iexact=external_id)


class ObjectTag(models.Model):
    """
    Represents the association between a tag and an Open edX object.

    Tagging content in Open edX involves linking the object to a particular name:value "tag", where the "name" is the
    tag's label, and the value is the content of the tag itself.

    Tagging objects can be time-consuming for users, and so we guard against the deletion of Taxonomies and Tags by
    providing fields to cache the name:value stored for an object.

    However, sometimes Taxonomy names or Tag values change (e.g if there's a typo, or a policy change about how a label
    is used), and so we still store a link to the original Taxonomy and Tag, so that these changes will take precedence
    over the original name:value used.

    Also, if an ObjectTag is associated with free-text Taxonomy, then the tag's value won't be stored as a standalone
    Tag in the database -- it'll be stored here.
    """

    id = models.BigAutoField(primary_key=True)
    object_id = case_sensitive_char_field(
        max_length=255,
        db_index=True,
        editable=False,
        help_text=_("Identifier for the object being tagged"),
    )
    taxonomy = models.ForeignKey(
        Taxonomy,
        null=True,
        default=None,
        on_delete=models.SET_NULL,
        help_text=_(
            "Taxonomy that this object tag belongs to. "
            "Used for validating the tag and provides the tag's 'name' if set."
        ),
    )
    tag = models.ForeignKey(
        Tag,
        null=True,  # NULL in the case of free text taxonomies or when the Tag gets deleted.
        blank=True,
        default=None,
        on_delete=models.SET_NULL,
        help_text=_(
            "Tag associated with this object tag. Provides the tag's 'value' if set."
        ),
    )
    _name = case_insensitive_char_field(
        max_length=255,
        help_text=_(
            "User-facing label used for this tag, stored in case taxonomy is (or becomes) null."
            " If the taxonomy field is set, then taxonomy.name takes precedence over this field."
        ),
    )
    _value = case_insensitive_char_field(
        max_length=500,
        help_text=_(
            "User-facing value used for this tag, stored in case tag is null, e.g if taxonomy is free text, or if it"
            " becomes null (e.g. if the Tag is deleted)."
            " If the tag field is set, then tag.value takes precedence over this field."
        ),
    )

    class Meta:
        indexes = [
            models.Index(fields=["taxonomy", "object_id"]),
            models.Index(fields=["taxonomy", "_value"]),
        ]
        unique_together = [
            ("object_id", "taxonomy", "tag_id"),
            ("object_id", "taxonomy", "_value"),
        ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if not self.pk:  # This is a new instance:
            # Set _name and _value automatically on creation, if they weren't set:
            if not self._name and self.taxonomy:
                self._name = self.taxonomy.name
            if not self._value and self.tag:
                self._value = self.tag.value

    def __repr__(self):
        """
        Developer-facing representation of an ObjectTag.
        """
        return str(self)

    def __str__(self):
        """
        User-facing string representation of an ObjectTag.
        """
        return f"<{self.__class__.__name__}> {self.object_id}: {self.name}={self.value}"

    @property
    def name(self) -> str:
        """
        Returns this tag's name/label.

        If taxonomy is set, then returns its name.
        Otherwise, returns the cached _name field.
        """
        return self.taxonomy.name if self.taxonomy else self._name

    @name.setter
    def name(self, name: str):
        """
        Stores to the _name field.
        """
        self._name = name

    @property
    def value(self) -> str:
        """
        Returns this tag's value.

        If tag is set, then returns its value.
        Otherwise, returns the cached _value field.
        """
        return self.tag.value if self.tag else self._value

    @value.setter
    def value(self, value: str):
        """
        Stores to the _value field.
        """
        self._value = value

    @property
    def is_deleted(self) -> bool:
        """
        Has this Tag been deleted from the Taxonomy? If so, we preserve this
        ObjecTag in the DB but it shouldn't be shown to the user.
        """
        return self.taxonomy is None or (self.tag is None and not self.taxonomy.allow_free_text)

    def clean(self):
        """
        Validate this ObjectTag.

        Note: this doesn't happen automatically on save(); only when edited in
        the django admin. So it's best practice to call obj_tag.full_clean()
        before saving.
        """
        if self.tag:
            if self.tag.taxonomy_id != self.taxonomy_id:
                raise ValidationError("ObjectTag's Taxonomy does not match Tag taxonomy")
            if self.tag.value != self._value:
                raise ValidationError("ObjectTag's _value is out of sync with Tag.value")
        else:
            # Note: self.taxonomy and/or self.tag may be NULL which is OK, because it means the Tag/Taxonomy
            # was deleted, but we still preserve this _value here in case the Taxonomy or Tag get re-created in future.
            if self._value == "":
                raise ValidationError("Invalid _value - empty string")
        if self.taxonomy and self.taxonomy.name != self._name:
            raise ValidationError("ObjectTag's _name is out of sync with Taxonomy.name")

    def get_lineage(self) -> Lineage:
        """
        Returns the lineage of the current tag as a list of value strings.

        If linked to a Tag, returns its lineage.
        Otherwise, returns an array containing its value string.
        """
        return self.tag.get_lineage() if self.tag else [self._value]

    def resync(self) -> bool:
        """
        Reconciles the stored ObjectTag properties with any changes made to its associated taxonomy or tag.

        This method is useful to propagate changes to a Taxonomy name or Tag value.

        It's also useful for a set of ObjectTags are imported from an external source prior to when a Taxonomy exists to
        validate or store its available Tags.

        Returns True if anything was changed, False otherwise.
        """
        changed = False

        # We used to have code here that would try to find a new taxonomy if the current taxonomy has been deleted.
        # But for now that's removed, as it risks things like linking a tag to the wrong org's taxonomy.

        # Sync the stored _name with the taxonomy.name
        if self.taxonomy and self._name != self.taxonomy.name:
            self.name = self.taxonomy.name
            changed = True

        # Closed taxonomies require a tag matching _value
        if self.taxonomy and not self.taxonomy.allow_free_text and not self.tag_id:
            tag = self.taxonomy.tag_set.filter(value=self.value).first()
            if tag:
                self.tag = tag
                changed = True

        # Sync the stored _value with the tag.name
        elif self.tag and self._value != self.tag.value:
            self.value = self.tag.value
            changed = True

        return changed

    @classmethod
    def cast(cls, object_tag: ObjectTag) -> Self:
        """
        Returns a cls instance with the same properties as the given ObjectTag.
        """
        return cls().copy(object_tag)

    def copy(self, object_tag: ObjectTag) -> Self:
        """
        Copy the fields from the given ObjectTag into the current instance.
        """
        self.id = object_tag.id
        self.tag = object_tag.tag
        self.taxonomy = object_tag.taxonomy
        self.object_id = object_tag.object_id
        self._value = object_tag._value  # pylint: disable=protected-access
        self._name = object_tag._name  # pylint: disable=protected-access
        return self
