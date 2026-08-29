"""
Tests for the pydantic input models.

IMPORTANT: These models define what we will accept from an archive file, which
means loosening them is easy and tightening them breaks backwards compatibility.
Be very cautious about changing an assertion here -- if an archive validated
yesterday, it needs to validate today.

These tests are strictly for the schema module, and therefore don't need Django
to run.
"""
from datetime import datetime, timezone
from unittest import TestCase

from pydantic import ValidationError

from openedx_content.applets.backup_restore.schema import (
    CollectionInput,
    CompletePackageInputData,
    EntityInputData,
    LearningPackageInputData,
    MetaInputData,
    SectionInputData,
    SubsectionInputData,
    UnitInputData,
)

CREATED = datetime(2026, 4, 8, 15, 22, 12, 780012, tzinfo=timezone.utc)


def minimal_package(**overrides) -> dict:
    """The smallest input we consider loadable."""
    return {
        "meta": {"format_version": 1},
        "learning_package": {"key": "lib:Axim:FunLib"},
        "entities": {},
        "collections": [],
        **overrides,
    }


class ContainerDiscriminationTest(TestCase):
    """
    The container union has to resolve to the right model.

    All three container models allow extra fields, so if the discriminating field
    were optional every one of them would validate every dict, and the union
    would always collapse to whichever model happens to be listed first. That
    failure is silent -- everything would load as a Unit -- so it's worth pinning
    down explicitly.
    """

    def _container_for(self, raw):
        entity = EntityInputData.model_validate({"created": CREATED, "container": raw})
        return entity.container

    def test_section(self):
        assert isinstance(self._container_for({"section": {}}), SectionInputData)

    def test_subsection(self):
        assert isinstance(self._container_for({"subsection": {}}), SubsectionInputData)

    def test_unit(self):
        assert isinstance(self._container_for({"unit": {}}), UnitInputData)

    def test_unknown_container_type_falls_through_to_dict(self):
        """
        A container type we don't recognize is still captured.

        We keep the raw dict rather than erroring here so that validation can
        report a useful message. Loading rejects it.
        """
        container = self._container_for({"chapter": {}})
        assert isinstance(container, dict)
        assert container == {"chapter": {}}

    def test_no_container_means_component(self):
        assert self._container_for(None) is None

    def test_absent_container_defaults_to_none(self):
        entity = EntityInputData.model_validate({"created": CREATED})
        assert entity.container is None


class StringConstraintsTest(TestCase):
    """
    The ref/code constraints have to actually be applied.

    These were declared with a trailing comma at one point, which made them
    tuples rather than StringConstraints, and pydantic silently ignored them.
    """

    def test_collection_key_is_stripped(self):
        collection = CollectionInput.model_validate(
            {"title": "Difficult Problems", "key": "  difficult-problems  "}
        )
        assert collection.key == "difficult-problems"

    def test_collection_key_rejects_spaces(self):
        with self.assertRaises(ValidationError):
            CollectionInput.model_validate({"title": "T", "key": "has spaces"})

    def test_collection_key_rejects_slashes(self):
        with self.assertRaises(ValidationError):
            CollectionInput.model_validate({"title": "T", "key": "has/slash"})

    def test_collection_key_rejects_trailing_newline(self):
        with self.assertRaises(ValidationError):
            CollectionInput.model_validate({"title": "T", "key": "trailing\nnewline"})

    def test_learning_package_key_is_stripped(self):
        lp = LearningPackageInputData.model_validate({"key": "  lib:Axim:FunLib  "})
        assert lp.key == "lib:Axim:FunLib"


class MetaInputDataTest(TestCase):
    """Tests for the archive provenance metadata."""

    def test_only_format_version_is_required(self):
        """
        Everything else in [meta] is provenance information we can't trust
        anyway, so an archive that omits it is still loadable.
        """
        meta = MetaInputData.model_validate({"format_version": 1})

        assert meta.format_version == 1
        assert meta.created_by is None
        assert meta.created_by_email is None
        assert meta.created_at is None
        assert meta.origin_server is None

    def test_format_version_is_required(self):
        with self.assertRaises(ValidationError):
            MetaInputData.model_validate({})

    def test_format_version_must_be_1(self):
        with self.assertRaises(ValidationError):
            MetaInputData.model_validate({"format_version": 2})

    def test_email_is_validated(self):
        with self.assertRaises(ValidationError):
            MetaInputData.model_validate(
                {"format_version": 1, "created_by_email": "not-an-email"}
            )


class LearningPackageInputDataTest(TestCase):
    """Tests for the top-level Learning Package fields."""

    def test_key_is_required(self):
        with self.assertRaises(ValidationError) as ctx:
            LearningPackageInputData.model_validate({"title": "Fun Library"})
        assert [err["loc"] for err in ctx.exception.errors()] == [("key",)]

    def test_title_has_a_default(self):
        lp = LearningPackageInputData.model_validate({"key": "lib:Axim:FunLib"})
        assert lp.title == "Untitled Library"

    def test_blank_title_is_rejected(self):
        with self.assertRaises(ValidationError):
            LearningPackageInputData.model_validate({"key": "lib:A:B", "title": ""})

    def test_dates_are_optional(self):
        lp = LearningPackageInputData.model_validate({"key": "lib:Axim:FunLib"})
        assert lp.created is None
        assert lp.updated is None

    def test_naive_datetimes_are_rejected(self):
        """We store everything in UTC, so an ambiguous timestamp is an error."""
        with self.assertRaises(ValidationError):
            LearningPackageInputData.model_validate(
                {"key": "lib:A:B", "created": datetime(2026, 4, 8, 15, 22, 12)}
            )


