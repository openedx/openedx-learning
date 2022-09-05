from django.db import models
from openedx_learning.core.publishing.models import LearningContext


class Library(models.Model):
    learning_context = models.OneToOneField(
        LearningContext,
        on_delete=models.CASCADE,
        primary_key=True,
    )

    