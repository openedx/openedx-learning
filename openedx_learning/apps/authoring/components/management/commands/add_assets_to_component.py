"""
Management command to add files to a Component.

This is mostly meant to be a debugging tool to let us to easily load some test
asset data into the system.
"""
import mimetypes
import pathlib
from datetime import datetime, timezone

from django.core.management.base import BaseCommand

from ....components.api import create_component_version_content
from ....contents.api import get_or_create_file_content, get_or_create_media_type
from ....publishing.api import get_learning_package_by_key
from ...api import create_next_component_version, get_component_by_key


class Command(BaseCommand):
    """
    Add files to a Component, creating a new Component Version.

    This does not publish the the Component.

    Note: This is a quick debug tool meant to stuff some asset data into
    Learning Core models for testing. It's not intended as a robust and
    performant tool for modifying actual production content, and should not be
    used for that purpose.
    """

    def add_arguments(self, parser):
        parser.add_argument(
            "learning_package_key",
            type=str,
            help="LearningPackage.key value for where the Component is located."
        )
        parser.add_argument(
            "component_key",
            type=str,
            help="Component.key that you want to add assets to."
        )
        parser.add_argument(
            "file_mappings",
            nargs="+",
            type=str,
            help=(
                "Mappings of desired Component asset paths to the disk paths "
                "of where to upload the file from, separated by ':'. (Example: "
                "static/donkey.jpg:/Users/dave/Desktop/donkey-big.jpg). A "
                "blank value for upload file means to remove that from the "
                "Component. You may upload/remove as many files as you want in "
                "a single invocation."
            )
        )

    def handle(self, *args, **options):
        """
        Add files to a Component as ComponentVersion -> Content associations.
        """
        learning_package_key = options["learning_package_key"]
        component_key = options["component_key"]
        file_mappings = options["file_mappings"]

        learning_package = get_learning_package_by_key(learning_package_key)
        # Parse something like: "xblock.v1:problem:area_of_circle_1"
        namespace, type_name, local_key = component_key.split(":", 2)
        component = get_component_by_key(
            learning_package.id, namespace, type_name, local_key
        )

        created = datetime.now(tz=timezone.utc)
        keys_to_remove = set()
        local_keys_to_content = {}

        for file_mapping in file_mappings:
            local_key, file_path = file_mapping.split(":", 1)

            # No file_path means to delete this entry from the next version.
            if not file_path:
                keys_to_remove.add(local_key)
                continue

            media_type_str, _encoding = mimetypes.guess_type(file_path)
            media_type = get_or_create_media_type(media_type_str)
            content = get_or_create_file_content(
                learning_package.id,
                media_type.id,
                data=pathlib.Path(file_path).read_bytes(),
                created=created,
            )
            local_keys_to_content[local_key] = content.id

        next_version = create_next_component_version(
            component.pk,
            content_to_replace={local_key: None for local_key in keys_to_remove},
            created=created,
        )
        for local_key, content_id in sorted(local_keys_to_content.items()):
            create_component_version_content(
                next_version.pk,
                content_id,
                key=local_key,
                learner_downloadable=True,
            )

        self.stdout.write(
            f"Created v{next_version.version_num} of "
            f"{next_version.component.key} ({next_version.uuid}):"
        )
        for cvc in next_version.componentversioncontent_set.all():
            self.stdout.write(f"- {cvc.key} ({cvc.uuid})")
