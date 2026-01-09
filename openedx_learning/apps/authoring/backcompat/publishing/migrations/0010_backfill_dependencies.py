"""
Backfill PublishableEntityVersionDependency entries based on ContainerVersions.

We're introducing a lower-level publishing concept of a dependency that will be
used by Containers, but this means we have to backfill that dependency info for
existing Containers in the system.
"""
from django.db import migrations
from django.db.models import F


def create_backfill(apps, schema_editor):
    """
    Create dependency entries and update dep hashes for Draft and Published.
    """
    _create_dependencies(apps)
    _update_drafts(apps)
    _update_draft_dependencies_hashes(apps)
    _update_published_dependencies_hashes(apps)


def _create_dependencies(apps):
    """
    Populate the PublishableEntityVersion.dependencies relation.

    The only ones we should have in the system at this point are the ones from
    containers, so we query ContainerVersion for that.
    """
    PublishableEntityVersionDependency = apps.get_model(
        "oel_publishing", "PublishableEntityVersionDependency"
    )
    ContainerVersion = apps.get_model("oel_publishing", "ContainerVersion")

    for container_version in ContainerVersion.objects.all():
        # child_entity_ids is a set to de-dupe. This doesn't handle pinned
        # child references yet, but you can't actually make those in a real
        # library yet, so we shouldn't have that data lying around to migrate.
        child_entity_ids = set(
            container_version
                .entity_list
                .entitylistrow_set
                .all()
                .values_list("entity_id", flat=True)
        )
        PublishableEntityVersionDependency.objects.bulk_create(
            [
                PublishableEntityVersionDependency(
                    referring_version_id=container_version.pk,
                    referenced_entity_id=entity_id
                )
                for entity_id in child_entity_ids
            ],
            ignore_conflicts=True,
        )


def _update_drafts(apps):
    """
    Update Draft entries to point to their most recent DraftLogRecord.

    This is slow and expensive.
    """
    Draft = apps.get_model("oel_publishing", "Draft")
    DraftChangeLogRecord = apps.get_model("oel_publishing", "DraftChangeLogRecord")
    for draft in Draft.objects.all():
        draft_log_record = (
            # Find the most recent DraftChangeLogRecord related to this Draft,
            DraftChangeLogRecord.objects
                .filter(entity_id=draft.pk)
                .order_by('-pk')
                .first()
        )
        draft.draft_log_record = draft_log_record
        draft.save()


def _update_draft_dependencies_hashes(apps):
    """
    Update the dependency_hash_digest for all DraftChangeLogRecords.

    Backfill dependency state hashes. The important thing here is that things
    without dependencies will have the default (blank) state hash, so we only
    need to query for Draft entries for Containers.

    We are only backfilling the current DraftChangeLogRecords pointed to by the
    Draft entries now. We are not backfilling all historical
    DraftChangeLogRecords. Full historical reconstruction is probably possible,
    but it's not really worth the cost and complexity.
    """
    from ..api import update_dependencies_hash_digests_for_log
    from ..models import DraftChangeLog

    # All DraftChangeLogs that have records that are pointed to by the current
    # Draft and have a possibility of having dependencies.
    change_logs = DraftChangeLog.objects.filter(
        pk=F('records__entity__draft__draft_log_record__draft_change_log'),
        records__entity__draft__version__isnull=False,
        records__entity__container__isnull=False,
    ).distinct()
    for change_log in change_logs:
        update_dependencies_hash_digests_for_log(change_log, backfill=True)

def _update_published_dependencies_hashes(apps):
    """
    Update all container Published.dependencies_hash_digest

    Backfill dependency state hashes. The important thing here is that things
    without dependencies will have the default (blank) state hash, so we only
    need to query for Published entries for Containers.
    """
    from ..api import update_dependencies_hash_digests_for_log
    from ..models import PublishLog

    # All PublishLogs that have records that are pointed to by the current
    # Published and have a possibility of having dependencies.
    change_logs = PublishLog.objects.filter(
        pk=F('records__entity__published__publish_log_record__publish_log'),
        records__entity__published__version__isnull=False,
        records__entity__container__isnull=False,
    ).distinct()
    for change_log in change_logs:
        update_dependencies_hash_digests_for_log(change_log, backfill=True)

def remove_backfill(apps, schema_editor):
    """
    Reset all dep hash values to default ('') and remove dependencies.
    """
    Draft = apps.get_model("oel_publishing", "Draft")
    DraftChangeLogRecord = apps.get_model("oel_publishing", "DraftChangeLogRecord")
    PublishLogRecord = apps.get_model("oel_publishing", "PublishLogRecord")
    PublishableEntityVersionDependency = apps.get_model(
        "oel_publishing", "PublishableEntityVersionDependency"
    )

    PublishLogRecord.objects.all().update(dependencies_hash_digest='')
    DraftChangeLogRecord.objects.all().update(dependencies_hash_digest='')
    PublishableEntityVersionDependency.objects.all().delete()
    Draft.objects.all().update(draft_log_record=None)


class Migration(migrations.Migration):

    dependencies = [
        ('oel_publishing', '0009_dependencies_and_hashing'),
    ]

    operations = [
        migrations.RunPython(create_backfill, reverse_code=remove_backfill)
    ]
