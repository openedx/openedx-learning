"""
Actions for import tags
"""
from typing import List

from django.utils.translation import gettext_lazy as _

from ..models import Taxonomy, Tag
from .exceptions import ImportActionError, ImportActionConflict


class ImportAction:
    """
    Base class to create actions

    Each action is a simple operation to be performed on the database.
    There are no compound actions or actions that have to do with each other.

    To create an Action you need to implement the following:

    Given a TagItem, the actions to be performed must be deduced
    by comparing with the tag on the database.
    Ex. The create action is inferred if the tag does not exist in the database.
    This check is done in `valid_for`

    Then each action validates if the change is consistent with the database
    or with previous actions.
    Ex. Verify that when creating a tag, there is not a previous creation action
    that has the same tag_id.
    This checks is done in `validate`

    Then the actions are executed. Ex. Create the tag on the database
    This is done in `execute`
    """

    name = "import_action"

    def __init__(self, taxonomy: Taxonomy, tag, index: int):
        self.taxonomy = taxonomy
        self.tag = tag
        self.index = index

    def __repr__(self):
        return str(_(f"Action {self.name} (index={self.index},id={self.tag.id})"))

    def __str__(self):
        return self.__repr__()

    @classmethod
    def valid_for(cls, taxonomy: Taxonomy, tag) -> bool:
        """
        Implement this to meet the conditions that a `TagItem` needs
        to have for this action. All actions that are valid with
        this function are created.
        """
        raise NotImplementedError

    def validate(self, indexed_actions) -> List[ImportActionError]:
        """
        Implement this to find inconsistencies with tags in the
        database or with previous actions.
        """
        raise NotImplementedError

    def execute(self):
        """
        Implement this to execute the action.
        """
        raise NotImplementedError

    def _get_tag(self):
        """
        Returns the respective tag of this actions
        """
        return self.taxonomy.tag_set.get(external_id=self.tag.id)

    def _search_action(
        self,
        indexed_actions: dict,
        action_name: str,
        attr: str,
        search_value: str,
    ):
        """
        Use this function to find and action using an `attr` of `TagItem`
        """
        for action in indexed_actions[action_name]:
            if search_value == getattr(action.tag, attr):
                return action

        return None

    def _validate_parent(self, indexed_actions) -> ImportActionError:
        """
        Validates if the parent is created
        """
        try:
            # Validates that the parent exists on the taxonomy
            self.taxonomy.tag_set.get(external_id=self.tag.parent_id)
        except Tag.DoesNotExist:
            # Or if the parent is created on previous actions
            if not self._search_action(
                indexed_actions, CreateTag.name, "id", self.tag.parent_id
            ):
                return ImportActionError(
                    action=self,
                    tag_id=self.tag.id,
                    message=_(
                        f"Unknown parent tag ({self.tag.parent_id}). "
                        "You need to add parent before the child in your file."
                    ),
                )

    def _validate_value(self, indexed_actions):
        """
        Check for value duplicates in the models and in previous create/rename
        actions
        """
        try:
            # Validates if exists a tag with the same value on the Taxonomy
            tag = self.taxonomy.tag_set.get(value=self.tag.value)
            return ImportActionError(
                action=self,
                tag_id=self.tag.id,
                message=_(f"Duplicated tag value with tag (id={tag.id})."),
            )
        except Tag.DoesNotExist:
            # Validates value duplication on create actions
            action = self._search_action(
                indexed_actions,
                CreateTag.name,
                "value",
                self.tag.value,
            )

            if not action:
                # Validates value duplication on rename actions
                action = self._search_action(
                    indexed_actions,
                    RenameTag.name,
                    "value",
                    self.tag.value,
                )

            if action:
                return ImportActionConflict(
                    action=self,
                    tag_id=self.tag.id,
                    conflict_action_index=action.index,
                    message=_("Duplicated tag value."),
                )


class CreateTag(ImportAction):
    """
    Action for create a Tag

    Action created if the tag doesn't exist on the database

    Validations:
    - Id duplicates with previous create actions.
    - Value duplicates with tags on the database.
    - Value duplicates with previous create and rename actions.
    - Parent validation. If the parent is in the database or created
      in previous actions.
    """

    name = "create"

    def __str__(self):
        return str(
            _(
                "Create a new tag with values "
                f"(external_id={self.tag.id}, value={self.tag.value}, "
                f"parent_id={self.tag.parent_id})."
            )
        )

    @classmethod
    def valid_for(cls, taxonomy: Taxonomy, tag) -> bool:
        """
        Validates if the tag does not exist
        """
        try:
            taxonomy.tag_set.get(external_id=tag.id)
            return False
        except Tag.DoesNotExist:
            return True

    def _validate_id(self, indexed_actions):
        """
        Check for id duplicates in previous create actions
        """
        action = self._search_action(indexed_actions, self.name, "id", self.tag.id)
        if action:
            return ImportActionConflict(
                action=self,
                tag_id=self.tag.id,
                conflict_action_index=action.index,
                message=_("Duplicated external_id tag."),
            )

    def validate(self, indexed_actions) -> List[ImportActionError]:
        """
        Validates the creation action
        """
        errors = []

        # Duplicate id validation with previous create actions
        error = self._validate_id(indexed_actions)
        if error:
            errors.append(error)

        # Duplicate value validation
        error = self._validate_value(indexed_actions)
        if error:
            errors.append(error)

        # Parent validation
        if self.tag.parent_id:
            error = self._validate_parent(indexed_actions)
            if error:
                errors.append(error)

        return errors

    def execute(self):
        """
        Creates a Tag
        """
        parent = None
        if self.tag.parent_id:
            parent = self.taxonomy.tag_set.get(external_id=self.tag.parent_id)
        tag = Tag(
            taxonomy=self.taxonomy,
            parent=parent,
            value=self.tag.value,
            external_id=self.tag.id,
        )
        tag.save()


