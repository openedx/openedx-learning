"""
Helper mixin classes for content apps that want to use the publishing app.
"""
from __future__ import annotations

from functools import cached_property

from django.core.exceptions import ImproperlyConfigured
from django.db import models
from django.db.models.query import QuerySet

from .models import Draft, PublishableEntity, PublishableEntityVersion, Published


class PublishableEntityMixin(models.Model):
    """
    Convenience mixin to link your models against PublishableEntity.

    Please see docstring for PublishableEntity for more details.

    If you use this class, you *MUST* also use PublishableEntityVersionMixin and
    the publishing app's api.register_content_models (see its docstring for
    details).
    """

    class PublishableEntityMixinManager(models.Manager):
        def get_queryset(self) -> QuerySet:
            return super().get_queryset().select_related("publishable_entity")

    objects: models.Manager[PublishableEntityMixin] = PublishableEntityMixinManager()

    publishable_entity = models.OneToOneField(
        PublishableEntity, on_delete=models.CASCADE, primary_key=True
    )

    @cached_property
    def versioning(self):
        return self.VersioningHelper(self)

    @property
    def uuid(self):
        return self.publishable_entity.uuid

    @property
    def key(self):
        return self.publishable_entity.key

    @property
    def created(self):
        return self.publishable_entity.created

    class Meta:
        abstract = True

    class VersioningHelper:
        """
        Helper class to link content models to their versions.

        The publishing app has PublishableEntity and PublishableEntityVersion.
        This is a helper class so that if you mix PublishableEntityMixin into
        a content model like Component, then you can do something like::

            component.versioning.draft  # current draft ComponentVersion
            component.versioning.published  # current published ComponentVersion

        It links the relationships between content models and their versioned
        counterparts *through* the connection between PublishableEntity and
        PublishableEntityVersion. So ``component.versioning.draft`` ends up
        querying: Component -> PublishableEntity -> Draft ->
        PublishableEntityVersion -> ComponentVersion. But the people writing
        Component don't need to understand how the publishing models work to do
        these common queries.

        Caching Warning
        ---------------
        Note that because we're just using the underlying model's relations,
        calling this a second time will returned the cached relation, and
        not cause a fetch of new data from the database. So for instance, if
        you do::

            # Create a new Component + ComponentVersion
            component, component_version = create_component_and_version(
                learning_package_id=learning_package.id,
                namespace="xblock.v1",
                type="problem",
                local_key="monty_hall",
                title="Monty Hall Problem",
                created=now,
                created_by=None,
            )

            # This will work, because it's never been published
            assert component.versioning.published is None

            # Publishing happens
            publish_all_drafts(learning_package.id, published_at=now)

            # This will FAIL because it's going to use the relation value
            # cached on component instead of going to the database again.
            # You need to re-fetch the component for this to work.
            assert component.versioning.published == component_version

            # You need to manually refetch it from the database to see the new
            # publish status:
            component = get_component_by_pk(component.pk)

            # Now this will work:
            assert component.versioning.published == component_version

        TODO: This probably means we should use a custom Manager to select
        related fields.
        """

        def __init__(self, content_obj):
            self.content_obj = content_obj

            self.content_version_model_cls = (
                PublishableContentModelRegistry.get_versioned_model_cls(
                    type(content_obj)
                )
            )
            # Get the field that points from the *versioned* content model
            # (e.g. ComponentVersion) to the PublishableEntityVersion.
            field_to_pev = self.content_version_model_cls._meta.get_field(
                "publishable_entity_version"
            )

            # Now that we know the field that leads to PublishableEntityVersion,
            # get the reverse related field name so that we can use that later.
            self.related_name = field_to_pev.related_query_name()

        @property
        def draft(self):
            """
            Return the content version object that is the current draft.
            """
            try:
                draft = Draft.objects.get(
                    entity_id=self.content_obj.publishable_entity_id
                )
            except Draft.DoesNotExist:
                # If no Draft object exists at all, then no
                # PublishableEntityVersion was ever created (just the
                # PublishableEntity).
                return None

            draft_pub_ent_version = draft.version

            # There is an entry for this Draft, but the entry is None. This means
            # there was a Draft at some point, but it's been "deleted" (though the
            # actual history is still preserved).
            if draft_pub_ent_version is None:
                return None

            # If we've gotten this far, then draft_pub_ent_version points to an
            # actual PublishableEntityVersion, but we want to follow that and go to
            # the matching content version model.
            return getattr(draft_pub_ent_version, self.related_name)

        @property
        def published(self):
            """
            Return the content version object that is currently published.
            """
            try:
                published = Published.objects.get(
                    entity_id=self.content_obj.publishable_entity_id
                )
            except Published.DoesNotExist:
                # This means it's never been published.
                return None

            published_pub_ent_version = published.version

            # There is a Published entry, but the entry is None. This means that
            # it was published at some point, but it's been "deleted" or
            # unpublished (though the actual history is still preserved).
            if published_pub_ent_version is None:
                return None

            # If we've gotten this far, then published_pub_ent_version points to an
            # actual PublishableEntityVersion, but we want to follow that and go to
            # the matching content version model.
            return getattr(published_pub_ent_version, self.related_name)

        @property
        def versions(self):
            """
            Return a QuerySet of content version models for this content model.

            Example: If you mix PublishableEntityMixin into a Component model,
            This would return you a QuerySet of ComponentVersion models.
            """
            pub_ent = self.content_obj.publishable_entity
            return self.content_version_model_cls.objects.filter(
                publishable_entity_version__entity_id=pub_ent.id
            )


