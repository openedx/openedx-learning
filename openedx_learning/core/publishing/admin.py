import re
from django.contrib import admin

from .models import (
    LearningContext,
    LearningContextVersion,
)


class LearningContextVersionInline(admin.TabularInline):
    model = LearningContextVersion
    fk_name = "learning_context"
    readonly_fields = ("created", "uuid")
    min_num = 1


@admin.register(LearningContext)
class LearningContextAdmin(admin.ModelAdmin):
    fields = ("identifier", "uuid", "created")
    readonly_fields = ("uuid", "created")
    list_display = ("identifier", "uuid", "created")

    def get_inlines(self, request, obj):
        if obj:
            return [LearningContextVersionInline]
        return []


# admin.site.register(LearningContextVersion)

"""
admin.site.register(LearningContextBranch)
admin.site.register(LearningAppVersionReport)
admin.site.register(LearningAppContentError)
"""
