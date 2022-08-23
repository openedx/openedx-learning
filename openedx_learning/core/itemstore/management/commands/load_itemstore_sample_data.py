"""
Seed some sample data.
"""
from datetime import datetime, timezone
import logging

from django.core.management.base import BaseCommand
from django.db import transaction

import yaml

from openedx_learning.contrib.staticassets.models import Asset, ComponentVersionAsset
from openedx_learning.core.publishing.models import (
    LearningContext, LearningContextVersion
)
from openedx_learning.core.itemstore.models import (
    Content, Component, ComponentVersion, LearningContextVersionComponentVersion
)
from openedx_learning.lib.fields import create_hash_digest

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Load sample data'

    def add_arguments(self, parser):
        parser.add_argument('learning_context_identifier', type=str)
        parser.add_argument('itemstore_yaml_file', type=open)

    def handle(self, learning_context_identifier, itemstore_yaml_file, **options):
        self.learning_context_identifier = learning_context_identifier
        now = datetime.now(timezone.utc)
        lc = LearningContext.objects.get_or_create(
            identifier=learning_context_identifier,
            defaults={'created': now},
        )
        load_itemstore_data(itemstore_yaml_file, lc)


def load_itemstore_data(itemstore_yaml_file, learning_context):
    data = yaml.safe_load(itemstore_yaml_file)
    for identifier, item_data in data['items'].items():
        pass


    print(data)

