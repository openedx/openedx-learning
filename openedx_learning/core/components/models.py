"""
The model hierarchy is Component -> ComponentVersion -> Content.

A Component is an entity like a Problem or Video. It has enough information to
identify the Component and determine what the handler should be (e.g. XBlock
Problem), but little beyond that.

Components have one or more ComponentVersions, which represent saved versions of
that Component. Managing the publishing of these versions is handled through the
publishing app. Component maps 1:1 to PublishableEntity and ComponentVersion
maps 1:1 to PublishableEntityVersion.

Multiple pieces of Content may be associated with a ComponentVersion, through
the ComponentVersionContent model. ComponentVersionContent allows to specify a
ComponentVersion-local identifier. We're using this like a file path by
convention, but it's possible we might want to have special identifiers later.
"""
from __future__ import annotations

from django.db import models

from ...lib.fields import case_sensitive_char_field, immutable_uuid_field, key_field
from ...lib.managers import WithRelationsManager
from ..contents.models import Content
from ..publishing.model_mixins import PublishableEntityMixin, PublishableEntityVersionMixin
from ..publishing.models import LearningPackage


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

    constraints = [
        models.UniqueConstraint(
            fields=[
                "namespace",
                "name",
            ],
            name="oel_component_type_uniq_ns_n",
        ),
    ]

    def __str__(self):
        return f"{self.namespace}:{self.name}"


