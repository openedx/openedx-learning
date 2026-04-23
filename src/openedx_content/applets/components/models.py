"""
The model hierarchy is Component -> ComponentVersion -> Media.

A Component is an entity like a Problem or Video. It has enough information to
identify the Component and determine what the handler should be (e.g. XBlock
Problem), but little beyond that.

Components have one or more ComponentVersions, which represent saved versions of
that Component. Managing the publishing of these versions is handled through the
publishing app. Component maps 1:1 to PublishableEntity and ComponentVersion
maps 1:1 to PublishableEntityVersion.

Multiple pieces of Media may be associated with a ComponentVersion, through
the ComponentVersionMedia model. ComponentVersionMedia allows to specify a
ComponentVersion-local identifier. We're using this like a file path by
convention, but it's possible we might want to have special identifiers later.
"""
from __future__ import annotations

from typing import ClassVar, NewType, cast

from django.db import models
from typing_extensions import deprecated

from openedx_django_lib.fields import case_sensitive_char_field, code_field, code_field_check, ref_field
from openedx_django_lib.managers import WithRelationsManager

from ..media.models import Media
from ..publishing.models import (
    LearningPackage,
    PublishableEntity,
    PublishableEntityMixin,
    PublishableEntityVersionMixin,
)

__all__ = [
    "ComponentType",
    "Component",
    "ComponentVersion",
    "ComponentVersionMedia",
]


class ComponentType(models.Model):
    """
    Normalized representation of a type of Component.

    The only namespace being used initially will be 'xblock.v1', but we will
    probably add a few others over time, such as a component type to represent
    packages of files for things like Files and Uploads or python_lib.zip files.

    Make a ForeignKey against this table if you have to set policy based on the
    type of Components–e.g. marking certain types of XBlocks as approved vs.
    experimental for use in libraries.
    """
    # We don't need the app default of 8-bytes for this primary key, but there
    # is just a tiny chance that we'll use ComponentType in a novel, user-
    # customizable way that will require more than 32K entries. So let's use a
    # 4-byte primary key.
    id = models.AutoField(primary_key=True)

    # namespace and name work together to help figure out what Component needs
    # to handle this data. A namespace is *required*. The namespace for XBlocks
    # is "xblock.v1" (to match the setup.py entrypoint naming scheme).
    namespace = case_sensitive_char_field(max_length=100, blank=False)

    # name is a way to help sub-divide namespace if that's convenient. This
    # field cannot be null, but it can be blank if it's not necessary. For an
    # XBlock, this corresponds to tag, e.g. "video". It's also the block_type in
    # the UsageKey.
    name = case_sensitive_char_field(max_length=100, blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=[
                    "namespace",
                    "name",
                ],
                name="oel_component_type_uniq_ns_n",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.namespace}:{self.name}"


