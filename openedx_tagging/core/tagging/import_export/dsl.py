from typing import List

from django.utils.translation import gettext_lazy as _

from ..models import Taxonomy
from .actions import DeleteTag, ImportAction, UpdateParentTag, available_actions


class TagDSL:
    """
    Tag representation on the import DSL
    """
    id: str
    value: str
    parent_id: str
    action: str
    index: int

    def __init__(
        self,
        id: str,
        value: str,
        index: str,
        parent_id: str=None,
        action: str=None,
    ):
        self.id = id
        self.value = value
        self.index = index
        self.parent_id = parent_id
        self.action = action

    
class TagImportDSL:
    actions: List[ImportAction]
    indexed_actions: dict
    actions_dict: dict
    taxonomy: Taxonomy

    def __init__(self, taxonomy: Taxonomy):
        self.actions = []
        self.errors = []
        self.taxonomy = taxonomy
        self.indexed_actions = {}
        self.actions_dict = {}
        for action in available_actions:
            self.indexed_actions[action.name] = []

    def _build_action(self, action_cls, tag: TagDSL):
        """
        Build an action with `tag`.

        Run action validation and adds the errors to the errors lists
        Add to the action list and the indexed actions
        """
        action = action_cls(self.taxonomy, tag, len(self.actions))

        # We validate if there are no inconsistencies when executing this action
        self.errors.append(action.validate(self.indexed_actions))

        # Add action
        self.actions.append(action)

        # Index the actions for search
        self.indexed_actions[action.name].append(action)

    def _delete_tags(self, tags: List[str]):
        """
        Delete `tags`
        """
        for tag in tags:
            for child in tag.children:
                if child.external_id not in tags:
                    # If the child is not to be removed, 
                    # then update its parent
                    self._build_action(
                        UpdateParentTag,
                        TagDSL(
                            id=child.external_id,
                            value=child.value,
                            parent_id=None,
                        )
                    )

            # Delete action
            self._build_action(
                DeleteTag,
                TagDSL(
                    id=tag.external_id,
                )
            )

    def generate_actions(
        self,
        tags: List[TagDSL],
        replace=False,
    ):
        """
        Generates actions from `tags`.
        
        Validates each action and create respective errors
        If `replace` is True, then deletes the tags that have not been read
        """
        self.actions.clear()
        self.errors.clear()
        tags_for_delete = {}

        if replace:
            tags_for_delete = {
                tag.external_id: tag
                for tag in self.taxonomy.tag_set
            }

        for tag in tags:
            # Check all available actions and add which ones should be executed
            for action_cls in available_actions:
                if action_cls.valid_for(self.taxonomy, tag):
                    self._build_action(action_cls, tag)

            if replace:
                tags_for_delete.pop(tag.id)

        if replace:
            # Delete all not readed tags
            self._delete_tags(tags_for_delete)

    def execute(self) -> List[ImportError]:
        pass

    def plan(self) -> List[str]:
        pass
