from django.contrib import admin

from .models import LearningPackage


@admin.register(LearningPackage)
class LearningPackageAdmin(admin.ModelAdmin):
    fields = ("identifier", "uuid", "created")
    readonly_fields = ("uuid", "created")
    list_display = ("identifier", "uuid", "created")
