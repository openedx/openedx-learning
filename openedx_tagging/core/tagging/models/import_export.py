"""
Models used by the Taxonomy import/export tasks.
"""

from datetime import datetime
from enum import Enum

from django.db import models
from django.utils.translation import gettext as _
from django.utils.translation import gettext_lazy

from .base import Taxonomy


class TagImportTaskState(Enum):
    """
    Enumerates the states that a TagImportTask can be in.
    """
    LOADING_DATA = "loading_data"
    PLANNING = "planning"
    EXECUTING = "executing"
    SUCCESS = "success"
    ERROR = "error"


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
        blank=True, default=None, help_text=gettext_lazy("Action execution logs")
    )

    status = models.CharField(
        max_length=20,
        choices=[(status, status.value) for status in TagImportTaskState],
        help_text=gettext_lazy("Task status"),
    )

    creation_date = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            models.Index(fields=["taxonomy", "-creation_date"]),
        ]

    @classmethod
    def create(cls, taxonomy: Taxonomy):
        """
        Creates and logs a new TagImportTask.
        """
        task = cls(
            taxonomy=taxonomy,
            status=TagImportTaskState.LOADING_DATA.value,
            log="",
        )
        task.add_log(_("Import task created"), save=False)
        task.save()
        return task

    def add_log(self, message: str, save=True):
        """
        Appends a log message to the task.
        """
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        log_message = f"[{timestamp}] {message}\n"
        self.log += log_message
        if save:
            self.save()

    def log_exception(self, exception: Exception):
        """
        Logs an exception and moves the task status to ERROR.
        """
        self.add_log(repr(exception), save=False)
        self.status = TagImportTaskState.ERROR.value
        self.save()

    def log_parser_start(self):
        """
        Logs the parser start event.
        """
        self.add_log(_("Starting to load data from file"))

    def log_parser_end(self):
        """
        Logs the parser finished event.
        """
        self.add_log(_("Load data finished"))

    def handle_parser_errors(self, errors):
        """
        Handles parser errors by logging them and moving the task status to ERROR.
        """
        for error in errors:
            self.add_log(f"{str(error)}", save=False)
        self.status = TagImportTaskState.ERROR.value
        self.save()

    def log_start_planning(self):
        """
        Starts task planning with a log message, and moves the task status to PLANNING.
        """
        self.add_log(_("Starting plan actions"), save=False)
        self.status = TagImportTaskState.PLANNING.value
        self.save()

    def log_plan(self, plan):
        """
        Logs the task plan.
        """
        self.add_log(_("Plan finished"))
        plan_str = plan.plan()
        self.log += f"\n{plan_str}\n"
        self.save()

    def handle_plan_errors(self):
        """
        Handles plan errors by moving the task status to ERROR.
        """
        # Error are logged with plan
        self.status = TagImportTaskState.ERROR.value
        self.save()

    def log_start_execute(self):
        """
        Starts task execution with a log message, and moves the task status to EXECUTING.
        """
        self.add_log(_("Starting execute actions"), save=False)
        self.status = TagImportTaskState.EXECUTING.value
        self.save()

    def end_success(self):
        """
        Completes task execution with a log message, and moves the task status to SUCCESS.
        """
        self.add_log(_("Execution finished"), save=False)
        self.status = TagImportTaskState.SUCCESS.value
        self.save()
