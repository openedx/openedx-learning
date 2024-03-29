# Generated by Django 3.2.22 on 2024-01-25 14:20

from django.db import migrations, models
from django.utils.text import slugify


def migrate_export_id(apps, schema_editor):
    Taxonomy = apps.get_model("oel_tagging", "Taxonomy")
    for taxonomy in Taxonomy.objects.all():
        # Adds the id of the taxonomy to avoid duplicates
        taxonomy.export_id = f"{taxonomy.id}-{slugify(taxonomy.name, allow_unicode=True)}"
        taxonomy.save(update_fields=["export_id"])

def reverse(app, schema_editor):
    pass

class Migration(migrations.Migration):

    dependencies = [
        ('oel_tagging', '0014_minor_fixes'),
    ]

    operations = [
        # Create the field allowing null 
        migrations.AddField(
            model_name='taxonomy',
            name='export_id',
            field=models.CharField(help_text="User-facing ID that is used on import/export. Should only contain alphanumeric characters or '_' '-' '.'", max_length=255, null=True, unique=True),
        ),
        # Fill the field for created taxonomies
        migrations.RunPython(migrate_export_id, reverse),
        # Alter the field to not allowing null
        migrations.AlterField(
            model_name='taxonomy',
            name='export_id',
            field=models.CharField(help_text="User-facing ID that is used on import/export. Should only contain alphanumeric characters or '_' '-' '.'", max_length=255, null=False, unique=True),
        ),
    ]
