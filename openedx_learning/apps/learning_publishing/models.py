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

Data Concepts

1. Learning App: These are applications with a unique identifier. They don't
   exist as an explicit table. [TODO: explain why] They may come and go, as apps
   are installed and uninstalled.
2. Learning Context: This is a published artifact, like a Course or Library.
   [TODO: expand on what makes an LC special–versioning/publishing, student
   state, etc.]
3.
"""
import uuid

from django.db import models
from django.conf import settings
from model_utils.models import TimeStampedModel
from simple_history.models import HistoricalRecords

from opaque_keys.edx.django.models import LearningContextKeyField, UsageKeyField


## Base models for the core data model of what it means to be "published"

class LearningContext(TimeStampedModel):
    """

    .. no_pii:
    """
    id = models.BigAutoField(primary_key=True)

    # TODO: Generic "indentifier" instead of LearningContextKey? Split out into
    # separate tables for things like Courses? Implies a "type" column as well.

    key = LearningContextKeyField(max_length=255, db_index=True, unique=True, null=False)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL)

    def __str__(self):
        """
        Get a string representation of this model instance.
        """
        # TODO: return a string appropriate for the data fields
        return '<PublishedLearningContext, ID: {}>'.format(self.id)


class LearningContextVersion(TimeStampedModel):
    """

    .. no_pii:
    """
    id = models.BigAutoField(primary_key=True)

    # TODO: Replace this with something that doesn't require opaque-keys
    learning_context = models.ForeignKey(LearningContext, on_delete=models.CASCADE)
    title = models.CharField(max_length=255, db_index=True)


class LearningContextBranch(TimeStampedModel):
    """

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
                fields=['learning_context_id', 'branch_name'],
                name='one_branch_per_learning_context'
            )
        ]

class LearningAppVersionReport(TimeStampedModel):
    """

    .. no_pii:
    """
    id = models.BigAutoField(primary_key=True)
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
                fields=['app_name', 'version'],
                name='one_report_per_app_and_version'
            )
        ]

#
class LearningAppContentError(models.Model):
    """

    .. no_pii:
    """
    id = models.BigAutoField(primary_key=True)
    app_version_report = models.ForeignKey(LearningAppVersionReport, on_delete=models.CASCADE)

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

    # usage_key is intentionally optional, since some errors cannot be tied to a
    # speicific item (e.g. "too many blocks").
    usage_key = UsageKeyField(max_length=255, null=True)

    # Generic JSON field
    data = models.JSONField()
