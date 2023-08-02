""" Tagging app system-defined taxonomies data models """
import logging
from typing import Any, List, Type, Union

from django.conf import settings
from django.contrib.auth import get_user_model
from django.db import models

from openedx_tagging.core.tagging.models.base import ObjectTag

from .base import Tag, Taxonomy, ObjectTag

log = logging.getLogger(__name__)


class SystemDefinedTaxonomy(Taxonomy):
    """
    Simple subclass of Taxonomy which requires the system_defined flag to be set.
    """

    class Meta:
        proxy = True

    @property
    def system_defined(self) -> bool:
        """
        Indicates that tags and metadata for this taxonomy are maintained by the system;
        taxonomy admins will not be permitted to modify them.
        """
        return True


class ModelObjectTag(ObjectTag):
    """
    Model-based ObjectTag, abstract class.

    Used by ModelSystemDefinedTaxonomy to maintain dynamic Tags which are associated with a configured Model instance.
    """

    class Meta:
        proxy = True

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        """
        Checks if the `tag_class_model` is correct
        """
        assert issubclass(self.tag_class_model, models.Model)
        super().__init__(*args, **kwargs)

    @property
    def tag_class_model(self) -> Type:
        """
        Subclasses must implement this method to return the Django.model
        class referenced by these object tags.
        """
        raise NotImplementedError

    @property
    def tag_class_value(self) -> str:
        """
        Returns the name of the tag_class_model field to use as the Tag.value when creating Tags for this taxonomy.

        Subclasses may override this method to use different fields.
        """
        return "pk"

    def get_instance(self) -> Union[models.Model, None]:
        """
        Returns the instance of tag_class_model associated with this object tag, or None if not found.
        """
        instance_id = self.tag.external_id if self.tag else None
        if instance_id:
            try:
                return self.tag_class_model.objects.get(pk=instance_id)
            except ValueError as e:
                log.exception(f"{self}: {str(e)}")
            except self.tag_class_model.DoesNotExist:
                log.exception(
                    f"{self}: {self.tag_class_model.__name__} pk={instance_id} does not exist."
                )

        return None

    def _resync_tag(self) -> bool:
        """
        Resync our tag's value with the value from the instance.

        If the instance associated with the tag no longer exists, we unset our tag, because it's no longer valid.

        Returns True if the given tag was changed, False otherwise.
        """
        instance = self.get_instance()
        if instance:
            value = getattr(instance, self.tag_class_value)
            self.value = value
            if self.tag and self.tag.value != value:
                self.tag.value = value
                self.tag.save()
                return True
        else:
            self.tag = None

        return False

    @property
    def tag_ref(self) -> str:
        return (self.tag.external_id or self.tag.id) if self.tag_id else self._value

    @tag_ref.setter
    def tag_ref(self, tag_ref: str):
        """
        Sets the ObjectTag's Tag and/or value, depending on whether a valid Tag is found, or can be created.

        Creates a Tag for the given tag_ref value, if one containing that external_id not already exist.
        """
        self.value = tag_ref

        if self.taxonomy_id:
            try:
                self.tag = self.taxonomy.tag_set.get(
                    external_id=tag_ref,
                )
            except (ValueError, Tag.DoesNotExist):
                # Creates a new Tag for this instance
                self.tag = Tag(
                    taxonomy=self.taxonomy,
                    external_id=tag_ref,
                )

            self._resync_tag()


class ModelSystemDefinedTaxonomy(SystemDefinedTaxonomy):
    """
    Model based system taxonomy abstract class.

    This type of taxonomy has an associated Django model in ModelObjectTag.tag_class_model().
    They are designed to create Tags when required for new ObjectTags, to maintain
    their status as "closed" taxonomies.
    The Tags are representations of the instances of the associated model.

    Tag.external_id stores an identifier from the instance (`pk` as default)
    and Tag.value stores a human readable representation of the instance
    (e.g. `username`).
    The subclasses can override this behavior, to choose the right field.

    When an ObjectTag is created with an existing Tag,
    the Tag is re-synchronized with its instance.
    """

    class Meta:
        proxy = True

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        """
        Checks if the `object_tag_class` is a subclass of ModelObjectTag.
        """
        assert issubclass(self.object_tag_class, ModelObjectTag)
        super().__init__(*args, **kwargs)

    @property
    def object_tag_class(self) -> Type:
        """
        Returns the ObjectTag subclass associated with this taxonomy.

        Model Taxonomy subclasses must implement this to provide a ModelObjectTag subclass.
        """
        raise NotImplementedError

    def _check_instance(self, object_tag: ObjectTag) -> bool:
        """
        Returns True if the instance exists

        Subclasses can override this method to perform their own instance validation checks.
        """
        object_tag = self.object_tag_class.cast(object_tag)
        return bool(object_tag.get_instance())

    def _check_tag(self, object_tag: ObjectTag) -> bool:
        """
        Returns True if the instance is valid
        """
        return super()._check_tag(object_tag) and self._check_instance(object_tag)


class UserModelObjectTag(ModelObjectTag):
    """
    ObjectTags for the UserSystemDefinedTaxonomy.
    """

    class Meta:
        proxy = True

    @property
    def tag_class_model(self) -> Type:
        """
        Associate the user model
        """
        return get_user_model()

    @property
    def tag_class_value(self) -> str:
        """
        Returns the name of the tag_class_model field to use as the Tag.value when creating Tags for this taxonomy.

        Subclasses may override this method to use different fields.
        """
        return "username"


class UserSystemDefinedTaxonomy(ModelSystemDefinedTaxonomy):
    """
    User based system taxonomy class.
    """

    class Meta:
        proxy = True

    @property
    def object_tag_class(self) -> Type:
        """
        Returns the ObjectTag subclass associated with this taxonomy, which is ModelObjectTag by default.

        Model Taxonomy subclasses must implement this to provide a ModelObjectTag subclass.
        """
        return UserModelObjectTag


class LanguageTaxonomy(SystemDefinedTaxonomy):
    """
    Language System-defined taxonomy

    The tags are filtered and validated taking into account the
    languages available in Django LANGUAGES settings var
    """

    class Meta:
        proxy = True

    def get_tags(self, tag_set: models.QuerySet = None) -> List[Tag]:
        """
        Returns a list of all the available Language Tags, annotated with ``depth`` = 0.
        """
        available_langs = self._get_available_languages()
        tag_set = self.tag_set.filter(external_id__in=available_langs)
        return super().get_tags(tag_set=tag_set)

    def _get_available_languages(cls) -> List[str]:
        """
        Get available languages from Django LANGUAGE.
        """
        langs = set()
        for django_lang in settings.LANGUAGES:
            # Split to get the language part
            langs.add(django_lang[0].split("-")[0])
        return langs

    def _check_valid_language(self, object_tag: ObjectTag) -> bool:
        """
        Returns True if the tag is on the available languages
        """
        available_langs = self._get_available_languages()
        return object_tag.tag.external_id in available_langs

    def _check_tag(self, object_tag: ObjectTag) -> bool:
        """
        Returns True if the tag is on the available languages
        """
        return super()._check_tag(object_tag) and self._check_valid_language(object_tag)
