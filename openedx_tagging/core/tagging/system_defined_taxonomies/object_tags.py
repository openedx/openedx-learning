from typing import List

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.exceptions import FieldDoesNotExist
from django.db import models


from openedx_tagging.core.tagging.models import (
    Tag,
    Taxonomy,
    OpenObjectTag,
    ClosedObjectTag,
)
from openedx_tagging.core.tagging.registry import register_object_tag_class


class OpenSystemObjectTag(OpenObjectTag):
    """
    Free-text object tag used on system-defined taxonomies
    """

    class Meta:
        proxy = True

    @classmethod
    def valid_for(cls, taxonomy: Taxonomy = None, **kwars):
        """
        Returns True if the the taxonomy is system-defined
        """
        return super().valid_for(taxonomy=taxonomy) and taxonomy.system_defined
    
class ClosedSystemObjectTag(ClosedObjectTag):
    """
    Object tags linked to a closed system-taxonomy
    """

    class Meta:
        proxy = True

    @classmethod
    def valid_for(cls, taxonomy: Taxonomy = None, tag: Tag = None, **kargs):
        """
        Returns True if the the taxonomy is system-defined
        """
        return super().valid_for(taxonomy=taxonomy, tag=tag) and taxonomy.system_defined


class ModelObjectTag(OpenSystemObjectTag):
    """
    Object tags used with tags that relate to the id of a model
    
    This object tag class is not registered as it needs to have an associated model
    """

    class Meta:
        proxy = True

    tag_class_model = None

    @classmethod
    def valid_for(cls, taxonomy: Taxonomy = None, **kwars):
        """
        Validates if has an associated Django model that has an Id
        """
        if not super().valid_for(taxonomy=taxonomy) or not cls.tag_class_model:
            return False
        
        # Verify that is a Django model
        if not issubclass(cls.tag_class_model, models.Model):
            return False

        # Verify that the model has 'id' field
        try:
            cls.tag_class_model._meta.get_field('id')
        except FieldDoesNotExist:
            return False

        return True
    
    def _check_instance(self):
        """
        Validates if the instance exists
        """
        try:
            intance_id = int(self.value)
        except ValueError:
            return False
        return self.tag_class_model.objects.filter(id=intance_id).exists()

    def _check_tag(self):
        """
        Validates if the instance exists
        """
        if not super()._check_tag():
            return False
        
        # Validates if the instance exists
        if not self._check_instance():
            return False
        
        return True


class UserObjectTag(ModelObjectTag):
    """
    Object tags used on taxonomies associated with user model
    """

    class Meta:
        proxy = True

    tag_class_model = get_user_model()


class LanguageObjectTag(ClosedSystemObjectTag):
    """
    Object tag for Languages

    The tags are filtered and validated taking into account the 
    languages available in Django LANGUAGES settings var
    """

    class Meta:
        proxy = True

    @classmethod
    def get_tags(cls, taxonomy: Taxonomy) -> List[Tag]:
        """
        Returns a list of tags of the available languages.
        """
        # TODO we need to overweite this
        # tags = super().get_tags()
        tags = taxonomy.tag_set.objects().all()
        result = []
        available_langs = cls.get_available_languages()
        for tag in tags:
            if tag.external_id in available_langs:
                result.append(tag)
        return result
    
    @classmethod
    def _get_available_languages(cls) -> List[str]:
        """
        Get the available languages from Django LANGUAGE.
        """
        langs = set()
        for django_lang in settings.LANGUAGES:
            # Split to get the language part
            langs.add(django_lang[0].split('-')[0])
        return langs


    def _check_tag(self):
        """
        Validates if the language tag is on the available languages
        """
        if not super()._check_tag():
            return False

        available_langs = self._get_available_languages()

        # Must be linked to a tag and must be an available language
        if not self.tag or not self.tag.external_id in available_langs:
            return False
        
        return True


# Register the object tag classes in reverse order for how we want them considered
register_object_tag_class(LanguageObjectTag)
register_object_tag_class(UserObjectTag)