class PublishableEntityVersionMixin(models.Model):
    """
    Convenience mixin to link your models against PublishableEntityVersion.

    Please see docstring for PublishableEntityVersion for more details.

    If you use this class, you *MUST* also use PublishableEntityMixin and the
    publishing app's api.register_content_models (see its docstring for
    details).
    """

    class PublishableEntityVersionMixinManager(models.Manager):
        def get_queryset(self) -> QuerySet:
            return (
                super()
                .get_queryset()
                .select_related(
                    "publishable_entity_version",
                )
            )

    objects: models.Manager[PublishableEntityVersionMixin] = PublishableEntityVersionMixinManager()

    publishable_entity_version = models.OneToOneField(
        PublishableEntityVersion, on_delete=models.CASCADE, primary_key=True
    )

    @property
    def uuid(self):
        return self.publishable_entity_version.uuid

    @property
    def title(self):
        return self.publishable_entity_version.title

    @property
    def created(self):
        return self.publishable_entity_version.created

    @property
    def version_num(self):
        return self.publishable_entity_version.version_num

    class Meta:
        abstract = True


class PublishableContentModelRegistry:
    """
    This class tracks content models built on PublishableEntity(Version).
    """

    _unversioned_to_versioned: dict[type[PublishableEntityMixin], type[PublishableEntityVersionMixin]] = {}
    _versioned_to_unversioned: dict[type[PublishableEntityVersionMixin], type[PublishableEntityMixin]] = {}

    @classmethod
    def register(
        cls,
        content_model_cls: type[PublishableEntityMixin],
        content_version_model_cls: type[PublishableEntityVersionMixin],
    ):
        """
        Register what content model maps to what content version model.

        If you want to call this from another app, please use the
        ``register_content_models`` function in this app's ``api`` module
        instead.
        """
        if not issubclass(content_model_cls, PublishableEntityMixin):
            raise ImproperlyConfigured(
                f"{content_model_cls} must inherit from PublishableEntityMixin"
            )
        if not issubclass(content_version_model_cls, PublishableEntityVersionMixin):
            raise ImproperlyConfigured(
                f"{content_version_model_cls} must inherit from PublishableEntityMixin"
            )

        cls._unversioned_to_versioned[content_model_cls] = content_version_model_cls
        cls._versioned_to_unversioned[content_version_model_cls] = content_model_cls

    @classmethod
    def get_versioned_model_cls(cls, content_model_cls):
        return cls._unversioned_to_versioned[content_model_cls]

    @classmethod
    def get_unversioned_model_cls(cls, content_version_model_cls):
        return cls._versioned_to_unversioned[content_version_model_cls]