class UpdateParentTag(ImportAction):
    """
    Action for update the parent of a Tag

    Action created if there is a change on the parent

    Validations:
    - Parent validation. If the parent is in the database
      or created in previous actions.
    """

    name = "update_parent"

    def __str__(self):
        taxonomy_tag = self._get_tag()
        if not taxonomy_tag.parent:
            from_str = _("from empty parent")
        else:
            from_str = _(f"from parent (external_id={taxonomy_tag.parent.external_id})")

        return str(
            _(
                f"Update the parent of tag (id={taxonomy_tag.id}) "
                f"{from_str} to parent (external_id={self.tag.parent_id})."
            )
        )

    @classmethod
    def valid_for(cls, taxonomy: Taxonomy, tag) -> bool:
        """
        Validates if there is a change on the parent
        """
        try:
            taxonomy_tag = taxonomy.tag_set.get(external_id=tag.id)
            return (
                taxonomy_tag.parent is not None
                and taxonomy_tag.parent.external_id != tag.parent_id
            ) or (taxonomy_tag.parent is None and tag.parent_id is not None)
        except Tag.DoesNotExist:
            return False

    def validate(self, indexed_actions) -> List[ImportActionError]:
        """
        Validates the update parent action
        """
        errors = []

        # Parent validation
        if self.tag.parent_id:
            error = self._validate_parent(indexed_actions)
            if error:
                errors.append(error)

        return errors

    def execute(self):
        """
        Updates the parent of a tag
        """
        tag = self._get_tag()
        parent = None
        if self.tag.parent_id:
            parent = self.taxonomy.tag_set.get(external_id=self.tag.parent_id)
        tag.parent = parent
        tag.save()


class RenameTag(ImportAction):
    """
    Action for rename a Tag

    Action created if there is a change on the tag value

    Validations:
    - Value duplicates with tags on the database.
    - Value duplicates with previous create and rename actions.
    """

    name = "rename"

    def __str__(self):
        taxonomy_tag = self._get_tag()
        return str(
            _(
                f"Rename tag value of tag (id={taxonomy_tag.id}) "
                f"from '{taxonomy_tag.value}' to '{self.tag.value}'"
            )
        )

    @classmethod
    def valid_for(cls, taxonomy: Taxonomy, tag) -> bool:
        """
        Validates if there is a change on the tag value
        """
        try:
            taxonomy_tag = taxonomy.tag_set.get(external_id=tag.id)
            return taxonomy_tag.value != tag.value
        except Tag.DoesNotExist:
            return False

    def validate(self, indexed_actions) -> List[ImportActionError]:
        """
        Validates the rename action
        """
        errors = []

        # Duplicate value validation
        error = self._validate_value(indexed_actions)
        if error:
            errors.append(error)

        return errors

    def execute(self):
        """
        Rename a tag
        """
        tag = self._get_tag()
        tag.value = self.tag.value
        tag.save()


class DeleteTag(ImportAction):
    """
    Action for delete a Tag

    Action created if the action of the tag is 'delete'

    Does not require validations
    """

    def __str__(self):
        taxonomy_tag = self._get_tag()
        return str(_(f"Delete tag (id={taxonomy_tag.id})"))

    name = "delete"

    @classmethod
    def valid_for(cls, taxonomy: Taxonomy, tag) -> bool:
        """
        Validates if the action is delete and the tag exists
        """
        try:
            taxonomy.tag_set.get(external_id=tag.id)
            return tag.action == cls.name
        except Tag.DoesNotExist:
            return False

    def validate(self, indexed_actions) -> List[ImportActionError]:
        """
        No validations necessary
        """
        # TODO: Will it be necessary to check if this tag has children?
        return []

    def execute(self):
        """
        Delete a tag
        """
        tag = self._get_tag()
        tag.delete()


class WithoutChanges(ImportAction):
    """
    Action when there is no change on the Tag

    Does not require validations
    """

    name = "without_changes"

    def __str__(self):
        return str(_(f"No changes needed for tag (external_id={self.tag.id})"))

    @classmethod
    def valid_for(cls, taxonomy: Taxonomy, tag) -> bool:
        """
        No validations necessary
        """
        return False

    def validate(self, indexed_actions) -> List[ImportActionError]:
        """
        No validations necessary
        """
        return []

    def execute(self):
        """
        Do nothing
        """


# Register actions here in the order in which you want to check.
available_actions = [
    UpdateParentTag,
    RenameTag,
    CreateTag,
    DeleteTag,
    WithoutChanges,
]
