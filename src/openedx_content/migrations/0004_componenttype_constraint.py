from django.db import migrations, models
from django.db.models import Count, Min


def consolidate_duplicate_component_types(apps, schema_editor):
    """
    Older installations may have multiple ComponentType rows with the same
    (namespace, name) due to a missing unique constraint.

    Before we apply the constraint, we need to fix the data by removing the
    duplicate entries. For each set of duplicates, keep the earliest row (lowest
    ID), repoint any Components that referenced the duplicates to it, then
    delete the duplicates so the new unique constraint can be applied cleanly.
    """
    ComponentType = apps.get_model("openedx_content", "ComponentType")
    Component = apps.get_model("openedx_content", "Component")

    duplicate_groups = (
        ComponentType.objects.values("namespace", "name").annotate(num=Count("id"), keep_id=Min("id")).filter(num__gt=1)
    )

    for group in duplicate_groups:
        keep_id = group["keep_id"]
        duplicate_ids = list(
            ComponentType.objects.filter(namespace=group["namespace"], name=group["name"])
            .exclude(id=keep_id)
            .values_list("id", flat=True)
        )
        Component.objects.filter(component_type_id__in=duplicate_ids).update(
            component_type_id=keep_id,
        )
        ComponentType.objects.filter(id__in=duplicate_ids).delete()


class Migration(migrations.Migration):
    dependencies = [
        ("openedx_content", "0003_rename_content_to_media"),
    ]

    operations = [
        migrations.RunPython(
            consolidate_duplicate_component_types,
            reverse_code=migrations.RunPython.noop,
        ),
        migrations.AddConstraint(
            model_name="componenttype",
            constraint=models.UniqueConstraint(fields=("namespace", "name"), name="oel_component_type_uniq_ns_n"),
        ),
    ]
