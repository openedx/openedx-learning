"""
Convenience functions to make consistent field conventions easier.

Per OEP-38, we're using the MySQL-friendly convention of BigInt ID as a
primary key + separate UUID column.
https://open-edx-proposals.readthedocs.io/en/latest/best-practices/oep-0038-Data-Modeling.html

We have helpers to make case sensitivity consistent across backends. MySQL is
case-insensitive by default, SQLite and Postgres are case-sensitive.
"""
from __future__ import annotations

import hashlib
import uuid
from typing import TYPE_CHECKING, Any

from django.db import models
from django.db.models.fields.related_descriptors import ForeignKeyDeferredAttribute
from django.db.models.query_utils import DeferredAttribute

from .collations import MultiCollationMixin
from .validators import validate_utc_datetime


def create_hash_digest(data_bytes: bytes, num_bytes=20) -> str:
    """
    Create a lower-case hex string representation of a hash digest.

    The hash itself is 20-bytes by default, so 40 characters when we return it
    as a hex-encoded string. We use BLAKE2b for the hashing algorithm.

    DON'T JUST MODIFY THIS HASH BEHAVIOR!!! We use hashing for de-duplication
    purposes. If this hash function ever changes, that deduplication will fail
    because the hashing behavior won't match what's already in the database.

    If we want to change this representation one day, we should create a new
    function for that and do the appropriate data migration.
    """
    return hashlib.blake2b(data_bytes, digest_size=num_bytes).hexdigest()


def case_insensitive_char_field(**kwargs) -> MultiCollationCharField:
    """
    Return a case-insensitive ``MultiCollationCharField``.

    This means that entries will sort in a case-insensitive manner, and that
    unique indexes will be case insensitive, e.g. you would not be able to
    insert "abc" and "ABC" into the same table field if you put a unique index
    on this field.

    You may override any argument that you would normally pass into
    ``MultiCollationCharField`` (which is itself a subclass of ``CharField``).
    """
    # Set our default arguments
    final_kwargs = {
        "null": False,
        "db_collations": {
            "sqlite": "NOCASE",
            # We're using utf8mb4_unicode_ci to keep MariaDB compatibility,
            # since their collation support diverges after this. MySQL is now on
            # utf8mb4_0900_ai_ci based on Unicode 9, while MariaDB has
            # uca1400_ai_ci based on Unicode 14.
            "mysql": "utf8mb4_unicode_ci",
        },
    }
    # Override our defaults with whatever is passed in.
    final_kwargs.update(kwargs)

    return MultiCollationCharField(**final_kwargs)


def case_sensitive_char_field(**kwargs) -> MultiCollationCharField:
    """
    Return a case-sensitive ``MultiCollationCharField``.

    This means that entries will sort in a case-sensitive manner, and that
    unique indexes will be case sensitive, e.g. "abc" and "ABC" would be
    distinct and you would not get a unique constraint violation by adding them
    both to the same table field.

    You may override any argument that you would normally pass into
    ``MultiCollationCharField`` (which is itself a subclass of ``CharField``).
    """
    # Set our default arguments
    final_kwargs = {
        "null": False,
        "db_collations": {
            "sqlite": "BINARY",
            "mysql": "utf8mb4_bin",
        },
    }
    # Override our defaults with whatever is passed in.
    final_kwargs.update(kwargs)

    return MultiCollationCharField(**final_kwargs)


def immutable_uuid_field() -> models.UUIDField:
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


def key_field(**kwargs) -> MultiCollationCharField:
    """
    Externally created Identifier fields.

    These will often be local to a particular scope, like within a
    LearningPackage. It's up to the application as to whether they're
    semantically meaningful or look more machine-generated.

    Other apps should *not* make references to these values directly, since
    these values may in theory change (even if this is rare in practice).
    """
    return case_sensitive_char_field(max_length=500, blank=False, **kwargs)


def hash_field(**kwargs) -> models.CharField:
    """
    Holds a hash digest meant to identify a piece of content.

    Do not assume that this is secure or globally unique. Accidental collisions
    are extremely unlikely, but we don't want to get into a place where someone
    can maliciously craft a collision and affect other users.

    Use the create_hash_digest function to generate data suitable for this
    field.

    There are a couple of ways that we could have stored this more efficiently,
    but we don't at this time:

    1. A BinaryField would be the most space efficient, but Django doesn't
       support indexing a BinaryField in a MySQL database.
    2. We could make the field case-sensitive and run it through a URL-safe
       base64 encoding. But the amount of space this saves vs. the complexity
       didn't seem worthwhile, particularly the possibility of case-sensitivity
       related bugs.
    """
    default_kwargs = {
        "max_length": 40,
        "blank": False,
        "null": False,
        "editable": False,
    }
    return models.CharField(**(default_kwargs | kwargs))


