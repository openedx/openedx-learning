"""
Model and functions to create a plan/execution with DSL actions.
"""
from datetime import datetime
from enum import Enum
from typing import List, Optional

from django.db import transaction
from django.utils.translation import gettext_lazy as _

from ..models import Taxonomy
from .actions import (
    DeleteTag,
    ImportAction,
    UpdateParentTag,
    WithoutChanges,
    available_actions,
)
from .exceptions import ImportActionError, TagParserError
from django.db import models

class TagImportTaskState(Enum):
    LOADING_DATA = 'loading_data'
    PLANNING = 'planning'
    EXECUTING = 'executing'
    SUCCESS = 'success'
    ERROR = 'error'


class TagImportTask(models.Model):
    """
    Stores the state, plan and logs of a tag import task
    """
    id = models.BigAutoField(primary_key=True)

    taxonomy = models.ForeignKey(
        "Taxonomy",
        on_delete=models.CASCADE,
        help_text=_("Taxonomy associated with this import"),
    )

    log = models.TextField(
        null=True,
        default=None,
        help_text=_("Action execution logs")
    )

    status = models.CharField(
        max_length=20, 
        choices=[(status, status.value) for status in TagImportTaskState],
        help_text=_("Task status"),
    )

    creation_date = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            models.Index(fields=['taxonomy', '-creation_date']),
        ]

    @classmethod
    def create(cls, taxonomy: Taxonomy):
        task = cls(
            taxonomy=taxonomy,
            status=TagImportTaskState.LOADING_DATA.value,
            log='',
        )
        task.save()
        return task
    
    def add_log(self, message: str, save=True):
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        log_message = f"[{timestamp}] {message}\n"
        self.log += log_message
        if save:
            self.save()

    def log_exception(self, exception: Exception):
        self.add_log(str(exception), save=False)
        self.status = TagImportTaskState.ERROR.value
        self.save()

    def log_parser_start(self):
        self.add_log(_("Starting to load data from file"))

    def log_parser_end(self):
        self.add_log(_("Load data finished"))

    def handle_parser_errors(self, errors: List[TagParserError]):
        for error in errors:
            self.add_log(f"{str(error)}", save=False)
        self.status = TagImportTaskState.ERROR.value
        self.save()

    def log_start_planning(self):
        self.add_log(_("Starting planning the actions"), save=False)
        self.status = TagImportTaskState.PLANNING.value
        self.save()
    
    def log_end_planning(self, plan: "TagDSL"):
        self.add_log(_("Plan finished"))
        plan_str = plan.plan()
        self.log += plan_str
        self.save()
        
    def handle_plan_errors(self):
        # Error are logged with plan
        self.status = TagImportTaskState.ERROR.value
        self.save()


class TagDSL:
    """
    Tag representation on the import DSL
    """

    id: str
    value: str
    index: Optional[int]
    parent_id: Optional[str]
    action: Optional[str]

    def __init__(
        self,
        id: str,
        value: str,
        index: str = 0,
        parent_id: str = None,
        action: str = None,
    ):
        self.id = id
        self.value = value
        self.index = index
        self.parent_id = parent_id
        self.action = action


class TagImportDSL:
    """
    Class with functions to build an import plan and excute the plan
    """

    actions: List[ImportAction]
    errors: List[ImportActionError]
    indexed_actions: dict
    actions_dict: dict
    taxonomy: Taxonomy

    def __init__(self, taxonomy: Taxonomy):
        self.actions = []
        self.errors = []
        self.taxonomy = taxonomy
        self.actions_dict = {}
        self._init_indexed_actions()

    def _init_indexed_actions(self):
        """
        Initialize the `indexed_actions` dict
        """
        self.indexed_actions = {}
        for action in available_actions:
            self.indexed_actions[action.name] = []

    def _build_action(self, action_cls, tag: TagDSL):
        """
        Build an action with `tag`.

        Run action validation and adds the errors to the errors lists
        Add to the action list and the indexed actions
        """
        action = action_cls(self.taxonomy, tag, len(self.actions) + 1)

        # We validate if there are no inconsistencies when executing this action
        self.errors.extend(action.validate(self.indexed_actions))

        # Add action
        self.actions.append(action)

        # Index the actions for search
        self.indexed_actions[action.name].append(action)

    def _build_delete_actions(self, tags: dict):
        """
        Adds delete actions for `tags`
        """
        for tag in tags.values():
            for child in tag.children.all():
                # child parent to avoid delete childs
                self._build_action(
                    UpdateParentTag,
                    TagDSL(
                        id=child.external_id,
                        value=child.value,
                        parent_id=None,
                    ),
                )

            # Delete action
            self._build_action(
                DeleteTag,
                TagDSL(
                    id=tag.external_id,
                    value=tag.value,
                ),
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

        TODO: Missing join/reduce actions. Eg. A tag may have no changes,
        but then its parent needs to be updated because its parent is deleted.
        Those two actions should be merged.
        """
        self.actions.clear()
        self.errors.clear()
        self._init_indexed_actions()
        tags_for_delete = {}

        if replace:
            tags_for_delete = {
                tag.external_id: tag for tag in self.taxonomy.tag_set.all()
            }

        for tag in tags:
            has_action = False

            # Check all available actions and add which ones should be executed
            for action_cls in available_actions:
                if action_cls.valid_for(self.taxonomy, tag):
                    self._build_action(action_cls, tag)
                    has_action = True

            if not has_action:
                # If it doesn't find an action, a "without changes" is added
                self._build_action(WithoutChanges, tag)

            if replace:
                tags_for_delete.pop(tag.id)

        if replace:
            # Delete all not readed tags
            self._build_delete_actions(tags_for_delete)

    def plan(self) -> str:
        """
        Returns an string with the plan and errors
        """
        result = "Plan\n" "--------------------------------\n"
        for action in self.actions:
            result += f"#{action.index}: {str(action)}\n"

        if self.errors:
            result += "Output errors\n" "--------------------------------\n"
            for error in self.errors:
                result += f"{str(error)}\n"

        return result

    @transaction.atomic()
    def execute(self, task: TagImportTask = None):
        if self.errors:
            return False
        for action in self.actions:
            if task:
                task.add_log(f"{str(action)} [Started]")
            action.execute()
            if task:
                task.add_log(f"{str(action)} [Success]")
        return True
