"""
This module defines the schema that we use during the backup/restore process.

The pydantic models defined in this module are divided into InputData and
OutputData. These are intentionally kept separate and do not inherit from each
other. The InputData classes will be much more permissive, with many optional
fields. The OutputData classes are meant for internal use when generating
exports, and will be stricter.
"""
from __future__ import annotations

from typing import Annotated, Literal

from pydantic import (
    AwareDatetime,
    BaseModel,
    ConfigDict,
    EmailStr,
    Field,
    StrictStr,
    StringConstraints,
    field_validator,
)

# Refs are arbitrary identifiers that we do almost no validation of, and are
# mainly there to assure uniqueness within some namespace.
REF_CONSTRAINTS = StringConstraints(
    strict=True,
    strip_whitespace=True,
)

# This is for things like the collection_code, library_code, etc.
CODE_CONSTRAINTS = StringConstraints(
    strict=True,
    strip_whitespace=True,
    # Note that we can't use \Z to indicate the end of line in our regex because
    # that's not supported syntax in JavaScript, and pydantic will raise an
    # error when trying to generate a JSON Schema. However, the combination of $
    # and strip_whitespace=True means that we're sure that we won't allow any
    # trailing newlines.
    pattern=r"^[a-zA-Z0-9_.-]+$",
)


def _reject_duplicate_keys(items, label: str) -> None:
    """
    Raise a ValueError if two items in ``items`` share a ``key``.

    Both Entities and Collections need this, and the message wants to name the
    file that redefined the key as well as the one that got there first, which is
    what each item's ``src_path`` is for.
    """
    keys_to_items: dict[str, object] = {}
    for item in items:
        if item.key in keys_to_items:
            original = keys_to_items[item.key]
            raise ValueError(
                f'{label} "{item.key}" redefined in '
                f'{item.src_path} (original in '
                f'{original.src_path})'      # type: ignore[attr-defined]
            )
        keys_to_items[item.key] = item


class InputData(BaseModel):
    """
    Base class for all inputs, here to set config defaults.

    InputData classes are frozen, i.e. they should only be initialized once from
    the unvalidated input. Allowing gradual mutations makes things much harder
    to debug.

    InputData clases are also set to allow parameters that they don't recognize
    (extra="allow") for the sake of forwards compatibility. As any given file
    format gets iterated on, it will get new attributes. Older installs of the
    platform should ignore these new attributes and just load the things that we
    know how to handle. The reason we don't set this to "ignore" is because
    unrecognized fields could be simple typos of known fields, so we still want
    to capture that information so we can potentially display warnings about it.
    """
    model_config = ConfigDict(frozen=True, extra="allow")


class CompletePackageInputData(InputData):
    """
    The contents of the entire Learning Package.
    """
    meta: MetaInputData
    learning_package: LearningPackageInputData

    # These are lists rather than dicts keyed by their "key" field, and that is
    # deliberate: a dict can only hold one entry per key, so a duplicated key
    # would silently overwrite its predecessor during extraction and there would
    # be nothing left for us to complain about here. Keeping them as lists is
    # what lets the duplicate checks below exist at all.
    entities: list[EntityInputData]

    collections: list[CollectionInput]

    @field_validator('entities', mode='after')
    @classmethod
    def check_for_duplicate_entity_keys(cls, entities: list[EntityInputData]):
        """
        Raise a ValueError if the same Entity is defined in two places.
        """
        _reject_duplicate_keys(entities, "Entity")
        return entities

    @field_validator('collections', mode='after')
    @classmethod
    def check_for_duplicate_collection_keys(cls, collections: list[CollectionInput]):
        """
        Raise a ValueError if we encounter a duplicate collection entry.

        In the longer term, we may want to be able to remove the duplicate
        entries (and other broken entries), while still otherwise allowing the
        restore to proceed. But for now, any error kills the restore process.
        """
        _reject_duplicate_keys(collections, "Collection")
        return collections


class MetaInputData(InputData):
    """
    Input Package Metadata, Version 1

    This is data about the backup file itself, as opposed to the Learning
    Package that it contains: who created this backup, when was it created, etc.
    On the input side, the fields here are only here so that we can give useful
    preview information when the user is uploading this to a new instance. None
    of these values are necessary for creating a new Learning Package—in fact,
    none of these can even be trusted, since a malicious actor could manipulate
    them to say whatever they wanted. It's just meant as a sanity check to help
    assure the user that they're restoring the correct package archive.

    The only truly critical field is ``format_version``, since that will one day
    affect input validation rules.
    """
    format_version: Literal[1]  # Only supported version at the moment
    created_by: StrictStr | None = Field(default=None, min_length=1)
    created_by_email: EmailStr | None = None
    created_at: AwareDatetime | None = None
    origin_server: StrictStr | None = None

    @field_validator("created_by", "created_by_email", "origin_server", mode="before")
    @classmethod
    def blank_means_absent(cls, value):
        """
        Treat a blank string in [meta] as "not supplied".

        The backup side writes these fields unconditionally, so an archive made
        by a user with no email address on file carries
        ``created_by_email = ""``. Since none of this metadata is required (or
        even trustworthy), refusing to restore such an archive would be far
        worse than not knowing who made it.
        """
        if isinstance(value, str) and not value.strip():
            return None
        return value


