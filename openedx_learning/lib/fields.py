"""
Convenience functions to make consistent field conventions easier.

Field conventions:

* Per OEP-38, we're using the MySQL-friendly convention of BigInt ID as a
  primary key + separtate UUID column.

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
import uuid

from django.db import models


def identifier_field():
    return models.CharField(
        max_length=255,
        blank=False,
        null=False,
    )

def immutable_uuid_field():
    return models.UUIDField(
        default=uuid.uuid4,
        blank=False,
        null=False,
        editable=False,
        unique=True,
    )

def hash_field():
    return models.CharField(
        max_length=40,
        blank=False,
        null=False,
        editable=False,
    )