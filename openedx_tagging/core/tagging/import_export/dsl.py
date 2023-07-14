from typing import List

from ..models import Taxonomy
from .actions import ImportAction, available_actions

class TagDSL:
    """
    Tag representation on the import DSL
    """
    id: str
    value: str
    parent_id: str
    action: str

    def __init__(
        self,
        id: str,
        value: str,
        parent_id: str=None,
        action: str=None,
    ):
        self.id = id
        self.value = value
        self.parent_id = parent_id
        self.action = action

    
class TagImportDSL:
    actions: List[ImportAction]
    taxonomy: Taxonomy

    def __init__(self, taxonomy: Taxonomy):
        self.actions = []
        self.taxonomy = taxonomy

    def generate_actions(
        self,
        tags: List[TagDSL],
        reaplace=False,
    ) -> List[ImportError]:
        pass

    def execute(self) -> List[ImportError]:
        pass

    def plan(self) -> List[str]:
        pass
