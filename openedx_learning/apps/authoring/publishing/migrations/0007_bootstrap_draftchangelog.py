"""
Bootstrap DraftChangeLogs

DraftChangeLog and DraftChangeLogRecord are being introduced after Drafts, so
we're going to retroactively make entries for all the changes that were in our
Learning Packages.

This migration will try to reconstruct create, edit, reset-to-published, and
delete operations, but it won't be fully accurate because we only have the
create dates of the versions and the current state of active Drafts to go on.
This means we won't accurately capture when things were deleted and then reset,
or when reset and then later edited. We're also missing the user for a number of
these operations, so we'll add those with null created_by entries. Addressing
these gaps is a big part of why we created DraftChangeLogs in the first place.
"""
# Generated by Django 4.2.18 on 2025-03-13 10:29
import logging
from datetime import datetime, timezone

from django.db import migrations

logger = logging.getLogger(__name__)


def bootstrap_draft_change_logs(apps, schema_editor):
    """
    Create a fake DraftChangeSet that encompasses the state of current Drafts.
    """
    LearningPackage = apps.get_model("oel_publishing", "LearningPackage")
    PublishableEntityVersion = apps.get_model("oel_publishing", "PublishableEntityVersion")

    Draft = apps.get_model("oel_publishing", "Draft")
    DraftChangeLogRecord = apps.get_model("oel_publishing", "DraftChangeLogRecord")
    DraftChangeLog = apps.get_model("oel_publishing", "DraftChangeLog")
    now = datetime.now(tz=timezone.utc)

    for learning_package in LearningPackage.objects.all().order_by("key"):
        logger.info(f"Creating bootstrap DraftChangeLogs for {learning_package.key}")
        pub_ent_versions = PublishableEntityVersion.objects.filter(
                               entity__learning_package=learning_package
                           ).select_related("entity")

        # First cycle though all the simple create/edit operations...
        last_version_seen = {}  # PublishableEntity.id -> PublishableEntityVersion.id
        for pub_ent_version in pub_ent_versions.order_by("pk"):
            draft_change_log = DraftChangeLog.objects.create(
                learning_package=learning_package,
                changed_at=pub_ent_version.created,
                changed_by=pub_ent_version.created_by,
            )
            DraftChangeLogRecord.objects.create(
                draft_change_log=draft_change_log,
                entity=pub_ent_version.entity,
                old_version_id=last_version_seen.get(pub_ent_version.entity.id),
                new_version_id=pub_ent_version.id,
            )
            last_version_seen[pub_ent_version.entity.id] = pub_ent_version.id

        # Now that we've created change sets for create/edit operations, we look
        # at the latest state of the Draft model in order to determine whether
        # we need to apply deletes or resets.
        for draft in Draft.objects.filter(entity__learning_package=learning_package).order_by("entity_id"):
            last_version_id = last_version_seen.get(draft.entity_id)
            if draft.version_id == last_version_id:
                continue
            # We don't really know who did this or when, so we use None and now.
            draft_change_log = DraftChangeLog.objects.create(
                learning_package=learning_package,
                changed_at=now,
                changed_by=None,
            )
            DraftChangeLogRecord.objects.create(
                draft_change_log=draft_change_log,
                entity_id=draft.entity_id,
                old_version_id=last_version_id,
                new_version_id=draft.version_id,
            )


def delete_draft_change_logs(apps, schema_editor):
    logger.info(f"Deleting all DraftChangeLogs (reverse migration)")
    DraftChangeLog = apps.get_model("oel_publishing", "DraftChangeLog")
    DraftChangeLog.objects.all().delete()


class Migration(migrations.Migration):

    dependencies = [
        ('oel_publishing', '0006_draftchangelog'),
    ]

    operations = [
        migrations.RunPython(bootstrap_draft_change_logs, reverse_code=delete_draft_change_logs)
    ]
