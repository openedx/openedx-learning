""" Tagging app data models """
from typing import List, Type

from django.db import models
from django.utils.module_loading import import_string
from django.utils.translation import gettext_lazy as _

from openedx_learning.lib.fields import MultiCollationTextField, case_insensitive_char_field

from .registry import cast_object_tag, register_object_tag_class

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
        null=True,
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
        tag = self
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
        null=True,
        blank=True,
        help_text=_(
            "Provides extra information for the user when applying tags from this taxonomy to an object."
        ),
    )
    enabled = models.BooleanField(
        default=True,
        help_text=_("Only enabled taxonomies will be shown to authors."),
    )
    required = models.BooleanField(
        default=False,
        help_text=_(
            "Indicates that one or more tags from this taxonomy must be added to an object."
        ),
    )
    allow_multiple = models.BooleanField(
        default=False,
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
    system_defined = models.BooleanField(
        default=False,
        editable=False,
        help_text=_(
            "Indicates that tags and metadata for this taxonomy are maintained by the system;"
            " taxonomy admins will not be permitted to modify them.",
        ),
    )
    visible_to_authors = models.BooleanField(
        default=True,
        editable=False,
        help_text=_(
            "Indicates whether this taxonomy should be visible to object authors."
        ),
    )
    _object_tag_class = models.CharField(
        null=True,
        max_length=255,
        help_text=_(
            "Overrides the default ObjectTag subclass associated with this taxonomy."
            "Must be a fully-qualified module and class name.",
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
        return f"<{self.__class__.__name__}> ({self.id}) {self.name}"

    @property
    def object_tag_class(self) -> Type:
        """
        Returns the ObjectTag subclass associated with this taxonomy, or None if none supplied.

        May raise ImportError if a custom object_tag_class cannot be imported.
        """
        if self._object_tag_class:
            return import_string(self._object_tag_class)
        return None

    @object_tag_class.setter
    def object_tag_class(self, object_tag_class: Type):
        """
        Assigns the given object_tag_class's module path.class to the field.

        Raises ValueError if the given `object_tag_class` is a built-in class; it should be an ObjectTag-like class.
        """
        if object_tag_class.__module__ == "builtins":
            raise ValueError(
                f"object_tag_class {object_tag_class} must be class like ObjectTag"
            )

        # ref: https://stackoverflow.com/a/2020083
        self._object_tag_class = ".".join(
            [object_tag_class.__module__, object_tag_class.__qualname__]
        )

    def get_tags(self) -> List[Tag]:
        """
        Returns a list of all Tags in the current taxonomy, from the root(s) down to TAXONOMY_MAX_DEPTH tags, in tree order.

        Annotates each returned Tag with its ``depth`` in the tree (starting at 0).

        Performance note: may perform as many as TAXONOMY_MAX_DEPTH select queries.
        """
        tags = []
        if self.allow_free_text:
            return tags

        parents = None
        for depth in range(TAXONOMY_MAX_DEPTH):
            filtered_tags = self.tag_set.prefetch_related("parent")
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
    object_id = case_insensitive_char_field(
        max_length=255,
        help_text=_("Identifier for the object being tagged"),
    )
    object_type = case_insensitive_char_field(
        max_length=255,
        help_text=_("Type of object being tagged"),
    )
    taxonomy = models.ForeignKey(
        Taxonomy,
        null=True,
        default=None,
        on_delete=models.SET_NULL,
        help_text=_(
            "Taxonomy that this object tag belongs to. Used for validating the tag and provides the tag's 'name' if set."
        ),
    )
    tag = models.ForeignKey(
        Tag,
        null=True,
        default=None,
        on_delete=models.SET_NULL,
        help_text=_(
            "Tag associated with this object tag. Provides the tag's 'value' if set."
        ),
    )
    _name = case_insensitive_char_field(
        null=False,
        max_length=255,
        help_text=_(
            "User-facing label used for this tag, stored in case taxonomy is (or becomes) null."
            " If the taxonomy field is set, then taxonomy.name takes precedence over this field."
        ),
    )
    _value = case_insensitive_char_field(
        null=False,
        max_length=500,
        help_text=_(
            "User-facing value used for this tag, stored in case tag is null, e.g if taxonomy is free text, or if it"
            " becomes null (e.g. if the Tag is deleted)."
            " If the tag field is set, then tag.value takes precedence over this field."
        ),
    )

    class Meta:
        indexes = [
            models.Index(fields=["taxonomy", "_value"]),
        ]

    def __repr__(self):
        """
        Developer-facing representation of an ObjectTag.
        """
        return str(self)

    def __str__(self):
        """
        User-facing string representation of an ObjectTag.
        """
        return f"<{self.__class__.__name__}> {self.object_id} ({self.object_type}): {self.name}={self.value}"

    @property
    def name(self) -> str:
        """
        Returns this tag's name/label.

        If taxonomy is set, then returns its name.
        Otherwise, returns the cached _name field.
        """
        return self.taxonomy.name if self.taxonomy_id else self._name

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
        return self.tag.value if self.tag_id else self._value

    @value.setter
    def value(self, value: str):
        """
        Stores to the _value field.
        """
        self._value = value

    @property
    def tag_ref(self) -> str:
        """
        Returns this tag's reference string.

        If tag is set, then returns its id.
        Otherwise, returns the cached _value field.
        """
        return self.tag.id if self.tag_id else self._value

    def copy(self, object_tag: "ObjectTag") -> "ObjectTag":
        """
        Copy the fields from the given ObjectTag into the current instance.
        """
        self.id = object_tag.id
        self.object_id = object_tag.object_id
        self.object_type = object_tag.object_type
        self.taxonomy = object_tag.taxonomy
        self.tag = object_tag.tag
        self._name = object_tag._name
        self._value = object_tag._value
        return self

    def get_lineage(self) -> Lineage:
        """
        Returns the lineage of the current tag as a list of value strings.

        If linked to a Tag, returns its lineage.
        Otherwise, returns an array containing its value string.
        """
        return self.tag.get_lineage() if self.tag_id else [self._value]

    def _check_taxonomy(self):
        """
        Always returns True.

        Subclasses should override this method to perform validation for the particular type of object tag.
        """
        return True

    def _check_tag(self):
        """
        Always returns True.

        Subclasses should override this method to perform validation for the particular type of object tag.
        """
        return True

    def _check_object(self):
        """
        Always returns True.

        Subclasses should override this method to perform validation for the particular type of object tag.
        """
        return True

    def is_valid(self, check_taxonomy=True, check_tag=True, check_object=True) -> bool:
        """
        Returns True if this ObjectTag is valid.

        If `check_taxonomy` is False, then we skip validating the object tag's taxonomy reference.
        If `check_tag` is False, then we skip validating the object tag's tag reference.
        If `check_object` is False, then we skip validating the object ID/type.
        """
        if check_taxonomy and not self._check_taxonomy():
            return False

        if check_tag and not self._check_tag():
            return False

        if check_object and not self._check_object():
            return False

        return True

    def resync(self) -> bool:
        """
        Reconciles the stored ObjectTag properties with any changes made to its associated taxonomy or tag.

        This method is useful to propagate changes to a Taxonomy name or Tag value.

        It's also useful for a set of ObjectTags are imported from an external source prior to when a Taxonomy exists to
        validate or store its available Tags.

        Subclasses may override this method to perform any additional syncing for the particular type of object tag.

        Returns True if anything was changed, False otherwise.
        """
        changed = False

        # Locate an enabled taxonomy matching _name, and maybe a tag matching _value
        if not self.taxonomy_id:
            for taxonomy in Taxonomy.objects.filter(
                name=self.name, enabled=True
            ).order_by("allow_free_text", "id"):
                # Closed taxonomies require a tag matching _value,
                # and we'd rather match a closed taxonomy than an open one.
                # So see if there's a matching tag available in this taxonomy.
                tag = self.tag or taxonomy.tag_set.filter(value=self.value).first()

                # Make sure this taxonomy will accept object tags like this.
                test_object_tag = cast_object_tag(
                    ObjectTag(
                        taxonomy=taxonomy,
                        tag=tag,
                        object_id=self.object_id,
                        object_type=self.object_type,
                        _name=self.name,
                        _value=self.value,
                    )
                )
                if test_object_tag:
                    self.taxonomy = taxonomy
                    self.tag = tag
                    changed = True
                    break
                # If not, try the next one

        # Sync the stored _name with the taxonomy.name
        if self.taxonomy_id and self._name != self.taxonomy.name:
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


class OpenObjectTag(ObjectTag):
    """
    Free-text object tag.

    Only needs a free-text taxonomy and a value to be valid.
    """

    class Meta:
        proxy = True

    def _check_taxonomy(self):
        """
        Returns True if this ObjectTag has a valid taxonomy.

        Subclasses should override this method to perform any additional validation for the particular type of object tag.
        """
        # Must be linked to a free-text taxonomy
        return self.taxonomy_id and self.taxonomy.allow_free_text

    def _check_tag(self):
        """
        Returns True if this ObjectTag has a valid tag value.

        Subclasses should override this method to perform any additional validation for the particular type of object tag.
        """
        # Open taxonomies don't need an associated tag, but we need a value.
        return bool(self._value)

    def _check_object(self):
        """
        Returns True if this ObjectTag has a valid object.

        Subclasses should override this method to perform any additional validation for the particular type of object tag.
        """
        # Must have a valid object id/type:
        return self.object_id and self.object_type


class ClosedObjectTag(OpenObjectTag):
    """
    Object tags linked to a closed taxonomy, where the available tag value options are known.
    """

    class Meta:
        proxy = True

    def _check_taxonomy(self):
        """
        Returns True if this ObjectTag is linked to a closed taxonomy.

        Subclasses should override this method to perform any additional validation for the particular type of object tag.
        """
        # Must be linked to a closed taxonomy
        return self.taxonomy_id and not self.taxonomy.allow_free_text

    def _check_tag(self):
        """
        Returns True if this ObjectTag has a valid tag.

        Subclasses should override this method to perform any additional validation for the particular type of object tag.
        """
        # Closed taxonomies require a Tag
        return bool(self.tag_id)

    def is_valid(self, check_taxonomy=True, check_tag=True, check_object=True) -> bool:
        """
        Returns True if this ObjectTag is valid for use with a closed taxonomy.

        Subclasses should override this method to perform any additional validation for the particular type of object tag.

        If `check_taxonomy` is False, then we skip validating the object tag's taxonomy reference.
        If `check_tag` is False, then we skip validating the object tag's tag reference.
        If `check_object` is False, then we skip validating the object ID/type.
        """
        if not super().is_valid(
            check_taxonomy=check_taxonomy,
            check_tag=check_tag,
            check_object=check_object,
        ):
            return False

        if check_tag and check_taxonomy and (self.tag.taxonomy_id != self.taxonomy_id):
            return False

        return True


# Register the ObjectTag subclasses in reverse order of how we want them considered.
register_object_tag_class(OpenObjectTag)
register_object_tag_class(ClosedObjectTag)