class VersionInputTest(TestCase):
    """Tests for entity versions and their draft/published pointers."""

    def _entity_with_version(self, **version_overrides):
        version = {"version_num": 1, "title": "Some Title", **version_overrides}
        return EntityInputData.model_validate(
            {"created": CREATED, "versions": [version]}
        )

    def test_blank_title_is_allowed(self):
        """
        Blank titles are legal and common -- content imported from courses (e.g.
        via the modulestore migrator) frequently has untitled units, and such
        content can be backed up. Restoring that same archive must work.
        """
        entity = self._entity_with_version(title="")
        assert entity.versions[0].title == ""

    def test_version_num_must_be_positive(self):
        with self.assertRaises(ValidationError):
            self._entity_with_version(version_num=0)

    def test_draft_and_published_default_to_none(self):
        entity = EntityInputData.model_validate({"created": CREATED})
        assert entity.draft.version_num is None
        assert entity.published.version_num is None

    def test_empty_published_table_means_unpublished(self):
        """
        An entity that has never been published exports an empty
        [entity.published] table rather than omitting it.
        """
        entity = EntityInputData.model_validate(
            {"created": CREATED, "published": {}, "draft": {"version_num": 2}}
        )
        assert entity.published.version_num is None
        assert entity.draft.version_num == 2


class CompletePackageInputDataTest(TestCase):
    """Tests for validating a whole package document at once."""

    def test_minimal_package(self):
        data = CompletePackageInputData.model_validate(minimal_package())

        assert data.learning_package.key == "lib:Axim:FunLib"
        assert data.entities == {}
        assert data.collections == []

    def test_duplicate_collection_keys_are_rejected(self):
        raw = minimal_package(
            collections=[
                {"title": "One", "key": "same-key", "src_path": "collections/a.toml"},
                {"title": "Two", "key": "same-key", "src_path": "collections/b.toml"},
            ]
        )
        with self.assertRaises(ValidationError) as ctx:
            CompletePackageInputData.model_validate(raw)

        message = str(ctx.exception)
        assert "same-key" in message
        # The message should name both files, so it's actionable.
        assert "collections/a.toml" in message
        assert "collections/b.toml" in message

    def test_distinct_collection_keys_are_fine(self):
        raw = minimal_package(
            collections=[
                {"title": "One", "key": "key-one"},
                {"title": "Two", "key": "key-two"},
            ]
        )
        data = CompletePackageInputData.model_validate(raw)
        assert [c.key for c in data.collections] == ["key-one", "key-two"]

    def test_collection_entities_default_to_empty(self):
        raw = minimal_package(collections=[{"title": "One", "key": "key-one"}])
        data = CompletePackageInputData.model_validate(raw)
        assert data.collections[0].entities == []

    def test_missing_meta_reports_against_meta(self):
        raw = minimal_package()
        del raw["meta"]

        with self.assertRaises(ValidationError) as ctx:
            CompletePackageInputData.model_validate(raw)
        assert ("meta",) in [err["loc"] for err in ctx.exception.errors()]

    def test_errors_are_reported_together(self):
        """
        Pydantic collects every problem, which is what lets us show someone
        repairing an archive all of their mistakes at once.
        """
        raw = {"meta": {}, "learning_package": {}, "entities": {}, "collections": []}

        with self.assertRaises(ValidationError) as ctx:
            CompletePackageInputData.model_validate(raw)

        locations = {err["loc"] for err in ctx.exception.errors()}
        assert ("meta", "format_version") in locations
        assert ("learning_package", "key") in locations


class ForwardsCompatibilityTest(TestCase):
    """
    Unrecognized fields are kept rather than dropped.

    Older installs need to load newer archives. We keep the unknown values rather
    than ignoring them so that we can eventually warn about fields that look like
    typos of ones we do know.
    """

    def test_unknown_fields_are_retained(self):
        data = CompletePackageInputData.model_validate(
            minimal_package(
                learning_package={"key": "lib:A:B", "some_future_field": "hello"}
            )
        )
        assert data.learning_package.some_future_field == "hello"

    def test_models_are_frozen(self):
        data = CompletePackageInputData.model_validate(minimal_package())
        with self.assertRaises(ValidationError):
            data.learning_package.title = "Changed"


class BlankMetadataTest(TestCase):
    """
    Blank [meta] values must not block a restore.

    The backup side writes ``created_by_email`` unconditionally, and Django's
    ``User.email`` defaults to an empty string, so archives with blank
    provenance fields are routinely produced by our own export.
    """

    def test_blank_email(self):
        meta = MetaInputData.model_validate(
            {"format_version": 1, "created_by_email": ""}
        )
        assert meta.created_by_email is None

    def test_blank_created_by(self):
        meta = MetaInputData.model_validate({"format_version": 1, "created_by": "  "})
        assert meta.created_by is None

    def test_blank_origin_server(self):
        meta = MetaInputData.model_validate({"format_version": 1, "origin_server": ""})
        assert meta.origin_server is None

    def test_real_values_still_come_through(self):
        meta = MetaInputData.model_validate({
            "format_version": 1,
            "created_by": "eddy",
            "created_by_email": "eddy@axim.org",
            "origin_server": "studio.local.openedx.io",
        })
        assert meta.created_by == "eddy"
        assert meta.created_by_email == "eddy@axim.org"
        assert meta.origin_server == "studio.local.openedx.io"

    def test_a_genuinely_bad_email_is_still_rejected(self):
        with self.assertRaises(ValidationError):
            MetaInputData.model_validate(
                {"format_version": 1, "created_by_email": "not-an-email"}
            )
