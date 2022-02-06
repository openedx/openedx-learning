"""
Database models for publishing.

Publishing new versions of content requires different bits of data to be pushed
into different apps, and this may not happen all at once. These publishes are
triggered asynchronously and apps may fail without being able to immediately
signal the caller. When this happens today in edx-platform, we can end up in a
mixed-published state where certain features (e.g. the course outline) are stale
because the process that updated it has failed.

In order to try to address these issues, we take the following approach:

1. Explicitly track each app's data creation for a version of content.
2. Only update the branch information to point to a new version when all the
   required apps have successfully completed.
3. Make the apps as resilient as possible, by giving them relatively simple data
   models and having them sift out strange/inconsistent data using
   ContentErrors.
4. Centralize the creation and reporting of these errors, to ease reporting and
   debugging.

Priority Considerations

Not all apps necessarily need to complete in order for a publish to be
successful. For instance, pushing course content data into CourseGraph for later
analysis is a task that the overall publish process doesn't need to wait for,
and a failure there shouldn't be fatal for the publish process.

Ordering Considerations

Some post-publish tasks will depend on data having already been written to
certain APIs that they can in turn query. For instance, learning_composition
requires that learning_partitioning has already run and populated its data
models.

# Cleanup

Associating things with versions and allowing for duplication/deletion, vs.
heavily normalizing and deduping, with the caveat that it will be harder to
determine what can and can't be deleted safely.

"""
import uuid

from django.db import models
from django.conf import settings
from model_utils.models import TimeStampedModel
from simple_history.models import HistoricalRecords

from openedx_learning.lib.fields import identifier_field, immutable_uuid_field

# Note: We probably want to make our own IdentifierField so that we can control
# how collation happens in a MySQL/Postgres compatible way.


class LearningContextType(models.Model):
    # Identifier
    identifier = models.CharField(max_length=100, blank=False, null=False)


class LearningContext(TimeStampedModel):
    """
    A LearningContext represents a set of content that is versioned together.

    Courses and Content Libraries are examples.

    .. no_pii:
    """
    uuid = immutable_uuid_field()
    identifier = identifier_field(unique=True)

    # Don't allow deletion of LearningContextTypes.
    type = models.ForeignKey(LearningContextType, on_delete=models.RESTRICT)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL
    )

    class Meta:
        verbose_name = "Learning Context"


    def __str__(self):
        """
        Get a string representation of this model instance.
        """
        # TODO: return a string appropriate for the data fields
        return "<PublishedLearningContext, ID: {}>".format(self.id)


class LearningContextVersion(TimeStampedModel):
    """
    What's a Context Version?

    .. no_pii:
    """
    uuid = immutable_uuid_field()
    identifier = identifier_field(unique=False)

    # TODO: Replace this with something that doesn't require opaque-keys
    learning_context = models.ForeignKey(LearningContext, on_delete=models.CASCADE)
    title = models.CharField(max_length=255, db_index=True)


class LearningContextBranch(TimeStampedModel):
    """
    What's a Branch?

    .. no_pii:
    """
    learning_context = models.ForeignKey(LearningContext, on_delete=models.CASCADE)
    branch_name = models.CharField(max_length=100)

    # The intent of having on_delete=RESTRICT for version and on_delete=CASCADE
    # for learning_context is to say, "You can't delete the version that is
    # being pointed to by a branch (because it might be the live version that
    # students are using), but if you're deleting _the entire Learning Context_,
    # then it's fine to delete the branch pointer info as well."
    version = models.ForeignKey(LearningContextVersion, on_delete=models.RESTRICT)

    history = HistoricalRecords()

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["learning_context_id", "branch_name"],
                name="one_branch_per_learning_context",
            )
        ]


class LearningObjectType(models.Model):
    """
    Encodes both the primary type (e.g. Unit) and sub-type if applicable.
    """
    major = models.CharField(
        max_length=50,
        blank=False,
        null=False,
        help_text="Major types include 'block', 'unit', and 'sequence'."
    )
    minor = models.CharField(
        max_length=50,
        blank=False,
        null=False,
        help_text="Minor types in"
    )


class LearningObject(models.Model):
    """
    We have a few different overlapping concepts:

    * A generic bit of leaf content.

      * Can potentially be from different sources.

    * A Unit

      * Different kinds of Units potentially

    * A Sequence

      * Can potentially be diffent sequences

    * A LearningObject

      * A sharable thing. All Units and Sequences are this. Are all leaf content?

    This model is immutable.

    Open Question: What does it mean for a LearningObject to not be associated
    with any LearningContext. With multiple LearningContexts? 
    """
    uuid = immutable_uuid_field()
    type = models.ForeignKey(LearningObjectType, on_delete=models.RESTRICT)

    # created_by


