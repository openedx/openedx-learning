"""
Quick and hacky management command to dump course data into our model for
experimentation purposes. This lives in its own app because it's not intended to
be a part of this repo in the longer term. Think of this as just an example app
to validate the data model can do what we need it to do.

This script manipulates the data models directly, instead of using stable API
calls. This is only because those APIs haven't been created yet, and this is
trying to validate basic questions about the data model. This is not how apps
are intended to use openedx-learning in the longer term.

Open Question: If the data model is extensible, how do we know whether a change
has really happened between what's currently stored/published for a particular
item and the new value we want to set? For Content that's easy, because we have
actual hashes of the data. But it's not clear how that would work for something
like an ComponentVersion. We'd have to have some kind of mechanism where every app
that wants to attach data gets to answer the question of "has anything changed?"
in order to decide if we really make a new ComponentVersion or not.
"""
from collections import defaultdict, Counter
from datetime import datetime, timezone
import codecs
import logging
import mimetypes
import pathlib
import xml.etree.ElementTree as ET

from django.core.management.base import BaseCommand
from django.db import transaction

from openedx_learning.contrib.staticassets.models import Asset, ComponentVersionAsset
from openedx_learning.core.publishing.models import (
    LearningPackage, LearningPackageVersion
)
from openedx_learning.core.components.models import (
    Content, Component, ComponentVersion, LearningPackageVersionComponentVersion
)
from openedx_learning.lib.fields import create_hash_digest

SUPPORTED_TYPES = ['lti', 'problem', 'video']
logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Load sample data'

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.learning_package = None
        self.init_known_types()

    def init_known_types(self):
        """Intialize mimetypes with some custom mappings we want to use."""
        mimetypes.add_type("application/vnd.openedx.srt+json", ".sjson")
        mimetypes.add_type("text/markdown", ".md")

    def add_arguments(self, parser):
        parser.add_argument('learning_package_identifier', type=str)
        parser.add_argument('course_data_path', type=pathlib.Path)

    def handle(self, learning_package_identifier, course_data_path, **options):
        self.learning_package_identifier = learning_package_identifier
        self.load_course_data(learning_package_identifier, course_data_path)

    def load_course_data(self, learning_package_identifier, course_data_path):
        print(f"Importing course from: {course_data_path}")
        now = datetime.now(timezone.utc)

        with transaction.atomic():
            learning_package, _created = LearningPackage.objects.get_or_create(
                identifier=learning_package_identifier,
                defaults={'created': now},
            )
            self.learning_package = learning_package

            # For now, create always create a new LearningPackageVersion (in the
            # future, we need to be careful about detecting changes).
            self.new_lcv = LearningPackageVersion.objects.create(
                learning_package=learning_package,
                prev_version=None,
                created=now,
            )

            # Future Note:
            #   Make the static asset loading happen after XBlock loading
            #   Make the static asset piece grep through created content.
            existing_item_raws = Content.objects \
                                     .filter(learning_package=learning_package) \
                                     .values_list('id', 'type', 'sub_type', 'hash_digest')
            item_raw_id_cache = {
                (f"{type}/{sub_type}", hash_digest): item_raw_id
                for item_raw_id, type, sub_type, hash_digest in existing_item_raws
            }

            static_asset_paths_to_atom_ids = {}

#            static_asset_paths_to_atom_ids = self.import_static_assets(
#                course_data_path,
#                item_raw_id_cache,
#                now,
#            )

            for block_type in SUPPORTED_TYPES:
                self.import_block_type(
                    block_type,
                    course_data_path / block_type,
                    static_asset_paths_to_atom_ids,
                    item_raw_id_cache,
                    now,
                )


    def import_static_assets(self, course_data_path, item_raw_id_cache, now):
        IGNORED_NAMES = [".DS_Store"]
        static_assets_path = course_data_path / "static"
        file_paths = (
            fp for fp in static_assets_path.glob("**/*")
            if fp.is_file() and fp.stem not in IGNORED_NAMES
        )

        num_files = 0
        cum_size = 0
        mime_types_seen = Counter()
        paths_to_item_raw_ids = {}
        longest_identifier_len = 0
        print("Reading static assets...\n")

        for file_path in file_paths:
            identifier = str(file_path.relative_to(course_data_path))
            longest_identifier_len = max(longest_identifier_len, len(str(identifier)))

            data_bytes = file_path.read_bytes()

            num_files += 1
            cum_size += len(data_bytes)
            print(f"Static file #{num_files}: ({(cum_size / 1_000_000):.2f} MB)", end="\r")

            data_hash = create_hash_digest(data_bytes)
            if file_path.suffix == "":
                mime_type = "text/plain"
            else:
                mime_type, _encoding = mimetypes.guess_type(identifier)

            mime_types_seen[mime_type] += 1

            if mime_type is None:
                print(identifier)

            item_raw_id = item_raw_id_cache.get((mime_type, data_hash))
            if item_raw_id is None:
                type, sub_type = mime_type.split('/')
                item_raw, _created = Content.objects.get_or_create(
                    learning_package=self.learning_package,
                    type=type,
                    sub_type=sub_type,
                    hash_digest=data_hash,
                    defaults={
                        'data': data_bytes,
                        'size': len(data_bytes),
                        'created': now,
                    }
                )
                item_raw_id = item_raw.id

            paths_to_item_raw_ids[identifier] = item_raw_id

        print(f"{num_files} assets, totaling {(cum_size / 1_000_000):.2f} MB")
        print(f"Longest identifier length seen: {longest_identifier_len}")
        print("MIME types seen:")
        for mime_type_str, freq in sorted(mime_types_seen.items()):
            print(f"* {mime_type_str}: {freq}")

        return paths_to_item_raw_ids


    def import_block_type(self, block_type, content_path, static_asset_paths_to_atom_ids, item_raw_id_cache, now):
        components_found = 0

        # Find everything that looks like a reference to a static file appearing
        # in attribute quotes, stripping off the querystring at the end. This is
        # not fool-proof as it will match static file references that are
        # outside of tag declarations as well.
        static_files_regex = r"""['"]\/static\/(.+?)["'\?]"""

        for xml_file_path in content_path.iterdir():
            components_found += 1
            identifier = xml_file_path.stem

            # Find or create the Item itself
            component, _created = Component.objects.get_or_create(
                learning_package=self.learning_package,
                namespace='xblock.v1',
                type=block_type,
                identifier=identifier,
                defaults = {
                    'created': now,
                    'modified': now,
                }
            )

            # Create the Content entry for the raw data...
            data_bytes = xml_file_path.read_bytes()
            hash_digest = create_hash_digest(data_bytes)
            data_str = codecs.decode(data_bytes, 'utf-8')
            content, _created = Content.objects.get_or_create(
                learning_package=self.learning_package,
                type='application',
                sub_type=f'vnd.openedx.xblock.v1.{block_type}+xml',
                hash_digest=hash_digest,
                defaults = dict(
                    data=data_bytes,
                    size=len(data_bytes),
                    created=now,
                )
            )

            try:
                block_root = ET.fromstring(data_str)
            except ET.ParseError as err:
                logger.error(f"Parse error for {xml_file_path}: {err}")
                continue

            display_name = block_root.attrib.get('display_name', "")

            # Create the ComponentVersion
            component_version = ComponentVersion.objects.create(
                component=component,
                # title=display_name,
                created=now,
            )
            component_version.contents.add(content)

            LearningPackageVersionComponentVersion.objects.create(
                learning_package_version=self.new_lcv,
                component_version=component_version,
                component=component,
            )

        print(f"{block_type}: {components_found}")
