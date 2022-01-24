from django.contrib import admin

from .models import (
    LearningContext,
    LearningContextVersion,
    LearningContextBranch,
    LearningAppVersionReport,
    LearningAppContentError,
)

#@admin.register(LearningContext)
#class LearningContextAdmin(admin.ModelAdmin):
#   pass

admin.site.register(LearningContext)
admin.site.register(LearningContextVersion)
admin.site.register(LearningContextBranch)
admin.site.register(LearningAppVersionReport)
admin.site.register(LearningAppContentError)

