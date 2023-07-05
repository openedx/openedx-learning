from typing import List

from django.conf import settings
from django.contrib.auth import get_user_model

from openedx_tagging.core.tagging.models import ObjectTag, Tag, SystemTaxonomy, SystemDefinedTaxonomyTagsType

class IdBasedSystemTaxonomyMixin:
    """
    Mixin for ID based taxonomies.

    Used to build tags with a prefix. E.x user:<Id>
    """

    prefix = ""
    separator = ":"

    @property
    def creation_type(self) -> SystemDefinedTaxonomyTagsType:
        return SystemDefinedTaxonomyTagsType.free_form
    
    def get_id(self, tag_value):
        """
        Get the id part of the tag
        """
        return tag_value.split(self.separator)[1]

    def build_tag(self, id):
        """
        Build the tag with the prefix and the separator
        """
        return f"{self.prefix}{self.separator}{id}"
    
    def tag_object(
        self, tags: List, object_id: str, object_type: str
    ) -> List["ObjectTag"]:
        """
        Overwriten the tag_object of the Taxonomy model

        Preprocess and build the new tags
        """
        new_tags = []
        for tag in tags:
            new_tags.append(self.build_tag(tag))
        
        return super().tag_object(tags, object_id, object_type)


class LanguageTaxonomy(SystemTaxonomy):
    """
    Language system-defined taxonomy.

    Tag creation: Hardcoded by fixtures
    Visible: True
    Allow multiple: False
    Tags: ISO 639-1 Languages

    The tags are filtered and validated taking into account the 
    languages available in Django LANGUAGES settings var
    """

    class Meta:
        proxy = True

    @property
    def is_visible(self) -> bool:
        raise True
    
    @property
    def creation_type(self) -> SystemDefinedTaxonomyTagsType:
        return SystemDefinedTaxonomyTagsType.closed
    
    def get_available_languages(self) -> List[str]:
        """
        Get the available languages from Django LANGUAGE.
        """
        langs = set()
        for django_lang in settings.LANGUAGES:
            # Split to get the language part
            langs.add(django_lang[0].split('-')[0])
        return langs

    def get_tags(self) -> List[Tag]:
        """
        Returns a list of tags of the available languages.
        """
        tags = super().get_tags()
        result = []
        available_langs = self.get_available_languages()
        for tag in tags:
            if tag.external_id in available_langs:
                result.append(tag)
        return result

    def validate_object_tag(
        self,
        object_tag: "ObjectTag",
        check_taxonomy=True,
        check_tag=True,
        check_object=True,
    ) -> bool:
        """
        Makes the normal object validation and validates if the
        tag is an available language
        """
        validation = super().validate_object_tag(
            object_tag,
            check_taxonomy,
            check_tag,
            check_object,
        )
        if not validation:
            return False

        available_langs = self.get_available_languages()

        # Must be linked to a tag and must be an available language
        if not object_tag.tag or not object_tag.tag.external_id in available_langs:
            return False

        return True
    

class AuthorTaxonomy(SystemTaxonomy, IdBasedSystemTaxonomyMixin):
    """
    Author system-defined taxonomy

    Tag creation: Free form
    Visible: False
    Allow multiple: False
    Tags: Id's of users in the form: author:<ID>
    """

    class Meta:
        proxy = True

    prefix = "author"

    @property
    def is_visible(self) -> bool:
        raise False

    def validate_object_tag(
        self,
        object_tag: "ObjectTag",
        check_taxonomy=True,
        check_tag=True,
        check_object=True,
    ) -> bool:
        """
        Makes the normal object validation and validates if the user exists
        """
        validation = super().validate_object_tag(
            object_tag,
            check_taxonomy,
            check_tag,
            check_object,
        )
        if not validation:
            return False
        
        user_id = self.get_id(object_tag.value)

        # The user must exists
        if not self._user_exists(user_id):
            return False
        
        return True

    def _user_exists(self, user_id):
        """
        Verify if an user exists
        """
        return get_user_model().objects.filter(id=user_id).exists()
