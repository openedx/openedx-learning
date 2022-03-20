from django.contrib import admin
from .models import (
    LearningContext,
    LearningContextVersion,
    BlockType,
    LearningContextBlock,
    BlockContent,
    BlockVersion,
)

@admin.register(LearningContext)
class LearningContextAdmin(admin.ModelAdmin):
    pass

@admin.register(LearningContextVersion)
class LearningContextVersionAdmin(admin.ModelAdmin):
    pass

@admin.register(BlockType)
class BlockTypeAdmin(admin.ModelAdmin):
    pass

@admin.register(LearningContextBlock)
class LearningContextBlockAdmin(admin.ModelAdmin):
    pass

@admin.register(BlockVersion)
class BlockVersionAdmin(admin.ModelAdmin):
    readonly_fields = (
        'title',
        'start_version_num',
        'end_version_num',
        'content',
        'block',
    )


@admin.register(BlockContent)
class BlockContentAdmin(admin.ModelAdmin):
    readonly_fields = (
        'learning_context',
        'hash_digest',
        'data',
    )