class Component(PublishableEntityMixin):
    """
    This represents any Component that has ever existed in a LearningPackage.

    What is a Component
    -------------------

    A Component is an entity like a Problem or Video. It has enough information
    to identify itself and determine what the handler should be (e.g. XBlock
    Problem), but little beyond that.

    A Component will have many ComponentVersions over time, and most metadata is
    associated with the ComponentVersion model and the Media that
    ComponentVersions are associated with.

    A Component belongs to exactly one LearningPackage.

    A Component is 1:1 with PublishableEntity and has matching primary key
    values. More specifically, ``Component.pk`` maps to
    ``Component.publishable_entity_id``, and any place where the Publishing API
    module expects to get a ``PublishableEntity.id``, you can use a
    ``Component.pk`` instead.

    Identifiers
    -----------

    Components have a ``publishable_entity`` OneToOneField to the ``publishing``
    app's PublishableEntity field, and it uses this as its primary key. Please
    see PublishableEntity's docstring for how you should use its ``uuid`` and
    ``key`` fields.

    State Consistency
    -----------------

    The ``key`` field on Component's ``publishable_entity`` is derived from the
    ``component_type`` and ``component_code`` fields in this model. We don't
    support changing the keys yet, but if we do, those values need to be kept
    in sync.

    How build on this model
    -----------------------

    Make a foreign key to the Component model when you need a stable reference
    that will exist for as long as the LearningPackage itself exists.
    """

    ComponentID = NewType("ComponentID", PublishableEntity.ID)
    type ID = ComponentID

    @property
    def id(self) -> ID:
        return cast(Component.ID, self.publishable_entity_id)

    @property
    @deprecated("Use .id instead")
    def pk(self):
        """Mark the .pk attribute as deprecated"""
        # Note: Django-Stubs forces mypy to identify the `.pk` attribute of this model as having 'Any' type (due to our
        # use of a OneToOneField primary key), and this is impossible for us to override, so we prefer to use
        # `.id` which we can control fully.
        # Since Django uses '.pk' internally, we have to make sure it still works, however. So the best we can do is
        # override this with a deprecated marker, so it shows a warning in developer's IDEs like VS Code.
        return self.id

    # Set up our custom manager. It has the same API as the default one, but selects related objects by default.
    objects: ClassVar[WithRelationsManager[Component]] = WithRelationsManager(  # type: ignore[assignment]
        'component_type'
    )

    with_publishing_relations = WithRelationsManager(
        'component_type',
        'publishable_entity',
        'publishable_entity__draft__version',
        'publishable_entity__draft__version__componentversion',
        'publishable_entity__published__version',
        'publishable_entity__published__version__componentversion',
        'publishable_entity__published__publish_log_record',
        'publishable_entity__published__publish_log_record__publish_log',
    )

    # This foreign key is technically redundant because we're already locked to
    # a single LearningPackage through our publishable_entity relation. However,
    # having this foreign key directly allows us to make indexes that efficiently
    # query by other Component fields within a given LearningPackage, which is
    # going to be a common use case (and we can't make a compound index using
    # columns from different tables).
    learning_package = models.ForeignKey(LearningPackage, on_delete=models.CASCADE)

    # What kind of Component are we? This will usually represent a specific
    # XBlock block_type, but we want it to be more flexible in the long term.
    component_type = models.ForeignKey(ComponentType, on_delete=models.PROTECT)

    # component_code is an identifier that is local to the learning_package and
    # component_type. The publishable.entity_ref is derived from component_type
    # and component_code.
    component_code = code_field(unicode=True)

    class Meta:
        constraints = [
            # The combination of (component_type, component_code) is unique
            # within a given LearningPackage. Note that this means it is
            # possible to have two Components in the same LearningPackage with
            # the same component_code if their component_types differ. For
            # example, a ProblemBlock and VideoBlock could both have the
            # component_code "week_1".
            models.UniqueConstraint(
                fields=[
                    "learning_package",
                    "component_type",
                    "component_code",
                ],
                name="oel_component_uniq_lc_ct_lk",
            ),
            code_field_check("component_code", name="oel_component_code_regex", unicode=True),
        ]
        indexes = [
            # Global Component-Type/Component-Code Index:
            #   * Search by the different Components fields across all Learning
            #     Packages on the site. This would be a support-oriented tool
            #     from Django Admin.
            models.Index(
                fields=[
                    "component_type",
                    "component_code",
                ],
                name="oel_component_idx_ct_lk",
            ),
        ]

        # These are for the Django Admin UI.
        verbose_name = "Component"
        verbose_name_plural = "Components"

    def __str__(self) -> str:
        return f"{self.component_type.namespace}:{self.component_type.name}:{self.component_code}"


class ComponentVersion(PublishableEntityVersionMixin):
    """
    A particular version of a Component.

    This holds the media using a M:M relationship with Media via
    ComponentVersionMedia.
    """

    # This is technically redundant, since we can get this through
    # publishable_entity_version.publishable.component, but this is more
    # convenient.
    component = models.ForeignKey(
        Component, on_delete=models.CASCADE, related_name="versions"
    )

    # The media relation holds the actual interesting data associated with this
    # ComponentVersion.
    media: models.ManyToManyField[Media, ComponentVersionMedia] = models.ManyToManyField(
        Media,
        through="ComponentVersionMedia",
        related_name="component_versions",
    )

    class Meta:
        verbose_name = "Component Version"
        verbose_name_plural = "Component Versions"


class ComponentVersionMedia(models.Model):
    """
    Determines the Media for a given ComponentVersion.

    An ComponentVersion may be associated with multiple pieces of binary data.
    For instance, a Video ComponentVersion might be associated with multiple
    transcripts in different languages.

    When Media is associated with a ComponentVersion, it has a ``path``
    that is unique within the context of that ComponentVersion. This is
    used as a local file-path-like identifier, e.g. "static/image.png".

    Media is immutable and sharable across multiple ComponentVersions.
    """

    component_version = models.ForeignKey(ComponentVersion, on_delete=models.CASCADE)
    media = models.ForeignKey(Media, on_delete=models.RESTRICT)

    # path is a local file-path-like identifier for the media within a
    # ComponentVersion.
    path = ref_field()

    class Meta:
        constraints = [
            # Uniqueness is only by ComponentVersion and path.
            models.UniqueConstraint(
                fields=["component_version", "path"],
                name="oel_cvcontent_uniq_cv_key",
            ),
        ]
        indexes = [
            models.Index(
                fields=["media", "component_version"],
                name="oel_cvmedia_c_cv",
            ),
            models.Index(
                fields=["component_version", "media"],
                name="oel_cvmedia_cv_d",
            ),
        ]
