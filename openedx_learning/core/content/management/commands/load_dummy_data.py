"""
Seed some sample data.

This is going to use some model code directly for now.
"""
from datetime import datetime, timezone
import logging
import textwrap

from django.core.management.base import BaseCommand
from django.db import transaction

import yaml

from openedx_learning.contrib.staticassets.models import Asset, ComponentVersionAsset
from openedx_learning.core.publishing.models import (
    LearningContext, LearningContextVersion
)
from openedx_learning.core.content.models import (
    Content, Component, ComponentVersion, LearningContextVersionComponentVersion,
    Item, ItemVersion
)
from openedx_learning.lib.fields import create_hash_digest

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Load dummy sample data'

    def handle(self, **options):
        learning_context_identifier = "dummy_library"
        now = datetime.now(timezone.utc)

        with transaction.atomic():
            lc = LearningContext.objects.create(
                identifier=learning_context_identifier,
                title="Dummy Library",
                created=now,
                updated=now,
            )
            video_item = create_video_item(lc, now)


def create_video_item(learning_context, now):
    video_item = Item.objects.create(
        learning_context=learning_context,
        identifier="intro_video",
        created=now,
        modified=now,
    )
    video_comp = Component.objects.create(
        learning_context=learning_context,
        namespace='xblock.v1',
        type='video',
        identifier='intro',
        created=now,
        modified=now,
    )
    video_xml_bytes = textwrap.dedent("""
        <video youtube="1.00:M-ckUWBp63w"
               url_name="23ceff0221674298a4410bc2174a86a2"
               display_name="Learning Core Intro"
               edx_video_id=""
               html5_sources="[]"
               youtube_id_1_0="M-ckUWBp63w"/>
    """).encode('utf-8')
    video_cont = Content.objects.create(
        learning_context=learning_context,

        type="application",
        sub_type="vnd.openedx.xblock.v1.video+xml",
    )


    return video_item
