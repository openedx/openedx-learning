"""
Low Level Contents API (warning: UNSTABLE, in progress API)

Please look at the models.py file for more information about the kinds of data
are stored in this app.
"""
import codecs

from django.core.files.base import ContentFile
from django.db.transaction import atomic

from openedx_learning.lib.fields import create_hash_digest
from .models import RawContent, TextContent


def create_raw_content(
    learning_package_id, data_bytes, mime_type, created, hash_digest=None
):
    hash_digest = hash_digest or create_hash_digest(data_bytes)
    raw_content = RawContent.objects.create(
        learning_package_id=learning_package_id,
        mime_type=mime_type,
        hash_digest=hash_digest,
        size=len(data_bytes),
        created=created,
    )
    raw_content.file.save(
        f"{raw_content.learning_package.uuid}/{hash_digest}",
        ContentFile(data_bytes),
    )
    return raw_content


def create_text_from_raw_content(raw_content, encoding="utf-8-sig"):
    text = codecs.decode(raw_content.file.open().read(), "utf-8-sig")
    return TextContent.objects.create(
        raw_content=raw_content,
        text=text,
        length=len(text),
    )


def get_or_create_raw_content(
    learning_package_id, data_bytes, mime_type, created, hash_digest=None
):
    hash_digest = hash_digest or create_hash_digest(data_bytes)
    try:
        raw_content = RawContent.objects.get(
            learning_package_id=learning_package_id, hash_digest=hash_digest
        )
        created = False
    except RawContent.DoesNotExist:
        raw_content = create_raw_content(
            learning_package_id, data_bytes, mime_type, created, hash_digest
        )
        created = True

    return raw_content, created


def get_or_create_text_content_from_bytes(
    learning_package_id,
    data_bytes,
    mime_type,
    created,
    hash_digest=None,
    encoding="utf-8-sig",
):
    with atomic():
        raw_content, rc_created = get_or_create_raw_content(
            learning_package_id, data_bytes, mime_type, created, hash_digest=None
        )
        if rc_created or not hasattr(raw_content, "text_content"):
            text = codecs.decode(data_bytes, "utf-8-sig")
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
