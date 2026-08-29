"""
Logic for taking the logical schema model for a Learning Package and loading it
into the database.
"""
import mimetypes
import os.path

from dataclasses import asdict, dataclass
from datetime import datetime, timedelta
from functools import cache, partial

from django.contrib.auth.models import User as UserType  # pylint: disable=imported-auth-user
from django.db.transaction import atomic

from ..components import api as components_api
from ..containers import api as containers_api
from ..collections import api as collections_api
from ..media import api as media_api
from ..publishing import api as publishing_api
from ..publishing.models import LearningPackage
from ..sections.models import Section
from ..subsections.models import Subsection
from ..units.models import Unit

from .schema import (
    SectionInputData,
    SubsectionInputData,
    UnitInputData,
)
from .validation import ValidatedLearningPackageInput
from .zipper import RestoreResult, RestoreLearningPackageData, BackupMetadata


class Loader:
    """
    Loads the validated input into a Learning Package in the database.

    This class does not understand the specifics of the archive file format. It
    only needs the ValidatedLearningPackageInput.
    """

    @dataclass(frozen=True)
    class Target:
        learning_package: LearningPackage
        user: UserType
        loaded_at: datetime

    def __init__(self, validated_input: ValidatedLearningPackageInput):
        self.validated_input = validated_input
        self.component_inputs = {}
        self.section_inputs = {}
        self.subsection_inputs = {}
        self.unit_inputs = {}

        entities = validated_input.data.entities

        # Split our entities into separate dicts for convenience.
        for entity_ref, entity_input in sorted(entities.items()):
            match entity_input.container:
                case SectionInputData():
                    self.section_inputs[entity_ref] = entity_input
                case SubsectionInputData():
                    self.subsection_inputs[entity_ref] = entity_input
                case UnitInputData():
                    self.unit_inputs[entity_ref] = entity_input
                case None:
                    # For the moment, if it's not a Container, it's a Component
                    self.component_inputs[entity_ref] = entity_input

    def load_into(self, target: Target):
        """
        This method intentionally takes a target (LearningPackage, User,
        Datetime) instead of putting that information into Loader object state.
        My hope is that this pattern will make it easier to adapt into handling
        incremental imports where we have to test the same input being imported
        into multiple Learning Packages with existing state.
        """
        with atomic(savepoint=False):
            bulk_change_context_for_time = partial(
                publishing_api.bulk_draft_changes_for,
                target.learning_package.id,
                changed_by=target.user.id,
            )

            # DraftChangeLog 1: Add all the PublishableEntities and their versions,
            # and set their versions to prepare for for publishing.
            with bulk_change_context_for_time(changed_at=target.loaded_at):
                loaded_components = self.load_components_into(target)
                loaded_entities = self.load_containers_into(target, loaded_components)
                self.set_draft_versions(target, for_publishing=True)

            publishing_api.publish_all_drafts(
                target.learning_package.id,
                published_at=target.loaded_at,
                published_by=target.user.id,
                message="Restore from backup.",
            )

            # DraftChangeLog 2: Set all PublishableEntities to their proper draft.
            # At this point, all versions have been loaded, and the correct versions
            # have been published, but the current draft version might be wrong.
            #
            # The history display will want draft changes to be slightly after the
            # published log entry.
            changed_at = target.loaded_at + timedelta(seconds=1)
            with bulk_change_context_for_time(changed_at=changed_at):
                self.set_draft_versions(target, for_publishing=False)

            # Collections are added at the end, in case publishing of contents would
            # cause more thrashing w.r.t. search indexing.
            self.load_collections_into(target, loaded_entities)

        return self.build_restore_result(target)

    def build_restore_result(self, target: Target):
        """
        This is for compatibility with what we're already sending to the frontend.

        TODO: We should return something more structured for our API and let the
        calling api.py handle the translation into what the REST API expects.
        """
        validated_data = self.validated_input.data

        # Fix this with better parsing later.
        _lib, org, slug = validated_data.learning_package.key.split(":")

        loaded_entities = publishing_api.get_publishable_entities(target.learning_package.id)

        result = RestoreResult(
            status="success",
            log_file_error=None,
            lp_restored_data=RestoreLearningPackageData(
                id=target.learning_package.id,
                key=target.learning_package.key,
                archive_lp_key=validated_data.learning_package.key,
                archive_org_key=org,
                archive_slug=slug,
                title=target.learning_package.title,
                num_containers=loaded_entities.filter(container__isnull=False).count(),
                num_sections=loaded_entities.filter(container__section__isnull=False).count(),
                num_subsections=loaded_entities.filter(container__subsection__isnull=False).count(),
                num_units=loaded_entities.filter(container__unit__isnull=False).count(),
                num_components=loaded_entities.filter(component__isnull=False).count(),
                num_collections=collections_api.get_collections(target.learning_package.id).count(),
            ),
            backup_metadata=BackupMetadata(
                format_version=validated_data.meta.format_version,
                created_by=validated_data.meta.created_by,
                created_by_email=validated_data.meta.created_by,
                created_at=validated_data.meta.created_at,
                original_server=validated_data.meta.origin_server,
            ),
        )
        return asdict(result)

    def load_components_into(self, target: Target):
        """ """

        @cache  # inner fn, so won't persist across calls to load_components_into
        def _get_component_type(namespace: str, name: str):
            return components_api.get_or_create_component_type(namespace, name)

        @cache  # inner fn, so won't persist across calls to load_components_into
        def _get_media_type(mime_type: str):
            return media_api.get_or_create_media_type(mime_type)

        mapping = {}
        for entity_ref, entity_input in self.component_inputs.items():
            namespace, name, component_code = entity_ref.split(":")
            component_type = _get_component_type(namespace, name)
            component = components_api.create_component(
                target.learning_package.id,
                component_type=component_type,
                local_key=component_code,
                created=target.loaded_at,
                created_by=target.user.id,
            )
            # TODO: Validate missing children
            sorted_version_inputs = sorted(
                entity_input.versions, key=lambda v: v.version_num
            )
            for version_input in sorted_version_inputs:
                media_to_replace = {}
                for path, text_val in version_input.component.media.items():
                    filename = os.path.basename(path)
                    if filename == "block.xml":
                        media_type = _get_media_type(
                            f"application/vnd.openedx.xblock.v1.{component_type.name}+xml"
                        )
                    else:
                        media_type_str, _encoding = mimetypes.guess_type(filename)
                        media_type_str = media_type_str or "application/octet-stream"
                        media_type = _get_media_type(media_type_str)

                    # TODO: Adopt data-urls for this.
                    if path.startswith('static/'):
                        # This is where we could add base64 encoded versions
                        # right now, we just use fs:/path/to/file
                        _resource_type, filepath = text_val.split(":")
                        new_media = media_api.get_or_create_file_media(
                            target.learning_package.id,
                            media_type.id,
                            data=self.validated_input.fs.read_bytes(filepath),
                            created=target.loaded_at,
                        )
                    else:
                        new_media = media_api.get_or_create_text_media(
                            target.learning_package.id,
                            media_type.id,
                            text=text_val,
                            created=target.loaded_at,
                        )

                    media_to_replace[path] = new_media.id

                # TODO: Modify create_next_component_version to take a Component
                # as an option, to save the needless fetches.
                components_api.create_next_component_version(
                    component.pk,
                    title=version_input.title,
                    media_to_replace=media_to_replace,
                    created=target.loaded_at,
                    created_by=target.user.id,
                    force_version_num=version_input.version_num,
                )
            mapping[entity_ref] = component

        return mapping

    def load_containers_into(self, target: Target, component_mapping: dict):

        # Ordering matters, since we want to build the references bottom-up.
        container_types_to_inputs = {
            Unit: self.unit_inputs,
            Subsection: self.subsection_inputs,
            Section: self.section_inputs,
        }
        mapping = component_mapping.copy()
        for container_type, container_inputs in container_types_to_inputs.items():
            for entity_ref, entity_input in container_inputs.items():
                container = containers_api.create_container(
                    target.learning_package.id,
                    entity_ref,
                    created=target.loaded_at,
                    created_by=target.user.id,
                    container_cls=container_type,
                )

                # TODO: Validate missing children
                sorted_version_inputs = sorted(
                    entity_input.versions, key=lambda v: v.version_num
                )
                for version_input in sorted_version_inputs:
                    containers_api.create_next_container_version(
                        container,
                        title=version_input.title,
                        entities=[
                            mapping[child_ref]
                            for child_ref in version_input.container.children
                        ],
                        created=target.loaded_at,
                        created_by=target.user.id,
                        force_version_num=version_input.version_num,
                    )

                mapping[entity_ref] = container

        return mapping

    def load_collections_into(self, target: Target, loaded_entities):
        for collection_input in self.validated_input.data.collections:
            collections_api.create_collection(
                target.learning_package.id,
                key=collection_input.key,
                title=collection_input.title,
                created_by=target.user.id,
                description=collection_input.description,
            )
            loaded_entity_refs = [
                ref for ref in collection_input.entities if ref in loaded_entities
            ]
            entities = publishing_api.get_publishable_entities(
                target.learning_package.id
            ).filter(key__in=loaded_entity_refs)

            collections_api.add_to_collection(
                target.learning_package.id,
                key=collection_input.key,
                entities_qset=entities,
            )

    def set_draft_versions(self, target: Target, for_publishing: bool):
        entity_inputs = self.validated_input.data.entities

        saved_entities = publishing_api.get_publishable_entities(
            target.learning_package.id
        )
        for saved_entity in saved_entities:
            saved_draft_version = publishing_api.get_draft_version(saved_entity)
            input_entity = entity_inputs[saved_entity.key]

            if for_publishing:
                input_version_num = input_entity.published.version_num
            else:
                input_version_num = input_entity.draft.version_num

            # The version we want to set is already the current draft, which
            # means there's nothing to do.
            if (
                saved_draft_version
                and saved_draft_version.version_num == input_version_num
            ):
                continue

            if input_version_num is None:
                version_id_to_set = None
            else:
                version_model_to_publish = saved_entity.versions.get(
                    version_num=input_version_num
                )
                version_id_to_set = version_model_to_publish.id

            publishing_api.set_draft_version(
                saved_entity.id,
                version_id_to_set,
                set_at=target.loaded_at,
                set_by=target.user.id,
            )
