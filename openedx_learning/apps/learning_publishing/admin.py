from django.contrib import admin

from .models import (
    LearningContext,
    LearningContextVersion,
    LearningContextBranch,
    LearningAppVersionReport,
    LearningAppContentError,
)

@admin.register(LearningContext)
class LearningContextAdmin(admin.ModelAdmin):
    pass