def manual_date_time_field() -> models.DateTimeField:
    """
    DateTimeField that does not auto-generate values.

    The datetimes entered for this field *must be UTC* or it will raise a
    ValidationError.

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
        validators=[
            validate_utc_datetime,
        ],
    )


class MultiCollationCharField(MultiCollationMixin, models.CharField):
    """
    CharField subclass with per-database-vendor collation settings.

    Django's CharField already supports specifying the database collation, but
    that only works with a single value. So there would be no way to say, "Use
    utf8mb4_bin for MySQL, and BINARY if we're running SQLite." This is a
    problem because we run tests in SQLite (and may potentially run more later).
    It's also a problem if we ever want to support other database backends, like
    PostgreSQL. Even MariaDB is starting to diverge from MySQL in terms of what
    collations are supported.
    """


class MultiCollationTextField(MultiCollationMixin, models.TextField):
    """
    TextField subclass with per-database-vendor collation settings.

    We don't ever really want to _sort_ by a TextField, but setting a collation
    forces the compatible charset to be set in MySQL, and that's the part that
    matters for our purposes.
    """


class TypedPK[ModelType]:
    value: int

    def __init__(self, value: int):
        self.value = value

    def __eq__(self, other: object) -> bool:
        # Compare equal to other ``TypedPK`` instances and to bare ``int``
        # values that match. Allowing equality with ``int`` is important for
        # interop with Django internals like ``Model.__eq__``, which compares
        # ``self.pk == other.pk`` directly. Not all primary key columns are
        # wrapped (e.g. multi-table-inheritance ``parent_link`` fields are
        # auto-generated as plain ``OneToOneField``s and store raw ``int``s),
        # so insisting on a ``TypedPK`` on both sides would make models with
        # the same row identity compare unequal.
        if isinstance(other, TypedPK):
            return self.value == other.value
        if isinstance(other, int):
            return self.value == other
        return NotImplemented

    def __hash__(self) -> int:
        # Must match ``hash(int)`` so that ``TypedPK(3)`` and ``3`` are
        # interchangeable in sets/dicts, consistent with ``__eq__``.
        return hash(self.value)

    def __repr__(self) -> str:
        return f"{type(self).__name__}({self.value!r})"


class _TypedPKDeferredAttribute(DeferredAttribute):
    """
    Data descriptor that wraps incoming ``int`` values into ``TypedPK`` boxes.

    Django's default field descriptor (``DeferredAttribute``) is a *non-data*
    descriptor -- it defines ``__get__`` only. That means ``setattr`` on a
    model instance bypasses it and writes straight into ``__dict__``. This
    matters for ``TypedPrimaryKeyField`` because:

    1. After an ``INSERT``, Django runs
       ``setattr(instance, pk.attname, last_insert_id)`` where
       ``last_insert_id`` is the raw ``int`` returned by the DB driver.
    2. During queryset hydration, ``Model.__init__`` does a ``setattr`` loop
       over the row values (which are still raw ``int``s for the PK column).

    Without a ``__set__``, both paths leave a bare ``int`` on the instance
    and ``pe.id`` ends up untyped at runtime. By promoting this to a *data*
    descriptor we intercept both paths and wrap the value in a ``TypedPK``.
    Direct user assignments like ``instance.id = 5`` get the same treatment.
    """

    def __set__(self, instance, value):
        if value is not None and not isinstance(value, TypedPK):
            value = TypedPK(int(value))
        instance.__dict__[self.field.attname] = value


if TYPE_CHECKING:
    # django-stubs models the standard ``Field`` descriptor as
    # ``Field[_ST, _GT]`` where ``_ST`` is the type accepted by the field's
    # setter and ``_GT`` is the type returned by the getter. The django-stubs
    # mypy plugin reparametrizes ``Field`` instances using these two type
    # parameters, so any custom field that wants to participate in that
    # propagation must expose the same shape. Plain ``models.BigAutoField`` is
    # not subscriptable at runtime, so we only widen its generics under
    # ``TYPE_CHECKING``.
    class _BigAutoFieldBase[_ST, _GT](models.BigAutoField[_ST, _GT]):
        pass
else:
    class _BigAutoFieldBase(models.BigAutoField):
        # The following is required to mark this class as subscriptable[...].
        def __class_getitem__(cls, _item):
            return cls


class TypedPrimaryKeyField[_ST, _GT](_BigAutoFieldBase[_ST, _GT]):
    """
    BigAutoField that wraps the integer in a typed ``TypedPK`` box.

    This field is generic over django-stubs' standard ``_ST`` (set type) and
    ``_GT`` (get type) parameters so that the django-stubs mypy plugin will
    correctly propagate the ``TypedPK[Model]`` type to readers and writers of
    the field. Use it like::

        class MyModel(models.Model):
            PK: TypeAlias = TypedPK["MyModel"]
            id = TypedPrimaryKeyField[PK | int | None, PK](primary_key=True)
    """

    # Install a data descriptor on the model class so that any value assigned
    # to the field (post-INSERT, queryset hydration, refresh_from_db, or a
    # direct ``instance.id = ...``) is normalized to a ``TypedPK``.
    descriptor_class = _TypedPKDeferredAttribute

    # The django-stubs plugin reads these class-level descriptor types when
    # generating the implicit ``<fk>_id`` attribute on models that have a
    # ``ForeignKey`` to a model whose primary key uses this field. Without
    # them, FK ``_id`` columns would inherit ``IntegerField``'s defaults
    # (``int | str | Combinable``) and reject ``TypedPK`` values. We can't
    # parameterize ``TypedPK`` by model here -- that information only exists
    # at the call site of each model's ``id =`` assignment -- so we fall back
    # to ``TypedPK[Any]`` for cross-model FK assignments. The model's *own*
    # ``id`` attribute still gets the precise ``TypedPK[Model]`` type because
    # the field-call transformer uses the instance-level type args.
    _pyi_private_set_type: TypedPK[Any] | int | None  # type: ignore[assignment]
    _pyi_private_get_type: TypedPK[Any]  # type: ignore[assignment]
    # Used by django-stubs for queryset filter/get lookups, e.g.
    # ``Model.objects.get(id=...)``.
    _pyi_lookup_exact_type: TypedPK[Any] | int  # type: ignore[assignment]

    def get_prep_value(self, value):
        if value is None:
            return None
        if isinstance(value, int):
            return value
        assert isinstance(value, TypedPK)
        try:
            return int(value.value)
        except (TypeError, ValueError) as e:
            raise e.__class__(
                "Field '%s' expected a PK containing an int value, but got %r." % (self.name, value)
            ) from e

    def to_python(self, value):
        if value is None:
            return value
        if isinstance(value, TypedPK):
            return value
        return TypedPK(value)


class _TypedFKDeferredAttribute(ForeignKeyDeferredAttribute):
    """
    Data descriptor for FKs that target a ``TypedPrimaryKeyField`` PK.

    Django's default ``ForeignKeyDeferredAttribute`` is a data descriptor
    (it does have ``__set__``), but its ``__set__`` just stores the raw value.
    For FKs whose target column is a ``TypedPrimaryKeyField``, that means the
    ``<fk>_id`` attribute holds a bare ``int`` after queryset hydration --
    inconsistent with how the target model's own ``pk`` is now boxed in a
    ``TypedPK``. This subclass wraps incoming non-None, non-``TypedPK`` values
    so that ``container.publishable_entity_id`` (and similar) returns a
    ``TypedPK`` regardless of whether the model was constructed in-memory or
    loaded from the database.
    """

    def __set__(self, instance, value):
        if value is not None and not isinstance(value, TypedPK):
            value = TypedPK(int(value))
        super().__set__(instance, value)


class TypedForeignKey(models.ForeignKey):
    """
    ``ForeignKey`` variant for relations to a model whose primary key is a
    ``TypedPrimaryKeyField``. Use this in place of ``models.ForeignKey``
    whenever the target model's PK is a ``TypedPK`` so that the ``<fk>_id``
    column attribute is normalized to a ``TypedPK`` at runtime.
    """

    descriptor_class = _TypedFKDeferredAttribute


class TypedOneToOneField(models.OneToOneField):
    """
    ``OneToOneField`` counterpart of ``TypedForeignKey``. Use this in place
    of ``models.OneToOneField`` (most commonly when modeling a 1-to-1 link
    to ``PublishableEntity`` via ``primary_key=True``).
    """

    descriptor_class = _TypedFKDeferredAttribute

