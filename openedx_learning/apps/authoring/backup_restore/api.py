"""
Backup Restore API
"""
import zipfile

from openedx_learning.apps.authoring.backup_restore.zipper import LearningPackageUnzipper, LearningPackageZipper
from openedx_learning.apps.authoring.publishing import api as publishing_api
from openedx_learning.apps.authoring.collections import api as collections_api


def create_zip_file(lp_key: str, path: str) -> None:
    """
    Creates a dump zip file for the given learning package key at the given path.

    Can throw a NotFoundError at get_learning_package_by_key
    """
    learning_package = publishing_api.get_learning_package_by_key(lp_key)
    LearningPackageZipper(learning_package).create_zip(path)


def load_dump_zip_file(path: str) -> None:
    """
    Loads a zip file derived from create_zip_file
    """
    with zipfile.ZipFile(path, "r") as zipf:
        LearningPackageUnzipper().load(zipf)

def tmp_delete_learning_package(lp_key: str) -> None:
    """
    Deletes a learning package and all its associated data.
    This is a temporary function to help with testing.

    Can throw a NotFoundError at get_learning_package_by_key
    """
    learning_package = publishing_api.get_learning_package_by_key(lp_key)
    collections = collections_api.get_collections(learning_package.id)
    for collection in collections:
        collection.delete()
    for entity in publishing_api.get_publishable_entities(learning_package):
        publishing_api.DraftSideEffect.objects.filter(cause__entity=entity).delete()
        publishing_api.Draft.objects.filter(entity=entity).delete()
        publishing_api.ContainerVersion.objects.filter(
            entity_list__entitylistrow__entity=entity,
        ).delete()
        publishing_api.EntityList.objects.filter(entitylistrow__entity=entity).delete()
        publishing_api.EntityListRow.objects.filter(entity=entity).delete()
        publishing_api.Published.objects.filter(entity=entity).delete()
        publishing_api.DraftChangeLogRecord.objects.filter(entity=entity).delete()
        publishing_api.PublishLogRecord.objects.filter(entity=entity).delete()
        entity.delete()
    learning_package.delete()
