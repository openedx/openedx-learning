"""
Quick and hacky management command to dump Component data into our model for
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
like an ComponentVersion. We'd have to have some kind of mechanism where every 
pp that wants to attach data gets to answer the question of "has anything
changed?" in order to decide if we really make a new ComponentVersion or not.
"""
from datetime import datetime, timezone
import codecs
import logging
import mimetypes
import pathlib
import xml.etree.ElementTree as ET

from django.core.management.base import BaseCommand
from django.db import transaction

from openedx_learning.core.publishing.models import LearningPackage, PublishLogEntry
from openedx_learning.core.components.models import (
    Content, Component, ComponentVersion,
    ComponentPublishLogEntry, PublishedComponent,
)
from openedx_learning.lib.fields import create_hash_digest

SUPPORTED_TYPES = ['problem', 'video', 'html']
logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Load sample Component data from course export'

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

    def get_course_title(self, course_data_path):
        course_type_dir = course_data_path / 'course'
        course_xml_file = next(course_type_dir.glob('*.xml'))
        course_root = ET.parse(course_xml_file).getroot()
        return course_root.attrib.get("display_name", "Unknown Course")

    def load_course_data(self, learning_package_identifier, course_data_path):
        print(f"Importing course from: {course_data_path}")
        now = datetime.now(timezone.utc)
        title = self.get_course_title(course_data_path)

        with transaction.atomic():
            learning_package, _created = LearningPackage.objects.get_or_create(
                identifier=learning_package_identifier,
                defaults={
                    'title': title,
                    'created': now,
                    'updated': now,
                },
            )
            self.learning_package = learning_package

            publish_log_entry = PublishLogEntry.objects.create(
                learning_package=learning_package,
                message="Initial Import",
                published_at=now,
                published_by=None,
            )

            for block_type in SUPPORTED_TYPES:
                self.import_block_type(
                    block_type,
                    course_data_path / block_type,
                    now,
                    publish_log_entry,
                )

    def import_block_type(self, block_type, content_path, now, publish_log_entry):
        components_found = 0

        # Find everything that looks like a reference to a static file appearing
        # in attribute quotes, stripping off the querystring at the end. This is
        # not fool-proof as it will match static file references that are
        # outside of tag declarations as well.
        static_files_regex = r"""['"]\/static\/(.+?)["'\?]"""

        for xml_file_path in content_path.glob('*.xml'):
            components_found += 1
            identifier = xml_file_path.stem

            # Find or create the Component itself
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
                created=now,
                version_num=1,  # This only works for initial import
                title=display_name,
            )
            component_version.contents.add(content)

            # Mark that Component as Published
            component_publish_log_entry = ComponentPublishLogEntry.objects.create(
                component=component,
                component_version=component_version,
                publish_log_entry=publish_log_entry,
            )
            PublishedComponent.objects.create(
                component=component,
                component_version=component_version,
                component_publish_log_entry=component_publish_log_entry,
            )

        print(f"{block_type}: {components_found}")
