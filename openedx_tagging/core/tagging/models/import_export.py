from datetime import datetime
from enum import Enum
from django.db import models

from django.utils.translation import gettext_lazy as _

from .base import Taxonomy


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

    def handle_parser_errors(self, errors):
        for error in errors:
            self.add_log(f"{str(error)}", save=False)
        self.status = TagImportTaskState.ERROR.value
        self.save()

    def log_start_planning(self):
        self.add_log(_("Starting planning the actions"), save=False)
        self.status = TagImportTaskState.PLANNING.value
        self.save()
    
    def log_end_planning(self, plan):
        self.add_log(_("Plan finished"))
        plan_str = plan.plan()
        self.log += plan_str
        self.save()
        
    def handle_plan_errors(self):
        # Error are logged with plan
        self.status = TagImportTaskState.ERROR.value
        self.save()