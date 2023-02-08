"""
Convenience functions to make consistent field conventions easier.

Field conventions:

* Per OEP-38, we're using the MySQL-friendly convention of BigInt ID as a
  primary key + separate UUID column.
https://open-edx-proposals.readthedocs.io/en/latest/best-practices/oep-0038-Data-Modeling.html

TODO:
* Try making a CaseSensitiveCharField and CaseInsensitiveCharField
* Investigate more efficient UUID binary encoding + search in MySQL

Other data thoughts:
* It would be good to make a data-dumping sort of script that exported part of
  the data to SQLite3.
* identifiers support stable import/export with serialized formats
* UUIDs will import/export in the SQLite3 dumps, but are not there in other contexts
"""
import hashlib
import uuid

from django.db import models


def identifier_field():
    """
    Externally created Identifier fields.

    These will often be local to a particular scope, like within a
    LearningPackage. It's up to the application as to whether they're
    semantically meaningful or look more machine-generated.

    Other apps should *not* make references to these values directly, since
    these values may in theory change.
    """
    return models.CharField(
        max_length=255,
        blank=False,
        null=False,
    )


def immutable_uuid_field():
    """
    Stable, randomly-generated UUIDs.

    These can be used as stable identifiers by other services that do not share
    a database, but you should prefer to make a ForeignKey to the primary (id)
    key of the model if you're in the same process.
    """
    return models.UUIDField(
        default=uuid.uuid4,
        blank=False,
        null=False,
        editable=False,
        unique=True,
        verbose_name="UUID",  # Just makes the Django admin output properly capitalized
    )


def hash_field():
    """
    Holds a hash digest meant to identify a piece of content.

    Do not assume that this is secure or globally unique. Accidental collisions
    are extremely unlikely, but we don't want to get into a place where someone
    can maliciously craft a collision and affect other users.

    Use the create_hash_digest function to generate data suitable for this
    field.
    """
    return models.CharField(
        max_length=40,
        blank=False,
        null=False,
        editable=False,
    )


def create_hash_digest(data_bytes):
    return hashlib.blake2b(data_bytes, digest_size=20).hexdigest()


def manual_date_time_field():
    """
    DateTimeField that does not auto-generate values.

    The reason for this convention is that we are often creating many rows of
    data in the same transaction. They are semantically being created or
    modified "at the same time", even if each individual row is milliseconds
    apart. This convention forces the caller to set a datetime up front and pass
    it in manually, so all the affected rows have the exact same time. This
    makes it easier to see which rows were changed at the same time more easily.

    When using these fields, the other conventions from OEP-38 still hold:

    * common field names: created, modified
    * Django's USE_TZ setting should be True
    * Times should be in UTC as a general rule
    """
    return models.DateTimeField(
        auto_now=False,
        auto_now_add=False,
        null=False,
    )
