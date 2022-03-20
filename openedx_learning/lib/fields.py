"""
Convenience functions to make consistent field conventions easier.
"""
import uuid

from django.db import models


def identifier_field(*, unique):
    return models.CharField(
        max_length=255,
        blank=False,
        null=False,

        unique=unique,
    )

def immutable_uuid_field():
    return models.UUIDField(
        default=uuid.uuid4,
        blank=False,
        null=False,
        editable=False,
        unique=True,
    )

def hash_field(*, unique):
    return models.CharField(
        max_length=40,
        blank=False,
        null=False,
        editable=False,
        unique=unique,
    )