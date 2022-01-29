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

"""
import uuid

from django.db import models
from django.conf import settings
from model_utils.models import TimeStampedModel
from simple_history.models import HistoricalRecords


# Note: We probably want to make our own IdentifierField so that we can control
# how collation happens in a MySQL/Postgres compatible way.


class LearningContextType(models.Model):
    id = models.BigAutoField(primary_key=True)

    # Identifier
    identifier = models.CharField(max_length=100, blank=False, null=False)


class LearningContext(TimeStampedModel):
    """
    Hello world!

    .. no_pii:
    """

    id = models.BigAutoField(primary_key=True)
    identifier = models.CharField(max_length=255, unique=True, blank=False, null=False)

    # Don't allow deletion of LearningContextTypes.
    type = models.ForeignKey(LearningContextType, on_delete=models.RESTRICT)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL
    )

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

    id = models.BigAutoField(primary_key=True)

    # TODO: Replace this with something that doesn't require opaque-keys
    learning_context = models.ForeignKey(LearningContext, on_delete=models.CASCADE)
    title = models.CharField(max_length=255, db_index=True)


class LearningContextBranch(TimeStampedModel):
    """
    What's a Branch?

    .. no_pii:
    """

    id = models.BigAutoField(primary_key=True)
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


class LearningAppVersionReport(TimeStampedModel):
    """
    Results of creating a version.

    .. no_pii:
    """

    id = models.BigAutoField(primary_key=True)

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

    id = models.BigAutoField(primary_key=True)
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