class Component(PublishableEntityMixin):  # type: ignore[django-manager-missing]
    """
    This represents any Component that has ever existed in a LearningPackage.

    What is a Component
    -------------------

    A Component is an entity like a Problem or Video. It has enough information
    to identify itself and determine what the handler should be (e.g. XBlock
    Problem), but little beyond that.

    A Component will have many ComponentVersions over time, and most metadata is
    associated with the ComponentVersion model and the Content that
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

    The ``key`` field on Component's ``publishable_entity`` is dervied from the
    ``component_type`` and ``local_key`` fields in this model. We don't support
    changing the keys yet, but if we do, those values need to be kept in sync.

    How build on this model
    -----------------------

    Make a foreign key to the Component model when you need a stable reference
    that will exist for as long as the LearningPackage itself exists.
    """
    # Tell mypy what type our objects manager has.
    # It's actually PublishableEntityMixinManager, but that has the exact same
    # interface as the base manager class.
    objects: models.Manager[Component] = WithRelationsManager(
        'component_type'
    )

    with_publishing_relations: models.Manager[Component] = WithRelationsManager(
        'component_type',
        'publishable_entity',
        'publishable_entity__draft__version',
        'publishable_entity__draft__version__componentversion',
        'publishable_entity__published__version',
        'publishable_entity__published__version__componentversion',
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

    # local_key is an identifier that is local to the learning_package and
    # component_type.  The publishable.key should be calculated as a
    # combination of component_type and local_key.
    local_key = key_field()

    class Meta:
        constraints = [
            # The combination of (component_type, local_key) is unique within
            # a given LearningPackage. Note that this means it is possible to
            # have two Components in the same LearningPackage to have the same
            # local_key if the component_types are different. So for example,
            # you could have a ProblemBlock and VideoBlock that both have the
            # local_key "week_1".
            models.UniqueConstraint(
                fields=[
                    "learning_package",
                    "component_type",
                    "local_key",
                ],
                name="oel_component_uniq_lc_ct_lk",
            ),
        ]
        indexes = [
            # Global Component-Type/Local-Key Index:
            #   * Search by the different Components fields across all Learning
            #     Packages on the site. This would be a support-oriented tool
            #     from Django Admin.
            models.Index(
                fields=[
                    "component_type",
                    "local_key",
                ],
                name="oel_component_idx_ct_lk",
            ),
        ]

        # These are for the Django Admin UI.
        verbose_name = "Component"
        verbose_name_plural = "Components"

    def __str__(self):
        return f"{self.component_type.namespace}:{self.component_type.name}:{self.local_key}"


class ComponentVersion(PublishableEntityVersionMixin):
    """
    A particular version of a Component.

    This holds the content using a M:M relationship with Content via
    ComponentVersionContent.
    """
    # Tell mypy what type our objects manager has.
    # It's actually PublishableEntityVersionMixinManager, but that has the exact
    # same interface as the base manager class.
    objects: models.Manager[ComponentVersion]

    # This is technically redundant, since we can get this through
    # publishable_entity_version.publishable.component, but this is more
    # convenient.
    component = models.ForeignKey(
        Component, on_delete=models.CASCADE, related_name="versions"
    )

    # The contents hold the actual interesting data associated with this
    # ComponentVersion.
    contents: models.ManyToManyField[Content, ComponentVersionContent] = models.ManyToManyField(
        Content,
        through="ComponentVersionContent",
        related_name="component_versions",
    )

    class Meta:
        verbose_name = "Component Version"
        verbose_name_plural = "Component Versions"


class ComponentVersionContent(models.Model):
    """
    Determines the Content for a given ComponentVersion.

    An ComponentVersion may be associated with multiple pieces of binary data.
    For instance, a Video ComponentVersion might be associated with multiple
    transcripts in different languages.

    When Content is associated with an ComponentVersion, it has some local
    key that is unique within the the context of that ComponentVersion. This
    allows the ComponentVersion to do things like store an image file and
    reference it by a "path" key.

    Content is immutable and sharable across multiple ComponentVersions.
    """

    component_version = models.ForeignKey(ComponentVersion, on_delete=models.CASCADE)
    content = models.ForeignKey(Content, on_delete=models.RESTRICT)

    uuid = immutable_uuid_field()

    # "key" is a reserved word for MySQL, so we're temporarily using the column
    # name of "_key" to avoid breaking downstream tooling. A possible
    # alternative name for this would be "path", since it's most often used as
    # an internal file path. However, we might also want to put special
    # identifiers that don't map as cleanly to file paths at some point.
    key = key_field(db_column="_key")

    # Long explanation for the ``learner_downloadable`` field:
    #
    # Is this Content downloadable during the learning experience? This is
    # NOT about public vs. private permissions on course assets, as that will be
    # a policy that can be changed independently of new versions of the content.
    # For instance, a course team could decide to flip their course assets from
    # private to public for CDN caching reasons, and that should not require
    # new ComponentVersions to be created.
    #
    # What the ``learner_downloadable`` field refers to is whether this asset is
    # supposed to *ever* be directly downloadable by browsers during the
    # learning experience. This will be True for things like images, PDFs, and
    # video transcript files. This field will be False for things like:
    #
    # * Problem Block OLX will contain the answers to the problem. The XBlock
    #   runtime and ProblemBlock will use this information to generate HTML and
    #   grade responses, but the the user's browser is never permitted to
    #   actually download the raw OLX itself.
    # * Many courses include a python_lib.zip file holding custom Python code
    #   to be used by codejail to assess student answers. This code will also
    #   potentially reveal answers, and is never intended to be downloadable by
    #   the student's browser.
    # * Some course teams will upload other file formats that their OLX is
    #   derived from (e.g. specially formatted LaTeX files). These files will
    #   likewise contain answers and should never be downloadable by the
    #   student.
    # * Other custom metadata may be attached as files in the import, such as
    #   custom identifiers, author information, etc.
    #
    # Even if ``learner_downloadble`` is True, the LMS may decide that this
    # particular student isn't allowed to see this particular piece of content
    # yet–e.g. because they are not enrolled, or because the exam this Component
    # is a part of hasn't started yet. That's a matter of LMS permissions and
    # policy that is not intrinsic to the content itself, and exists at a layer
    # above this.
    learner_downloadable = models.BooleanField(default=False)

    class Meta:
        constraints = [
            # Uniqueness is only by ComponentVersion and key. If for some reason
            # a ComponentVersion wants to associate the same piece of content
            # with two different identifiers, that is permitted.
            models.UniqueConstraint(
                fields=["component_version", "key"],
                name="oel_cvcontent_uniq_cv_key",
            ),
        ]
        indexes = [
            models.Index(
                fields=["content", "component_version"],
                name="oel_cvcontent_c_cv",
            ),
            models.Index(
                fields=["component_version", "content"],
                name="oel_cvcontent_cv_d",
            ),
        ]
