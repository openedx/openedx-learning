"""
Low Level Contents API (warning: UNSTABLE, in progress API)

Please look at the models.py file for more information about the kinds of data
are stored in this app.
"""
from __future__ import annotations

import codecs
from datetime import datetime

from django.core.files.base import ContentFile
from django.db.transaction import atomic

from openedx_learning.lib.cache import lru_cache
from openedx_learning.lib.fields import create_hash_digest

from .models import MediaType, RawContent, TextContent


def create_raw_content(
    learning_package_id: int,
    /,
    data_bytes: bytes,
    mime_type: str,
    created: datetime,
    hash_digest: str | None = None,
) -> RawContent:
    """
    Create a new RawContent instance and persist it to storage.
    """
    hash_digest = hash_digest or create_hash_digest(data_bytes)

    raw_content = RawContent.objects.create(
        learning_package_id=learning_package_id,
        media_type_id=get_media_type_id(mime_type),
        hash_digest=hash_digest,
        size=len(data_bytes),
        created=created,
    )
    raw_content.file.save(
        f"{raw_content.learning_package.uuid}/{hash_digest}",
        ContentFile(data_bytes),
    )
    return raw_content


def create_text_from_raw_content(raw_content: RawContent, encoding="utf-8-sig") -> TextContent:
    """
    Create a new TextContent instance for the given RawContent.
    """
    text = codecs.decode(raw_content.file.open().read(), encoding)
    return TextContent.objects.create(
        raw_content=raw_content,
        text=text,
        length=len(text),
    )


@lru_cache(maxsize=128)
def get_media_type_id(mime_type: str) -> int:
    """
    Return the MediaType.id for the desired mime_type string.

    If it is not found in the database, a new entry will be created for it. This
    lazy-writing means that MediaType entry IDs will *not* be the same across
    different server instances, and apps should not assume that will be the
    case. Even if we were to preload a bunch of common ones, we can't anticipate
    the different XBlocks that will be installed in different server instances,
    each of which will use their own MediaType.

    This will typically only be called when create_raw_content is calling it to
    lookup the media_type_id it should use for a new RawContent. If you already
    have a RawContent instance, it makes much more sense to access its
    media_type relation.
    """
    if "+" in mime_type:
        base, suffix = mime_type.split("+")
    else:
        base = mime_type
        suffix = ""

    main_type, sub_type = base.split("/")
    mt, _created = MediaType.objects.get_or_create(
        type=main_type,
        sub_type=sub_type,
        suffix=suffix,
    )

    return mt.id


def get_or_create_raw_content(
    learning_package_id: int,
    /,
    data_bytes: bytes,
    mime_type: str,
    created: datetime,
    hash_digest: str | None = None,
) -> tuple[RawContent, bool]:
    """
    Get the RawContent in the given learning package with the specified data,
    or create it if it doesn't exist.
    """
    hash_digest = hash_digest or create_hash_digest(data_bytes)
    try:
        raw_content = RawContent.objects.get(
            learning_package_id=learning_package_id, hash_digest=hash_digest
        )
        was_created = False
    except RawContent.DoesNotExist:
        raw_content = create_raw_content(
            learning_package_id, data_bytes, mime_type, created, hash_digest
        )
        was_created = True

    return raw_content, was_created


def get_or_create_text_content_from_bytes(
    learning_package_id: int,
    /,
    data_bytes: bytes,
    mime_type: str,
    created: datetime,
    hash_digest: str | None = None,
    encoding: str = "utf-8-sig",
):
    """
    Get the TextContent in the given learning package with the specified data,
    or create it if it doesn't exist.
    """
    with atomic():
        raw_content, rc_created = get_or_create_raw_content(
            learning_package_id, data_bytes, mime_type, created, hash_digest
        )
        if rc_created or not hasattr(raw_content, "text_content"):
            text = codecs.decode(data_bytes, encoding)
            text_content = TextContent.objects.create(
                raw_content=raw_content,
                text=text,
                length=len(text),
            )
            tc_created = True
        else:
            text_content = raw_content.text_content
            tc_created = False

        return (text_content, tc_created)