class LearningPackageInputData(InputData):
    """
    High level data for a Learning Package itself (not its contents).
    """
    title: StrictStr = Field(min_length=1, default="Untitled Library")
    key: Annotated[
        str,
        REF_CONSTRAINTS,
        Field(
            description=(
                "This is often a LibraryLocatorV2-formatted string, but can be "
                "any arbitrary string at the moment. It must be unique within a"
                " given server instance."
            ),
            examples=[
                "lib:OrgName:LibraryName",
                "lib:Axim:IntroPhysics",
                "lp-restore:Axim:IntroPhysics:1775752130941",
            ],
        ),
    ]
    description: StrictStr | None = Field(default="", max_length=10_000)
    created: AwareDatetime | None = None
    updated: AwareDatetime | None = None


class DraftInputData(InputData):
    version_num: Annotated[int, Field(gt=0)] | None = None


class PublishedInputData(InputData):
    version_num: Annotated[int, Field(gt=0)] | None = None


class EntityInputData(InputData):
    """A PublishableEntity: either a Component or a Container."""

    key: Annotated[str, REF_CONSTRAINTS]

    can_stand_alone: bool = True

    created: AwareDatetime

    # Weird edge case: If you create something, never publish it, and then do a
    # "reset to published state", the resulting export in Ulmo would omit the
    # [entity.draft] section entirely, rather than it being an empty dictionary.
    draft: DraftInputData = DraftInputData(version_num=None)
    published: PublishedInputData = PublishedInputData(version_num=None)

    versions: list[VersionInput] = []

    # Not all entities are containers, and we may one day have containers that
    # this version of the code does not understand. So we have a generic dict
    # for unknown containers and None means it's something that is not a
    # container.
    #
    # TODO: Test unknown container type.
    container: UnitInputData | SubsectionInputData | SectionInputData | dict | None = None

    # The source file this Entity was defined in. See the note on
    # CollectionInput.src_path -- this is for error messages only.
    src_path: str | None = None


class SectionInputData(InputData):
    """Marks an entity as a Section."""

    # Note: this field is intentionally required, with no default. These three
    # container models are all `extra="allow"`, so if the discriminating field
    # were optional, every one of them would happily validate every dict and the
    # union in EntityInputData.container would always resolve to whichever model
    # is listed first.
    section: dict


class SubsectionInputData(InputData):
    subsection: dict  # Required. See the note on SectionInputData.


class UnitInputData(InputData):
    unit: dict  # Required. See the note on SectionInputData.


class VersionInput(InputData):
    version_num: Annotated[int, Field(gt=0)]
    title: str
    component: ComponentVersionInput | None = None
    container: ContainerVersionInput | None = None


class ComponentVersionInput(InputData):
    media: dict


class ContainerVersionInput(InputData):
    children: list[Annotated[str, REF_CONSTRAINTS]]


class CollectionInput(InputData):
    """A named grouping of PublishableEntities within a Learning Package."""

    title: StrictStr = Field(min_length=1)
    key: Annotated[
        str,
        CODE_CONSTRAINTS,
        Field(
            description=(
                "A unique slug-like code field. Must be unique within a given Learning Package."
            ),
            examples=[
                "difficult-problems",
                "practice-exams",
            ],
        ),
    ]
    description: StrictStr | None = Field(default="", max_length=10_000)

    # It looks like we weren't actually serializing the modified date.
    created: AwareDatetime | None = None

    # The PublishableEntities that belong to this Collection. Entity refs that
    # aren't in the archive are ignored at load time rather than being an error,
    # since a Collection with a dangling member is still perfectly usable.
    entities: list[Annotated[str, REF_CONSTRAINTS]] = []

    # This is the source file where this Collection was defined. This is only
    # for being able to create useful error messages. We should never be reading
    # from this file directly because the exact format of this file should be
    # free to change as needed. That's the responsibilty of the payload.py
    # module.
    src_path: str | None = None


# --- Output models. Not in use yet; the backup side still writes TOML directly. ---


class PackageConfigOutputData(BaseModel):
    """
    Writes the package.toml file when we're writing a backup archive.
    """
    meta: MetaOutputData
    learning_package: LearningPackageOutputData


class MetaOutputData(BaseModel):
    """
    Output Package Metadata

    This is metadata that is written so that people can more easily figure out
    where a backup archive came from.

    The "created_by", "created_by_email", and "created_at" fields all refer to
    the user who created the backup archive, not the user who created the
    Library (Learning Package).
    """
    format_version: Literal[1]
    created_by: StrictStr = Field(min_length=1)
    created_by_email: EmailStr
    created_at: AwareDatetime
    origin_server: StrictStr


class LearningPackageOutputData(BaseModel):
    """
    High level data for a Learning Package.
    """
    title: StrictStr = Field(min_length=1)
    key: StrictStr = Field(
        pattern=r"^lib:[\w\-.]+:[\w\-.]+$",
        description="This is a LibraryLocatorV2",
        examples=[
            "lib:OrgName:LibraryName",
            "lib:Axim:IntroPhysics",
        ]
    )
    description: StrictStr
    created: AwareDatetime
    updated: AwareDatetime
