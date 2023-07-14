from ..models import Taxonomy
from .dsl import TagDSL

class ImportAction:

    @classmethod
    def valid_for(cls, taxonomy: Taxonomy, tag: TagDSL):
        raise NotImplementedError

    def validate(self):
        raise NotImplementedError

    def execute(self):
        raise NotImplementedError

    def __init__(self, taxonomy: Taxonomy, tag: TagDSL):
        self.taxonomy = taxonomy
        self.tag = tag


class CreateTag(ImportAction):

    @classmethod
    def valid_for(cls, taxonomy: Taxonomy, tag: TagDSL):
        pass

    def validate(self):
        pass

    def execute(self):
        pass


class UpdateParentTag(ImportAction):

    @classmethod
    def valid_for(cls, taxonomy: Taxonomy, tag: TagDSL):
        pass

    def validate(self):
        pass

    def execute(self):
        pass


class RenameTag(ImportAction):

    @classmethod
    def valid_for(cls, taxonomy: Taxonomy, tag: TagDSL):
        pass

    def validate(self):
        pass

    def execute(self):
        pass


class DeleteTag(ImportAction):

    @classmethod
    def valid_for(cls, taxonomy: Taxonomy, tag: TagDSL):
        pass

    def validate(self):
        pass

    def execute(self):
        pass        


# Register actions here
available_actions = [
    CreateTag,
    UpdateParentTag,
    RenameTag,
    DeleteTag,
]