class LearningObjectVersion(models.Model):
    """
    This represents a semantically different version of a Learning Object.

    Some important notes:


    """
    learning_object = models.ForeignKey(LearningObject, on_delete=models.CASCADE)

    # identifier and title would seem to make more sense to attach to the
    # LearningObject than the LearningObjectVersion, but while these things
    # change infrequently, they *can* change. Things are periodically renamed,
    # and even identifiers are sometimes changed (e.g. for case-sensitivity
    # issues).
    identifier = identifier_field(unique=False)
    title = models.CharField(max_length=255, db_index=True)


class LearningContextVersionContents(models.Model):
    """
    What LearningObjectVersions are in a given LearningContextVersion?

    This is effectively gives us a snapshot of all the versioned content
    associated with a version of the Learning Context. This could be used to
    diff what changed from a previously published version to the next one.

    Note that content does not have to be directly accessible via any sort of
    parent-child hierarchy to be in this this list. It's pefectly possible for
    detached blocks of content to be published as well.

    This table can potentially grow to be very large if versions are not cleaned
    up. Once a :model:`learning_publishing.LearningContextVersion` is deleted,
    all entries pointing to it from this model will cascade delete.

    Open Questions:
    * Does a container LO change if its list of children remains the same,
        but the contents of one of those children changes?
        - Actually, yeah, it does, because a container points to LOVs, not
        LOs. So its hash would change, as we'd expect.

    * Can a LearningContextVersion simply point to other LearningContextVersions
      by reference, so that we don't have to copy the contents of every library
      version to our own each time?
      - Probably?
      - I think that implies that it's not a LearningContextVersion. Or rather
        that there are three things at work:
        1. LearningObjectVersions
        2. Something that maps a bunch of LearningObjectVersions together in a
           coherent version (LearningContextVersion?)
        3. Something that ties together multiple #2's into the same published
           branch of a course.
           - Ooohhh... maybe a branch points to multiple versions of different
             libraries? This would also help us with the issue we have around
             knowing what versions of libraries are safe to clean up, since
             branches would have an fkey on them preventing them from deleting.
             - Or do we need those references in the LearningObjectVersions
               themselves?
    """
    # If the LearningContextVersion itself gets deleted, we should remove the
    # mappings for all versioned content that is associated with it.
    learning_context_version = models.ForeignKey(LearningContextVersion, on_delete=models.CASCADE)

    # A LearningObjectVersion should not be deleted if it's in a version that
    # is still potentially live.
    learning_object_version = models.ForeignKey(LearningObjectVersion, on_delete=models.RESTRICT)





### The stuff below this is error reporting related


class LearningAppVersionReport(TimeStampedModel):
    """
    Results of creating a version.

    .. no_pii:
    """
    # Put custom collation setting here? utf8mb4_0900_ai_ci
    app_name = models.CharField(max_length=100, blank=False, null=False)
    version = models.ForeignKey(LearningContextVersion, on_delete=models.CASCADE)

    # Summary of the ContentErrors associated with a Learning App processing a
    # LearningContextVersion's content data.
    num_critical = models.PositiveIntegerField()
    num_errors = models.PositiveIntegerField()
    num_warnings = models.PositiveIntegerField()

    # The only time when it makes sense to have a history for this model is when
    # there are code-related errors, and we're retring the same version with new
    # code. Unfortunately, this kind of thing does happen, and historical data
    # is useful for debugging these cases.
    history = HistoricalRecords()

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["app_name", "version"], name="one_report_per_app_and_version"
            )
        ]


class LearningAppContentError(models.Model):
    """
    Generic Error Container

    .. no_pii:
    """
    app_version_report = models.ForeignKey(
        LearningAppVersionReport, on_delete=models.CASCADE
    )

    # Convention for error_code should be {app}.{plugin}.{short_name}?
    error_code = models.CharField(max_length=100, blank=False, null=False)
    level = models.CharField(
        max_length=10,
        choices=[
            ("critical", "critical"),
            ("error", "error"),
            ("warning", "warning"),
        ],
    )

    # identifier is intentionally optional, since some errors cannot be tied to
    # a speicific item (e.g. "too many blocks").
    usage_key = models.CharField(max_length=255, null=True)

    # Generic JSON field
    data = models.JSONField()
