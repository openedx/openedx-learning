"""
These models are the most basic pieces of content we support. Think of them as
the simplest building blocks to store data with. They need to be composed into
more intelligent data models to be useful.
"""
from django.conf import settings
from django.core.files.storage import default_storage
from django.core.validators import MaxValueValidator
from django.db import models

from openedx_learning.lib.fields import (
    MultiCollationTextField,
    case_insensitive_char_field,
    hash_field,
    manual_date_time_field,
)

from ..publishing.models import LearningPackage


class RawContent(models.Model):  # type: ignore[django-manager-missing]
    """
    This is the most basic piece of raw content data, with no version metadata.

    RawContent stores data using the "file" field. This data is not
    auto-normalized in any way, meaning that pieces of content that are
    semantically equivalent (e.g. differently spaced/sorted JSON) may result in
    new entries. This model is intentionally ignorant of what these things mean,
    because it expects supplemental data models to build on top of it.

    Two RawContent instances _can_ have the same hash_digest if they are of
    different MIME types. For instance, an empty text file and an empty SRT file
    will both hash the same way, but be considered different entities.

    The other fields on RawContent are for data that is intrinsic to the file
    data itself (e.g. the size). Any smart parsing of the contents into more
    structured metadata should happen in other models that hang off of
    RawContent.

    RawContent models are not versioned in any way. The concept of versioning
    only exists at a higher level.

    RawContent is optimized for cheap storage, not low latency. It stores
    content in a FileField. If you need faster text access across multiple rows,
    add a TextContent entry that corresponds to the relevant RawContent.

    If you need to transform this RawContent into more structured data for your
    application, create a model with a OneToOneField(primary_key=True)
    relationship to RawContent. Just remember that *you should always create the
    RawContent entry* first, to ensure content is always exportable, even if
    your app goes away in the future.

    Operational Notes
    -----------------

    RawContent stores data using a FileField, which you'd typically want to back
    with something like S3 when running in a production environment. That file
    storage backend will not support rollback, meaning that if you start the
    import process and things break halfway through, the RawContent model rows
    will be rolled back, but the uploaded files will still remain on your file
    storage system. The files are based on a hash of the contents though, so it
    should still work later on when the import succeeds (it'll just have to
    upload fewer files).

    TODO: Write about cleaning up accidental uploads of really large/unnecessary
    files. Pruning of unreferenced (never published, or currently unused)
    component versions and assets, and how that ties in?
    """

    # 50 MB is our current limit, based on the current Open edX Studio file
    # upload size limit.
    MAX_FILE_SIZE = 50_000_000

    learning_package = models.ForeignKey(LearningPackage, on_delete=models.CASCADE)

    # This hash value may be calculated using create_hash_digest from the
    # openedx.lib.fields module.
    hash_digest = hash_field()

    # MIME type, such as "text/html", "image/png", etc. Per RFC 4288, MIME type
    # and sub-type may each be 127 chars, making a max of 255 (including the "/"
    # in between). Also, while MIME types are almost always written in lowercase
    # as a matter of convention, by spec they are NOT case sensitive.
    #
    # DO NOT STORE parameters here, e.g. "charset=". We can make a new field if
    # that becomes necessary. If we do decide to store parameters and values
    # later, note that those *may be* case sensitive.
    mime_type = case_insensitive_char_field(max_length=255, blank=False)

    # This is the size of the raw data file in bytes. This can be different than
    # the character length, since UTF-8 encoding can use anywhere between 1-4
    # bytes to represent any given character.
    size = models.PositiveBigIntegerField(
        validators=[MaxValueValidator(MAX_FILE_SIZE)],
    )

    # This should be manually set so that multiple RawContent rows being set in
    # the same transaction are created with the same timestamp. The timestamp
    # should be UTC.
    created = manual_date_time_field()

    # All content for the LearningPackage should be stored in files. See model
    # docstring for more details on how to store this data in supplementary data
    # models that offer better latency guarantees.
    file = models.FileField(
        null=True,
        storage=settings.OPENEDX_LEARNING.get("STORAGE", default_storage),  # type: ignore
    )

    class Meta:
        constraints = [
            # Make sure we don't store duplicates of this raw data within the
            # same LearningPackage, unless they're of different MIME types.
            models.UniqueConstraint(
                fields=[
                    "learning_package",
                    "mime_type",
                    "hash_digest",
                ],
                name="oel_content_uniq_lc_mime_type_hash_digest",
            ),
        ]
        indexes = [
            # LearningPackage MIME type Index:
            #   * Break down Content counts by type/subtype with in a
            #     LearningPackage.
            #   * Find all the Content in a LearningPackage that matches a
            #     certain MIME type (e.g. "image/png", "application/pdf".
            models.Index(
                fields=["learning_package", "mime_type"],
                name="oel_content_idx_lp_mime_type",
            ),
            # LearningPackage (reverse) Size Index:
            #   * Find largest Content in a LearningPackage.
            #   * Find the sum of Content size for a given LearningPackage.
            models.Index(
                fields=["learning_package", "-size"],
                name="oel_content_idx_lp_rsize",
            ),
            # LearningPackage (reverse) Created Index:
            #   * Find most recently added Content.
            models.Index(
                fields=["learning_package", "-created"],
                name="oel_content_idx_lp_rcreated",
            ),
        ]
        verbose_name = "Raw Content"
        verbose_name_plural = "Raw Contents"


class TextContent(models.Model):
    """
    TextContent supplements RawContent to give an in-table text copy.

    This model exists so that we can have lower-latency access to this data,
    particularly if we're pulling back multiple rows at once.

    Apps are encouraged to create their own data models that further extend this
    one with a more intelligent, parsed data model. For example, individual
    XBlocks might parse the OLX in this model into separate data models for
    VideoBlock, ProblemBlock, etc. You can do this by making your supplementary
    model linked to this model via OneToOneField with primary_key=True.

    The reason this is built directly into the Learning Core data model is
    because we want to be able to easily access and browse this data even if the
    app-extended models get deleted (e.g. if they are deprecated and removed).
    """

    # 100K is our limit for text data, like OLX. This means 100K *characters*,
    # not bytes. Since UTF-8 encodes characters using as many as 4 bytes, this
    # could be as much as 400K of data if we had nothing but emojis.
    MAX_TEXT_LENGTH = 100_000

    raw_content = models.OneToOneField(
        RawContent,
        on_delete=models.CASCADE,
        primary_key=True,
        related_name="text_content",
    )
    text = MultiCollationTextField(
        blank=True,
        max_length=MAX_TEXT_LENGTH,
        # We don't really expect to ever sort by the text column. This is here
        # primarily to force the column to be created as utf8mb4 on MySQL. I'm
        # using the binary collation because it's a little cheaper/faster.
        db_collations={
            "sqlite": "BINARY",
            "mysql": "utf8mb4_bin",
        }
    )
    length = models.PositiveIntegerField(null=False)
