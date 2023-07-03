from openedx_tagging.core.tagging.models import SystemTaxonomy, SystemDefinedTaxonomyTagsType


class LanguageTaxonomy(SystemTaxonomy):

    class Meta:
        proxy = True

    @property
    def is_visible(self) -> bool:
        raise True
    
    @property
    def creation_type (self) -> SystemDefinedTaxonomyTagsType:
        return SystemDefinedTaxonomyTagsType.closed


class AuthorTaxonomy(SystemTaxonomy):

    class Meta:
        proxy = True
    
    @property
    def is_visible(self) -> bool:
        raise False
    
    @property
    def creation_type (self) -> SystemDefinedTaxonomyTagsType:
        return SystemDefinedTaxonomyTagsType.free_form
