"""
Quick and hacky management command to dump course data into our model for
experimentation purposes.

This should live in its own app, since it will likely need to understand
different apps.
"""
from collections import defaultdict, Counter
import codecs
import hashlib
import json
import logging
import mimetypes
import pathlib
import random
import re
import string
import sys
import xml.etree.ElementTree as ET

from django.core.management.base import BaseCommand, CommandError

from ...models import (
    BlockType,
    ContentAtom,
    ContentObject,
    ContentObjectPart,
    ContentPackage,
    ContentSegment,
    LearningContext,
    LearningContextVersion,
)

SUPPORTED_TYPES = ['lti', 'problem', 'video']
logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Load sample data'

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.learning_context = None
        self.content_package = None

        # Intialize mimetypes with some custom values:
        mimetypes.add_type("application/x-srt+json", ".sjson")
        mimetypes.add_type("text/markdown", ".md")

    def add_arguments(self, parser):
        parser.add_argument('course_data_path', type=pathlib.Path)

    def handle(self, course_data_path, **options):
        logger.warning("Resetting database before data load.")
        self.reset_data()
        self.load_course_data(course_data_path)

    def reset_data(self):
        """Big hammer reset for testing purposes."""
        ContentSegment.objects.all().delete()
        ContentObjectPart.objects.all().delete()
        ContentObject.objects.all().delete()
        ContentAtom.objects.all().delete()

        # Just this should be sufficient to delete most things, right?
        ContentPackage.objects.all().delete()

        LearningContextVersion.objects.all().delete()
        LearningContext.objects.all().delete()
        BlockType.objects.all().delete()

    def load_course_data(self, course_data_path):
        learning_context, _created = LearningContext.objects.get_or_create(identifier="big-sample-course")
        self.learning_context = learning_context
        
        # Interesting, how do we tie it back to an existing content_package without using some kind of ID scheme?
        # This only works for now because we always reset.
        content_package = ContentPackage.objects.create(learning_context=learning_context)
        self.content_package = content_package

        static_asset_paths_to_atom_ids = self.import_static_assets(course_data_path)

        print(f"Importing course from: {course_data_path}")
        for block_type in SUPPORTED_TYPES:
            self.import_block_type(
                block_type,
                course_data_path / block_type,
                static_asset_paths_to_atom_ids,
            )


    def import_static_assets(self, course_data_path):
        IGNORED_NAMES = [".DS_Store"]
        static_assets_path = course_data_path / "static"
        file_paths = (
            fp for fp in static_assets_path.glob("**/*")
            if fp.is_file() and fp.stem not in IGNORED_NAMES
        )

        num_files = 0
        cum_size = 0
        mime_types_seen = Counter()
        paths_to_atom_ids = {}
        longest_identifier_len = 0
        print("")

        for file_path in file_paths:
            identifier = str(file_path.relative_to(course_data_path))
            longest_identifier_len = max(longest_identifier_len, len(str(identifier)))

            data_bytes = file_path.read_bytes()

            num_files += 1
            cum_size += len(data_bytes)
            print(f"Static file #{num_files}: ({(cum_size / 1_000_000):.2f} MB)", end="\r")

            data_hash = hashlib.blake2b(data_bytes, digest_size=20).hexdigest()
            if file_path.suffix == "":
                mime_type = "text/plain"
            else:
                mime_type, _encoding = mimetypes.guess_type(identifier)
            
            mime_types_seen[mime_type] += 1

            if mime_type is None:
                print(identifier)

            text_data, json_data, bin_data = parse_data(mime_type, data_bytes)

            atom, _created = ContentAtom.objects.get_or_create(
                content_package=self.content_package,
                hash_digest=data_hash,
                defaults={
                    'mime_type': mime_type,
                    'text_data': text_data,
                    'json_data': json_data,
                    'bin_data': bin_data,
                    'size': len(next(data for data in [text_data, json_data, bin_data] if data is not None))
                }
            )
            paths_to_atom_ids[identifier] = atom.id

        print(f"{num_files} assets, totaling {(cum_size / 1_000_000):.2f} MB")
        print(f"Longest identifier length seen: {longest_identifier_len}")
        print("MIME types seen:")
        for mime_type_str, freq in sorted(mime_types_seen.items()):
            print(f"* {mime_type_str}: {freq}")

        #print(list(paths_to_atom_ids.items())[:10])
        #sys.exit()

        return paths_to_atom_ids


    def import_block_type(self, block_type, content_path, static_asset_paths_to_atom_ids):
        block_type, _created = BlockType.objects.get_or_create(major="atom", minor=f"xblock-{block_type}")
        block_type_id = block_type.id
        items_found = 0

        # Find everything that looks like a reference to a static file appearing
        # in attribute quotes, stripping off the querystring at the end. This is
        # not fool-proof as it will match static file references that are
        # outside of tag declarations as well.
        static_files_regex = r"""['"]\/static\/(.+?)["'\?]"""

        for xml_file_path in content_path.iterdir():
            items_found += 1
            identifier = xml_file_path.stem
            data_bytes = xml_file_path.read_bytes()
            data_hash = hashlib.blake2b(data_bytes, digest_size=20).hexdigest()
            data_str = codecs.decode(data_bytes, 'utf-8')
            modified = xml_file_path.stat().st_mtime

            try:
                root_el = ET.fromstring(data_str)
                title = root_el.attrib.get('display_name', '')
            except ET.ParseError as err:
                title = ''
                logger.error(f"Could not parse XML for {xml_file_path}: {err}")

            # This logic is not really working properly for incremental updates,
            # (BlockVersions aren't properly incremented for one).
            #
            # But even this really naive algorithm loads a 2200 block course in
            # about 8 seconds locally, with 2 seconds being used in reads (both
            # file and database) and 6 seconds in database writes.

            # TODOs:
            #    Create segment, Create Atoms, Create ContentObjectParts

            # We're playing fast and loose with identifier scoping here.
            # TODO: Should be unique by type?
            segment = ContentSegment.objects.create(identifier=identifier)
            content_obj = ContentObject.objects.create(content_segment=segment, segment_order_num=0)

            atom, _created = ContentAtom.objects.get_or_create(
                content_package=self.content_package,
                hash_digest=data_hash,
                defaults={
                    'text_data': data_str,
                    'size': len(data_bytes),  # TODO: Should this be the length of the string instead?
                    'mime_type': 'application/x+xblock',
                },
            )
            ContentObjectPart.objects.create(content_object=content_obj, content_atom=atom, identifier=identifier)
            static_file_paths = frozenset(
                f"static/{static_reference_path}"
                for static_reference_path in re.findall(static_files_regex, data_str)    
            )
            for static_file_path in static_file_paths:
                if static_file_path in static_asset_paths_to_atom_ids:
                    atom_id = static_asset_paths_to_atom_ids[static_file_path]
                    ContentObjectPart.objects.create(content_object=content_obj, content_atom_id=atom_id, identifier=static_file_path)
            """
            lcb, _created = LearningContextBlock.objects.get_or_create(
                learning_context_id=learning_context_id,
                identifier=identifier,
                defaults={'block_type_id': block_type_id},
            )
            bc, _created = BlockContent.objects.get_or_create(
                learning_context_id=learning_context_id,
                hash_digest=data_hash.hex(),
                defaults={'data': data_str}
            )
            bv, _created = BlockVersion.objects.get_or_create(
                block_id=lcb.id,
                content_id=bc.id,
                defaults={'start_version_num': 0, 'title': title},
            )
            """
            # print(f"{identifier}\t {title}: {len(data)}")

        print(f"{block_type}: {items_found}")


def content_atom_exists(hash_digest):
    return ContentAtom.objects.filter(hash_digest=hash_digest).exists()

def is_json_type(mime_type):
    return mime_type.endswith("json")

def is_text_type(mime_type):
    return (
        mime_type.startswith("text/") or
        (mime_type in ["application/javascript", "application/x-subrip"])
    )

def parse_data(mime_type, data_bytes):
    if is_json_type(mime_type):
        return (None, json.loads(data_bytes), None)

    if is_text_type(mime_type):
        text_data = codecs.decode(data_bytes, 'utf-8')
        return (text_data, None, None)
    
    return (None, None, data_bytes)
