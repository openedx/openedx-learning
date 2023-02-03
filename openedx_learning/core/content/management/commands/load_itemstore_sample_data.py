"""
Seed some sample data.

This is going to use some model code directly for now.
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
    Content, Component, ComponentVersion, LearningContextVersionComponentVersion,
    Item, ItemVersion
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

        with transaction.atomic():
            lc = LearningContext.objects.get_or_create(
                identifier=learning_context_identifier,
                title="Placeholder Title",
                defaults={
                    'created': now,
                    'updated': now,
                },
            )
            load_itemstore_data(itemstore_yaml_file, lc, now)


def load_itemstore_data(itemstore_yaml_file, learning_context, now):
    data = yaml.safe_load(itemstore_yaml_file)
    for identifier, item_data in data['items'].items():
        create_or_update_item(learning_context, identifier, item_data, now)


def create_or_update_item(learning_context, identifier, item_data, now):
    item, created = Item.objects.get_or_create(
        learning_context=learning_context,
        identifier=identifier,
        defaults={
            'created': now,
            'updated': now,
        }
    )

def create_or_update_copmonent(learning_context, identifier, component_data):
    pass

def create_or_update_content(learing_context, identifier, content_data):
    pass


